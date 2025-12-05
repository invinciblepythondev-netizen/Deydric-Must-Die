"""
Action Generation Service

Generates action options for characters using LLMs with:
- Multi-action sequences (think → speak → act)
- Mood awareness and escalation/de-escalation
- Context-appropriate diversity
- Proper public/private action tracking
"""

import logging
import json
import random
from typing import List, Dict, Any, Optional
from uuid import UUID

from models.action_sequence import (
    ActionSequence, ActionOption, GeneratedActionOptions,
    SingleAction, ActionType, MoodCategory, create_simple_action
)
from models.scene_mood import SceneMood
from models.game_time import GameTime
from services.context_manager import build_character_context, ContextPriority

logger = logging.getLogger(__name__)


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
        current_turn: int
    ):
        self.db_session = db_session
        self.character = character
        self.game_state_id = game_state_id
        self.location = location
        self.visible_characters = visible_characters
        self.current_turn = current_turn

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

        # Mood
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
                'deescalation_required': True,
                'mood_category': 'neutral'
            }

        # Character state
        context['character_name'] = self.character.get('name')
        context['character_emotional_state'] = self.character.get('current_emotional_state')
        context['character_motivations'] = self.character.get('motivations_short_term')

        # Visible characters (basic attributes only)
        context['visible_characters'] = []
        for char in self.visible_characters:
            context['visible_characters'].append({
                'name': char.get('name'),
                'appearance': char.get('physical_appearance'),
                'stance': char.get('current_stance'),
                'clothing': char.get('current_clothing')
            })

        # TODO: Add relationships, working memory, wounds, inventory
        # These should come from the database via stored procedures

        return context


class ActionGenerationPrompt:
    """
    Builds prompts for action generation with mood awareness.
    """

    @staticmethod
    def build_system_prompt() -> str:
        """Build system prompt for action generation."""
        return """You are an expert at generating character action options for a dark fantasy text adventure game.

Your task is to generate distinctive action options for a character's turn. Each option should be a SEQUENCE of actions that execute in order.

Action types available:
- think: Private thought (only the character knows)
- speak: Public dialogue (others hear)
- emote: Body language/gesture (others see)
- interact: Interact with object/character
- examine: Look at something closely
- move: Change location
- attack: Combat action
- steal: Take something covertly
- use_item: Use inventory item
- wait: Do nothing/observe
- hide: Attempt stealth

IMPORTANT RULES:
1. Generate 4-6 distinctive options covering different emotional approaches
2. Each option can contain MULTIPLE actions in sequence (think → speak → act → think → steal)
3. Always include at least ONE option that de-escalates the mood/tension
4. If the mood is escalating, include more options that escalate further
5. Show internal thoughts (think actions) to reveal character psychology
6. Mix public and private actions appropriately

Format each option as JSON:
{
  "summary": "Brief description of this approach",
  "emotional_tone": "cunning|aggressive|friendly|cautious|romantic|etc",
  "escalates_mood": true/false,
  "deescalates_mood": true/false,
  "estimated_mood_impact": {"tension": +/-X, "hostility": +/-X, "romance": +/-X},
  "actions": [
    {"type": "think", "description": "...", "is_private": true},
    {"type": "speak", "description": "...", "is_private": false},
    {"type": "interact", "description": "...", "is_private": false, "target": "character_name"}
  ]
}

Return a JSON array of options."""

    @staticmethod
    def build_user_prompt(context: Dict[str, Any]) -> str:
        """
        Build user prompt with full context.

        Args:
            context: Context dictionary from ActionGenerationContext.build()

        Returns:
            Formatted prompt string
        """
        mood_guidance = context['mood_guidance']
        escalation_needed = mood_guidance['should_generate_escalation']
        escalation_weight = mood_guidance['escalation_weight']

        # Calculate how many escalation vs neutral vs de-escalation options
        total_options = 5
        if escalation_needed:
            # High tension = more escalation options
            num_escalation = int(total_options * escalation_weight)  # 2-4
            num_deescalation = 1  # Always at least one
            num_neutral = total_options - num_escalation - num_deescalation
        else:
            num_escalation = 1
            num_deescalation = 1
            num_neutral = total_options - 2

        prompt_parts = []

        # Character identity (relevant attributes only - handled by situational awareness)
        prompt_parts.append(f"CHARACTER: {context['character_name']}")
        prompt_parts.append(f"Emotional state: {context['character_emotional_state']}")
        prompt_parts.append(f"Current objectives: {context['character_motivations']}")

        # Time and location
        prompt_parts.append(f"\nTIME: {context['time_of_day']}")
        prompt_parts.append(f"{context['lighting_description']}")
        prompt_parts.append(f"\nLOCATION: {context['location_name']}")
        prompt_parts.append(f"{context['location_description']}")

        # Mood
        prompt_parts.append(f"\nMOOD: {context['mood_description']}")

        # Other characters present
        if context['visible_characters']:
            prompt_parts.append("\nPRESENT CHARACTERS:")
            for char in context['visible_characters']:
                prompt_parts.append(
                    f"- {char['name']}: {char['appearance']}. "
                    f"Currently {char['stance']}. Wearing {char['clothing']}."
                )
        else:
            prompt_parts.append("\nNo other characters present.")

        # TODO: Add relationships, working memory, wounds, inventory

        # Generation instructions based on mood
        prompt_parts.append(f"\n--- GENERATE {total_options} DISTINCTIVE ACTION OPTIONS ---")

        if escalation_needed:
            prompt_parts.append(
                f"\nThe situation is ESCALATING. Generate {num_escalation} options that "
                f"escalate the mood further, {num_neutral} neutral options, and "
                f"{num_deescalation} option(s) that de-escalate."
            )
        else:
            prompt_parts.append(
                f"\nGenerate {num_escalation} option(s) that could escalate, "
                f"{num_neutral} neutral options, and {num_deescalation} "
                f"option(s) that de-escalate."
            )

        prompt_parts.append(
            "\nMake each option DISTINCTIVE - cover different emotional approaches, "
            "objectives, and interaction styles. Remember to include internal thoughts "
            "(think actions) to show character psychology."
        )

        prompt_parts.append("\nReturn a JSON array of options as specified in the system prompt.")

        return "\n".join(prompt_parts)


