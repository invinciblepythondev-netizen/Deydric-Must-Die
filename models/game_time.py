"""
Game Time Model - Thin wrapper for time tracking stored procedures

Handles in-game time tracking where 10 turns = 1 hour.
All operations use stored procedures from database/procedures/game_state_procedures.sql
"""

from sqlalchemy import text
from typing import Dict, Any, Optional, Tuple
from uuid import UUID
import logging

logger = logging.getLogger(__name__)


class GameTime:
    """Thin wrapper for game time operations via stored procedures"""

    @staticmethod
    def get_time_context(db_session, game_state_id: UUID) -> Dict[str, Any]:
        """
        Get comprehensive time information for LLM context assembly.

        Args:
            db_session: SQLAlchemy session
            game_state_id: UUID of the game state

        Returns:
            Dictionary with time context:
            {
                'game_day': 1,
                'formatted_time': '7:00 AM',
                'time_of_day': 'morning',
                'is_daytime': True,
                'minutes_since_midnight': 420
            }
        """
        result = db_session.execute(text("""
            SELECT * FROM game_state_get_time_context(
                p_game_state_id := :game_state_id
            )
        """), {
            "game_state_id": str(game_state_id)
        })

        row = result.fetchone()
        if not row:
            logger.error(f"No time context found for game_state_id {game_state_id}")
            return {
                'game_day': 1,
                'formatted_time': '7:00 AM',
                'time_of_day': 'morning',
                'is_daytime': True,
                'minutes_since_midnight': 420
            }

        return {
            'game_day': row.game_day,
            'formatted_time': row.formatted_time,
            'time_of_day': row.time_of_day,
            'is_daytime': row.is_daytime,
            'minutes_since_midnight': row.minutes_since_midnight
        }

    @staticmethod
    def advance_time(db_session, game_state_id: UUID) -> Dict[str, Any]:
        """
        Advance time by the configured minutes per turn (default 6 minutes).

        Args:
            db_session: SQLAlchemy session
            game_state_id: UUID of the game state

        Returns:
            Dictionary with updated time:
            {
                'game_day': 1,
                'minutes_since_midnight': 426,
                'time_of_day': '7:06 AM'
            }
        """
        result = db_session.execute(text("""
            SELECT * FROM game_state_advance_time(
                p_game_state_id := :game_state_id
            )
        """), {
            "game_state_id": str(game_state_id)
        })

        row = result.fetchone()
        db_session.commit()

        logger.info(
            f"Advanced time to Day {row.game_day}, {row.time_of_day}"
        )

        return {
            'game_day': row.game_day,
            'minutes_since_midnight': row.minutes_since_midnight,
            'time_of_day': row.time_of_day
        }

    @staticmethod
    def advance_turn(db_session, game_state_id: UUID) -> Dict[str, Any]:
        """
        Increment turn number and advance time simultaneously.
        Use this at the end of each game turn.

        Args:
            db_session: SQLAlchemy session
            game_state_id: UUID of the game state

        Returns:
            Dictionary with turn and time info:
            {
                'current_turn': 2,
                'game_day': 1,
                'formatted_time': '7:06 AM',
                'time_of_day': 'morning'
            }
        """
        result = db_session.execute(text("""
            SELECT * FROM game_state_advance_turn(
                p_game_state_id := :game_state_id
            )
        """), {
            "game_state_id": str(game_state_id)
        })

        row = result.fetchone()
        db_session.commit()

        logger.info(
            f"Advanced to turn {row.current_turn}, Day {row.game_day} {row.formatted_time} ({row.time_of_day})"
        )

        return {
            'current_turn': row.current_turn,
            'game_day': row.game_day,
            'formatted_time': row.formatted_time,
            'time_of_day': row.time_of_day
        }

    @staticmethod
    def format_time(db_session, minutes: int) -> str:
        """
        Convert minutes since midnight to readable format (e.g., "7:00 AM").

        Args:
            db_session: SQLAlchemy session
            minutes: Minutes since midnight (0-1439)

        Returns:
            Formatted time string
        """
        result = db_session.execute(text("""
            SELECT game_state_format_time(:minutes)
        """), {
            "minutes": minutes
        })

        return result.scalar()

    @staticmethod
    def get_time_of_day_category(db_session, minutes: int) -> str:
        """
        Get time of day category for a given time.

        Args:
            db_session: SQLAlchemy session
            minutes: Minutes since midnight (0-1439)

        Returns:
            Time category: 'dawn', 'morning', 'afternoon', 'evening', 'dusk', or 'night'
        """
        result = db_session.execute(text("""
            SELECT game_state_time_of_day(:minutes)
        """), {
            "minutes": minutes
        })

        return result.scalar()

    @staticmethod
    def is_daytime(db_session, minutes: int) -> bool:
        """
        Check if the given time is during daylight hours (7am-7pm).

        Args:
            db_session: SQLAlchemy session
            minutes: Minutes since midnight (0-1439)

        Returns:
            True if between sunrise and sunset
        """
        result = db_session.execute(text("""
            SELECT game_state_is_daytime(:minutes)
        """), {
            "minutes": minutes
        })

        return result.scalar()

    @staticmethod
    def format_time_for_prompt(time_context: Dict[str, Any]) -> str:
        """
        Format time context into a natural language string for LLM prompts.

        Args:
            time_context: Dictionary from get_time_context()

        Returns:
            Formatted string like:
            "Day 1, 7:00 AM (early morning, sun is up)"
        """
        day = time_context['game_day']
        time = time_context['formatted_time']
        tod = time_context['time_of_day']
        is_day = time_context['is_daytime']

        # Add contextual description
        if tod == 'night':
            desc = "dark, sun is down"
        elif tod == 'dawn':
            desc = "dawn, sun is rising"
        elif tod == 'morning':
            desc = "morning, sun is up"
        elif tod == 'afternoon':
            desc = "afternoon, sun is up"
        elif tod == 'evening':
            desc = "evening, sun is up"
        elif tod == 'dusk':
            desc = "dusk, sun is setting"
        else:
            desc = "sun is up" if is_day else "sun is down"

        return f"Day {day}, {time} ({desc})"

    @staticmethod
    def get_lighting_description(time_context: Dict[str, Any]) -> str:
        """
        Get a description of lighting conditions based on time of day.
        Useful for location descriptions in LLM context.

        Args:
            time_context: Dictionary from get_time_context()

        Returns:
            Description like "The area is well-lit by sunlight" or
            "The area is dark; torches or candles would be needed to see well"
        """
        tod = time_context['time_of_day']

        lighting_map = {
            'night': "The area is dark; torches or candles would be needed to see well.",
            'dawn': "The area is dimly lit by the early morning light.",
            'morning': "The area is well-lit by bright morning sunlight.",
            'afternoon': "The area is fully illuminated by midday sun.",
            'evening': "The area is lit by warm evening sunlight.",
            'dusk': "The area is dimly lit as the sun sets; shadows are lengthening."
        }

        return lighting_map.get(tod, "The area's lighting is unclear.")


