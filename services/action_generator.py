"""
Action Generation Service

Generates action options for characters using LLMs with:
- Multi-action sequences (think → speak → act)
- Mood awareness and escalation/de-escalation
- Context-appropriate diversity
- Proper public/private action tracking
- Automatic provider fallback for content policy handling
"""

import logging
import json
import random
from typing import List, Dict, Any, Optional
from uuid import UUID

from models.action_sequence import (
    ActionSequence, ActionOption, GeneratedActionOptions,
    SingleAction, ActionType, create_simple_action
)
from models.scene_mood import SceneMood
from models.game_time import GameTime
from models.turn import Turn
from services.context_manager import build_character_context, ContextPriority, _get_adaptive_memory_window
from services.item_store import ItemStore
from services.item_context_helper import ItemContextHelper
from sqlalchemy import text

# Import for proper error handling of provider fallback
try:
    from services.llm.resilient_generator import AllProvidersFailedError
except ImportError:
    # Fallback if not available
    class AllProvidersFailedError(Exception):
        pass

logger = logging.getLogger(__name__)


def _format_combined_turn_history(actions: List[Dict[str, Any]]) -> List[str]:
    """
    Format turn history by combining all actions for each character per turn.

    Example output:
    Turn 3: Sir Gelarthon Findraell - Speak "I dream of the way you move",
    Speak: "Fizrae, my love...", Interact: "Sir Gelarthon reaches for Fizrae" (2T, 1 remaining)

    Args:
        actions: List of action dictionaries with turn_number, sequence_number,
                character_name, action_type, action_description, turn_duration, etc.

    Returns:
        List of formatted turn strings
    """
    from collections import defaultdict

    # Group actions by (turn_number, character_name)
    turns_grouped = defaultdict(list)
    for action in actions:
        key = (action['turn_number'], action['character_name'])
        turns_grouped[key].append(action)

    # Sort each group by sequence_number to maintain order
    for key in turns_grouped:
        turns_grouped[key].sort(key=lambda a: a.get('sequence_number', 0))

    # Format each turn
    formatted_lines = []
    for (turn_num, char_name), turn_actions in sorted(turns_grouped.items()):
        # Combine all action descriptions for this character's turn
        action_parts = []
        for action in turn_actions:
            action_type = action['action_type'].capitalize()
            description = action['action_description']

            # Format based on action type
            if action_type.lower() in ['speak', 'think']:
                # For speech/thoughts, show type and quoted text
                action_parts.append(f'{action_type} "{description}"')
            else:
                # For other actions, show type: description
                action_parts.append(f'{action_type}: "{description}"')

        # Build the line: Turn X: Character Name - action1, action2, action3
        combined_actions = ', '.join(action_parts)
        line = f"Turn {turn_num}: {char_name} - {combined_actions}"

        # Add turn duration info if applicable (use info from last action in sequence)
        last_action = turn_actions[-1]
        turn_duration = last_action.get('turn_duration', 1)
        remaining_duration = last_action.get('remaining_duration', 0)

        if turn_duration > 1 or remaining_duration > 0:
            line += f" ({turn_duration}T"
            if remaining_duration > 0:
                line += f", {remaining_duration} remaining"
            line += ")"

        formatted_lines.append(line)

    return formatted_lines


