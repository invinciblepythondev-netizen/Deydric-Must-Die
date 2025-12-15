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
                system_prompt_text = self._build_action_system_prompt(intensity, model)
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

                print(f"ResilientActionGenerator system_prompt_text:",system_prompt_text)
                print(f"ResilientActionGenerator adjusted_prompt:",adjusted_prompt)

                # Generate with this provider
                response = provider.generate(
                    prompt=adjusted_prompt,
                    system_prompt=system_prompt_text,
                    model=model,
                    max_tokens=dynamic_max_tokens
                )

                print(f"✓ ResilientActionGenerator: Received response from {provider_label}")
                print("ResilientActionGenerator response:", response)

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

    def _build_action_system_prompt(self, intensity: ContentIntensity, model: str = None) -> str:
        """
        Build system prompt for action generation (matches action_generator.py).

        Args:
            intensity: Content intensity level
            model: Model identifier (for context-aware prompt)

        Returns:
            System prompt string
        """
        from services.context_manager import ModelContextLimits

        # Get base intensity framing
        base = self._build_system_prompt(intensity)

        # Determine if this is a small model (<=16K context)
        is_small_model = False
        if model:
            context_limit = ModelContextLimits.get_limit(model)
            is_small_model = context_limit <= 16384

        # Core action types (always included)
        core_actions = """- think: Private thought (only the character knows)
- speak: Public dialogue (what they actually say rather than a description) (what others hear)
- interact: Interact with object/character
- move: Change location
- attack: Combat action
- steal: Take something covertly
- use_item: Use inventory item"""

        # Atmospheric action types (excluded for small models)
        atmospheric_actions = """- emote: Body language/gesture (others see)
- examine: Look at something closely
- wait: Do nothing/observe
- hide: Attempt stealth"""

        # Build action types list
        if is_small_model:
            action_types = core_actions
        else:
            action_types = core_actions + "\n" + atmospheric_actions

        action_instructions = f"""

Your task is to generate distinctive action options for a character's turn. Each option should be a SEQUENCE of actions that execute in order.

Action types available:
{action_types}

CRITICAL NARRATIVE RULES:
1. Write ALL action descriptions in third-person narrative prose, as if writing a novel, except for think actions (first-person) and speak actions (direct dialogue)
2. ALWAYS use the character's FULL NAME as the subject of EVERY action description (except think/speak)
3. Write complete sentences, not fragments or verb phrases
4. Avoid unclear pronouns - be explicit about who is doing what to whom
5. Include sensory details and emotional context where appropriate
6. Check the recent context, if a draft action could not happen within another 30 seconds of game time, replace it with an action that fits but will lead to the same result.
7. Ensure that the character is responding in some way to any speech or actions directed at them whilst performing the draft action.

STRUCTURE RULES:
1. Generate 5 distinctive options based on supplied drafts
2. Each option can contain MULTIPLE actions in sequence (think → speak → act)
3. Show internal thoughts (think actions) to reveal character psychology
4. Mix public and private actions appropriately
5. Always ensure that there is a speech or interaction action.

**TURN DURATION RULES:**
- Each turn = ~30 seconds of in-game time
- Most actions complete in 1 turn (default)
- Complex/lengthy actions need 2-5 turns (e.g., searching a room thoroughly, having an extended conversation, intimacy that builds over time)
- If recent events show a character mid-action with "(XT, Y remaining)" notation:
  * They are performing a multi-turn action
  * Some options should CONTINUE that action with turn_duration = Y (the remaining value)
  * Other options can ABANDON it to do something new (turn_duration = 1 or appropriate for new action)

Format each option as JSON:
{{
  "summary": "Brief description of this approach",
  "emotional_tone": "cunning|aggressive|friendly|cautious|romantic|seductive|passionate|lustful|etc",
  "escalates_mood": true/false,
  "deescalates_mood": true/false,
  "estimated_mood_impact": {{"tension": 5, "hostility": -3, "romance": 0}} (range -10 to 10 for each),
  "turn_duration": 1-5 (number of turns to complete; if continuing from draft ideas, use the specified duration),
  "current_stance": "description of character's stance/position after actions: standing by the window|sitting on a chair|lying down|etc. Base on provided current stance but update if actions change it",
  "current_clothing": "brief but detailed description of clothing appearance after actions. Base on provided current clothing but update if actions change it (disheveled, torn, removed items, etc)",
  "current_emotional_state": "brief description of character's internal emotional state",
  "actions": [
    {{"type": "think", "description": "...", "is_private": true}},
    {{"type": "speak", "description": "...", "is_private": false}},
    {{"type": "interact", "description": "...", "is_private": false, "target": "character_name"}}
  ]
}}

IMPORTANT: current_stance and current_clothing should maintain continuity with the provided values unless the actions explicitly change them.

Return a JSON array of options."""

        return base + action_instructions

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

        # Build simplified context (just essentials since drafts are pre-selected)
        character_name = character.get('name', 'Unknown')
        emotional_state = character.get('current_emotional_state', 'neutral')
        motivations = character.get('motivations_short_term', [])

        # Get current physical state for continuity
        current_stance = character.get('current_stance', context.get('character_stance', 'standing'))
        current_clothing = character.get('current_clothing', context.get('character_clothing', 'unchanged'))

        location_name = context.get('location_name', 'Unknown')
        visible_chars = context.get('visible_characters', [])
        char_names = [c.get('name', '') for c in visible_chars] if visible_chars else []

        # Get only most recent 2-3 actions
        working_memory = context.get('working_memory', '')
        recent_actions = '\n'.join(working_memory.split('\n')[:3]) if working_memory else ''

        mood_desc = context.get('mood_description', '')

        # Build minimal context prompt
        context_prompt = f"""CHARACTER: {character_name}
Emotional state: {emotional_state}
Objectives: {motivations}
Current stance: {current_stance}
Current clothing: {current_clothing}

RECENT CONTEXT:
{recent_actions}

LOCATION: {location_name}
PRESENT: {', '.join(char_names) if char_names else 'Alone'}
MOOD: {mood_desc}
"""

        # Check if we have pre-selected draft action ideas to expand
        selected_drafts = context.get('selected_draft_summaries', [])

        if selected_drafts:
            logger.info(f"✅ Using {len(selected_drafts)} pre-selected draft action ideas")
            print(f"✅ ResilientActionGenerator: Expanding {len(selected_drafts)} pre-selected draft ideas")

            instruction = f"""{'='*60}
EXPAND THESE {len(selected_drafts)} ACTION IDEAS WITH NARRATIVE DETAIL
{'='*60}

"""
            for i, summary in enumerate(selected_drafts, 1):
                instruction += f"{i}. {summary}\n"

            instruction += f"""
For each idea, create a rich action sequence with narrative detail.
Return exactly {len(selected_drafts)} options in the same order.

Return ONLY a JSON array (no other text).
{'='*60}
"""
        else:
            logger.info(f"⚠️  No pre-selected drafts, generating {num_options} options from scratch")

            instruction = f"""Generate {num_options} distinctive action options.

Return ONLY a JSON array (no other text).
"""

        full_prompt = context_prompt + "\n" + instruction

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

        Raises:
            ProviderRefusalError: If response contains content policy refusal
        """
        import json
        import re

        logger.info(f"Parsing response (length: {len(response)} chars)")

        # First, check if the response is a content refusal
        # Some models (even "permissive" ones) refuse in the response text instead of via API error
        refusal_phrases = [
            "i cannot create explicit content",
            "i can't create explicit content",
            "i cannot generate",
            "i can't generate",
            "i'm not able to create",
            "i'm not able to generate",
            "content policy",
            "inappropriate content",
            "against my guidelines",
            "against my programming",
            "i cannot assist with",
            "i can't assist with"
        ]

        response_lower = response.lower()
        for phrase in refusal_phrases:
            if phrase in response_lower and len(response) < 500:  # Short responses are likely refusals
                logger.warning(f"Detected content refusal in response text: '{response[:100]}'")
                raise ProviderRefusalError(
                    RefusalReason.CONTENT_POLICY,
                    f"Model refused in response text: {response[:200]}"
                )

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
                    # Check if it looks like an action option (has expected fields)
                    # New format: summary, emotional_tone, actions array
                    # Old format: thought, private_thought, action, speech
                    if any(key in action for key in ['summary', 'emotional_tone', 'actions', 'thought', 'private_thought', 'action', 'speech']):
                        actions.append(action)
                except json.JSONDecodeError:
                    continue

            if actions:
                return actions
        except Exception:
            pass

        # Fallback: create a single generic action from the response text
        logger.error(f"Could not parse structured actions, using fallback. Response preview: {response[:500]}")

        # Try to at least create a reasonable fallback (new format)
        return [{
            "summary": "Take a cautious moment to observe",
            "emotional_tone": "cautious",
            "escalates_mood": False,
            "deescalates_mood": False,
            "estimated_mood_impact": {"tension": 0, "hostility": 0, "romance": 0},
            "turn_duration": 1,
            "current_stance": "standing",
            "current_clothing": "unchanged",
            "current_emotional_state": "contemplative",
            "actions": [
                {"type": "think", "description": "Considering the situation carefully", "is_private": True},
                {"type": "wait", "description": "Take a moment to assess the situation and consider options", "is_private": False}
            ]
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

    def _build_atmospheric_system_prompt(self, intensity: ContentIntensity) -> str:
        """
        Build system prompt for atmospheric description generation.

        Args:
            intensity: Content intensity level

        Returns:
            System prompt string
        """
        base = self._build_system_prompt(intensity)

        # Add atmospheric-specific instructions
        atmospheric_instructions = """

