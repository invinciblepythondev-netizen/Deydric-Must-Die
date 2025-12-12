"""
Character Intent Model

Manages multi-turn action intents that persist across turns.
"""

from uuid import UUID
from typing import Optional, List, Dict, Any
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)


# Action chain templates defining multi-turn action sequences
ACTION_CHAINS = {
    'seduction': {
        'stages': [
            {
                'name': 'show_interest',
                'progress_range': (0, 25),
                'keywords': ['smile', 'glance', 'compliment', 'laugh', 'notice', 'eye contact'],
                'description': 'Showing initial interest'
            },
            {
                'name': 'flirt',
                'progress_range': (25, 50),
                'keywords': ['flirt', 'tease', 'touch lightly', 'move closer', 'whisper', 'playful'],
                'description': 'Flirting and building attraction'
            },
            {
                'name': 'escalate_touch',
                'progress_range': (50, 75),
                'keywords': ['caress', 'hold', 'stroke', 'embrace', 'lean in', 'kiss'],
                'description': 'Escalating physical contact'
            },
            {
                'name': 'intimate',
                'progress_range': (75, 100),
                'keywords': ['kiss', 'undress', 'bed', 'passionate', 'desire', 'intimate'],
                'description': 'Intimate actions'
            }
        ]
    },
    'intimidation': {
        'stages': [
            {
                'name': 'verbal_threat',
                'progress_range': (0, 25),
                'keywords': ['threaten', 'warn', 'glare', 'raise voice', 'menace'],
                'description': 'Verbal threats and posturing'
            },
            {
                'name': 'physical_posturing',
                'progress_range': (25, 50),
                'keywords': ['step forward', 'loom', 'block', 'tower over', 'invade space'],
                'description': 'Physical intimidation'
            },
            {
                'name': 'physical_contact',
                'progress_range': (50, 75),
                'keywords': ['grab', 'shove', 'pin', 'seize', 'restrain'],
                'description': 'Forceful physical contact'
            },
            {
                'name': 'violence',
                'progress_range': (75, 100),
                'keywords': ['strike', 'punch', 'attack', 'choke', 'stab', 'hurt'],
                'description': 'Physical violence'
            }
        ]
    },
    'persuasion': {
        'stages': [
            {
                'name': 'establish_rapport',
                'progress_range': (0, 25),
                'keywords': ['agree', 'common ground', 'empathize', 'listen', 'understand'],
                'description': 'Building rapport'
            },
            {
                'name': 'present_argument',
                'progress_range': (25, 50),
                'keywords': ['explain', 'reasoning', 'evidence', 'benefits', 'logical'],
                'description': 'Presenting arguments'
            },
            {
                'name': 'handle_objections',
                'progress_range': (50, 75),
                'keywords': ['address concerns', 'compromise', 'alternative', 'counter'],
                'description': 'Handling objections'
            },
            {
                'name': 'close',
                'progress_range': (75, 100),
                'keywords': ['agreement', 'commit', 'seal', 'decide', 'accept'],
                'description': 'Closing the deal'
            }
        ]
    }
}


