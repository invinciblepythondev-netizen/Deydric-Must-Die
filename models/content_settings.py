"""
Content Settings Model - Thin wrapper for content rating stored procedures

Handles per-game content boundaries and NSFW handling.
All operations use stored procedures from database/procedures/content_settings_procedures.sql
"""

from sqlalchemy import text
from typing import Dict, Any, Optional
from uuid import UUID
import logging

logger = logging.getLogger(__name__)


class ContentSettings:
    """Thin wrapper for content settings operations via stored procedures"""

    @staticmethod
    def get(db_session, game_state_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get content settings for a game.

        Args:
            db_session: SQLAlchemy session
            game_state_id: Game state UUID

        Returns:
            Content settings dictionary or None if not found
        """
        result = db_session.execute(text("""
            SELECT * FROM content_settings_get(
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
            'content_rating': row.content_rating,
            'violence_max_level': row.violence_max_level,
            'romance_max_level': row.romance_max_level,
            'intimacy_max_level': row.intimacy_max_level,
            'language_max_level': row.language_max_level,
            'horror_max_level': row.horror_max_level,
            'allow_graphic_violence': row.allow_graphic_violence,
            'allow_sexual_content': row.allow_sexual_content,
            'allow_substance_use': row.allow_substance_use,
            'allow_psychological_horror': row.allow_psychological_horror,
            'allow_death': row.allow_death,
            'fade_to_black_violence': row.fade_to_black_violence,
            'fade_to_black_intimacy': row.fade_to_black_intimacy,
            'fade_to_black_death': row.fade_to_black_death,
            'preferred_nsfw_provider': row.preferred_nsfw_provider,
            'created_at': row.created_at,
            'updated_at': row.updated_at
        }

    @staticmethod
    def upsert(
        db_session,
        game_state_id: UUID,
        content_rating: str = 'pg13',
        violence_max_level: int = 2,
        romance_max_level: int = 1,
        intimacy_max_level: int = 0,
        language_max_level: int = 2,
        horror_max_level: int = 2,
        allow_graphic_violence: bool = False,
        allow_sexual_content: bool = False,
        allow_substance_use: bool = True,
        allow_psychological_horror: bool = True,
        allow_death: bool = True,
        fade_to_black_violence: bool = False,
        fade_to_black_intimacy: bool = True,
        fade_to_black_death: bool = False,
        preferred_nsfw_provider: Optional[str] = None
    ) -> UUID:
        """
        Create or update content settings.

        Args:
            db_session: SQLAlchemy session
            game_state_id: Game state UUID
            content_rating: Overall rating (g, pg, pg13, r, nc17, unrestricted)
            violence_max_level: Max violence intensity 0-4
            romance_max_level: Max romance intensity 0-4
            intimacy_max_level: Max intimacy intensity 0-4
            language_max_level: Max language intensity 0-4
            horror_max_level: Max horror intensity 0-4
            allow_graphic_violence: Allow graphic violence descriptions
            allow_sexual_content: Allow sexual content
            allow_substance_use: Allow drug/alcohol use
            allow_psychological_horror: Allow psychological horror
            allow_death: Allow character death
            fade_to_black_violence: Describe aftermath not details
            fade_to_black_intimacy: Imply not describe
            fade_to_black_death: Fade before death moment
            preferred_nsfw_provider: LLM provider for mature content

        Returns:
            Game state UUID
        """
        result = db_session.execute(text("""
            SELECT content_settings_upsert(
                p_game_state_id := :game_state_id,
                p_content_rating := :content_rating,
                p_violence_max_level := :violence_max_level,
                p_romance_max_level := :romance_max_level,
                p_intimacy_max_level := :intimacy_max_level,
                p_language_max_level := :language_max_level,
                p_horror_max_level := :horror_max_level,
                p_allow_graphic_violence := :allow_graphic_violence,
                p_allow_sexual_content := :allow_sexual_content,
                p_allow_substance_use := :allow_substance_use,
                p_allow_psychological_horror := :allow_psychological_horror,
                p_allow_death := :allow_death,
                p_fade_to_black_violence := :fade_to_black_violence,
                p_fade_to_black_intimacy := :fade_to_black_intimacy,
                p_fade_to_black_death := :fade_to_black_death,
                p_preferred_nsfw_provider := :preferred_nsfw_provider
            )
        """), {
            "game_state_id": str(game_state_id),
            "content_rating": content_rating,
            "violence_max_level": violence_max_level,
            "romance_max_level": romance_max_level,
            "intimacy_max_level": intimacy_max_level,
            "language_max_level": language_max_level,
            "horror_max_level": horror_max_level,
            "allow_graphic_violence": allow_graphic_violence,
            "allow_sexual_content": allow_sexual_content,
            "allow_substance_use": allow_substance_use,
            "allow_psychological_horror": allow_psychological_horror,
            "allow_death": allow_death,
            "fade_to_black_violence": fade_to_black_violence,
            "fade_to_black_intimacy": fade_to_black_intimacy,
            "fade_to_black_death": fade_to_black_death,
            "preferred_nsfw_provider": preferred_nsfw_provider
        })

        game_id = result.scalar()
        db_session.commit()

        logger.info(f"Updated content settings for game {game_state_id}: {content_rating}")

        return UUID(game_id)

    @staticmethod
    def set_preset(
        db_session,
        game_state_id: UUID,
        content_rating: str
    ) -> UUID:
        """
        Apply preset content rating (easier than manually setting all values).

        Presets:
        - g: No violence, romance, intimacy, language, or horror
        - pg: Mild/implied content only
        - pg13: Moderate content, kissing allowed (DEFAULT)
        - r: Intense content, implied sexual content
        - nc17: Graphic content, sexual content allowed
        - unrestricted: Everything allowed

        Args:
            db_session: SQLAlchemy session
            game_state_id: Game state UUID
            content_rating: Rating preset (g, pg, pg13, r, nc17, unrestricted)

        Returns:
            Game state UUID
        """
        result = db_session.execute(text("""
            SELECT content_settings_set_preset(
                p_game_state_id := :game_state_id,
                p_content_rating := :content_rating
            )
        """), {
            "game_state_id": str(game_state_id),
            "content_rating": content_rating
        })

        game_id = result.scalar()
        db_session.commit()

        logger.info(f"Set content rating preset for game {game_state_id}: {content_rating}")

        return UUID(game_id)

    @staticmethod
    def get_emotion_max_level(
        db_session,
        game_state_id: UUID,
        emotion_category: str
    ) -> int:
        """
        Get maximum allowed intensity level for specific emotion category.

        Args:
            db_session: SQLAlchemy session
            game_state_id: Game state UUID
            emotion_category: Emotion category (violence, romance, intimacy, fear, etc.)

        Returns:
            Max level 0-4
        """
        result = db_session.execute(text("""
            SELECT content_settings_get_emotion_max_level(
                p_game_state_id := :game_state_id,
                p_emotion_category := :emotion_category
            )
        """), {
            "game_state_id": str(game_state_id),
            "emotion_category": emotion_category
        })

        return result.scalar() or 4  # Default to no limit

    @staticmethod
    def can_escalate(
        db_session,
        game_state_id: UUID,
        emotion_category: str,
        target_level: int
    ) -> Dict[str, Any]:
        """
        Check if emotion can escalate to target level without violating boundaries.

        Args:
            db_session: SQLAlchemy session
            game_state_id: Game state UUID
            emotion_category: Emotion category
            target_level: Desired intensity level

        Returns:
            Dict with can_escalate (bool) and reason (str if False)
        """
        result = db_session.execute(text("""
            SELECT * FROM content_settings_can_escalate(
                p_game_state_id := :game_state_id,
                p_emotion_category := :emotion_category,
                p_target_level := :target_level
            )
        """), {
            "game_state_id": str(game_state_id),
            "emotion_category": emotion_category,
            "target_level": target_level
        })

        row = result.fetchone()
        return {
            'can_escalate': row.can_escalate,
            'reason': row.reason
        }

    @staticmethod
    def get_fade_instructions(
        db_session,
        game_state_id: UUID
    ) -> str:
        """
        Generate LLM prompt instructions for fade-to-black handling.

        Args:
            db_session: SQLAlchemy session
            game_state_id: Game state UUID

        Returns:
            Instructions string for LLM system prompt
        """
        result = db_session.execute(text("""
            SELECT content_settings_get_fade_instructions(
                p_game_state_id := :game_state_id
            )
        """), {
            "game_state_id": str(game_state_id)
        })

        return result.scalar() or "Keep content appropriate for PG-13 audiences."

    @staticmethod
    def delete(db_session, game_state_id: UUID) -> bool:
        """
        Delete content settings (game will revert to default PG-13).

        Args:
            db_session: SQLAlchemy session
            game_state_id: Game state UUID

        Returns:
            True if deleted
        """
        result = db_session.execute(text("""
            SELECT content_settings_delete(
                p_game_state_id := :game_state_id
            )
        """), {
            "game_state_id": str(game_state_id)
        })

        success = result.scalar()
        db_session.commit()

        if success:
            logger.info(f"Deleted content settings for game {game_state_id}")

        return success


# Content rating definitions
CONTENT_RATINGS = {
    'g': {
        'name': 'General Audiences',
        'description': 'Suitable for all ages. No violence, romance, or mature content.',
        'violence': 0, 'romance': 0, 'intimacy': 0, 'language': 0, 'horror': 0
    },
    'pg': {
        'name': 'Parental Guidance',
        'description': 'Mild content. Some suspense and light conflict.',
        'violence': 1, 'romance': 1, 'intimacy': 0, 'language': 1, 'horror': 1
    },
    'pg13': {
        'name': 'Parents Strongly Cautioned',
        'description': 'Moderate content. Action violence, kissing, mild language.',
        'violence': 2, 'romance': 2, 'intimacy': 1, 'language': 2, 'horror': 2
    },
    'r': {
        'name': 'Restricted',
        'description': 'Intense content. Graphic violence, passionate romance, implied sexual content.',
        'violence': 3, 'romance': 3, 'intimacy': 2, 'language': 3, 'horror': 3
    },
    'nc17': {
        'name': 'Adults Only',
        'description': 'Graphic mature content. Explicit violence and sexual content.',
        'violence': 4, 'romance': 4, 'intimacy': 3, 'language': 4, 'horror': 4
    },
    'unrestricted': {
        'name': 'Unrestricted',
        'description': 'No content limits. All themes and intensities allowed.',
        'violence': 4, 'romance': 4, 'intimacy': 4, 'language': 4, 'horror': 4
    }
}

# Level descriptions for reference
INTENSITY_LEVEL_DESCRIPTIONS = {
    0: "None - Content category not present",
    1: "Mild - Implied or very light content",
    2: "Moderate - Clearly present but not graphic",
    3: "Intense - Strong content, may be disturbing",
    4: "Graphic - Explicit, detailed, unrestricted"
}
