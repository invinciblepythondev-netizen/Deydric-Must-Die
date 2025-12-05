"""
Scene Mood Model - Thin wrapper for mood tracking stored procedures

Handles emotional/tension dynamics in locations between characters.
All operations use stored procedures from database/procedures/mood_procedures.sql
"""

from sqlalchemy import text
from typing import Dict, Any, Optional, Tuple
from uuid import UUID
import logging

logger = logging.getLogger(__name__)


class SceneMood:
    """Thin wrapper for scene mood operations via stored procedures"""

    @staticmethod
    def get(db_session, game_state_id: UUID, location_id: int) -> Optional[Dict[str, Any]]:
        """
        Get current mood for a location.

        Args:
            db_session: SQLAlchemy session
            game_state_id: UUID of the game state
            location_id: Location ID

        Returns:
            Mood dictionary or None if no mood tracked
        """
        result = db_session.execute(text("""
            SELECT * FROM scene_mood_get(
                p_game_state_id := :game_state_id,
                p_location_id := :location_id
            )
        """), {
            "game_state_id": str(game_state_id),
            "location_id": location_id
        })

        row = result.fetchone()
        if not row:
            return None

        return {
            'scene_mood_id': row.scene_mood_id,
            'game_state_id': row.game_state_id,
            'location_id': row.location_id,
            'tension_level': row.tension_level,
            'romance_level': row.romance_level,
            'hostility_level': row.hostility_level,
            'cooperation_level': row.cooperation_level,
            'tension_trajectory': row.tension_trajectory,
            'intensity_level': row.intensity_level,
            'intensity_points': row.intensity_points,
            'dominant_arc': row.dominant_arc,
            'scene_phase': row.scene_phase,
            'last_mood_change_turn': row.last_mood_change_turn,
            'last_mood_change_description': row.last_mood_change_description,
            'last_level_change_turn': row.last_level_change_turn,
            'character_ids': row.character_ids,
            'updated_at': row.updated_at
        }

    @staticmethod
    def create_or_update(
        db_session,
        game_state_id: UUID,
        location_id: int,
        tension_level: int = 0,
        romance_level: int = 0,
        hostility_level: int = 0,
        cooperation_level: int = 0,
        tension_trajectory: str = 'stable',
        intensity_level: int = 0,
        intensity_points: int = 0,
        dominant_arc: Optional[str] = None,
        scene_phase: str = 'building',
        last_mood_change_turn: Optional[int] = None,
        last_mood_change_description: Optional[str] = None,
        character_ids: Optional[list] = None
    ) -> UUID:
        """
        Create or update scene mood.

        Args:
            db_session: SQLAlchemy session
            game_state_id: UUID of the game state
            location_id: Location ID
            tension_level: Tension (-100 to +100)
            romance_level: Romance (-100 to +100)
            hostility_level: Hostility (-100 to +100)
            cooperation_level: Cooperation (-100 to +100)
            tension_trajectory: 'rising', 'falling', or 'stable'
            intensity_level: Overall intensity tier 0-4 (NEUTRAL, ENGAGED, PASSIONATE, EXTREME, BREAKING)
            intensity_points: Point accumulation 0-120
            dominant_arc: Strongest emotional progression (conflict, intimacy, fear, social, neutral)
            scene_phase: Narrative phase (building, climax, resolution, aftermath)
            last_mood_change_turn: Turn when last changed
            last_mood_change_description: What caused the change
            character_ids: List of character UUIDs in the scene

        Returns:
            UUID of scene_mood record
        """
        result = db_session.execute(text("""
            SELECT scene_mood_upsert(
                p_game_state_id := :game_state_id,
                p_location_id := :location_id,
                p_tension_level := :tension_level,
                p_romance_level := :romance_level,
                p_hostility_level := :hostility_level,
                p_cooperation_level := :cooperation_level,
                p_tension_trajectory := :tension_trajectory,
                p_intensity_level := :intensity_level,
                p_intensity_points := :intensity_points,
                p_dominant_arc := :dominant_arc,
                p_scene_phase := :scene_phase,
                p_last_mood_change_turn := :last_mood_change_turn,
                p_last_mood_change_description := :last_mood_change_description,
                p_character_ids := :character_ids::jsonb
            )
        """), {
            "game_state_id": str(game_state_id),
            "location_id": location_id,
            "tension_level": tension_level,
            "romance_level": romance_level,
            "hostility_level": hostility_level,
            "cooperation_level": cooperation_level,
            "tension_trajectory": tension_trajectory,
            "intensity_level": intensity_level,
            "intensity_points": intensity_points,
            "dominant_arc": dominant_arc,
            "scene_phase": scene_phase,
            "last_mood_change_turn": last_mood_change_turn,
            "last_mood_change_description": last_mood_change_description,
            "character_ids": character_ids or []
        })

        scene_mood_id = result.scalar()
        db_session.commit()

        logger.info(
            f"Updated mood for location {location_id}: "
            f"Level {intensity_level} ({intensity_points} pts), arc={dominant_arc}, phase={scene_phase}"
        )

        return UUID(scene_mood_id)

    @staticmethod
    def adjust(
        db_session,
        game_state_id: UUID,
        location_id: int,
        tension_delta: int = 0,
        romance_delta: int = 0,
        hostility_delta: int = 0,
        cooperation_delta: int = 0,
        current_turn: Optional[int] = None,
        mood_change_description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Adjust mood levels by delta amounts.

        Args:
            db_session: SQLAlchemy session
            game_state_id: UUID of the game state
            location_id: Location ID
            tension_delta: Amount to change tension (e.g., +10, -5)
            romance_delta: Amount to change romance
            hostility_delta: Amount to change hostility
            cooperation_delta: Amount to change cooperation
            current_turn: Current turn number
            mood_change_description: What caused the change

        Returns:
            Dictionary with new mood levels
        """
        result = db_session.execute(text("""
            SELECT * FROM scene_mood_adjust(
                p_game_state_id := :game_state_id,
                p_location_id := :location_id,
                p_tension_delta := :tension_delta,
                p_romance_delta := :romance_delta,
                p_hostility_delta := :hostility_delta,
                p_cooperation_delta := :cooperation_delta,
                p_current_turn := :current_turn,
                p_mood_change_description := :mood_change_description
            )
        """), {
            "game_state_id": str(game_state_id),
            "location_id": location_id,
            "tension_delta": tension_delta,
            "romance_delta": romance_delta,
            "hostility_delta": hostility_delta,
            "cooperation_delta": cooperation_delta,
            "current_turn": current_turn,
            "mood_change_description": mood_change_description
        })

        row = result.fetchone()
        db_session.commit()

        if row.level_changed:
            logger.info(
                f"Mood level changed for location {location_id}: "
                f"Level {row.new_intensity_level} ({row.new_intensity_points} pts), arc={row.dominant_arc}"
            )
        else:
            logger.debug(
                f"Adjusted mood for location {location_id}: "
                f"tension={row.new_tension}, trajectory={row.tension_trajectory}"
            )

        return {
            'tension': row.new_tension,
            'romance': row.new_romance,
            'hostility': row.new_hostility,
            'cooperation': row.new_cooperation,
            'intensity_level': row.new_intensity_level,
            'intensity_points': row.new_intensity_points,
            'dominant_arc': row.dominant_arc,
            'tension_trajectory': row.tension_trajectory,
            'level_changed': row.level_changed
        }

    @staticmethod
    def get_description(db_session, game_state_id: UUID, location_id: int) -> str:
        """
        Get natural language description of mood for LLM prompts.

        Args:
            db_session: SQLAlchemy session
            game_state_id: UUID of the game state
            location_id: Location ID

        Returns:
            Natural language mood description
        """
        result = db_session.execute(text("""
            SELECT scene_mood_get_description(
                p_game_state_id := :game_state_id,
                p_location_id := :location_id
            )
        """), {
            "game_state_id": str(game_state_id),
            "location_id": location_id
        })

        description = result.scalar()
        return description or "General mood: Neutral. The atmosphere is calm and unremarkable."

    @staticmethod
    def get_action_guidance(
        db_session,
        game_state_id: UUID,
        location_id: int
    ) -> Dict[str, Any]:
        """
        Get guidance for action generation based on current mood.

        Args:
            db_session: SQLAlchemy session
            game_state_id: UUID of the game state
            location_id: Location ID

        Returns:
            Dictionary with action generation guidance:
            {
                'should_generate_escalation': bool,
                'escalation_weight': float (0-1),
                'deescalation_required': bool (always True),
                'intensity_level': int (0-4),
                'intensity_points': int (0-120),
                'dominant_arc': str (conflict, intimacy, fear, social, neutral),
                'scene_phase': str (building, climax, resolution, aftermath),
                'can_escalate_further': bool (respects content boundaries),
                'content_boundary_near': bool,
                'mood_category': str
            }
        """
        result = db_session.execute(text("""
            SELECT * FROM scene_mood_get_action_guidance(
                p_game_state_id := :game_state_id,
                p_location_id := :location_id
            )
        """), {
            "game_state_id": str(game_state_id),
            "location_id": location_id
        })

        row = result.fetchone()

        return {
            'should_generate_escalation': row.should_generate_escalation,
            'escalation_weight': row.escalation_weight,
            'deescalation_required': row.deescalation_required,
            'intensity_level': row.intensity_level,
            'intensity_points': row.intensity_points,
            'dominant_arc': row.dominant_arc,
            'scene_phase': row.scene_phase,
            'can_escalate_further': row.can_escalate_further,
            'content_boundary_near': row.content_boundary_near,
            'mood_category': row.mood_category
        }

    @staticmethod
    def apply_action_impact(
        db_session,
        game_state_id: UUID,
        location_id: int,
        mood_impact: Dict[str, int],
        current_turn: int,
        action_description: str
    ) -> Dict[str, Any]:
        """
        Apply the mood impact of an executed action.

        Args:
            db_session: SQLAlchemy session
            game_state_id: UUID of the game state
            location_id: Location ID
            mood_impact: Dict like {'tension': +10, 'hostility': +5}
            current_turn: Current turn number
            action_description: What happened

        Returns:
            Updated mood levels
        """
        return SceneMood.adjust(
            db_session,
            game_state_id,
            location_id,
            tension_delta=mood_impact.get('tension', 0),
            romance_delta=mood_impact.get('romance', 0),
            hostility_delta=mood_impact.get('hostility', 0),
            cooperation_delta=mood_impact.get('cooperation', 0),
            current_turn=current_turn,
            mood_change_description=action_description
        )