class ActionGenerationContext:
    """
    Assembles context specifically for action generation prompts.

    This is more focused than general character context - includes only
    what's needed for generating action options.
    """

    def __init__(
        self,
        db_session,
        character: Dict[str, Any],
        game_state_id: UUID,
        location: Dict[str, Any],
        visible_characters: List[Dict[str, Any]],
        current_turn: int,
        llm_provider=None
    ):
        self.db_session = db_session
        self.character = character
        self.game_state_id = game_state_id
        self.location = location
        self.visible_characters = visible_characters
        self.current_turn = current_turn
        self.llm_provider = llm_provider

        # Initialize item system
        try:
            self.item_store = ItemStore()
            self.item_context_helper = ItemContextHelper(self.item_store)
        except Exception as e:
            logger.warning(f"Failed to initialize item system: {e}")
            self.item_store = None
            self.item_context_helper = None

    def build(self, model: str) -> Dict[str, Any]:
        """
        Build complete context for action generation.

        Returns dictionary with all context components.
        """
        context = {}

        # Time context
        time_context = GameTime.get_time_context(self.db_session, self.game_state_id)
        context['time_of_day'] = GameTime.format_time_for_prompt(time_context)
        context['lighting_description'] = GameTime.get_lighting_description(time_context)

        # Location
        context['location_name'] = self.location.get('name')
        context['location_description'] = self.location.get('description')

        # Character state
        context['character_name'] = self.character.get('name')
        context['character_emotional_state'] = self.character.get('current_emotional_state')
        context['character_motivations'] = self.character.get('motivations_short_term')
        context['character_stance'] = self.character.get('current_stance', 'standing')

        # Get clothing from Qdrant items (dynamic)
        if self.item_context_helper:
            try:
                character_id = self.character.get('character_id')
                clothing_from_items = self.item_context_helper.get_clothing_description_from_items(
                    character_id, brief=True
                )
                context['character_clothing'] = clothing_from_items or self.character.get('current_clothing', 'unchanged')
            except Exception as e:
                logger.warning(f"Failed to get clothing from items: {e}")
                context['character_clothing'] = self.character.get('current_clothing', 'unchanged')
        else:
            context['character_clothing'] = self.character.get('current_clothing', 'unchanged')

        # Visible characters (basic attributes only)
        context['visible_characters'] = []
        for char in self.visible_characters:
            # Get clothing for visible characters from Qdrant too
            char_clothing = char.get('current_clothing')
            if self.item_context_helper:
                try:
                    char_clothing_from_items = self.item_context_helper.get_clothing_description_from_items(
                        char.get('character_id'), brief=True
                    )
                    char_clothing = char_clothing_from_items or char_clothing
                except Exception as e:
                    logger.debug(f"Failed to get clothing from items for {char.get('name')}: {e}")

            context['visible_characters'].append({
                'name': char.get('name'),
                'appearance': char.get('physical_appearance'),
                'stance': char.get('current_stance'),
                'clothing': char_clothing
            })

        # Working memory - fixed 4 turns (excluding atmospheric descriptions)
        memory_window = 4
        witnessed_actions = Turn.get_witnessed_memory(
            db_session=self.db_session,
            game_state_id=self.game_state_id,
            character_id=self.character['character_id'],
            last_n_turns=memory_window
        )

        # Filter out atmospheric actions from context
        witnessed_actions = [
            action for action in witnessed_actions
            if action.get('action_type') != 'atmospheric'
        ]

        # Mood - Will be analyzed inline during draft generation (no separate LLM call)
        # Fallback to database mood if needed
        mood = SceneMood.get(self.db_session, self.game_state_id, self.location['location_id'])
        if mood:
            context['mood_description'] = SceneMood.get_description(
                self.db_session,
                self.game_state_id,
                self.location['location_id']
            )
            context['mood_guidance'] = SceneMood.get_action_guidance(
                self.db_session,
                self.game_state_id,
                self.location['location_id']
            )
        else:
            context['mood_description'] = "General mood: Neutral. The atmosphere is calm."
            context['mood_guidance'] = {
                'should_generate_escalation': False,
                'escalation_weight': 0.5,
                'deescalation_required': False,
                'mood_category': 'neutral'
            }

        # Format working memory for prompt - combine all actions per character per turn
        if witnessed_actions:
            memory_lines = _format_combined_turn_history(witnessed_actions)
            context['working_memory'] = "\n".join(memory_lines)
        else:
            context['working_memory'] = "No recent events to recall."

        # Tiered memory summaries (with model-aware selection of descriptive vs condensed)
        from services.memory_summarizer import MemorySummarizer
        from services.context_manager import ModelContextLimits

        # Determine if we should use descriptive (large models) or condensed (small models) summaries
        context_limit = ModelContextLimits.get_limit(model)
        use_descriptive = context_limit >= 100000  # Use descriptive for models with 100K+ token windows

        # Get memory summarizer instance
        memory_summarizer = MemorySummarizer(self.llm_provider)

        # Get tiered summaries for this character
        tiered_summaries = memory_summarizer.get_summaries_for_context(
            db_session=self.db_session,
            game_state_id=self.game_state_id,
            character_id=self.character['character_id'],
            use_descriptive=use_descriptive,
            exclude_recent_n_turns=memory_window  # Exclude what's in working memory
        )

        if tiered_summaries:
            # Format summaries by time window
            summary_parts = []
            for summary_info in tiered_summaries:
                window_label = summary_info['window_type'].replace('_', ' ').title()
                turn_range = f"{summary_info['start_turn']}-{summary_info['end_turn']}"
                summary_parts.append(
                    f"[{window_label} - Turns {turn_range}]\n{summary_info['summary']}"
                )
            context['event_summary'] = "\n\n".join(summary_parts)
        else:
            context['event_summary'] = None

        # Relationships with visible characters
        if self.visible_characters:
            relationships = []
            for char in self.visible_characters:
                rel = self.db_session.execute(
                    text("""
                        SELECT * FROM character_relationship_get(
                            p_source_character_id := :source_id,
                            p_target_character_id := :target_id
                        )
                    """),
                    {
                        "source_id": str(self.character['character_id']),
                        "target_id": str(char['character_id'])
                    }
                ).fetchone()

                if rel:
                    relationships.append(
                        f"{char['name']}: Trust {rel.trust:.1f}, Fear {rel.fear:.1f}, "
                        f"Respect {rel.respect:.1f} ({rel.relationship_type or 'neutral'})"
                    )

            if relationships:
                context['relationships'] = "\n".join(relationships)
            else:
                context['relationships'] = None
        else:
            context['relationships'] = None

        # Items and Inventory (using Qdrant-based item system)
        if self.item_context_helper:
            try:
                # Get character's inventory (formatted)
                inventory_text = self.item_context_helper.format_inventory_for_prompt(
                    character_id=self.character['character_id'],
                    include_details=False  # Brief format to save tokens
                )
                context['inventory'] = inventory_text

                # Get relevant items at location (for interaction)
                visible_items = self.item_context_helper.get_relevant_items_for_context(
                    location_id=self.location['location_id'],
                    action_description=None,  # No specific action yet
                    character_id=self.character['character_id'],
                    max_items=5  # Limit to avoid token bloat
                )

                if visible_items:
                    items_text = self.item_context_helper.format_items_for_prompt(
                        items=visible_items,
                        include_details=False  # Brief format
                    )
                    context['visible_items'] = items_text
                else:
                    context['visible_items'] = None

            except Exception as e:
                logger.warning(f"Error loading items for context: {e}")
                context['inventory'] = None
                context['visible_items'] = None
        else:
            # Fallback to old inventory system if item system unavailable
            inventory = self.db_session.execute(
                text("""
                    SELECT item_name, quantity, item_properties
                    FROM character.character_inventory
                    WHERE character_id = :character_id
                    ORDER BY item_name
                """),
                {"character_id": str(self.character['character_id'])}
            ).fetchall()

            if inventory:
                inventory_items = []
                for item in inventory:
                    qty_str = f" x{item.quantity}" if item.quantity > 1 else ""
                    inventory_items.append(f"{item.item_name}{qty_str}")
                context['inventory'] = ", ".join(inventory_items)
            else:
                context['inventory'] = None

            context['visible_items'] = None

        return context


