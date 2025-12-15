"""
Context Manager for LLM Prompts

Handles dynamic context assembly based on model token limits.
Ensures context fits within limits while preserving critical information.

Key features:
- Track context window per model
- Priority-based context inclusion
- Intelligent truncation without breaking meaning
- Token counting per provider
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import tiktoken

logger = logging.getLogger(__name__)


class ContextPriority(Enum):
    """Priority levels for context components"""
    CRITICAL = 1      # Must always include (character identity, current situation)
    HIGH = 2          # Very important (working memory, relationships)
    MEDIUM = 3        # Useful but can trim (short-term summaries)
    LOW = 4           # Nice to have (long-term memories)
    OPTIONAL = 5      # Can drop entirely (flavor text, extended backstory)


@dataclass
class ContextComponent:
    """A single component of the context"""
    name: str
    content: str
    priority: ContextPriority
    token_count: int = 0
    is_required: bool = False  # If True, never drop this

    def __post_init__(self):
        if self.token_count == 0:
            # Estimate if not provided
            self.token_count = estimate_tokens(self.content)


@dataclass
class ModelContextLimits:
    """Context window limits for various models"""

    # Model-specific limits (total context window)
    LIMITS = {
        # Anthropic
        "claude-3-5-sonnet-20241022": 200000,
        "claude-3-5-haiku-20241022": 200000,
        "claude-3-opus-20240229": 200000,

        # OpenAI
        "gpt-4": 8192,
        "gpt-4-turbo": 128000,
        "gpt-4o": 128000,
        "gpt-4o-mini": 128000,
        "gpt-3.5-turbo": 16385,

        # AIML API
        "mistralai/Mistral-7B-Instruct-v0.2": 32768,
        "mistralai/Mixtral-8x7B-Instruct-v0.1": 32768,
        "meta-llama/Meta-Llama-3-70B-Instruct": 8192,
        "meta-llama/Meta-Llama-3.1-405B-Instruct": 131072,
        "meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo": 131072,
        "meta-llama/Llama-3.1-405B-Instruct-Turbo": 131072,

        # Together.ai
        "mistralai/Mixtral-8x7B-Instruct-v0.1": 32768,
        "meta-llama/Llama-3-70b-chat-hf": 8192,
        "meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo": 131072,

        # Local models
        "llama-3-70b-instruct": 8192,
        "mistral-7b-instruct": 32768,
    }

    @classmethod
    def get_limit(cls, model: str) -> int:
        """
        Get context window limit for a model.

        Args:
            model: Model identifier

        Returns:
            Token limit (defaults to 8192 if unknown)
        """
        # Try exact match first
        if model in cls.LIMITS:
            return cls.LIMITS[model]

        # Try partial match
        for known_model, limit in cls.LIMITS.items():
            if model in known_model or known_model in model:
                return limit

        # Default to conservative limit
        logger.warning(f"Unknown model {model}, using default limit of 8192")
        return 8192

    @classmethod
    def get_safe_limit(cls, model: str, safety_margin: float = 0.85) -> int:
        """
        Get safe context limit with margin for response tokens.

        Args:
            model: Model identifier
            safety_margin: Use this % of total limit (default 85%)

        Returns:
            Safe token limit for input
        """
        total_limit = cls.get_limit(model)
        safe_limit = int(total_limit * safety_margin)

        logger.debug(
            f"Model {model}: total={total_limit}, safe={safe_limit} "
            f"({safety_margin*100:.0f}% of total)"
        )

        return safe_limit


def estimate_tokens(text: str, model: str = "gpt-4") -> int:
    """
    Estimate token count for text.

    Args:
        text: Text to count
        model: Model to use for tokenization (defaults to gpt-4)

    Returns:
        Estimated token count
    """
    if not text:
        return 0

    try:
        # Use tiktoken for accurate counting
        if "gpt" in model.lower() or "claude" in model.lower():
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        else:
            # Fallback: rough estimate for other models
            # Most models use similar tokenization (~4 chars per token)
            return len(text) // 4
    except Exception as e:
        logger.warning(f"Token counting error: {e}, using rough estimate")
        return len(text) // 4


def calculate_max_tokens(
    model: str,
    input_tokens: int,
    safety_margin: float = 0.9,
    min_output: int = 512,
    max_output: int = 3000
) -> int:
    """
    Calculate appropriate max_tokens for a model given input size.

    Args:
        model: Model identifier
        input_tokens: Number of tokens in the input
        safety_margin: Use this % of remaining space (default 90%)
        min_output: Minimum output tokens to allow
        max_output: Maximum output tokens to cap at

    Returns:
        Recommended max_tokens value
    """
    # Get model's total context limit
    total_limit = ModelContextLimits.get_limit(model)

    # Calculate available space for output
    available = total_limit - input_tokens

    if available <= 0:
        logger.error(
            f"Input ({input_tokens} tokens) exceeds model limit ({total_limit} tokens)!"
        )
        return min_output

    # Apply safety margin
    safe_available = int(available * safety_margin)

    # Clamp to reasonable range
    result = max(min_output, min(safe_available, max_output))

    logger.debug(
        f"Calculated max_tokens for {model}: "
        f"input={input_tokens}, limit={total_limit}, "
        f"available={available}, result={result}"
    )

    return result


class ContextAssembler:
    """
    Assembles context for LLM prompts with intelligent prioritization and truncation.
    """

    def __init__(self, model: str, max_response_tokens: int = 2048):
        """
        Initialize context assembler.

        Args:
            model: Target model identifier
            max_response_tokens: Expected max tokens in response
        """
        self.model = model
        self.max_response_tokens = max_response_tokens

        # Calculate available tokens for input
        total_limit = ModelContextLimits.get_limit(model)
        self.input_token_limit = total_limit - max_response_tokens

        # Use 90% of available input space to be safe
        self.safe_input_limit = int(self.input_token_limit * 0.9)

        logger.info(
            f"ContextAssembler for {model}: "
            f"total_limit={total_limit}, "
            f"input_limit={self.input_token_limit}, "
            f"safe_limit={self.safe_input_limit}"
        )

        self.components: List[ContextComponent] = []

    def add_component(
        self,
        name: str,
        content: str,
        priority: ContextPriority = ContextPriority.MEDIUM,
        is_required: bool = False
    ):
        """
        Add a context component.

        Args:
            name: Component identifier
            content: Component text
            priority: Priority level
            is_required: If True, never drop this component
        """
        component = ContextComponent(
            name=name,
            content=content,
            priority=priority,
            is_required=is_required
        )

        self.components.append(component)

        logger.debug(
            f"Added component '{name}': "
            f"{component.token_count} tokens, "
            f"priority={priority.name}"
        )

    def get_total_tokens(self) -> int:
        """Calculate total tokens across all components."""
        return sum(c.token_count for c in self.components)

    def assemble(
        self,
        system_prompt: Optional[str] = None,
        preserve_order: bool = False
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Assemble final context, truncating if necessary.

        Args:
            system_prompt: System prompt (not counted against limit)
            preserve_order: If True, maintain component order; if False, prioritize by importance

        Returns:
            Tuple of (assembled_context, metadata)
        """
        logger.info(f"Assembling context for {self.model}")

        # Calculate system prompt tokens (not part of user context)
        system_tokens = estimate_tokens(system_prompt or "", self.model)

        # Adjust available tokens
        available_tokens = self.safe_input_limit - system_tokens

        logger.info(
            f"Available tokens: {available_tokens} "
            f"(system_prompt: {system_tokens} tokens)"
        )

        # Get total tokens needed
        total_tokens = self.get_total_tokens()

        if total_tokens <= available_tokens:
            # All components fit
            logger.info(f"✓ All components fit ({total_tokens}/{available_tokens} tokens)")
            return self._assemble_all(preserve_order)

        # Need to truncate
        logger.warning(
            f"⚠ Context too large: {total_tokens} tokens needed, "
            f"only {available_tokens} available. Truncating..."
        )

        return self._assemble_with_truncation(available_tokens, preserve_order)

    def _assemble_all(self, preserve_order: bool) -> Tuple[str, Dict[str, Any]]:
        """Assemble all components without truncation."""
        if preserve_order:
            components = self.components
        else:
            # Sort by priority (CRITICAL first, OPTIONAL last)
            components = sorted(self.components, key=lambda c: c.priority.value)

        sections = [c.content for c in components]
        full_context = "\n\n".join(sections)

        metadata = {
            "total_tokens": self.get_total_tokens(),
            "available_tokens": self.safe_input_limit,
            "components_included": [c.name for c in components],
            "components_dropped": [],
            "was_truncated": False
        }

        return full_context, metadata

    def _assemble_with_truncation(
        self,
        available_tokens: int,
        preserve_order: bool
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Assemble context with intelligent truncation.

        Strategy:
        1. Always include REQUIRED components
        2. Include components by priority until limit reached
        3. Trim individual components if needed
        """
        # Separate required and optional components
        required = [c for c in self.components if c.is_required]
        optional = [c for c in self.components if not c.is_required]

        # Sort optional by priority
        optional_sorted = sorted(optional, key=lambda c: c.priority.value)

        # Calculate required tokens
        required_tokens = sum(c.token_count for c in required)

        if required_tokens > available_tokens:
            logger.error(
                f"⚠ CRITICAL: Required components ({required_tokens} tokens) "
                f"exceed available tokens ({available_tokens}). "
                f"Will need to trim required components!"
            )
            # This is bad - need to trim even required components
            return self._emergency_truncate(available_tokens)

        # Remaining tokens for optional components
        remaining_tokens = available_tokens - required_tokens

        # Greedily add optional components by priority
        included = list(required)
        dropped = []

        for component in optional_sorted:
            if component.token_count <= remaining_tokens:
                included.append(component)
                remaining_tokens -= component.token_count
            else:
                # Try to trim this component
                trimmed_content = self._trim_component(
                    component.content,
                    remaining_tokens
                )

                if trimmed_content:
                    # Include trimmed version
                    trimmed_component = ContextComponent(
                        name=f"{component.name} (trimmed)",
                        content=trimmed_content,
                        priority=component.priority,
                        token_count=remaining_tokens
                    )
                    included.append(trimmed_component)
                    remaining_tokens = 0
                    logger.info(
                        f"Trimmed component '{component.name}' "
                        f"from {component.token_count} to {trimmed_component.token_count} tokens"
                    )
                else:
                    # Drop entirely
                    dropped.append(component.name)
                    logger.info(f"Dropped component '{component.name}'")

        # Sort back to original order if requested
        if preserve_order:
            included.sort(key=lambda c: self.components.index(
                next(comp for comp in self.components if comp.name == c.name or c.name.startswith(comp.name))
            ))

        # Assemble
        sections = [c.content for c in included]
        final_context = "\n\n".join(sections)

        final_tokens = estimate_tokens(final_context, self.model)

        metadata = {
            "total_tokens": final_tokens,
            "available_tokens": available_tokens,
            "components_included": [c.name for c in included],
            "components_dropped": dropped,
            "was_truncated": True,
            "tokens_saved": self.get_total_tokens() - final_tokens
        }

        logger.info(
            f"✓ Context assembled: {final_tokens}/{available_tokens} tokens, "
            f"dropped {len(dropped)} components"
        )

        return final_context, metadata

    def _trim_component(self, content: str, max_tokens: int) -> Optional[str]:
        """
        Trim a component to fit within token limit.

        Args:
            content: Component content
            max_tokens: Maximum tokens allowed

        Returns:
            Trimmed content or None if too small
        """
        if max_tokens < 50:
            # Too small to be useful
            return None

        # Rough character estimate
        max_chars = max_tokens * 4

        if len(content) <= max_chars:
            return content

        # Trim to character limit, then find last sentence boundary
        trimmed = content[:max_chars]

        # Find last complete sentence
        last_period = trimmed.rfind('.')
        last_newline = trimmed.rfind('\n')

        boundary = max(last_period, last_newline)

        if boundary > max_chars * 0.7:  # At least 70% of desired length
            trimmed = trimmed[:boundary + 1]
            return trimmed + "\n\n[... rest of content truncated due to context limits ...]"

        # Just cut at character limit with ellipsis
        return trimmed + "..."

    def _emergency_truncate(self, available_tokens: int) -> Tuple[str, Dict[str, Any]]:
        """
        Emergency truncation when even required components don't fit.

        This should rarely happen, but handles the edge case.
        """
        logger.error("⚠ EMERGENCY TRUNCATION: Required components don't fit!")

        # Take components in priority order until we hit limit
        all_sorted = sorted(self.components, key=lambda c: c.priority.value)

        included = []
        remaining = available_tokens

        for component in all_sorted:
            if component.token_count <= remaining:
                included.append(component)
                remaining -= component.token_count
            elif remaining > 100:
                # Try to fit trimmed version
                trimmed = self._trim_component(component.content, remaining)
                if trimmed:
                    trimmed_comp = ContextComponent(
                        name=f"{component.name} (emergency trim)",
                        content=trimmed,
                        priority=component.priority,
                        token_count=remaining
                    )
                    included.append(trimmed_comp)
                    remaining = 0
                break

        sections = [c.content for c in included]
        final_context = "\n\n".join(sections)

        metadata = {
            "total_tokens": estimate_tokens(final_context, self.model),
            "available_tokens": available_tokens,
            "components_included": [c.name for c in included],
            "components_dropped": [c.name for c in self.components if c not in included],
            "was_truncated": True,
            "emergency_truncation": True,
            "warning": "Required components were truncated! Results may be poor."
        }

        return final_context, metadata


def _detect_context_relevance(
    character: Dict[str, Any],
    game_context: Dict[str, Any]
) -> Dict[str, bool]:
    """
    Detect which character attributes are relevant to the current situation.

    Args:
        character: Character profile
        game_context: Current game state

    Returns:
        Dict mapping attribute names to relevance (True/False)
    """
    relevance = {
        # Always relevant
        "objectives": True,
        "appearance": True,
        "clothing": True,
        "items": True,
        "stance": True,
        "state": True,
        "personality": True,
        "emotional_state": True,

        # Conditionally relevant (default False)
        "food_preferences": False,
        "clothing_preferences": False,
        "hobbies": False,
        "superstitions": False,
        "attraction_types": False,
        "education_details": False,
        "social_class_details": False
    }

    # Analyze context for relevance triggers
    action_type = game_context.get('action_type', '').lower()
    location_desc = game_context.get('location_description', '').lower()
    working_memory = game_context.get('working_memory', '').lower()
    recent_topics = game_context.get('recent_conversation_topics', [])

    # Food preferences relevant when eating/cooking/discussing food
    food_triggers = ['eat', 'food', 'meal', 'cook', 'drink', 'tavern', 'kitchen', 'hungry']
    if any(trigger in action_type or trigger in location_desc or trigger in working_memory
           for trigger in food_triggers):
        relevance["food_preferences"] = True

    # Clothing preferences relevant when shopping/discussing appearance
    clothing_triggers = ['shop', 'tailor', 'merchant', 'wear', 'dress', 'appearance', 'clothing']
    if any(trigger in action_type or trigger in location_desc or trigger in working_memory
           for trigger in clothing_triggers):
        relevance["clothing_preferences"] = True

    # Hobbies relevant in leisure/social contexts
    hobby_triggers = ['leisure', 'free time', 'hobby', 'pastime', 'entertainment']
    if any(trigger in action_type or trigger in working_memory for trigger in hobby_triggers):
        relevance["hobbies"] = True

    # Superstitions relevant in supernatural/religious contexts
    superstition_triggers = ['supernatural', 'curse', 'blessing', 'ritual', 'omen', 'magic']
    if any(trigger in action_type or trigger in location_desc or trigger in working_memory
           for trigger in superstition_triggers):
        relevance["superstitions"] = True

    # Attraction types relevant in romantic/social contexts
    attraction_triggers = ['romance', 'attraction', 'flirt', 'court', 'seduce', 'intimate']
    if any(trigger in action_type or trigger in working_memory for trigger in attraction_triggers):
        relevance["attraction_types"] = True

    # Education details relevant in intellectual/academic contexts
    education_triggers = ['study', 'knowledge', 'library', 'scholar', 'academic', 'learn', 'teach']
    if any(trigger in action_type or trigger in location_desc or trigger in working_memory
           for trigger in education_triggers):
        relevance["education_details"] = True

    # Social class details relevant in political/social hierarchy contexts
    social_triggers = ['noble', 'lord', 'peasant', 'social', 'hierarchy', 'status', 'class']
    if any(trigger in action_type or trigger in location_desc or trigger in working_memory
           for trigger in social_triggers):
        relevance["social_class_details"] = True

    return relevance


def _build_dynamic_character_identity(
    character: Dict[str, Any],
    relevance: Dict[str, bool],
    model: str = None
) -> str:
    """
    Build character identity string with only relevant attributes.

    Args:
        character: Character profile
        relevance: Which attributes are relevant
        model: Model name for determining whether to use detailed or summary appearance

    Returns:
        Formatted character identity string
    """
    parts = []

    # Always include core identity
    parts.append(f"You are roleplaying as {character.get('name')}.")

    if character.get('physical_appearance'):
        parts.append(f"Appearance: {character.get('physical_appearance')}")

    # Get current clothing from Qdrant (dynamically generated from worn items)
    clothing_description = character.get('current_clothing_from_items')
    if clothing_description:
        parts.append(f"Clothing: {clothing_description}")
    elif character.get('current_clothing'):
        # Fallback to static database field if dynamic clothing not available
        parts.append(f"Clothing: {character.get('current_clothing')}")

    # Add appearance state (detailed for large models, summary for small models)
    from services.context_manager import ModelContextLimits
    context_limit = ModelContextLimits.get_limit(model) if model else 100000
    use_detailed = context_limit >= 100000  # Use detailed for models with 100K+ token windows

    appearance_state = None
    if use_detailed and character.get('appearance_state_detailed'):
        appearance_state = character.get('appearance_state_detailed')
    elif character.get('appearance_state_summary'):
        appearance_state = character.get('appearance_state_summary')

    if appearance_state:
        parts.append(f"Current appearance state: {appearance_state}")

    if relevance["personality"]:
        parts.append(f"Personality: {character.get('personality_traits')}")

    if relevance["emotional_state"]:
        parts.append(f"Current emotional state: {character.get('current_emotional_state')}")

    if character.get('current_stance'):
        parts.append(f"Current stance: {character.get('current_stance')}")

    # Objectives/motivations (always relevant)
    if character.get('motivations_short_term'):
        parts.append(f"Current objectives: {character.get('motivations_short_term')}")

    # Conditionally include based on relevance
    if relevance.get("food_preferences") and character.get('preferences', {}).get('food'):
        parts.append(f"Food preferences: {character['preferences']['food']}")

    if relevance.get("clothing_preferences") and character.get('preferences', {}).get('clothing_style'):
        parts.append(f"Clothing style: {character['preferences']['clothing_style']}")

    if relevance.get("hobbies") and character.get('hobbies'):
        parts.append(f"Hobbies: {character.get('hobbies')}")

    if relevance.get("superstitions") and character.get('superstitions'):
        parts.append(f"Superstitions/beliefs: {character.get('superstitions')}")

    if relevance.get("attraction_types") and character.get('preferences', {}).get('attraction_types'):
        parts.append(f"Attraction preferences: {character['preferences']['attraction_types']}")

    if relevance.get("education_details") and character.get('education_level'):
        parts.append(f"Education: {character.get('education_level')}")
        if character.get('skills'):
            parts.append(f"Skills: {character.get('skills')}")

    if relevance.get("social_class_details") and character.get('social_class'):
        parts.append(f"Social class: {character.get('social_class')}")
        if character.get('reputation'):
            parts.append(f"Reputation: {character.get('reputation')}")

    return "\n".join(parts)


def _get_adaptive_memory_window(model: str) -> int:
    """
    Determine optimal working memory window size for a model.

    Args:
        model: Model identifier

    Returns:
        Number of turns to include in working memory
    """
    context_limit = ModelContextLimits.get_limit(model)

    # Small models (8K-16K): Use 5 turns
    if context_limit <= 16384:
        return 5

    # Medium models (16K-64K): Use 8 turns
    elif context_limit <= 65536:
        return 8

    # Large models (64K+): Use full 10 turns
    else:
        return 10


def build_character_context(
    character: Dict[str, Any],
    game_context: Dict[str, Any],
    model: str,
    max_response_tokens: int = 2048
) -> Tuple[str, Dict[str, Any]]:
    """
    Build context for character action generation with optimal token usage.

    Now with situational awareness: dynamically includes only relevant character
    attributes and adapts working memory window to model capacity.

    Args:
        character: Character profile
        game_context: Game state (location, visible characters, memory, etc.)
        model: Target model
        max_response_tokens: Expected response size

    Returns:
        Tuple of (assembled_context, metadata)
    """
    assembler = ContextAssembler(model, max_response_tokens)

    # Detect which character attributes are relevant to current situation
    relevance = _detect_context_relevance(character, game_context)

    # Determine optimal memory window for this model
    memory_window = _get_adaptive_memory_window(model)

    # CRITICAL - always include (now with dynamic relevance-based identity)
    character_identity = _build_dynamic_character_identity(character, relevance, model)
    assembler.add_component(
        name="character_identity",
        content=character_identity,
        priority=ContextPriority.CRITICAL,
        is_required=True
    )

    # Build current situation with time context
    situation_parts = []

    # Time information (if available)
    if game_context.get('time_of_day'):
        situation_parts.append(f"Time: {game_context.get('time_of_day')}")

        # Add lighting description if available
        if game_context.get('lighting_description'):
            situation_parts.append(game_context.get('lighting_description'))

    # Location information
    situation_parts.append(f"Current location: {game_context.get('location_name')}")
    situation_parts.append(f"Location description: {game_context.get('location_description')}")

    # Format visible characters - handle both list of strings and list of dicts
    visible_chars = game_context.get('visible_characters', [])
    if visible_chars:
        if isinstance(visible_chars[0], dict):
            # List of character dicts - extract names
            char_names = [char.get('name', 'Unknown') for char in visible_chars]
            situation_parts.append(f"Present characters: {', '.join(char_names)}")
        else:
            # List of strings (legacy format)
            situation_parts.append(f"Present characters: {', '.join(visible_chars)}")
    else:
        situation_parts.append("Present characters: None")

    assembler.add_component(
        name="current_situation",
        content="\n".join(situation_parts),
        priority=ContextPriority.CRITICAL,
        is_required=True
    )

    # HIGH - very important (now with adaptive window size)
    assembler.add_component(
        name="working_memory",
        content=f"Recent events (last {memory_window} turns):\n{game_context.get('working_memory', '')}",
        priority=ContextPriority.HIGH
    )

    # Include relationships if present
    if game_context.get('relationships'):
        assembler.add_component(
            name="relationships",
            content=f"Relationships with present characters:\n{game_context.get('relationships')}",
            priority=ContextPriority.HIGH
        )

    # SHORT-TERM SUMMARY - priority depends on model size
    # For small models, summaries are MORE important than full working memory
    if game_context.get('short_term_summary'):
        summary_priority = ContextPriority.HIGH if memory_window <= 5 else ContextPriority.MEDIUM
        assembler.add_component(
            name="session_summary",
            content=f"Session summary:\n{game_context.get('short_term_summary')}",
            priority=summary_priority
        )

    # Character state (wounds, inventory)
    if game_context.get('character_wounds') or game_context.get('character_inventory'):
        state_content = ""
        if game_context.get('character_wounds'):
            state_content += f"Current wounds:\n{game_context.get('character_wounds')}\n\n"
        if game_context.get('character_inventory'):
            state_content += f"Inventory:\n{game_context.get('character_inventory')}"

        assembler.add_component(
            name="character_state",
            content=state_content,
            priority=ContextPriority.HIGH
        )

    # LOW - nice to have
    if game_context.get('long_term_memories'):
        assembler.add_component(
            name="long_term_memories",
            content=f"Relevant past events:\n{game_context.get('long_term_memories')}",
            priority=ContextPriority.LOW
        )

    # OPTIONAL - extended backstory
    if character.get('backstory'):
        assembler.add_component(
            name="backstory",
            content=f"Backstory:\n{character.get('backstory')}",
            priority=ContextPriority.OPTIONAL
        )

    # Assemble with intelligent truncation
    final_context, metadata = assembler.assemble(
        system_prompt=game_context.get('system_prompt'),
        preserve_order=True  # Keep narrative flow
    )

    # Add adaptive strategy metadata
    metadata['adaptive_strategy'] = {
        'memory_window': memory_window,
        'relevant_attributes': [k for k, v in relevance.items() if v and k not in
                               ['objectives', 'appearance', 'clothing', 'items', 'stance',
                                'state', 'personality', 'emotional_state']],
        'summary_priority': 'HIGH' if memory_window <= 5 else 'MEDIUM',
        'context_limit': ModelContextLimits.get_limit(model)
    }

    logger.info(
        f"Adaptive context for {model}: "
        f"memory_window={memory_window}, "
        f"relevant_attrs={len([k for k, v in relevance.items() if v])}"
    )

    return final_context, metadata