class CharacterIntent:
    """Model for managing character intents that span multiple turns."""

    @staticmethod
    def get_active(
        db_session,
        character_id: UUID,
        game_state_id: UUID,
        intent_type: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get the active intent for a character.

        Args:
            db_session: Database session
            character_id: UUID of the character
            game_state_id: UUID of the game state
            intent_type: Optional filter by intent type

        Returns:
            Dictionary with intent data or None
        """
        result = db_session.execute(
            text("SELECT * FROM character_intent_get_active(:character_id, :game_state_id, :intent_type)"),
            {
                "character_id": str(character_id),
                "game_state_id": str(game_state_id),
                "intent_type": intent_type
            }
        ).fetchone()

        if result:
            return {
                'intent_id': result.intent_id,
                'character_id': result.character_id,
                'game_state_id': result.game_state_id,
                'intent_type': result.intent_type,
                'intent_description': result.intent_description,
                'target_character_id': result.target_character_id,
                'target_character_name': result.target_character_name,
                'target_object': result.target_object,
                'progress_level': result.progress_level,
                'current_stage': result.current_stage,
                'intensity': result.intensity,
                'approach_style': result.approach_style,
                'started_turn': result.started_turn,
                'last_action_turn': result.last_action_turn,
                'is_active': result.is_active,
                'completion_status': result.completion_status,
                'completion_turn': result.completion_turn
            }

        return None

    @staticmethod
    def create_or_update(
        db_session,
        character_id: UUID,
        game_state_id: UUID,
        intent_type: str,
        target_character_id: Optional[UUID] = None,
        target_object: Optional[str] = None,
        progress_level: int = 0,
        current_stage: Optional[str] = None,
        intensity: str = 'moderate',
        approach_style: Optional[str] = None,
        started_turn: Optional[int] = None,
        intent_id: Optional[UUID] = None,
        intent_description: Optional[str] = None
    ) -> UUID:
        """
        Create a new intent or update an existing one.

        Args:
            db_session: Database session
            character_id: UUID of the character
            game_state_id: UUID of the game state
            intent_type: Type of intent (seduction, intimidation, etc.)
            target_character_id: Optional target character UUID
            target_object: Optional target object name
            progress_level: Initial progress (0-100)
            current_stage: Current stage name
            intensity: Intensity level (subtle, moderate, aggressive, desperate)
            approach_style: Approach style (gentle, forceful, playful, etc.)
            started_turn: Turn when intent started
            intent_id: Optional UUID for updating existing intent
            intent_description: Human-readable description

        Returns:
            UUID of the intent
        """
        result = db_session.execute(
            text("""
                SELECT character_intent_upsert(
                    p_intent_id := :intent_id,
                    p_character_id := :character_id,
                    p_game_state_id := :game_state_id,
                    p_intent_type := :intent_type,
                    p_intent_description := :intent_description,
                    p_target_character_id := :target_character_id,
                    p_target_object := :target_object,
                    p_progress_level := :progress_level,
                    p_current_stage := :current_stage,
                    p_intensity := :intensity,
                    p_approach_style := :approach_style,
                    p_started_turn := :started_turn,
                    p_last_action_turn := :started_turn
                )
            """),
            {
                "intent_id": str(intent_id) if intent_id else None,
                "character_id": str(character_id),
                "game_state_id": str(game_state_id),
                "intent_type": intent_type,
                "intent_description": intent_description,
                "target_character_id": str(target_character_id) if target_character_id else None,
                "target_object": target_object,
                "progress_level": progress_level,
                "current_stage": current_stage,
                "intensity": intensity,
                "approach_style": approach_style,
                "started_turn": started_turn
            }
        )

        intent_id_result = result.scalar()
        db_session.commit()

        logger.info(
            f"Created/updated intent {intent_type} for character {character_id}, "
            f"progress={progress_level}%, stage={current_stage}"
        )

        # Return UUID properly
        if isinstance(intent_id_result, UUID):
            return intent_id_result
        else:
            return UUID(intent_id_result)

    @staticmethod
    def update_progress(
        db_session,
        intent_id: UUID,
        progress_delta: int,
        current_turn: int,
        current_stage: Optional[str] = None
    ) -> int:
        """
        Update the progress of an intent.

        Args:
            db_session: Database session
            intent_id: UUID of the intent
            progress_delta: Change in progress (-100 to +100)
            current_turn: Current turn number
            current_stage: Optional new stage name

        Returns:
            New progress level
        """
        result = db_session.execute(
            text("""
                SELECT character_intent_update_progress(
                    :intent_id,
                    :progress_delta,
                    :current_stage,
                    :current_turn
                )
            """),
            {
                "intent_id": str(intent_id),
                "progress_delta": progress_delta,
                "current_stage": current_stage,
                "current_turn": current_turn
            }
        )

        new_progress = result.scalar()
        db_session.commit()

        logger.info(f"Updated intent {intent_id} progress by {progress_delta:+d} to {new_progress}%")

        return new_progress

    @staticmethod
    def complete(
        db_session,
        intent_id: UUID,
        completion_status: str,
        completion_turn: int
    ):
        """
        Mark an intent as complete.

        Args:
            db_session: Database session
            intent_id: UUID of the intent
            completion_status: Status (achieved, abandoned, interrupted, rejected)
            completion_turn: Turn when completed
        """
        db_session.execute(
            text("""
                SELECT character_intent_complete(
                    :intent_id,
                    :completion_status,
                    :completion_turn
                )
            """),
            {
                "intent_id": str(intent_id),
                "completion_status": completion_status,
                "completion_turn": completion_turn
            }
        )

        db_session.commit()

        logger.info(f"Completed intent {intent_id} with status: {completion_status}")

    @staticmethod
    def detect_progress_from_action(
        intent_type: str,
        action_description: str
    ) -> int:
        """
        Detect progress made from an action based on keywords.

        Args:
            intent_type: Type of intent
            action_description: Description of the action taken

        Returns:
            Progress delta (0-20)
        """
        chain = ACTION_CHAINS.get(intent_type)
        if not chain:
            return 5  # Default progress if no chain defined

        action_lower = action_description.lower()

        # Check each stage for keyword matches
        for stage in chain['stages']:
            keywords = stage.get('keywords', [])
            if any(keyword in action_lower for keyword in keywords):
                # Matched this stage - give progress appropriate to the stage
                progress_range = stage['progress_range']
                # Give progress that moves toward this stage
                return 10  # Moderate progress

        # No keywords matched - minimal progress
        return 3

    @staticmethod
    def get_stage_from_progress(intent_type: str, progress: int) -> Optional[str]:
        """
        Get the current stage name based on progress level.

        Args:
            intent_type: Type of intent
            progress: Progress level (0-100)

        Returns:
            Stage name or None
        """
        chain = ACTION_CHAINS.get(intent_type)
        if not chain:
            return None

        for stage in chain['stages']:
            min_prog, max_prog = stage['progress_range']
            if min_prog <= progress < max_prog:
                return stage['name']

        # If at 100%, return last stage
        if progress >= 100 and chain['stages']:
            return chain['stages'][-1]['name']

        return None

    @staticmethod
    def deactivate_stale_intents(
        db_session,
        game_state_id: UUID,
        current_turn: int,
        stale_threshold: int = 3
    ) -> int:
        """
        Deactivate intents that haven't been pursued recently.

        Args:
            db_session: Database session
            game_state_id: UUID of the game state
            current_turn: Current turn number
            stale_threshold: Number of turns without action to consider stale

        Returns:
            Number of intents deactivated
        """
        result = db_session.execute(
            text("""
                SELECT character_intent_deactivate_stale(
                    :game_state_id,
                    :current_turn,
                    :stale_threshold
                )
            """),
            {
                "game_state_id": str(game_state_id),
                "current_turn": current_turn,
                "stale_threshold": stale_threshold
            }
        )

        count = result.scalar()
        db_session.commit()

        if count > 0:
            logger.info(f"Deactivated {count} stale intent(s)")

        return count