class ActionGenerator:
    """
    Generates action options for characters using LLMs.
    """

    def __init__(self, llm_provider):
        """
        Initialize action generator.

        Args:
            llm_provider: LLM provider instance (Claude, OpenAI, etc.)
        """
        self.llm_provider = llm_provider
        self.prompt_builder = ActionGenerationPrompt()

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
        logger.info(
            f"Generating {num_options} action options for {character.get('name')} "
            f"at turn {current_turn}"
        )

        # Build context
        context_builder = ActionGenerationContext(
            db_session,
            character,
            game_state_id,
            location,
            visible_characters,
            current_turn
        )
        context = context_builder.build(model=self.llm_provider.model_name)

        # Build prompts
        system_prompt = self.prompt_builder.build_system_prompt()
        user_prompt = self.prompt_builder.build_user_prompt(context)

        logger.debug(f"System prompt: {system_prompt[:200]}...")
        logger.debug(f"User prompt: {user_prompt[:500]}...")

        # Call LLM
        try:
            response = self.llm_provider.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.8,  # More creative for diverse options
                max_tokens=2048
            )

            logger.debug(f"LLM response: {response[:500]}...")

            # Parse response into action sequences
            options = self._parse_response(response, context)

            # Validate we have required de-escalation option
            deescalation_options = [opt for opt in options if opt.sequence.deescalates_mood]
            if not deescalation_options:
                logger.warning("No de-escalation option generated, adding fallback")
                options.append(self._create_fallback_deescalation(character, location))

            # Create result
            result = GeneratedActionOptions(
                character_id=str(character.get('character_id')),
                turn_number=current_turn,
                options=options,
                mood_category=MoodCategory(context['mood_guidance']['mood_category']),
                generation_context=context
            )

            logger.info(
                f"Successfully generated {len(options)} options for {character.get('name')}"
            )

            return result

        except Exception as e:
            logger.error(f"Error generating action options: {e}", exc_info=True)

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

            parsed = json.loads(json_str)

            options = []
            for idx, option_data in enumerate(parsed, start=1):
                # Parse actions
                actions = []
                for action_data in option_data.get('actions', []):
                    action = SingleAction(
                        action_type=ActionType(action_data['type']),
                        description=action_data['description'],
                        is_private=action_data.get('is_private', False),
                        target_character_id=action_data.get('target'),
                        metadata=action_data
                    )
                    actions.append(action)

                # Create sequence
                sequence = ActionSequence(
                    actions=actions,
                    summary=option_data.get('summary', f'Option {idx}'),
                    escalates_mood=option_data.get('escalates_mood', False),
                    deescalates_mood=option_data.get('deescalates_mood', False),
                    emotional_tone=option_data.get('emotional_tone', 'neutral'),
                    estimated_mood_impact=option_data.get('estimated_mood_impact', {})
                )

                # Create option
                option = ActionOption(
                    option_id=idx,
                    sequence=sequence,
                    selection_weight=1.0
                )

                options.append(option)

            return options

        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}", exc_info=True)
            logger.debug(f"Response was: {response}")
            raise

    def _create_fallback_deescalation(
        self,
        character: Dict[str, Any],
        location: Dict[str, Any]
    ) -> ActionOption:
        """Create a fallback de-escalation option."""
        sequence = ActionSequence(
            actions=[
                SingleAction(
                    action_type=ActionType.THINK,
                    description=f"{character['name']} thinks about calming the situation",
                    is_private=True
                ),
                SingleAction(
                    action_type=ActionType.EMOTE,
                    description=f"{character['name']} takes a deep breath and relaxes their posture",
                    is_private=False
                ),
                SingleAction(
                    action_type=ActionType.SPEAK,
                    description=f"{character['name']} says calmly, \"Let's all take a moment.\"",
                    is_private=False
                )
            ],
            summary="Attempt to calm the situation",
            escalates_mood=False,
            deescalates_mood=True,
            emotional_tone="calming",
            estimated_mood_impact={'tension': -10, 'hostility': -5}
        )

        return ActionOption(option_id=99, sequence=sequence, selection_weight=1.0)

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
            mood_category=MoodCategory.NEUTRAL,
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
