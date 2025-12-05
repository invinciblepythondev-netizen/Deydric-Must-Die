"""
Character Emotional State Model - Thin wrapper for emotional state stored procedures

Handles individual character emotional intensity and progression tracking.
All operations use stored procedures from database/procedures/character_emotional_state_procedures.sql
"""

from sqlalchemy import text
from typing import Dict, Any, Optional, List
from uuid import UUID
import logging
import json

logger = logging.getLogger(__name__)


class CharacterEmotionalState:
    """Thin wrapper for character emotional state operations via stored procedures"""

    @staticmethod
    def get(
        db_session,
        character_id: UUID,
        game_state_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """
        Get character emotional state.

        Args:
            db_session: SQLAlchemy session
            character_id: Character UUID
            game_state_id: Game state UUID

        Returns:
            Emotional state dictionary or None if not found
        """
        result = db_session.execute(text("""
            SELECT * FROM character_emotional_state_get(
                p_character_id := :character_id,
                p_game_state_id := :game_state_id
            )
        """), {
            "character_id": str(character_id),
            "game_state_id": str(game_state_id)
        })

        row = result.fetchone()
        if not row:
            return None

        return {
            'state_id': row.state_id,
            'character_id': row.character_id,
            'game_state_id': row.game_state_id,
            'primary_emotion': row.primary_emotion,
            'intensity_level': row.intensity_level,
            'intensity_points': row.intensity_points,
            'emotion_scores': row.emotion_scores,
            'last_intensity_change_turn': row.last_intensity_change_turn,
            'emotional_trajectory': row.emotional_trajectory,
            'triggered_by_character_id': row.triggered_by_character_id,
            'trigger_description': row.trigger_description,
            'created_at': row.created_at,
            'updated_at': row.updated_at
        }

    @staticmethod
    def upsert(
        db_session,
        character_id: UUID,
        game_state_id: UUID,
        primary_emotion: str = 'calm',
        intensity_level: int = 0,
        intensity_points: int = 0,
        emotion_scores: Optional[Dict] = None,
        emotional_trajectory: str = 'stable',
        triggered_by_character_id: Optional[UUID] = None,
        trigger_description: Optional[str] = None
    ) -> UUID:
        """
        Create or update character emotional state.

        Args:
            db_session: SQLAlchemy session
            character_id: Character UUID
            game_state_id: Game state UUID
            primary_emotion: Dominant emotion (anger, fear, attraction, joy, sadness, calm, etc.)
            intensity_level: Intensity tier 0-4 (NEUTRAL, ENGAGED, PASSIONATE, EXTREME, BREAKING)
            intensity_points: Point accumulation 0-120
            emotion_scores: Dict of emotion -> score (e.g., {"anger": 45, "fear": 20})
            emotional_trajectory: Direction of change (rising, falling, stable, volatile)
            triggered_by_character_id: Who triggered this emotional state
            trigger_description: What triggered it

        Returns:
            State UUID
        """
        result = db_session.execute(text("""
            SELECT character_emotional_state_upsert(
                p_character_id := :character_id,
                p_game_state_id := :game_state_id,
                p_primary_emotion := :primary_emotion,
                p_intensity_level := :intensity_level,
                p_intensity_points := :intensity_points,
                p_emotion_scores := :emotion_scores::jsonb,
                p_emotional_trajectory := :emotional_trajectory,
                p_triggered_by_character_id := :triggered_by_character_id,
                p_trigger_description := :trigger_description
            )
        """), {
            "character_id": str(character_id),
            "game_state_id": str(game_state_id),
            "primary_emotion": primary_emotion,
            "intensity_level": intensity_level,
            "intensity_points": intensity_points,
            "emotion_scores": json.dumps(emotion_scores) if emotion_scores else '{}',
            "emotional_trajectory": emotional_trajectory,
            "triggered_by_character_id": str(triggered_by_character_id) if triggered_by_character_id else None,
            "trigger_description": trigger_description
        })

        state_id = result.scalar()
        db_session.commit()

        logger.info(
            f"Updated emotional state for character {character_id}: "
            f"{primary_emotion} (Level {intensity_level}, {intensity_points} points)"
        )

        return UUID(state_id)

    @staticmethod
    def adjust(
        db_session,
        character_id: UUID,
        game_state_id: UUID,
        emotion: str,
        points_delta: int,
        triggered_by_character_id: Optional[UUID] = None,
        trigger_description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Adjust character emotional state by delta (respects content boundaries).

        Args:
            db_session: SQLAlchemy session
            character_id: Character UUID
            game_state_id: Game state UUID
            emotion: Emotion to adjust (anger, fear, attraction, etc.)
            points_delta: Points to add/subtract (-120 to +120)
            triggered_by_character_id: Who triggered this change
            trigger_description: What triggered it

        Returns:
            Dict with new_intensity_level, new_intensity_points, level_changed,
            content_boundary_hit, previous_level
        """
        result = db_session.execute(text("""
            SELECT * FROM character_emotional_state_adjust(
                p_character_id := :character_id,
                p_game_state_id := :game_state_id,
                p_emotion := :emotion,
                p_points_delta := :points_delta,
                p_triggered_by_character_id := :triggered_by_character_id,
                p_trigger_description := :trigger_description
            )
        """), {
            "character_id": str(character_id),
            "game_state_id": str(game_state_id),
            "emotion": emotion,
            "points_delta": points_delta,
            "triggered_by_character_id": str(triggered_by_character_id) if triggered_by_character_id else None,
            "trigger_description": trigger_description
        })

        row = result.fetchone()
        db_session.commit()

        adjustment_result = {
            'new_intensity_level': row.new_intensity_level,
            'new_intensity_points': row.new_intensity_points,
            'level_changed': row.level_changed,
            'content_boundary_hit': row.content_boundary_hit,
            'previous_level': row.previous_level
        }

        if row.level_changed:
            logger.info(
                f"Character {character_id} emotion escalated: "
                f"{emotion} changed from Level {row.previous_level} to {row.new_intensity_level}"
            )

        if row.content_boundary_hit:
            logger.warning(
                f"Character {character_id} hit content boundary for {emotion} "
                f"at Level {row.new_intensity_level}"
            )

        return adjustment_result

    @staticmethod
    def reset(
        db_session,
        character_id: UUID,
        game_state_id: UUID
    ) -> bool:
        """
        Reset character emotional state to neutral/calm.

        Args:
            db_session: SQLAlchemy session
            character_id: Character UUID
            game_state_id: Game state UUID

        Returns:
            True if reset successful
        """
        result = db_session.execute(text("""
            SELECT character_emotional_state_reset(
                p_character_id := :character_id,
                p_game_state_id := :game_state_id
            )
        """), {
            "character_id": str(character_id),
            "game_state_id": str(game_state_id)
        })

        success = result.scalar()
        db_session.commit()

        if success:
            logger.info(f"Reset emotional state for character {character_id}")

        return success

    @staticmethod
    def get_description(
        db_session,
        character_id: UUID,
        game_state_id: UUID
    ) -> str:
        """
        Get natural language description of emotional state.

        Args:
            db_session: SQLAlchemy session
            character_id: Character UUID
            game_state_id: Game state UUID

        Returns:
            Description like "Feeling anger (extreme intensity, escalating) - 85 points"
        """
        result = db_session.execute(text("""
            SELECT character_emotional_state_get_description(
                p_character_id := :character_id,
                p_game_state_id := :game_state_id
            )
        """), {
            "character_id": str(character_id),
            "game_state_id": str(game_state_id)
        })

        return result.scalar() or "Emotionally stable"

    @staticmethod
    def list_by_location(
        db_session,
        game_state_id: UUID,
        location_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get emotional states for all characters at a location.

        Args:
            db_session: SQLAlchemy session
            game_state_id: Game state UUID
            location_id: Location ID

        Returns:
            List of character emotional states
        """
        result = db_session.execute(text("""
            SELECT * FROM character_emotional_state_list_by_location(
                p_game_state_id := :game_state_id,
                p_location_id := :location_id
            )
        """), {
            "game_state_id": str(game_state_id),
            "location_id": location_id
        })

        states = []
        for row in result.fetchall():
            states.append({
                'character_id': row.character_id,
                'character_name': row.character_name,
                'primary_emotion': row.primary_emotion,
                'intensity_level': row.intensity_level,
                'intensity_points': row.intensity_points,
                'emotional_trajectory': row.emotional_trajectory
            })

        return states

    @staticmethod
    def delete(
        db_session,
        character_id: UUID,
        game_state_id: UUID
    ) -> bool:
        """
        Delete character emotional state.

        Args:
            db_session: SQLAlchemy session
            character_id: Character UUID
            game_state_id: Game state UUID

        Returns:
            True if deleted
        """
        result = db_session.execute(text("""
            SELECT character_emotional_state_delete(
                p_character_id := :character_id,
                p_game_state_id := :game_state_id
            )
        """), {
            "character_id": str(character_id),
            "game_state_id": str(game_state_id)
        })

        success = result.scalar()
        db_session.commit()

        if success:
            logger.info(f"Deleted emotional state for character {character_id}")

        return success


# Intensity level name mapping for external use
INTENSITY_LEVELS = {
    0: "NEUTRAL",
    1: "ENGAGED",
    2: "PASSIONATE",
    3: "EXTREME",
    4: "BREAKING"
}

# Emotion category to emotional arc mapping
EMOTION_ARC_MAPPING = {
    'conflict': ['anger', 'hostility', 'aggression', 'violence', 'rage'],
    'intimacy': ['attraction', 'desire', 'romance', 'affection', 'lust'],
    'fear': ['fear', 'terror', 'dread', 'panic', 'anxiety', 'unease'],
    'social': ['cooperation', 'camaraderie', 'devotion', 'trust', 'loyalty'],
    'positive': ['joy', 'happiness', 'excitement', 'contentment'],
    'negative': ['sadness', 'despair', 'grief', 'melancholy']
}
