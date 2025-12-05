"""
Resilient LLM Action Generator with Automatic Provider Fallback

Handles content policy violations by automatically trying alternative providers
in order of preference.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from .provider_strategy import (
    ProviderStrategy,
    ContentIntensity,
    RefusalReason,
    get_provider_strategy
)
from .provider import LLMProvider
from .claude import ClaudeProvider
from .openai import OpenAIProvider
from .aimlapi import AIMLAPIProvider
from ..context_manager import build_character_context

logger = logging.getLogger(__name__)


class ProviderRefusalError(Exception):
    """Raised when a provider refuses to generate content."""
    def __init__(self, reason: RefusalReason, message: str):
        self.reason = reason
        super().__init__(message)


class AllProvidersFailedError(Exception):
    """Raised when all providers in the fallback chain fail."""
    pass


class ResilientActionGenerator:
    """
    Generates character actions with automatic provider fallback.

    When a provider refuses due to content policy:
    1. Detects the refusal reason
    2. Logs the refusal
    3. Automatically tries next provider in chain
    4. Adjusts prompts as needed for each provider
    5. Falls back to local models if all else fails
    """

    def __init__(
        self,
        strategy: Optional[ProviderStrategy] = None,
        providers: Optional[Dict[str, LLMProvider]] = None
    ):
        """
        Args:
            strategy: Provider strategy (uses global if not provided)
            providers: Dict of initialized provider instances
        """
        self.strategy = strategy or get_provider_strategy()
        self.providers = providers or self._init_default_providers()

    def _init_default_providers(self) -> Dict[str, LLMProvider]:
        """Initialize default provider instances."""
        providers = {}

        # Try to initialize each provider (may fail if API keys not set)
        try:
            providers["anthropic"] = ClaudeProvider()
        except Exception as e:
            logger.warning(f"Could not initialize Anthropic provider: {e}")

        try:
            providers["openai"] = OpenAIProvider()
        except Exception as e:
            logger.warning(f"Could not initialize OpenAI provider: {e}")

        try:
            providers["aimlapi"] = AIMLAPIProvider()
        except Exception as e:
            logger.warning(f"Could not initialize AIML API provider: {e}")

        # TODO: Add Together.ai provider when implemented
        # try:
        #     providers["together_ai"] = TogetherAIProvider()
        # except Exception as e:
        #     logger.warning(f"Could not initialize Together.ai provider: {e}")

        # TODO: Add local model providers when implemented
        # try:
        #     providers["local"] = LocalModelProvider()
        # except Exception as e:
        #     logger.warning(f"Could not initialize local provider: {e}")

        return providers

    def _detect_refusal(self, error: Exception) -> Optional[RefusalReason]:
        """
        Check if an error is a content policy refusal.

        Args:
            error: Exception from provider

        Returns:
            RefusalReason if it's a refusal, None otherwise
        """
        return self.strategy.detect_refusal_reason(error)

    def generate_action_options(
        self,
        character: Dict[str, Any],
        context: Dict[str, Any],
        num_options: int = 4
    ) -> List[Dict[str, Any]]:
        """
        Generate action options for a character, with automatic fallback.

        Args:
            character: Character profile
            context: Game context (location, visible characters, working memory, etc.)
            num_options: Number of action options to generate

        Returns:
            List of action options

        Raises:
            AllProvidersFailedError: If all providers fail
        """
        # Classify content intensity
        intensity = self.strategy.classify_content_intensity(context)

        logger.info(
            f"Generating actions for {character.get('name')} "
            f"(intensity: {intensity.value})"
        )

        # Get provider fallback chain
        provider_chain = self.strategy.get_provider_chain(intensity)

        if not provider_chain:
            raise AllProvidersFailedError(
                f"No providers available for intensity: {intensity.value}"
            )

        logger.info(
            f"Provider chain: "
            f"{[f'{p['provider']}/{p['model']}' for p in provider_chain]}"
        )

        # Try each provider in the chain
        for i, provider_config in enumerate(provider_chain):
            provider_name = provider_config["provider"]
            model = provider_config["model"]

            logger.info(
                f"Attempt {i+1}/{len(provider_chain)}: "
                f"Trying {provider_name}/{model}"
            )

            # Check if we have this provider initialized
            if provider_name not in self.providers:
                logger.warning(f"Provider {provider_name} not initialized, skipping")
                continue

            provider = self.providers[provider_name]

            try:
                # Build prompt with context manager (model-aware)
                prompt, context_metadata = self._build_action_prompt(
                    character, context, num_options, model
                )

                logger.info(
                    f"Context for {model}: {context_metadata['total_tokens']} tokens, "
                    f"truncated={context_metadata['was_truncated']}"
                )

                # Adjust prompt for this provider
                adjusted_prompt = self.strategy.adjust_prompt_for_provider(
                    prompt, provider_name, model, intensity
                )

                # Generate with this provider
                response = provider.generate(
                    prompt=adjusted_prompt,
                    system_prompt=self._build_system_prompt(intensity),
                    model=model
                )

                # Parse actions from response
                actions = self._parse_actions(response)

                logger.info(
                    f"✓ Success with {provider_name}/{model} "
                    f"(generated {len(actions)} actions)"
                )

                return actions

            except Exception as e:
                # Check if this is a refusal
                refusal_reason = self._detect_refusal(e)

                if refusal_reason:
                    # Log the refusal
                    self.strategy.log_refusal(
                        provider_name, model, refusal_reason,
                        intensity, str(e)
                    )

                    logger.warning(
                        f"✗ {provider_name}/{model} refused "
                        f"(reason: {refusal_reason.value})"
                    )

                    # Continue to next provider
                    continue
                else:
                    # Non-refusal error (API error, timeout, etc.)
                    logger.error(
                        f"✗ {provider_name}/{model} failed with error: {e}"
                    )

                    # Continue to next provider
                    continue

        # All providers failed
        raise AllProvidersFailedError(
            f"All {len(provider_chain)} providers failed for intensity {intensity.value}"
        )

    def _build_system_prompt(self, intensity: ContentIntensity) -> str:
        """
        Build system prompt with appropriate framing for content intensity.

        Args:
            intensity: Content intensity level

        Returns:
            System prompt
        """
        base = (
            "You are a narrative AI for a dark fantasy role-playing game. "
            "Generate realistic, immersive character actions that fit the world's tone. "
            "This is a game for mature audiences. "
        )

        if intensity in [ContentIntensity.MODERATE, ContentIntensity.MATURE]:
            base += (
                "\n\nThe game features realistic consequences: injuries are serious, "
                "death is permanent, and characters have complex moral motivations. "
                "Focus on narrative impact and psychological realism rather than gratuitous details."
            )

        if intensity == ContentIntensity.UNRESTRICTED:
            base += (
                "\n\nThis content may involve extreme situations. "
                "Maintain narrative coherence and character authenticity."
            )

        return base

    def _build_action_prompt(
        self,
        character: Dict[str, Any],
        context: Dict[str, Any],
        num_options: int,
        model: str
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Build the action generation prompt with model-aware context management.

        Args:
            character: Character profile
            context: Game context
            num_options: Number of options to generate
            model: Target model (for context window limits)

        Returns:
            Tuple of (prompt_string, context_metadata)
        """
        # Use context manager for intelligent truncation
        assembled_context, metadata = build_character_context(
            character=character,
            game_context=context,
            model=model,
            max_response_tokens=2048  # Expected response size
        )

        # Add generation instruction
        instruction = f"""
Generate {num_options} possible action options for this character.

Each action should include:
1. A private thought (what they're thinking)
2. What they say (if anything)
3. What they do (physical action)

Format each option as JSON.
"""

        full_prompt = assembled_context + "\n\n" + instruction

        return full_prompt, metadata

    def _format_character(self, character: Dict[str, Any]) -> str:
        """Format character profile for prompt."""
        # Simplified - would be more detailed in real implementation
        return (
            f"Name: {character.get('name')}\n"
            f"Personality: {character.get('personality_traits')}\n"
            f"Motivations: {character.get('motivations_short_term')}\n"
            f"Current State: {character.get('current_emotional_state')}\n"
        )

    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format game context for prompt."""
        # Simplified - would be more detailed in real implementation
        parts = [
            f"Location: {context.get('location_name')}",
            f"Present: {', '.join(context.get('visible_characters', []))}",
            f"Recent Events:\n{context.get('working_memory', '')}"
        ]
        return "\n".join(parts)

    def _parse_actions(self, response: str) -> List[Dict[str, Any]]:
        """
        Parse action options from LLM response.

        Args:
            response: Raw LLM response

        Returns:
            List of parsed action dictionaries
        """
        # This would use proper JSON parsing in real implementation
        # For now, simplified placeholder
        import json

        try:
            # Assume response is JSON array
            actions = json.loads(response)
            return actions
        except json.JSONDecodeError:
            # Fallback: create single action from text
            return [{
                "thought": "",
                "speech": "",
                "action": response,
                "action_type": "wait"
            }]

    def generate_single_action(
        self,
        action_type: str,
        character: Dict[str, Any],
        context: Dict[str, Any],
        target: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a specific action execution (e.g., attack, speak, move).

        This is used after a player/AI has selected an action option.

        Args:
            action_type: Type of action (attack, speak, move, etc.)
            character: Character profile
            context: Game context
            target: Target of action (if applicable)

        Returns:
            Action result with description and outcomes
        """
        # Add action type to context for intensity classification
        action_context = {**context, "action_type": action_type}

        intensity = self.strategy.classify_content_intensity(action_context)

        logger.info(
            f"Generating {action_type} action for {character.get('name')} "
            f"(intensity: {intensity.value})"
        )

        provider_chain = self.strategy.get_provider_chain(intensity)

        # Similar fallback logic as generate_action_options
        for provider_config in provider_chain:
            provider_name = provider_config["provider"]
            model = provider_config["model"]

            if provider_name not in self.providers:
                continue

            provider = self.providers[provider_name]

            try:
                prompt = self._build_action_execution_prompt(
                    action_type, character, context, target
                )

                adjusted_prompt = self.strategy.adjust_prompt_for_provider(
                    prompt, provider_name, model, intensity
                )

                response = provider.generate(
                    prompt=adjusted_prompt,
                    system_prompt=self._build_system_prompt(intensity),
                    model=model
                )

                result = self._parse_action_result(response, action_type)

                logger.info(f"✓ Success with {provider_name}/{model}")

                return result

            except Exception as e:
                refusal_reason = self._detect_refusal(e)

                if refusal_reason:
                    self.strategy.log_refusal(
                        provider_name, model, refusal_reason,
                        intensity, str(e)
                    )
                    continue
                else:
                    logger.error(f"Error with {provider_name}/{model}: {e}")
                    continue

        raise AllProvidersFailedError(
            f"All providers failed for {action_type} action"
        )

    def _build_action_execution_prompt(
        self,
        action_type: str,
        character: Dict[str, Any],
        context: Dict[str, Any],
        target: Optional[str]
    ) -> str:
        """Build prompt for specific action execution."""
        prompt = f"""
Execute a {action_type} action for {character.get('name')}.

Character: {self._format_character(character)}
Context: {self._format_context(context)}
Target: {target or 'None'}

Describe what happens in narrative form.
Include outcomes and consequences.
"""
        return prompt

    def _parse_action_result(
        self,
        response: str,
        action_type: str
    ) -> Dict[str, Any]:
        """Parse action execution result."""
        # Simplified - would be more sophisticated
        return {
            "action_type": action_type,
            "description": response,
            "was_successful": True,  # Would determine from response
            "outcomes": []  # Would extract from response
        }