Your task is to generate atmospheric descriptions with mood analysis for a dark fantasy game.

CRITICAL OUTPUT FORMAT:
You MUST return a valid JSON object with this EXACT structure (no markdown, no code blocks):
{
  "description": "2-3 sentence atmospheric description here",
  "mood_deltas": {
    "tension": 0,
    "romance": 0,
    "hostility": 0,
    "cooperation": 0
  }
}

DESCRIPTION REQUIREMENTS:
- Focus on the AFTEREFFECTS and ATMOSPHERE following the action
- DO NOT repeat or narrate the action itself
- Include sensory details: sight, sound, smell, physical sensations
- Describe visible reactions: expressions, breathing, posture, tremors, stillness
- Note environmental elements: lighting, shadows, temperature, ambient sounds
- Track state changes: stance shifts, clothing dishevelment
- Write in third-person, cinematic style (like a film scene)
- Keep tone dark fantasy, atmospheric, concise (4-6 sentences)

MOOD ANALYSIS REQUIREMENTS:
Analyze the emotional impact on these dimensions (delta values: -20 to +20):
- tension: Overall stress/tension (+ = more tense, - = calmer)
- romance: Romantic/sexual atmosphere (+ = more intimate, - = colder)
- hostility: Anger/aggression (+ = more hostile, - = friendlier)
- cooperation: Willingness to work together (+ = more cooperative, - = less)

