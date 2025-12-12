"""
Content Settings Model

Manages content rating controls for game states.
"""

from sqlalchemy import text
from typing import Dict, Any, Optional
from uuid import UUID
import logging

logger = logging.getLogger(__name__)


class ContentSettings:
    """Thin wrapper for content_settings operations via stored procedures"""

    # Rating presets with their level definitions
    PRESETS = {
        'G': {
            'violence': 0,
            'intimacy': 0,
            'horror': 0,
            'profanity': 0,
            'description': 'General Audiences - No mature content'
        },
        'PG': {
            'violence': 1,
            'intimacy': 0,
            'horror': 1,
            'profanity': 1,
            'description': 'Parental Guidance - Mild content'
        },
        'PG-13': {
            'violence': 2,
            'intimacy': 1,
            'horror': 2,
            'profanity': 2,
            'description': 'PG-13 - Moderate content (default)'
        },
        'R': {
            'violence': 3,
            'intimacy': 2,
            'horror': 3,
            'profanity': 3,
            'description': 'Restricted - Strong content'
        },
        'Mature': {
            'violence': 3,
            'intimacy': 3,
            'horror': 3,
            'profanity': 3,
            'description': 'Mature - Explicit content'
        },
        'Unrestricted': {
            'violence': 4,
            'intimacy': 4,
            'horror': 4,
            'profanity': 4,
            'description': 'Unrestricted - No limits'
        }
    }

    @staticmethod
    def get(db_session, game_state_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get content settings for a game state.

        Args:
            db_session: SQLAlchemy session
            game_state_id: Game state UUID

        Returns:
            Dictionary with settings or None if not found
        """
        result = db_session.execute(
            text("""
                SELECT * FROM content_settings_get(:game_state_id)
            """),
            {"game_state_id": str(game_state_id)}
        ).fetchone()

        if not result:
            return None

        return {
            'content_settings_id': result.content_settings_id,
            'game_state_id': result.game_state_id,
            'violence_max_level': result.violence_max_level,
            'intimacy_max_level': result.intimacy_max_level,
            'horror_max_level': result.horror_max_level,
            'profanity_max_level': result.profanity_max_level,
            'rating_preset': result.rating_preset,
            'created_at': result.created_at,
            'updated_at': result.updated_at
        }

    @staticmethod
    def upsert(
        db_session,
        game_state_id: UUID,
        violence_max_level: int = 2,
        intimacy_max_level: int = 1,
        horror_max_level: int = 2,
        profanity_max_level: int = 2,
        rating_preset: str = 'PG-13'
    ) -> UUID:
        """
        Create or update content settings.

        Args:
            db_session: SQLAlchemy session
            game_state_id: Game state UUID
            violence_max_level: Max violence (0-4)
            intimacy_max_level: Max intimacy (0-4)
            horror_max_level: Max horror (0-4)
            profanity_max_level: Max profanity (0-4)
            rating_preset: Rating preset name

        Returns:
            Content settings UUID
        """
        result = db_session.execute(
            text("""
                SELECT content_settings_upsert(
                    :game_state_id,
                    :violence_max_level,
                    :intimacy_max_level,
                    :horror_max_level,
                    :profanity_max_level,
                    :rating_preset
                )
            """),
            {
                "game_state_id": str(game_state_id),
                "violence_max_level": violence_max_level,
                "intimacy_max_level": intimacy_max_level,
                "horror_max_level": horror_max_level,
                "profanity_max_level": profanity_max_level,
                "rating_preset": rating_preset
            }
        ).fetchone()

        db_session.commit()

        return result[0]

    @staticmethod
    def set_from_preset(
        db_session,
        game_state_id: UUID,
        preset: str = 'PG-13'
    ) -> UUID:
        """
        Set content settings using a rating preset.

        Args:
            db_session: SQLAlchemy session
            game_state_id: Game state UUID
            preset: Rating preset (G, PG, PG-13, R, Mature, Unrestricted)

        Returns:
            Content settings UUID
        """
        if preset not in ContentSettings.PRESETS:
            logger.warning(f"Invalid preset '{preset}', using PG-13")
            preset = 'PG-13'

        result = db_session.execute(
            text("""
                SELECT content_settings_set_from_preset(
                    :game_state_id,
                    :preset
                )
            """),
            {
                "game_state_id": str(game_state_id),
                "preset": preset
            }
        ).fetchone()

        db_session.commit()

        return result[0]

    @staticmethod
    def get_or_create_default(db_session, game_state_id: UUID) -> Dict[str, Any]:
        """
        Get content settings, or create with PG-13 defaults if not exists.

        Args:
            db_session: SQLAlchemy session
            game_state_id: Game state UUID

        Returns:
            Dictionary with settings
        """
        settings = ContentSettings.get(db_session, game_state_id)

        if not settings:
            logger.info(f"Creating default PG-13 content settings for game {game_state_id}")
            ContentSettings.set_from_preset(db_session, game_state_id, 'PG-13')
            settings = ContentSettings.get(db_session, game_state_id)

        return settings

    @staticmethod
    def get_level_description(category: str, level: int) -> str:
        """
        Get human-readable description of a content level.

        Args:
            category: Content category (violence, intimacy, horror, profanity)
            level: Level (0-4)

        Returns:
            Description string
        """
        descriptions = {
            'violence': [
                'None',
                'Mild (cartoon violence, no blood)',
                'Moderate (action violence, minimal blood)',
                'Strong (realistic violence, injury detail)',
                'Unrestricted (graphic violence, gore)'
            ],
            'intimacy': [
                'None',
                'Mild (kissing, hand-holding)',
                'Moderate (passionate kissing, fade-to-black)',
                'Strong (explicit sexual content)',
                'Unrestricted (no limits)'
            ],
            'horror': [
                'None',
                'Mild (suspense, mild scares)',
                'Moderate (horror themes, some disturbing images)',
                'Strong (intense horror, disturbing content)',
                'Unrestricted (extreme horror, graphic content)'
            ],
            'profanity': [
                'None',
                'Mild (damn, hell)',
                'Moderate (some strong language)',
                'Strong (frequent strong language)',
                'Unrestricted (no limits)'
            ]
        }

        if category not in descriptions:
            return f"Level {level}"

        if 0 <= level < len(descriptions[category]):
            return descriptions[category][level]

        return f"Level {level}"