class GameState:
    """Thin wrapper for game state operations"""

    @staticmethod
    def get(db_session, game_state_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get full game state including time tracking.

        Args:
            db_session: SQLAlchemy session
            game_state_id: UUID of the game state

        Returns:
            Game state dictionary or None
        """
        result = db_session.execute(text("""
            SELECT * FROM game_state_get(
                p_game_state_id := :game_state_id
            )
        """), {
            "game_state_id": str(game_state_id)
        })

        row = result.fetchone()
        if not row:
            return None

        return {
            'game_state_id': row.game_state_id,
            'current_turn': row.current_turn,
            'turn_order': row.turn_order,
            'is_active': row.is_active,
            'created_at': row.created_at,
            'updated_at': row.updated_at,
            'game_settings': row.game_settings,
            'game_day': row.game_day,
            'minutes_since_midnight': row.minutes_since_midnight,
            'minutes_per_turn': row.minutes_per_turn
        }

    @staticmethod
    def create(
        db_session,
        game_state_id: Optional[UUID] = None,
        current_turn: int = 1,
        turn_order: Optional[Dict] = None,
        is_active: bool = True,
        game_settings: Optional[Dict] = None,
        game_day: int = 1,
        minutes_since_midnight: int = 420,  # 7:00 AM
        minutes_per_turn: int = 6
    ) -> UUID:
        """
        Create or update a game state.

        Args:
            db_session: SQLAlchemy session
            game_state_id: UUID (if updating existing)
            current_turn: Turn number
            turn_order: JSONB array of character IDs
            is_active: Whether game is active
            game_settings: Game configuration
            game_day: Starting day (default 1)
            minutes_since_midnight: Starting time (default 420 = 7am)
            minutes_per_turn: Minutes per turn (default 6 = 10 turns/hour)

        Returns:
            UUID of the game state
        """
        result = db_session.execute(text("""
            SELECT game_state_upsert(
                p_game_state_id := :game_state_id,
                p_current_turn := :current_turn,
                p_turn_order := :turn_order,
                p_is_active := :is_active,
                p_game_settings := :game_settings,
                p_game_day := :game_day,
                p_minutes_since_midnight := :minutes_since_midnight,
                p_minutes_per_turn := :minutes_per_turn
            )
        """), {
            "game_state_id": str(game_state_id) if game_state_id else None,
            "current_turn": current_turn,
            "turn_order": turn_order,
            "is_active": is_active,
            "game_settings": game_settings or {},
            "game_day": game_day,
            "minutes_since_midnight": minutes_since_midnight,
            "minutes_per_turn": minutes_per_turn
        })

        new_game_state_id = result.scalar()
        db_session.commit()

        logger.info(
            f"Created/updated game state {new_game_state_id} "
            f"starting at Day {game_day}, {minutes_since_midnight // 60}:{minutes_since_midnight % 60:02d}"
        )

        return UUID(new_game_state_id)