class ActionGenerationPrompt:
    """
    Builds prompts for action generation with mood awareness.
    """

    @staticmethod
    def build_system_prompt(model: str = None, character_name: str = None) -> str:
        """
        Build system prompt for action generation.

        Args:
            model: Model identifier (optional, for context-aware prompt)
            character_name: The character's name to use in examples (optional)

        Returns:
            System prompt string
        """
        from services.context_manager import ModelContextLimits

        # Determine if this is a small model (<=16K context)
        is_small_model = False
        if model:
            context_limit = ModelContextLimits.get_limit(model)
            is_small_model = context_limit <= 16384

        # Use character_name if provided, otherwise use a placeholder
        char_placeholder = character_name if character_name else "[the character's full name]"

        # Core action types (always included)
        core_actions = f"""- think: Private thought (only the character knows). Write in FIRST PERSON: "I think/wonder/consider... [character's internal monologue]"
- speak: Public dialogue (what others hear). Write as DIRECT DIALOGUE in first person: "dialogue spoken by character" (do NOT include "I say" or character name, just the dialogue itself)
- interact: Interact with object/character. Write in THIRD PERSON with character's FULL NAME: "{char_placeholder} [verb] the [object/character], [additional sensory detail]"
- move: Change location. Write in THIRD PERSON with character's FULL NAME: "{char_placeholder} moves/walks/runs to [location], [optional detail about how]"
- attack: Combat action. Write in THIRD PERSON with character's FULL NAME: "{char_placeholder} strikes/lunges at [target], [description of attack]"
- steal: Take something covertly. Write in THIRD PERSON with character's FULL NAME: "{char_placeholder} quietly/discreetly takes [item], [description]"
- use_item: Use inventory item. Write in THIRD PERSON with character's FULL NAME: "{char_placeholder} uses/applies/consumes [item], [effect/result]" """

        # Atmospheric action types (excluded for small models)
        atmospheric_actions = f"""- emote: Body language/gesture (others see). Write in THIRD PERSON with character's FULL NAME: "{char_placeholder} [gesture/expression], [detail about body language]"
- examine: Look at something closely. Write in THIRD PERSON with character's FULL NAME: "{char_placeholder} examines/studies [object/person], [what they notice]"
- wait: Do nothing/observe. Write in THIRD PERSON with character's FULL NAME: "{char_placeholder} waits/observes, [what they're watching or thinking]"
- hide: Attempt stealth. Write in THIRD PERSON with character's FULL NAME: "{char_placeholder} conceals themselves [location/method], [description]" """

        # Build action types list
        if is_small_model:
            action_types = core_actions
        else:
            action_types = core_actions + "\n" + atmospheric_actions

        # Build the example with character name
        example_interact = f'{{"type": "interact", "description": "{char_placeholder} reaches out and gently touches the other character\'s shoulder, her hand lingering for just a moment.", "is_private": false, "target": "character_name"}}'

        return f"""You are an expert at generating character action options for a dark fantasy text adventure game.

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
    {{"type": "think", "description": "I wonder if I can trust this stranger. My mind races with possibilities and doubts—should I reveal my true purpose?", "is_private": true}},
    {{"type": "speak", "description": "I've been waiting for you. There's something we need to discuss.", "is_private": false}},
    {example_interact}
  ]
}}

CRITICAL FORMATTING RULES:
- think actions: FIRST PERSON internal monologue ("I think...", "I wonder...", etc.)
- speak actions: DIRECT DIALOGUE only, first person ("Hello," "I need your help," etc.) - do NOT include narrative tags like "I say" or character name
- All other actions: THIRD PERSON with the character's FULL NAME as subject ("{char_placeholder} reaches out...", "{char_placeholder} walks to...")

IMPORTANT:
- ALWAYS use the character's FULL NAME in every third-person action description
- current_stance and current_clothing should maintain continuity with the provided values unless the actions explicitly change them

Return a JSON array of options."""

    @staticmethod
    def build_user_prompt(
        context: Dict[str, Any],
        num_escalation: int = None,
        num_neutral: int = None,
        num_deescalation: int = None
    ) -> str:
        """
        Build user prompt with full context.

        Args:
            context: Context dictionary from ActionGenerationContext.build()
            num_escalation: Number of escalating options (calculated externally if using draft system)
            num_neutral: Number of neutral options
            num_deescalation: Number of de-escalating options
            strong_escalation_mode: Whether strong escalation is required

        Returns:
            Formatted prompt string
        """
        # Extract mood guidance first (needed throughout prompt building)
        mood_guidance = context['mood_guidance']
        escalation_needed = mood_guidance['should_generate_escalation']
        escalation_weight = mood_guidance['escalation_weight']
        mood_category = mood_guidance.get('mood_category', 'neutral')

        # Use provided escalation requirements if available (from draft selection)
        # Otherwise calculate them here (legacy behavior)
        if num_escalation is None or num_neutral is None or num_deescalation is None:
            print('mood_guidance:', mood_guidance)
            print('escalation_weight:', escalation_weight)

            # Calculate how many escalation vs neutral vs de-escalation options
            total_options = 5

            if escalation_needed:
                # De-escalation: 20% chance for 1 de-escalation, 80% chance for STRONG escalation
                include_deescalation = random.random() < 0.2

                if include_deescalation:
                    # 20% case: Include 1 de-escalation option
                    num_deescalation = 1
                    # Escalation: 2-4 (randomized)
                    num_escalation = random.randint(2, 4)
                    # Neutral: make up the remainder
                    num_neutral = total_options - num_escalation - num_deescalation
                else:
                    # 80% case: STRONG ESCALATION MODE - no de-escalation, bold uninhibited actions
                    num_deescalation = 0
                    # More escalation options (2-4, all should be STRONG)
                    num_escalation = random.randint(2, 4)
                    # Neutral: make up the remainder
                    num_neutral = total_options - num_escalation
            else:
                num_escalation = 1
                num_deescalation = 1
                num_neutral = total_options - 2
        else:
            # Using pre-calculated values from draft selection
            escalation_needed = (num_escalation > 1) 

        total_options = num_escalation + num_neutral + num_deescalation
        prompt_parts = []

        # Character essentials
        prompt_parts.append(f"CHARACTER: {context['character_name']}")
        prompt_parts.append(f"Emotional state: {context['character_emotional_state']}")
        prompt_parts.append(f"Objectives: {context['character_motivations']}")

        # Current physical state (for continuity)
        current_stance = context.get('character_stance', 'standing')
        current_clothing = context.get('character_clothing', 'unchanged')
        prompt_parts.append(f"Current stance: {current_stance}")
        prompt_parts.append(f"Current clothing: {current_clothing}")

        # Immediate context (most recent 2-3 actions only)
        if context.get('working_memory'):
            memory_lines = context['working_memory'].split('\n')
            if memory_lines:
                recent_actions = memory_lines[:3]  # Only last 3 actions
                prompt_parts.append(f"\nRECENT CONTEXT:")
                prompt_parts.append('\n'.join(recent_actions))

        # Location and present characters (minimal)
        prompt_parts.append(f"\nLOCATION: {context['location_name']}")
        if context['visible_characters']:
            char_names = [char['name'] for char in context['visible_characters']]
            prompt_parts.append(f"PRESENT: {', '.join(char_names)}")

        # Visible items in location
        if context.get('visible_items'):
            prompt_parts.append(f"\nVISIBLE ITEMS:\n{context['visible_items']}")

        # Character's inventory
        if context.get('inventory'):
            prompt_parts.append(f"\nYOUR INVENTORY:\n{context['inventory']}")

        # Mood description
        if context.get('mood_description'):
            prompt_parts.append(f"\nMOOD: {context['mood_description']}")

        # Include selected draft summaries to expand
        if context.get('selected_draft_summaries'):
            prompt_parts.append(f"\n{'='*60}")
            prompt_parts.append(f"EXPAND THESE {total_options} ACTION IDEAS WITH NARRATIVE DETAIL")
            prompt_parts.append(f"{'='*60}\n")
            for i, summary in enumerate(context['selected_draft_summaries'], 1):
                prompt_parts.append(f"{i}. {summary}")
            prompt_parts.append(f"\nFor each idea, create a rich action sequence:")
            prompt_parts.append(f"- ALWAYS use '{context['character_name']}' as the subject in every action description")
            prompt_parts.append("- Write in third-person narrative prose (like a novel)")
            prompt_parts.append("- Add character's internal thoughts")
            prompt_parts.append("- Include dialogue if they speak")
            prompt_parts.append("- Describe physical actions with sensory detail")
            prompt_parts.append("- Set turn_duration appropriately (check draft for multi-turn actions)")
            prompt_parts.append(f"{'='*60}\n")
        else:
            prompt_parts.append(f"\nGenerate {total_options} distinctive action options.")
            prompt_parts.append(f"- ALWAYS use '{context['character_name']}' as the subject in every action description")
            prompt_parts.append("- Write in third-person narrative prose (like a novel)")

        prompt_parts.append("\nReturn JSON array as specified in system prompt.")

        return "\n".join(prompt_parts)