IMPORTANT: Return ONLY the JSON object. No additional text, no markdown formatting."""

        return base + atmospheric_instructions

    def _build_atmospheric_user_prompt(
        self,
        character_name: str,
        action_description: str,
        location_name: str,
        location_description: Optional[str] = None,
        other_characters: List[str] = None,
        recent_history: str = None,
        current_stance: Optional[str] = None,
        current_clothing: Optional[str] = None,
        appearance_state: Optional[str] = None
    ) -> str:
        """
        Build concise user prompt for atmospheric description.

        Args:
            character_name: Name of acting character
            action_description: What they did
            location_name: Current location
            location_description: Description of the location
            other_characters: Other characters present
            recent_history: Recent turn history (condensed)
            current_stance: Character's current stance
            current_clothing: Character's current clothing
            appearance_state: Dynamic appearance changes

        Returns:
            User prompt string
        """
        prompt_parts = []

        # Location
        if location_description:
            prompt_parts.append(f"LOCATION: {location_name} - {location_description}")
        else:
            prompt_parts.append(f"LOCATION: {location_name}")

        # Character state
        if current_stance or current_clothing or appearance_state:
            state = []
            if current_stance:
                state.append(f"{current_stance}")
            if current_clothing:
                state.append(f"wearing {current_clothing}")
            if appearance_state:
                state.append(f"appearance: {appearance_state}")
            prompt_parts.append(f"CHARACTER STATE: {character_name} is {', '.join(state)}")

        # Others present
        if other_characters:
            prompt_parts.append(f"OTHERS PRESENT: {', '.join(other_characters)}")

        # Recent context (only last 1-2 actions to save tokens)
        if recent_history:
            history_lines = recent_history.split('\n')[:2]  # Only last 2 lines
            prompt_parts.append(f"\nRECENT CONTEXT:\n{chr(10).join(history_lines)}")

        # Current action
        prompt_parts.append(f"\nCURRENT ACTION: {character_name} {action_description}")

        prompt_parts.append("\nGenerate the atmospheric aftermath and mood analysis as JSON.")

        return '\n'.join(prompt_parts)

    def generate_atmospheric_description(
        self,
        character_name: str,
        action_description: str,
        location_name: str,
        location_description: Optional[str] = None,
        other_characters: List[str] = None,
        recent_history: str = None,
        current_stance: Optional[str] = None,
        current_clothing: Optional[str] = None,
        appearance_state: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate atmospheric description with mood analysis and automatic fallback for adult content.

        Handles violent, sexual, and disturbing content by using the provider
        fallback chain. Content intensity is automatically classified.

        Args:
            character_name: Name of character who acted
            action_description: What they did
            location_name: Current location
            location_description: Description of the location
            other_characters: List of other character names present
            recent_history: Recent turn history
            current_stance: Character's current stance/posture (e.g., "standing", "sitting")
            current_clothing: Description of what the character is wearing
            appearance_state: Dynamic appearance changes (disheveled, removed items, positioning, etc.)

        Returns:
            Dictionary with:
                - 'description': Atmospheric description text
                - 'mood_deltas': Dict with tension, romance, hostility, cooperation deltas

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

        # Build structured system prompt (similar to action_generator style)
        system_prompt = self._build_atmospheric_system_prompt(intensity)

        # Build concise user prompt (minimal context to save tokens)
        user_prompt = self._build_atmospheric_user_prompt(
            character_name=character_name,
            action_description=action_description,
            location_name=location_name,
            location_description=location_description,
            other_characters=other_characters,
            recent_history=recent_history,
            current_stance=current_stance,
            current_clothing=current_clothing
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
                logger.info(f"Trying {provider_label} for atmospheric description")

                # Adjust prompts for this provider (handles content policy differences)
                adjusted_user_prompt = self.strategy.adjust_prompt_for_provider(
                    user_prompt, provider_name, model, intensity
                )
                adjusted_system_prompt = self.strategy.adjust_prompt_for_provider(
                    system_prompt, provider_name, model, intensity
                )

                response = provider.generate(
                    prompt=adjusted_user_prompt,
                    system_prompt=adjusted_system_prompt,
                    model=model,
                    temperature=0.7,  # Lower temperature for more consistent JSON
                    max_tokens=600
                )

                logger.info(f"✓ Atmospheric description generated with {provider_label}")

                # Parse JSON response
                import json
                import re

                # Clean up response (remove markdown code blocks if present)
                cleaned_response = response.strip()
                # Remove markdown code blocks
                cleaned_response = re.sub(r'^```json\s*', '', cleaned_response)
                cleaned_response = re.sub(r'^```\s*', '', cleaned_response)
                cleaned_response = re.sub(r'\s*```$', '', cleaned_response)
                cleaned_response = cleaned_response.strip()

                try:
                    result = json.loads(cleaned_response)

                    # Validate structure
                    if 'description' not in result or 'mood_deltas' not in result:
                        logger.warning(f"Invalid JSON structure from {provider_label}, extracting description field if possible")
                        # Try to extract description field even if mood_deltas is missing
                        if isinstance(result, dict) and 'description' in result:
                            return {
                                'description': result['description'],
                                'mood_deltas': {'tension': 0, 'romance': 0, 'hostility': 0, 'cooperation': 0}
                            }
                        else:
                            # Fallback: use cleaned response but DON'T include JSON structure
                            # Try to extract text that looks like a description
                            description_text = cleaned_response
                            try:
                                # If it looks like JSON, try to extract description field with regex
                                # This handles escaped quotes and multiline descriptions
                                desc_match = re.search(r'"description"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned_response, re.DOTALL)
                                if desc_match:
                                    description_text = desc_match.group(1)
                                    # Unescape common escape sequences
                                    description_text = description_text.replace('\\n', '\n').replace('\\r', '\r').replace('\\t', '\t').replace('\\"', '"')
                            except:
                                pass
                            return {
                                'description': description_text,
                                'mood_deltas': {'tension': 0, 'romance': 0, 'hostility': 0, 'cooperation': 0}
                            }

                    # Ensure mood_deltas has all required fields
                    mood_deltas = result.get('mood_deltas', {})
                    mood_deltas.setdefault('tension', 0)
                    mood_deltas.setdefault('romance', 0)
                    mood_deltas.setdefault('hostility', 0)
                    mood_deltas.setdefault('cooperation', 0)

                    return {
                        'description': result['description'],
                        'mood_deltas': mood_deltas
                    }

                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse JSON from {provider_label}: {e}. Attempting to extract description.")
                    # Try to extract description field from the malformed JSON using regex
                    description_text = cleaned_response
                    try:
                        # This handles escaped quotes and multiline descriptions
                        desc_match = re.search(r'"description"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned_response, re.DOTALL)
                        if desc_match:
                            description_text = desc_match.group(1)
                            # Unescape common escape sequences
                            description_text = description_text.replace('\\n', '\n').replace('\\r', '\r').replace('\\t', '\t').replace('\\"', '"')
                            logger.info("Successfully extracted description from malformed JSON")
                        else:
                            # If we can't extract, at least don't show JSON structure
                            # Just use the first 200 chars as a fallback
                            if len(cleaned_response) > 200:
                                description_text = cleaned_response[:200] + "..."
                    except Exception as extract_error:
                        logger.warning(f"Could not extract description: {extract_error}")
                        # Last resort: truncate the response
                        if len(cleaned_response) > 200:
                            description_text = cleaned_response[:200] + "..."

                    return {
                        'description': description_text,
                        'mood_deltas': {'tension': 0, 'romance': 0, 'hostility': 0, 'cooperation': 0}
                    }

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
