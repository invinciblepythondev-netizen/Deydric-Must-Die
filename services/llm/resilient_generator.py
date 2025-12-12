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
from .together_ai import TogetherAIProvider
from ..context_manager import build_character_context, calculate_max_tokens, estimate_tokens

logger = logging.getLogger(__name__)


class ProviderRefusalError(Exception):
    """Raised when a provider refuses to generate content."""
    def __init__(self, reason: RefusalReason, message: str):
        self.reason = reason
        super().__init__(message)


class AllProvidersFailedError(Exception):
    """
    Raised when all providers in the fallback chain fail.

    This is a user-facing error that should pause the game and
    provide helpful debugging information.
    """
    def __init__(
        self,
        message: str,
        intensity: Optional[ContentIntensity] = None,
        attempted_providers: Optional[List[str]] = None,
        last_error: Optional[str] = None
    ):
        """
        Args:
            message: User-friendly error message
            intensity: Content intensity that was attempted
            attempted_providers: List of provider names that were tried
            last_error: Last error message from providers
        """
        self.intensity = intensity
        self.attempted_providers = attempted_providers or []
        self.last_error = last_error

        # Build detailed message
        detailed_msg = message

        if attempted_providers:
            detailed_msg += f"\n\nAttempted providers: {', '.join(attempted_providers)}"

        if intensity:
            detailed_msg += f"\nContent intensity: {intensity.value}"

        if last_error:
            detailed_msg += f"\nLast error: {last_error}"

        detailed_msg += "\n\nPossible solutions:"
        detailed_msg += "\n- Check that your API keys are valid in .env file"
        detailed_msg += "\n- Check provider status (https://status.anthropic.com, https://status.openai.com)"
        detailed_msg += "\n- Check your API usage limits and billing"
        detailed_msg += "\n- If content was refused, try adjusting the game situation"

        super().__init__(detailed_msg)


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

    @property
    def model_name(self) -> str:
        """
        Return a default model name for context management.

        Uses the first available provider's default model.
        This is used by ActionGenerator for context window sizing.
        """
        # Return a reasonable default for context management
        # claude-3-5-sonnet has 200k context, which is our primary model
        return "claude-3-5-sonnet-20241022"

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

        try:
            providers["together_ai"] = TogetherAIProvider()
        except Exception as e:
            logger.warning(f"Could not initialize Together.ai provider: {e}")

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

    def generate(
        self,
        prompt: str = None,
        system_prompt: str = None,
        user_prompt: str = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs
    ) -> str:
        """
        Generate text with automatic provider fallback.

        This method makes ResilientActionGenerator compatible with the
        standard provider interface so it can be used by ActionGenerator.

        Args:
            prompt: Combined prompt (if not using system/user split)
            system_prompt: System prompt
            user_prompt: User prompt
            temperature: Sampling temperature
            max_tokens: Max tokens to generate
            **kwargs: Additional arguments

        Returns:
            Generated text

        Raises:
            AllProvidersFailedError: If all providers fail
        """
        # Build context for intensity classification
        context_text = user_prompt or prompt or ""
        context = {"situation_summary": context_text}

        # Classify content intensity
        intensity = self.strategy.classify_content_intensity(context)

        logger.info(f"Generating with resilient fallback (intensity: {intensity.value})")

        # Get provider chain
        provider_chain = self.strategy.get_provider_chain(intensity)
        attempted_providers = []
        last_error = None

        # Try each provider in chain
        for provider_config in provider_chain:
            provider_name = provider_config["provider"]
            model = provider_config["model"]
            provider_label = f"{provider_name}/{model}"

            if provider_name not in self.providers:
                attempted_providers.append(f"{provider_label} (not initialized)")
                last_error = f"Provider {provider_name} not initialized"
                continue

            provider = self.providers[provider_name]
            attempted_providers.append(provider_label)

            try:
                logger.info(f"Trying {provider_label} for generation")

                # Adjust prompt for this provider
                if user_prompt:
                    adjusted_prompt = self.strategy.adjust_prompt_for_provider(
                        user_prompt, provider_name, model, intensity
                    )
                else:
                    adjusted_prompt = self.strategy.adjust_prompt_for_provider(
                        prompt, provider_name, model, intensity
                    )

                # Generate with provider
                if system_prompt and hasattr(provider.generate, '__code__') and 'system_prompt' in provider.generate.__code__.co_varnames:
                    # Provider supports system_prompt parameter
                    response = provider.generate(
                        prompt=adjusted_prompt,
                        system_prompt=system_prompt,
                        model=model,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                else:
                    # Provider doesn't support system_prompt, combine them
                    combined = f"{system_prompt}\n\n{adjusted_prompt}" if system_prompt else adjusted_prompt
                    response = provider.generate(
                        prompt=combined,
                        model=model,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )

                logger.info(f"✓ Generated with {provider_label}")
                return response

            except Exception as e:
                last_error = str(e)
                refusal_reason = self._detect_refusal(e)

                if refusal_reason:
                    self.strategy.log_refusal(
                        provider_name, model, refusal_reason,
                        intensity, str(e)
                    )
                    logger.warning(f"✗ {provider_label} refused: {refusal_reason.value}")
                    continue
                else:
                    logger.error(f"✗ {provider_label} failed: {e}")
                    continue

        # All providers failed
        raise AllProvidersFailedError(
            message="All providers failed for text generation",
            intensity=intensity,
            attempted_providers=attempted_providers,
            last_error=last_error
        )

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
                message=f"No providers available for intensity: {intensity.value}",
                intensity=intensity,
                attempted_providers=[],
                last_error="No providers configured for this content intensity"
            )

        logger.info(
            f"Provider chain: "
            f"{[f'{p['provider']}/{p['model']}' for p in provider_chain]}"
        )

        # Try each provider in the chain
        attempted_providers = []
        last_error = None

        for i, provider_config in enumerate(provider_chain):
            provider_name = provider_config["provider"]
            model = provider_config["model"]
            provider_label = f"{provider_name}/{model}"

            logger.info(
                f"Attempt {i+1}/{len(provider_chain)}: "
                f"Trying {provider_label}"
            )

            # Check if we have this provider initialized
            if provider_name not in self.providers:
                logger.warning(f"Provider {provider_name} not initialized, skipping")
                attempted_providers.append(f"{provider_label} (not initialized)")
                last_error = f"Provider {provider_name} not initialized"
                continue

            provider = self.providers[provider_name]
            attempted_providers.append(provider_label)

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

                # Calculate appropriate max_tokens for this model and input size
                system_prompt_text = self._build_system_prompt(intensity)
                input_tokens = (
                    estimate_tokens(adjusted_prompt, model) +
                    estimate_tokens(system_prompt_text, model)
                )
                dynamic_max_tokens = calculate_max_tokens(
                    model=model,
                    input_tokens=input_tokens,
                    min_output=512,
                    max_output=3000
                )

                logger.info(
                    f"Token allocation for {model}: "
                    f"input={input_tokens}, max_output={dynamic_max_tokens}"
                )

                # Generate with this provider
                response = provider.generate(
                    prompt=adjusted_prompt,
                    system_prompt=system_prompt_text,
                    model=model,
                    max_tokens=dynamic_max_tokens
                )

                # Parse actions from response
                actions = self._parse_actions(response)

                logger.info(
                    f"✓ Success with {provider_label} "
                    f"(generated {len(actions)} actions)"
                )

                return actions

            except Exception as e:
                last_error = str(e)

                # Check if this is a refusal
                refusal_reason = self._detect_refusal(e)

                if refusal_reason:
                    # Log the refusal
                    self.strategy.log_refusal(
                        provider_name, model, refusal_reason,
                        intensity, str(e)
                    )

                    logger.warning(
                        f"✗ {provider_label} refused "
                        f"(reason: {refusal_reason.value})"
                    )

                    # Continue to next provider
                    continue
                else:
                    # Non-refusal error (API error, timeout, etc.)
                    logger.error(
                        f"✗ {provider_label} failed with error: {e}"
                    )

                    # Continue to next provider
                    continue

        # All providers failed
        raise AllProvidersFailedError(
            message=f"All {len(provider_chain)} providers failed for action generation",
            intensity=intensity,
            attempted_providers=attempted_providers,
            last_error=last_error
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

        # Check if we have pre-selected draft action ideas to expand
        selected_drafts = context.get('selected_draft_summaries', [])

        if selected_drafts:
            # Build prompt to expand the specific selected draft ideas
            logger.info(f"✅ Using {len(selected_drafts)} pre-selected draft action ideas")
            print(f"✅ ResilientActionGenerator: Expanding {len(selected_drafts)} pre-selected draft ideas")
            for i, draft in enumerate(selected_drafts, 1):
                print(f"   {i}. {draft}")

            instruction = f"""
{'='*80}
CRITICAL INSTRUCTION: EXPAND THESE {len(selected_drafts)} SELECTED ACTION IDEAS
{'='*80}

You MUST expand each of the following action ideas into a full action sequence.
DO NOT generate new ideas - ONLY expand the ones listed below:

"""
            for i, summary in enumerate(selected_drafts, 1):
                instruction += f"  {i}. {summary}\n"

            instruction += f"""
For EACH idea above, create a complete action with:
- private_thought: Character's internal thinking (what they're feeling/planning)
- dialogue: What they say out loud (use empty string "" if they say nothing)
- action: The physical action they take

Return ONLY a JSON array with this exact structure (no other text):

```json
[
  {{
    "private_thought": "expand idea #1 - internal thinking",
    "dialogue": "expand idea #1 - what they say (or empty string)",
    "action": "expand idea #1 - physical action"
  }},
  {{
    "private_thought": "expand idea #2 - internal thinking",
    "dialogue": "expand idea #2 - what they say (or empty string)",
    "action": "expand idea #2 - physical action"
  }}
]
```

CRITICAL: Return exactly {len(selected_drafts)} options, one for each idea listed above, in the same order.
{'='*80}
"""
        else:
            # Fallback: Generate from scratch (original behavior)
            logger.info(f"⚠️  No pre-selected drafts found, generating {num_options} options from scratch")
            print(f"⚠️  ResilientActionGenerator: No pre-selected drafts, generating from scratch")

            instruction = f"""
Generate {num_options} possible action options for this character.

Return ONLY a JSON array with this exact structure (no other text):

```json
[
  {{
    "private_thought": "what the character is thinking (internal, not spoken)",
    "dialogue": "what they say out loud (or empty string if silent)",
    "action": "what they physically do"
  }},
  {{
    "private_thought": "second option thinking",
    "dialogue": "second option speech",
    "action": "second option physical action"
  }}
]
```

Important:
- Return ONLY the JSON array, nothing else
- Each option must have all three fields: private_thought, dialogue, and action
- Use empty string "" for dialogue if character says nothing
- Make options diverse and fitting to the character's personality
"""

        full_prompt = assembled_context + "\n\n" + instruction

        return full_prompt, metadata

    def _format_character(self, character: Dict[str, Any]) -> str:
        """Format character profile for prompt."""
        parts = [
            f"Name: {character.get('name')}",
            f"Appearance: {character.get('physical_appearance', 'Not specified')}",
            f"Currently wearing: {character.get('current_clothing', 'simple clothing')}",
            f"Current stance: {character.get('current_stance', 'standing')}",
            f"Personality: {character.get('personality_traits')}",
            f"Emotional state: {character.get('current_emotional_state', 'neutral')}",
            f"Motivations: {character.get('motivations_short_term')}"
        ]
        return "\n".join(parts)

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
        import json
        import re

        logger.info(f"Parsing response (length: {len(response)} chars)")

        # Try multiple parsing strategies

        # Strategy 1: Direct JSON array parsing
        try:
            # Remove markdown code blocks if present
            clean_response = response.strip()

            # Handle markdown code blocks
            if "```json" in clean_response:
                match = re.search(r'```json\s*(\[.*?\])\s*```', clean_response, re.DOTALL)
                if match:
                    clean_response = match.group(1)
            elif "```" in clean_response:
                match = re.search(r'```\s*(\[.*?\])\s*```', clean_response, re.DOTALL)
                if match:
                    clean_response = match.group(1)

            # Try to find JSON array anywhere in response
            if not clean_response.startswith('['):
                match = re.search(r'\[.*\]', clean_response, re.DOTALL)
                if match:
                    clean_response = match.group(0)

            actions = json.loads(clean_response)
            if isinstance(actions, list) and len(actions) > 0:
                logger.info(f"✓ Successfully parsed {len(actions)} actions from JSON array")
                return actions
        except (json.JSONDecodeError, AttributeError) as e:
            logger.warning(f"JSON array parsing failed: {e}")

        # Strategy 2: Extract JSON objects from text with "Option N:" labels
        try:
            # Find all JSON-like objects in the text
            option_pattern = r'Option \d+:\s*(\{[^}]+\})'
            matches = re.findall(option_pattern, response, re.DOTALL)

            if matches:
                actions = []
                for match in matches:
                    try:
                        action_obj = json.loads(match)
                        actions.append(action_obj)
                    except json.JSONDecodeError:
                        continue

                if actions:
                    return actions
        except Exception:
            pass

        # Strategy 3: Extract standalone JSON objects
        try:
            # Find all {...} blocks
            json_objects = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
            actions = []
            for obj_str in json_objects:
                try:
                    action = json.loads(obj_str)
                    # Check if it looks like an action (has expected fields)
                    if any(key in action for key in ['thought', 'private_thought', 'action', 'speech']):
                        actions.append(action)
                except json.JSONDecodeError:
                    continue

            if actions:
                return actions
        except Exception:
            pass

        # Fallback: create a single generic action from the response text
        logger.error(f"Could not parse structured actions, using fallback. Response preview: {response[:500]}")

        # Try to at least create a reasonable fallback
        return [{
            "private_thought": "Considering the situation carefully",
            "dialogue": "",
            "action": "Take a moment to assess the situation and consider options",
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
        attempted_providers = []
        last_error = None

        for provider_config in provider_chain:
            provider_name = provider_config["provider"]
            model = provider_config["model"]
            provider_label = f"{provider_name}/{model}"

            if provider_name not in self.providers:
                attempted_providers.append(f"{provider_label} (not initialized)")
                last_error = f"Provider {provider_name} not initialized"
                continue

            provider = self.providers[provider_name]
            attempted_providers.append(provider_label)

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

                logger.info(f"✓ Success with {provider_label}")

                return result

            except Exception as e:
                last_error = str(e)
                refusal_reason = self._detect_refusal(e)

                if refusal_reason:
                    self.strategy.log_refusal(
                        provider_name, model, refusal_reason,
                        intensity, str(e)
                    )
                    continue
                else:
                    logger.error(f"Error with {provider_label}: {e}")
                    continue

        raise AllProvidersFailedError(
            message=f"All providers failed for {action_type} action execution",
            intensity=intensity,
            attempted_providers=attempted_providers,
            last_error=last_error
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

    def generate_atmospheric_description(
        self,
        character_name: str,
        action_description: str,
        location_name: str,
        other_characters: List[str],
        recent_history: str,
        current_stance: Optional[str] = None,
        current_clothing: Optional[str] = None
    ) -> str:
        """
        Generate atmospheric description with automatic fallback for adult content.

        Handles violent, sexual, and disturbing content by using the provider
        fallback chain. Content intensity is automatically classified.

        Args:
            character_name: Name of character who acted
            action_description: What they did
            location_name: Current location
            other_characters: List of other character names present
            recent_history: Recent turn history
            current_stance: Character's current stance/posture (e.g., "standing", "sitting")
            current_clothing: Description of what the character is wearing

        Returns:
            Atmospheric description text

        Raises:
            AllProvidersFailedError: If all providers fail
        """
        # Build context for intensity classification
        context = {
            "situation_summary": f"{character_name} {action_description}",
            "recent_events": recent_history,
            "location": location_name
        }

        # Classify content intensity (detects violence, sexual content, disturbing themes)
        intensity = self.strategy.classify_content_intensity(context)

        logger.info(
            f"Generating atmospheric description for '{action_description}' "
            f"(intensity: {intensity.value})"
        )

        # Get appropriate provider chain based on content intensity
        provider_chain = self.strategy.get_provider_chain(intensity)
        attempted_providers = []
        last_error = None

        # Build prompt
        context_parts = [f"Location: {location_name}"]

        # Add character state information
        character_state_parts = []
        if current_stance:
            character_state_parts.append(f"{character_name} is {current_stance}")
        if current_clothing:
            character_state_parts.append(f"wearing {current_clothing}")

        if character_state_parts:
            context_parts.append(f"Character state: {', '.join(character_state_parts)}")

        if other_characters:
            context_parts.append(f"Others present: {', '.join(other_characters)}")
        if recent_history:
            context_parts.append(f"\nWhat just happened:\n{recent_history}")
        context_parts.append(f"\nCurrent action: {character_name} {action_description}")

        prompt = f"""{chr(10).join(context_parts)}

Generate a rich, atmospheric aftermath scene (4-6 sentences) that captures what the environment and characters are like immediately following the recent actions.

Requirements:
- Focus on the aftereffects: reactions, shifts in mood, tension in the air — do not repeat the action itself
- Include sensory details across sight, sound, smell, and subtle physical sensations
- Describe characters present: clothing movement, posture, expressions, breathing, sweat, tremors, or stillness — only if visible
- Track character state changes: note if {character_name}'s stance or clothing changed (e.g., if standing became sitting, if clothing became disheveled)
- Include environmental elements: lighting, shadows, objects, temperature, weather, and distant or ambient sounds
- Maintain a tone of dark fantasy, cinematic and atmospheric, not verbose
- Write in a third-person, visual narrative style — as if the scene is unfolding on film

Return ONLY the atmospheric description (4-6 sentences), nothing else."""

        system_prompt = self._build_system_prompt(intensity)

        # Try each provider in the fallback chain
        for provider_config in provider_chain:
            provider_name = provider_config["provider"]
            model = provider_config["model"]
            provider_label = f"{provider_name}/{model}"

            if provider_name not in self.providers:
                attempted_providers.append(f"{provider_label} (not initialized)")
                last_error = f"Provider {provider_name} not initialized"
                continue

            provider = self.providers[provider_name]
            attempted_providers.append(provider_label)

            try:
                logger.info(f"Trying {provider_label} for atmospheric description")

                # Adjust prompt for this provider (handles content policy differences)
                adjusted_prompt = self.strategy.adjust_prompt_for_provider(
                    prompt, provider_name, model, intensity
                )

                response = provider.generate(
                    prompt=adjusted_prompt,
                    system_prompt=system_prompt,
                    model=model,
                    temperature=0.8,
                    max_tokens=500
                )

                logger.info(f"✓ Atmospheric description generated with {provider_label}")
                return response.strip()

            except Exception as e:
                last_error = str(e)
                refusal_reason = self._detect_refusal(e)

                if refusal_reason:
                    # Content policy refusal - log and try next provider
                    self.strategy.log_refusal(
                        provider_name, model, refusal_reason,
                        intensity, str(e)
                    )
                    logger.warning(
                        f"✗ {provider_label} refused atmospheric description "
                        f"(reason: {refusal_reason.value})"
                    )
                    continue
                else:
                    # Technical error - log and try next provider
                    logger.error(f"✗ {provider_label} failed: {e}")
                    continue

        # All providers failed
        raise AllProvidersFailedError(
            message="All providers failed for atmospheric description generation",
            intensity=intensity,
            attempted_providers=attempted_providers,
            last_error=last_error
        )

    def summarize_memory(
        self,
        turns: List[Dict[str, Any]],
        importance: str = "routine"
    ) -> str:
        """
        Summarize turn history with automatic fallback for adult content.

        Handles violent, sexual, and disturbing content by using the provider
        fallback chain. Content intensity is automatically classified from turns.

        Args:
            turns: List of turn dictionaries with 'turn_number' and 'action_description'
            importance: Importance level ("routine", "significant", "critical")

        Returns:
            Summary text

        Raises:
            AllProvidersFailedError: If all providers fail
        """
        # Build context for intensity classification from turn content
        turn_descriptions = " ".join([t.get('action_description', '') for t in turns])
        context = {
            "situation_summary": turn_descriptions,
            "turn_count": len(turns)
        }

        # Classify content intensity (detects violence, sexual content, disturbing themes)
        intensity = self.strategy.classify_content_intensity(context)

        logger.info(
            f"Summarizing {len(turns)} turns "
            f"(importance: {importance}, intensity: {intensity.value})"
        )

        # Get appropriate provider chain based on content
        provider_chain = self.strategy.get_provider_chain(intensity)
        attempted_providers = []
        last_error = None

        # Format turns for summarization
        turn_text = "\n".join([
            f"Turn {t.get('turn_number')}: {t.get('action_description')}"
            for t in turns
        ])

        prompt = f"""Summarize the following game events into a concise narrative (2-4 sentences).

Events:
{turn_text}

Focus on:
- Key actions and their consequences
- Character interactions and relationship changes
- Important environmental or situational changes

Return only the summary, nothing else."""

        system_prompt = (
            "You are a narrative AI that summarizes game events concisely and clearly. "
            "This is a dark fantasy game for mature audiences."
        )

        # Try each provider in the fallback chain
        for provider_config in provider_chain:
            provider_name = provider_config["provider"]
            model = provider_config["model"]
            provider_label = f"{provider_name}/{model}"

            if provider_name not in self.providers:
                attempted_providers.append(f"{provider_label} (not initialized)")
                last_error = f"Provider {provider_name} not initialized"
                continue

            provider = self.providers[provider_name]
            attempted_providers.append(provider_label)

            try:
                logger.info(f"Trying {provider_label} for memory summarization")

                # Adjust prompt for this provider
                adjusted_prompt = self.strategy.adjust_prompt_for_provider(
                    prompt, provider_name, model, intensity
                )

                response = provider.generate(
                    prompt=adjusted_prompt,
                    system_prompt=system_prompt,
                    model=model,
                    temperature=0.5,
                    max_tokens=300
                )

                logger.info(f"✓ Memory summary generated with {provider_label}")
                return response.strip()

            except Exception as e:
                last_error = str(e)
                refusal_reason = self._detect_refusal(e)

                if refusal_reason:
                    # Content policy refusal - log and try next provider
                    self.strategy.log_refusal(
                        provider_name, model, refusal_reason,
                        intensity, str(e)
                    )
                    logger.warning(
                        f"✗ {provider_label} refused memory summarization "
                        f"(reason: {refusal_reason.value})"
                    )
                    continue
                else:
                    # Technical error - log and try next provider
                    logger.error(f"✗ {provider_label} failed: {e}")
                    continue

        # All providers failed
        raise AllProvidersFailedError(
            message="All providers failed for memory summarization",
            intensity=intensity,
            attempted_providers=attempted_providers,
            last_error=last_error
        )