class ActionGenerator:
    """
    Generates action options for characters using LLMs with automatic provider fallback.

    PROVIDER FALLBACK SYSTEM:
    -------------------------
    All LLM calls in this class automatically use the ResilientActionGenerator
    fallback chain when llm_provider is a ResilientActionGenerator instance.

    The fallback chain handles:
    - Content policy violations (automatic retry with next provider)
    - API failures (automatic retry with next provider)
    - Provider-specific prompt adaptation
    - Graceful degradation to fallback options

    LLM CALLS WITH FALLBACK (2-STEP PROCESS):
    1. _generate_draft_options() - Generate 20 varied draft options + inline mood analysis
    2. generate_options() - Final detailed action generation from selected drafts

    All calls will automatically try providers in this order:
    - Anthropic Claude (primary)
    - OpenAI GPT (fallback)
    - AIML API (permissive fallback)
    - Together.ai (backup)
    - Local models (if configured)

    ERROR HANDLING:
    - AllProvidersFailedError: Caught and fallback options provided
    - Generic exceptions: Caught and fallback options provided
    - All errors logged with provider chain information
    """

    def __init__(self, llm_provider):
        """
        Initialize action generator.

        Args:
            llm_provider: LLM provider instance (should be ResilientActionGenerator
                         for automatic fallback, but can be any provider with a
                         generate() method)
        """
        self.llm_provider = llm_provider
        self.prompt_builder = ActionGenerationPrompt()

        # Log provider type for debugging
        provider_type = type(llm_provider).__name__
        logger.info(f"ActionGenerator initialized with provider: {provider_type}")
        if "Resilient" not in provider_type:
            logger.warning(
                f"ActionGenerator initialized with non-resilient provider: {provider_type}. "
                "Consider using ResilientActionGenerator for automatic fallback."
            )

    def _generate_draft_options(
        self,
        context: Dict[str, Any],
        num_drafts: int = 20
    ) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Generate draft action options with escalation scores AND inline mood analysis.
        Uses resilient provider fallback automatically.
        Retries up to 2 times on invalid JSON responses.

        This replaces the separate mood analysis LLM call by incorporating mood detection
        into the draft generation step.

        Args:
            context: Context dictionary from ActionGenerationContext.build()
            num_drafts: Number of draft options to generate

        Returns:
            Tuple of (draft_options_list, mood_guidance_dict)
        """
        # Extract key context for analysis
        immediate_context = ""
        character_last_turn = None
        others_actions_since = []

        if context.get('working_memory'):
            memory_lines = context['working_memory'].split('\n')
            if memory_lines:
                # Find the character's MOST RECENT turn (last occurrence, not first)
                character_last_turn_index = None
                for i, line in enumerate(memory_lines):
                    if context['character_name'] in line:
                        character_last_turn_index = i
                        character_last_turn = line

                # Get all actions from character's last turn onward
                if character_last_turn_index is not None:
                    # Include character's last turn AND everything after it
                    actions_from_last_turn = memory_lines[character_last_turn_index:]

                    # Use this as immediate context (all actions since character's last turn)
                    immediate_context = '\n'.join(actions_from_last_turn)

                    # Others' actions are everything AFTER the character's last turn
                    if character_last_turn_index < len(memory_lines) - 1:
                        others_actions_since = memory_lines[character_last_turn_index + 1:]
                else:
                    # Character hasn't acted yet in working memory, use recent context
                    immediate_context = '\n'.join(memory_lines[-5:])  # Last 5 turns

        # Build comprehensive prompt that does BOTH mood analysis AND draft generation
        draft_system_prompt = f"""You are generating action ideas for a character in a dark fantasy game.

Your task is TWO-FOLD:
1. Analyze the emotional tone/atmosphere from recent actions
2. Generate {num_drafts} diverse action ideas that directly proceed from the recent actions and give each action idea an escalation score

For MOOD ANALYSIS, consider:
- Emotional tone of recent events (calm, tense, romantic, hostile, etc.)
- Escalation trajectory (de-escalating, stable, escalating)

For ACTION IDEAS, each turn represents ~30 seconds of in-game time. Actions that take longer should specify turn_duration > 1.

IMPORTANT: In the recent events, look for actions with turn duration notation like "(3T, 2 remaining)" which indicates:
- The action takes 3 turns total
- 2 turns remain to complete it
- The character is in the middle of performing this action
- Ensure that the action ideas directly respond to the most recent events, including any speech or actions directed at the character

When a character is continuing a multi-turn action, REDUCE the turn_duration for continuation options by the number of turns already spent.

Return a JSON object with TWO sections:
{{
  "mood_analysis": {{
    "emotional_tone": "brief description of current emotional atmosphere",
    "mood_category": "a single descriptive word capturing the dominant mood (e.g., neutral, tense, romantic, hostile, playful, melancholic, anxious, passionate, suspicious, intimate, aggressive, fearful, joyful, etc.)",
    "should_escalate": true/false,
    "escalation_weight": 0.0-1.0
  }},
  "draft_options": [
    {{
      "summary": "1-2 sentence action description",
      "escalation_score": -10 to +10,
      "turn_duration": 1-5 (estimated turns to complete; if continuing an action, use the remaining_duration value)
    }},
    ...{num_drafts} total...
  ]
}}"""

        # Build context-aware user prompt
        continuing_action_note = ""
        multi_turn_instructions = ""
        if character_last_turn:
            continuing_action_note = f"\n\nCHARACTER'S MOST RECENT ACTION:\n{character_last_turn}"

            # Check if the last action has turn duration info
            if "T" in character_last_turn and "remaining" in character_last_turn:
                continuing_action_note += "\n\n⚠️ IMPORTANT: This character is in the middle of a multi-turn action!"
                multi_turn_instructions = """
MULTI-TURN ACTION HANDLING:
- Generate several options (30-40% of total) that CONTINUE the current multi-turn action
- For continuation options, use the "remaining" number as the turn_duration
- Also generate some options that ABANDON the current action to do something else
- Example: If action shows "(4T, 3 remaining)", continuation options should have turn_duration: 3"""

        draft_user_prompt = f"""CHARACTER: {context['character_name']}
Emotional state: {context['character_emotional_state']}
Short-term objectives: {context['character_motivations']}

LOCATION: {context['location_name']}

RECENT EVENTS (all actions since character's last turn, including their last turn):
{immediate_context if immediate_context else 'Scene is just beginning'}{continuing_action_note}

OTHER CHARACTERS PRESENT:
{', '.join([c['name'] for c in context['visible_characters']]) if context['visible_characters'] else 'None'}
{multi_turn_instructions}

TASK:
1. Analyze the emotional tone/mood from the recent events
2. Generate {num_drafts} varied action ideas:
   - Range from strong de-escalation (-10) to strong escalation (+10)
   - Include mix across full spectrum but only action that could be performed 30 seconds after the most recent events
   - Consider character's objectives and emotional state
   - Pay attention to turn_duration notation in recent events (XT, Y remaining)
   - Set appropriate turn_duration for each action (1 turn = ~30 seconds)
   - If character is mid-action, include continuation options with correct remaining duration
   - If a speech or an action has been directed at the character in the recent events, ensure that the options responds to it, including deciding to ignore it

Return the JSON object as specified."""

        #print ("draft_user_prompt", draft_user_prompt)
        logger.info(f"Generating {num_drafts} draft options with inline mood analysis...")
        print(f"\n🎲 Generating {num_drafts} draft options with inline mood analysis (2-in-1 LLM call)...")


        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    logger.info(f"Retrying draft generation (attempt {attempt + 1}/{max_retries + 1})...")
                    print(f"🔄 Retrying draft generation (attempt {attempt + 1}/{max_retries + 1})...")

                # This automatically uses ResilientActionGenerator's fallback chain
                # if llm_provider is a ResilientActionGenerator (which it should be)
                response = self.llm_provider.generate(
                    system_prompt=draft_system_prompt,
                    user_prompt=draft_user_prompt,
                    temperature=0.8,  # High temperature for variety, but not too random
                    max_tokens=2000  # Increased for mood analysis + drafts
                )

                # Log the response for debugging
                logger.info(f"Draft generation response length: {len(response)} chars")
                logger.debug(f"Draft generation response: {response[:500]}...")
                print(f"📄 Draft response length: {len(response)} chars")
                #print(f"📄 Draft response: {response}")

                # Check for empty response
                if not response or not response.strip():
                    raise ValueError("Empty response from LLM")

                # Parse response with multiple strategies
                import re
                json_str = response.strip()

                # Strategy 1: Extract from markdown code blocks
                if "```json" in json_str:
                    match = re.search(r'```json\s*(\{.*?\})\s*```', json_str, re.DOTALL)
                    if match:
                        json_str = match.group(1)
                    else:
                        # Try simpler extraction
                        json_str = json_str.split("```json")[1].split("```")[0].strip()
                elif "```" in json_str:
                    match = re.search(r'```\s*(\{.*?\})\s*```', json_str, re.DOTALL)
                    if match:
                        json_str = match.group(1)
                    else:
                        json_str = json_str.split("```")[1].split("```")[0].strip()

                # Strategy 2: Find JSON object anywhere in response
                if not json_str.startswith('{'):
                    match = re.search(r'\{.*\}', json_str, re.DOTALL)
                    if match:
                        json_str = match.group(0)
                    else:
                        raise ValueError("No JSON object found in response")

                # Clean up JSON
                json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)  # Remove trailing commas

                # Log what we're trying to parse
                logger.debug(f"Attempting to parse JSON: {json_str[:200]}...")
                print(f"🔍 Parsing JSON object ({len(json_str)} chars)...")

                result = json.loads(json_str)
                #print("result:", result)

                # Validate structure
                if not isinstance(result, dict):
                    raise ValueError(f"Expected dict, got {type(result)}")
                if 'mood_analysis' not in result or 'draft_options' not in result:
                    raise ValueError("Missing required sections: mood_analysis or draft_options")

                mood_analysis = result['mood_analysis']
                drafts = result['draft_options']

                if not isinstance(drafts, list) or len(drafts) == 0:
                    raise ValueError("draft_options must be non-empty list")

                # Convert mood_analysis to mood_guidance format
                mood_guidance = {
                    'should_generate_escalation': mood_analysis.get('should_escalate', False),
                    'escalation_weight': float(mood_analysis.get('escalation_weight', 0.5)),
                    'deescalation_required': True,  # Always provide de-escalation option
                    'mood_category': mood_analysis.get('mood_category', 'neutral')
                }

                logger.info(f"✓ Successfully generated {len(drafts)} draft options with mood analysis")
                logger.info(f"  Mood: {mood_guidance['mood_category']}, escalation_weight={mood_guidance['escalation_weight']:.2f}")
                print(f"✓ Parsed {len(drafts)} draft options successfully")
                print(f"🎭 Mood detected: {mood_guidance['mood_category']} (escalation_weight={mood_guidance['escalation_weight']:.2f})")
                print(f"🎭 Emotional tone: {mood_analysis.get('emotional_tone', 'N/A')}")

                return drafts, mood_guidance

            except json.JSONDecodeError as e:
                logger.warning(f"JSON decode error in draft generation (attempt {attempt + 1}/{max_retries + 1}): {e}")
                logger.warning(f"Response was: {response[:500]}...")
                logger.warning(f"JSON string attempted: {json_str[:500] if 'json_str' in locals() else 'N/A'}...")
                print(f"⚠️  JSON decode error in draft generation: {str(e)[:100]}")
                print(f"⚠️  Response preview: {response[:200]}...")
                if attempt < max_retries:
                    continue  # Retry
                else:
                    # Final attempt failed, fall through to fallback
                    print(f"⚠️  All retry attempts exhausted. Using fallback drafts.")
                    break

            except AllProvidersFailedError as e:
                logger.error(f"All providers failed for draft generation: {e}", exc_info=True)
                print(f"⚠️  All providers failed for draft generation. Using fallback drafts.")
                # Don't retry on provider failures - fallback immediately
                break

            except ValueError as e:
                logger.warning(f"Value error in draft generation (attempt {attempt + 1}/{max_retries + 1}): {e}")
                logger.warning(f"Response was: {response[:500] if 'response' in locals() else 'N/A'}...")
                print(f"⚠️  Value error in draft generation: {str(e)[:100]}")
                print(f"⚠️  Response preview: {response[:200] if 'response' in locals() else 'N/A'}...")
                if attempt < max_retries:
                    continue  # Retry
                else:
                    # Final attempt failed, fall through to fallback
                    print(f"⚠️  All retry attempts exhausted. Using fallback drafts.")
                    break

            except Exception as e:
                logger.error(f"Error generating draft options (attempt {attempt + 1}/{max_retries + 1}): {e}", exc_info=True)
                logger.error(f"Response was: {response[:500] if 'response' in locals() else 'N/A'}...")
                print(f"⚠️  Error in draft generation: {str(e)[:100]}")
                print(f"⚠️  Response preview: {response[:200] if 'response' in locals() else 'N/A'}...")
                if attempt < max_retries:
                    continue  # Retry
                else:
                    # Final attempt failed, fall through to fallback
                    break

        # All retries exhausted or provider failed - return fallback drafts
        logger.warning("Using fallback drafts after retries exhausted")
        fallback_mood_guidance = {
            'should_generate_escalation': False,
            'escalation_weight': 0.5,
            'deescalation_required': True,
            'mood_category': 'neutral'
        }
        fallback_drafts = [
            {"summary": "Wait and observe the situation", "escalation_score": 0, "turn_duration": 1},
            {"summary": "Speak calmly to de-escalate", "escalation_score": -5, "turn_duration": 1},
            {"summary": "Take a cautious neutral action", "escalation_score": -1, "turn_duration": 1},
            {"summary": "Take a bold forward action", "escalation_score": 5, "turn_duration": 1},
            {"summary": "Escalate the situation decisively", "escalation_score": 8, "turn_duration": 1}
        ]
        return fallback_drafts, fallback_mood_guidance

    def _select_drafts_by_requirements(
        self,
        drafts: List[Dict[str, Any]],
        num_escalation: int,
        num_neutral: int,
        num_deescalation: int
    ) -> List[Dict[str, Any]]:
        """
        Select draft options based on escalation requirements.
        Ensures no duplicates are selected.

        Args:
            drafts: List of draft options with escalation_score
            num_escalation: Number of escalating options needed
            num_neutral: Number of neutral options needed
            num_deescalation: Number of de-escalating options needed

        Returns:
            Selected subset of drafts (no duplicates)
        """
        # Sort by escalation score
        sorted_drafts = sorted(drafts, key=lambda d: d.get('escalation_score', 0))

        # Categorize drafts
        deescalating = [d for d in sorted_drafts if d.get('escalation_score', 0) < -2]
        neutral = [d for d in sorted_drafts if -2 <= d.get('escalation_score', 0) <= 2]
        escalating = [d for d in sorted_drafts if d.get('escalation_score', 0) > 2]

        selected = []
        selected_ids = set()  # Track IDs to prevent duplicates

        def add_unique(draft_list, count):
            """Add drafts ensuring no duplicates."""
            available = [d for d in draft_list if id(d) not in selected_ids]
            to_select = min(count, len(available))
            if to_select > 0:
                selected_drafts = random.sample(available, to_select)
                for draft in selected_drafts:
                    selected.append(draft)
                    selected_ids.add(id(draft))
                return to_select
            return 0

        def add_weighted_unique(draft_list, count):
            """Add drafts with weighted selection (bias to higher scores) ensuring no duplicates."""
            available = [d for d in draft_list if id(d) not in selected_ids]
            to_select = min(count, len(available))
            if to_select > 0:
                # Use weighted random selection without replacement
                weights = [d.get('escalation_score', 0) for d in available]
                selected_drafts = []
                available_copy = available.copy()
                weights_copy = weights.copy()

                for _ in range(to_select):
                    if not available_copy:
                        break
                    # Normalize weights to be positive for random.choices
                    min_weight = min(weights_copy)
                    if min_weight < 0:
                        normalized_weights = [w - min_weight + 1 for w in weights_copy]
                    else:
                        normalized_weights = [w + 1 for w in weights_copy]  # +1 to avoid zero weights

                    chosen = random.choices(available_copy, weights=normalized_weights, k=1)[0]
                    selected_drafts.append(chosen)

                    # Remove chosen from available pool
                    idx = available_copy.index(chosen)
                    available_copy.pop(idx)
                    weights_copy.pop(idx)

                for draft in selected_drafts:
                    selected.append(draft)
                    selected_ids.add(id(draft))
                return len(selected_drafts)
            return 0

        # Select de-escalating (random from bottom scores)
        if num_deescalation > 0:
            add_unique(deescalating, num_deescalation)

        # Select escalating (random from top scores, with bias towards highest in strong mode)
        if num_escalation > 0:
            add_unique(escalating, num_escalation)

        # Select neutral (random from middle scores)
        if num_neutral > 0:
            add_unique(neutral, num_neutral)

        # If we don't have enough, pad with random drafts from any category
        target_count = num_escalation + num_neutral + num_deescalation
        while len(selected) < target_count:
            remaining = [d for d in drafts if id(d) not in selected_ids]
            if remaining:
                chosen = random.choice(remaining)
                selected.append(chosen)
                selected_ids.add(id(chosen))
            else:
                break

        # Final duplicate check using summary text as key (just in case)
        seen_summaries = set()
        deduplicated = []
        for draft in selected:
            summary = draft.get('summary', '')
            if summary not in seen_summaries:
                seen_summaries.add(summary)
                deduplicated.append(draft)
            else:
                logger.warning(f"Removed duplicate draft: {summary[:50]}...")

        return deduplicated

    def generate_options(
        self,
        db_session,
        character: Dict[str, Any],
        game_state_id: UUID,
        location: Dict[str, Any],
        visible_characters: List[Dict[str, Any]],
        current_turn: int,
        num_options: int = 5
    ) -> GeneratedActionOptions:
        """
        Generate action options for a character's turn.

        Uses automatic provider fallback for content policy handling:
        1. Generates 20 draft options with escalation scores
        2. Selects best subset based on mood requirements
        3. Generates detailed options from selected drafts

        All LLM calls use ResilientActionGenerator for automatic fallback
        through the provider chain if content is refused.

        Args:
            db_session: Database session
            character: Character profile dictionary
            game_state_id: Game state UUID
            location: Location dictionary
            visible_characters: List of character dictionaries
            current_turn: Current turn number
            num_options: Number of options to generate

        Returns:
            GeneratedActionOptions containing all generated options
        """
        print("ActionGenerator generate_options (with resilient fallback)")
        logger.info(
            f"Generating {num_options} action options for {character.get('name')} "
            f"at turn {current_turn} (using resilient provider fallback)"
        )

        # Build context
        context_builder = ActionGenerationContext(
            db_session,
            character,
            game_state_id,
            location,
            visible_characters,
            current_turn,
            llm_provider=self.llm_provider
        )
        context = context_builder.build(model=self.llm_provider.model_name)

        print('Initial mood guidance (from DB):', context['mood_guidance'])

        # STAGE 1: Generate draft options with escalation scores AND inline mood analysis (2-in-1)
        draft_options, mood_guidance = self._generate_draft_options(context, num_drafts=20)

        # Override context mood_guidance with LLM-analyzed mood
        context['mood_guidance'] = mood_guidance

        # Print draft options for monitoring
        #print(f"\n📋 Generated {len(draft_options)} draft options:")
        for i, draft in enumerate(draft_options, 1):
            score = draft.get('escalation_score', 0)
            duration = draft.get('turn_duration', 1)
            emoji = "🔥" if score >= 6 else "⚡" if score > 2 else "➡️" if score >= -2 else "🕊️" if score > -6 else "❄️"
            duration_str = f" ({duration}T)" if duration > 1 else ""
            print(f"  {i:2d}. [{score:+3d}] {emoji} {draft.get('summary', 'No summary')}{duration_str}")
        escalation_needed = mood_guidance['should_generate_escalation']
        escalation_weight = mood_guidance['escalation_weight']

        # Calculate requirements (from build_user_prompt logic)
        total_options = 5

        if escalation_needed:
            include_deescalation = random.random() < 0.2

            if include_deescalation:
                num_deescalation = 1
                num_escalation = random.randint(2, 4)
                num_neutral = total_options - num_escalation - num_deescalation
            else:
                num_deescalation = 0
                num_escalation = random.randint(3, 4)
                num_neutral = total_options - num_escalation

        else:
            num_escalation = 1
            num_deescalation = 1
            num_neutral = total_options - 2

        # STAGE 2: Select subset based on requirements
        selected_drafts = self._select_drafts_by_requirements(
            draft_options,
            num_escalation,
            num_neutral,
            num_deescalation
        )

        # Print selected drafts
        print(f"\n✅ Selected {len(selected_drafts)} drafts for final generation:")
        print(f"   Escalating: {num_escalation}, Neutral: {num_neutral}, De-escalating: {num_deescalation}")

        for i, draft in enumerate(selected_drafts, 1):
            score = draft.get('escalation_score', 0)
            emoji = "🔥" if score >= 6 else "⚡" if score > 2 else "➡️" if score >= -2 else "🕊️"
            print(f"  {i}. [{score:+3d}] {emoji} {draft.get('summary', 'No summary')}")

        # Add selected drafts to context for final generation (include turn_duration info)
        draft_summaries = []
        for d in selected_drafts:
            summary = d.get('summary', 'No summary')
            turn_duration = d.get('turn_duration', 1)
            if turn_duration > 1:
                summary += f" [Duration: {turn_duration} turns]"
            draft_summaries.append(summary)
        context['selected_draft_summaries'] = draft_summaries

        # Build prompts (pass pre-calculated escalation requirements and character name)
        system_prompt = self.prompt_builder.build_system_prompt(
            model=self.llm_provider.model_name,
            character_name=character.get('name')
        )
        user_prompt = self.prompt_builder.build_user_prompt(
            context,
            num_escalation=num_escalation,
            num_neutral=num_neutral,
            num_deescalation=num_deescalation
        )

        logger.debug(f"System prompt: {system_prompt[:200]}...")
        logger.debug(f"User prompt: {user_prompt[:500]}...")

        print(f"\n📝 User prompt length: {len(user_prompt)} chars")
        print(f"📝 System prompt length: {len(system_prompt)} chars")
        print("user_prompt", user_prompt)

        # Call LLM
        try:
            # Check if provider is ResilientActionGenerator (has built-in action generation)
            if hasattr(self.llm_provider, 'generate_action_options'):
                # Use resilient action generation with built-in parsing and fallback
                logger.info("Using ResilientActionGenerator.generate_action_options()")
                print("Using ResilientActionGenerator.generate_action_options()")
                options_dicts = self.llm_provider.generate_action_options(
                    character=character,
                    context=context,
                    num_options=num_options
                )

                # Convert to ActionOption objects
                options = []
                for idx, opt in enumerate(options_dicts, start=1):
                    # Build actions from the dict
                    actions = []

                    # NEW FORMAT: Check if there's an 'actions' array (new structured format)
                    if opt.get('actions') and isinstance(opt['actions'], list):
                        for action_dict in opt['actions']:
                            action_type_str = action_dict.get('type', 'interact')
                            # Map string to ActionType enum
                            action_type_map = {
                                'think': ActionType.THINK,
                                'speak': ActionType.SPEAK,
                                'interact': ActionType.INTERACT,
                                'move': ActionType.MOVE,
                                'attack': ActionType.ATTACK,
                                'steal': ActionType.STEAL,
                                'use_item': ActionType.USE_ITEM,
                                'emote': ActionType.EMOTE,
                                'examine': ActionType.EXAMINE,
                                'wait': ActionType.WAIT,
                                'hide': ActionType.HIDE
                            }
                            action_type = action_type_map.get(action_type_str, ActionType.INTERACT)

                            # Handle target field (can be character name or object)
                            target = action_dict.get('target')
                            target_character_id = None
                            target_object = None

                            if target:
                                # For now, assume targets are character names (can be enhanced later)
                                # The name will be resolved to character_id during execution
                                target_object = target  # Store as object name for now

                            actions.append(SingleAction(
                                action_type=action_type,
                                description=action_dict.get('description', ''),
                                is_private=action_dict.get('is_private', False),
                                target_character_id=target_character_id,
                                target_object=target_object
                            ))

                    # OLD FORMAT: Fallback to old field names for backwards compatibility
                    else:
                        if opt.get('private_thought'):
                            actions.append(SingleAction(
                                action_type=ActionType.THINK,
                                description=opt['private_thought'],
                                is_private=True
                            ))
                        if opt.get('dialogue') or opt.get('speech'):
                            actions.append(SingleAction(
                                action_type=ActionType.SPEAK,
                                description=opt.get('dialogue') or opt.get('speech'),
                                is_private=False
                            ))
                        if opt.get('action'):
                            actions.append(SingleAction(
                                action_type=ActionType.INTERACT,
                                description=opt['action'],
                                is_private=False
                            ))

                    if actions:
                        sequence = ActionSequence(
                            actions=actions,
                            summary=opt.get('summary', f'Option {idx}'),
                            escalates_mood=opt.get('escalates_mood', False),
                            deescalates_mood=opt.get('deescalates_mood', False),
                            emotional_tone=opt.get('emotional_tone', 'neutral'),
                            estimated_mood_impact=opt.get('estimated_mood_impact', {}),
                            turn_duration=opt.get('turn_duration', 1),
                            current_stance=opt.get('current_stance', 'standing'),
                            current_clothing=opt.get('current_clothing', 'unchanged'),
                            current_emotional_state=opt.get('current_emotional_state', 'neutral')
                        )
                        options.append(ActionOption(
                            option_id=idx,
                            sequence=sequence,
                            selection_weight=1.0
                        ))
            else:
                # Use generic generate method (with resilient fallback if provider supports it)
                # Retry up to 2 times on JSON parsing errors
                logger.info("Using LLM provider.generate() with resilient fallback")
                print("🔄 Using LLM provider.generate() (automatic fallback enabled)")

                max_retries = 2
                options = None
                for attempt in range(max_retries + 1):
                    try:
                        if attempt > 0:
                            logger.info(f"Retrying action generation (attempt {attempt + 1}/{max_retries + 1})...")
                            print(f"🔄 Retrying action generation (attempt {attempt + 1}/{max_retries + 1})...")

                        response = self.llm_provider.generate(
                            system_prompt=system_prompt,
                            user_prompt=user_prompt,
                            temperature=0.8,  # More creative for diverse options
                            max_tokens=2048
                        )

                        logger.debug(f"LLM response: {response[:500]}...")

                        # Parse response into action sequences
                        options = self._parse_response(response, context)
                        print("action-option response:", response)

                        # Success!
                        break

                    except (json.JSONDecodeError, ValueError) as e:
                        error_type = "JSON decode" if isinstance(e, json.JSONDecodeError) else "parsing"
                        logger.warning(f"{error_type} error in action generation (attempt {attempt + 1}/{max_retries + 1}): {e}")
                        print(f"⚠️  {error_type} error in action generation: {str(e)[:100]}")
                        if attempt < max_retries:
                            continue  # Retry
                        else:
                            # Final attempt failed, re-raise to be caught by outer exception handler
                            raise

                if options is None:
                    # This shouldn't happen, but just in case
                    raise ValueError("Failed to generate options after retries")
                
            

            # Create result
            result = GeneratedActionOptions(
                character_id=str(character.get('character_id')),
                turn_number=current_turn,
                options=options,
                mood_category=context['mood_guidance']['mood_category'],  # String from LLM mood analysis
                generation_context=context
            )

            logger.info(
                f"Successfully generated {len(options)} options for {character.get('name')}"
            )

            return result

        except AllProvidersFailedError as e:
            logger.error(f"All providers failed for action generation: {e}", exc_info=True)
            print(f"⚠️  All providers failed. Using fallback action options.")
            print(f"    Attempted providers: {', '.join(e.attempted_providers) if hasattr(e, 'attempted_providers') else 'unknown'}")
            # Return fallback options
            return self._create_fallback_options(
                character,
                location,
                current_turn,
                context
            )

        except Exception as e:
            logger.error(f"Error generating action options: {e}", exc_info=True)
            print(f"⚠️  Error in action generation: {str(e)[:100]}")
            print("    Falling back to default action options.")
            # Return fallback options
            return self._create_fallback_options(
                character,
                location,
                current_turn,
                context
            )

    def _parse_response(
        self,
        response: str,
        context: Dict[str, Any]
    ) -> List[ActionOption]:
        """
        Parse LLM response into ActionOption objects.

        Args:
            response: Raw LLM response (should be JSON array)
            context: Generation context

        Returns:
            List of ActionOption objects
        """
        try:
            # Extract JSON from response (may have markdown code blocks)
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()

            # Clean up common JSON issues
            # Remove trailing commas before } or ]
            import re
            json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)

            # Try to fix incomplete JSON
            # If it ends mid-object, try to close it
            if json_str.count('{') > json_str.count('}'):
                missing_closes = json_str.count('{') - json_str.count('}')
                json_str += '}' * missing_closes
            if json_str.count('[') > json_str.count(']'):
                missing_closes = json_str.count('[') - json_str.count(']')
                json_str += ']' * missing_closes

            parsed = json.loads(json_str)

            options = []
            for idx, option_data in enumerate(parsed, start=1):
                # Parse actions
                actions = []
                actions_data = option_data.get('actions', [])

                # Handle case where actions might not be a list
                if not isinstance(actions_data, list):
                    logger.warning(f"Actions is not a list for option {idx}, skipping")
                    continue

                for action_data in actions_data:
                    if not isinstance(action_data, dict):
                        logger.warning(f"Action data is not a dict, skipping: {action_data}")
                        continue

                    try:
                        action = SingleAction(
                            action_type=ActionType(action_data.get('type', 'wait')),
                            description=action_data.get('description', 'No description'),
                            is_private=action_data.get('is_private', False),
                            target_character_id=action_data.get('target'),
                            metadata=action_data
                        )
                        actions.append(action)
                    except (KeyError, ValueError) as e:
                        logger.warning(f"Error parsing action: {e}, skipping")
                        continue

                if not actions:
                    # Skip options with no valid actions
                    continue

                # Create sequence
                sequence = ActionSequence(
                    actions=actions,
                    summary=option_data.get('summary', f'Option {idx}'),
                    escalates_mood=option_data.get('escalates_mood', False),
                    deescalates_mood=option_data.get('deescalates_mood', False),
                    emotional_tone=option_data.get('emotional_tone', 'neutral'),
                    estimated_mood_impact=option_data.get('estimated_mood_impact', {}),
                    turn_duration=option_data.get('turn_duration', 1),
                    current_stance=option_data.get('current_stance', 'standing'),
                    current_clothing=option_data.get('current_clothing', 'unchanged')
                )

                # Create option
                option = ActionOption(
                    option_id=idx,
                    sequence=sequence,
                    selection_weight=1.0
                )

                options.append(option)

            if options:
                return options
            else:
                # No valid options parsed, raise to trigger fallback
                raise ValueError("No valid action options parsed from response")

        except json.JSONDecodeError as e:
            logger.error(f"Error parsing LLM response: {e}")
            logger.error(f"Response snippet: {response[:500]}...")
            logger.error(f"JSON string attempted: {json_str[:500] if 'json_str' in locals() else 'N/A'}...")
            raise
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}", exc_info=True)
            logger.debug(f"Response was: {response[:1000]}...")
            raise

    def _create_fallback_options(
        self,
        character: Dict[str, Any],
        location: Dict[str, Any],
        current_turn: int,
        context: Dict[str, Any]
    ) -> GeneratedActionOptions:
        """Create fallback options when generation fails."""
        logger.warning("Using fallback action options")

        options = [
            ActionOption(
                option_id=1,
                sequence=ActionSequence(
                    actions=[SingleAction(ActionType.WAIT, "Wait and observe", False)],
                    summary="Wait and observe",
                    escalates_mood=False,
                    deescalates_mood=False,
                    emotional_tone="cautious"
                )
            ),
            ActionOption(
                option_id=2,
                sequence=ActionSequence(
                    actions=[SingleAction(ActionType.SPEAK, "Speak calmly", False)],
                    summary="Speak calmly",
                    escalates_mood=False,
                    deescalates_mood=True,
                    emotional_tone="friendly"
                )
            )
        ]

        return GeneratedActionOptions(
            character_id=str(character.get('character_id')),
            turn_number=current_turn,
            options=options,
            mood_category='neutral',  # Fallback mood string
            generation_context=context
        )


class ActionSelector:
    """
    Handles selection of action options (AI random selection or player choice).
    """

    @staticmethod
    def random_select_for_ai(generated_options: GeneratedActionOptions) -> ActionOption:
        """
        Randomly select an action option for an AI character.

        Uses selection weights to bias towards certain options.

        Args:
            generated_options: Generated action options

        Returns:
            Selected action option
        """
        options = generated_options.options
        weights = [opt.selection_weight for opt in options]

        selected = random.choices(options, weights=weights, k=1)[0]

        logger.info(
            f"AI selected option {selected.option_id}: {selected.sequence.summary} "
            f"(tone: {selected.sequence.emotional_tone})"
        )

        return selected

    @staticmethod
    def player_select(
        generated_options: GeneratedActionOptions,
        choice: int
    ) -> Optional[ActionOption]:
        """
        Handle player selection of an action option.

        Args:
            generated_options: Generated action options
            choice: Option ID chosen by player (1-based)

        Returns:
            Selected action option or None if invalid choice
        """
        selected = generated_options.get_option_by_id(choice)

        if selected:
            logger.info(
                f"Player selected option {selected.option_id}: {selected.sequence.summary}"
            )
        else:
            logger.warning(f"Invalid player choice: {choice}")

        return selected
