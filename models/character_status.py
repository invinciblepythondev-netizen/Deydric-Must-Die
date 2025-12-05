"""
Character Status Model - Thin wrapper for status stored procedures

Handles character statuses that affect behavior (intoxication, emotions, conditions).
All operations use stored procedures from database/procedures/character_status_procedures.sql
"""

from sqlalchemy import text
from typing import List, Dict, Any, Optional
from uuid import UUID
import logging

logger = logging.getLogger(__name__)


class CharacterStatus:
    """Thin wrapper for character status operations via stored procedures"""

    @staticmethod
    def add_status(
        db_session,
        character_id: UUID,
        status_type_code: str,
        intensity: int = 50,
        onset_turn: int = 0,
        duration_turns: Optional[int] = None,
        source: Optional[str] = None,
        notes: Optional[str] = None
    ) -> UUID:
        """
        Add or update a character status.

        Args:
            db_session: SQLAlchemy session
            character_id: UUID of the character
            status_type_code: Type of status (e.g., 'intoxicated', 'angry')
            intensity: Strength of effect (0-100)
            onset_turn: Turn when status began
            duration_turns: How many turns it lasts (None = indefinite)
            source: What caused the status
            notes: Additional context for LLM

        Returns:
            UUID of the character_status record
        """
        result = db_session.execute(text("""
            SELECT character_status_upsert(
                p_character_id := :character_id,
                p_status_type_code := :status_type_code,
                p_intensity := :intensity,
                p_onset_turn := :onset_turn,
                p_duration_turns := :duration_turns,
                p_source := :source,
                p_notes := :notes
            )
        """), {
            "character_id": str(character_id),
            "status_type_code": status_type_code,
            "intensity": intensity,
            "onset_turn": onset_turn,
            "duration_turns": duration_turns,
            "source": source,
            "notes": notes
        })

        status_id = result.scalar()
        db_session.commit()

        logger.info(
            f"Added status '{status_type_code}' (intensity: {intensity}) "
            f"to character {character_id}"
        )

        return UUID(status_id)

    @staticmethod
    def get_active_statuses(
        db_session,
        character_id: UUID,
        current_turn: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all active statuses for a character.

        Args:
            db_session: SQLAlchemy session
            character_id: UUID of the character
            current_turn: Current game turn (for expiry calculation)

        Returns:
            List of status dictionaries
        """
        result = db_session.execute(text("""
            SELECT * FROM character_status_list_active(
                p_character_id := :character_id,
                p_current_turn := :current_turn
            )
        """), {
            "character_id": str(character_id),
            "current_turn": current_turn
        })

        statuses = []
        for row in result.fetchall():
            statuses.append({
                "character_status_id": row.character_status_id,
                "status_type_code": row.status_type_code,
                "display_name": row.display_name,
                "category": row.category,
                "intensity": row.intensity,
                "onset_turn": row.onset_turn,
                "duration_turns": row.duration_turns,
                "expiry_turn": row.expiry_turn,
                "turns_remaining": row.turns_remaining,
                "source": row.source,
                "notes": row.notes
            })

        return statuses

    @staticmethod
    def get_status_summary(
        db_session,
        character_id: UUID,
        current_turn: Optional[int] = None
    ) -> str:
        """
        Get formatted summary of all active statuses for LLM context.

        Args:
            db_session: SQLAlchemy session
            character_id: UUID of the character
            current_turn: Current game turn

        Returns:
            Formatted string describing active statuses

        Example output:
            "severely intoxicated (drank ale) [4 turns remaining]
             moderately angry (witnessed insult) - may seek confrontation
             mildly frightened (heard scream)"
        """
        result = db_session.execute(text("""
            SELECT character_status_get_summary(
                p_character_id := :character_id,
                p_current_turn := :current_turn
            )
        """), {
            "character_id": str(character_id),
            "current_turn": current_turn
        })

        summary = result.scalar()
        return summary or "No active statuses"

    @staticmethod
    def update_intensity(
        db_session,
        character_status_id: UUID,
        intensity_change: int
    ) -> int:
        """
        Update the intensity of a status (e.g., getting more drunk, calming down).

        Args:
            db_session: SQLAlchemy session
            character_status_id: UUID of the status to update
            intensity_change: Amount to add (positive) or subtract (negative)

        Returns:
            New intensity value (0-100)
        """
        result = db_session.execute(text("""
            SELECT character_status_update_intensity(
                p_character_status_id := :character_status_id,
                p_intensity_change := :intensity_change
            )
        """), {
            "character_status_id": str(character_status_id),
            "intensity_change": intensity_change
        })

        new_intensity = result.scalar()
        db_session.commit()

        logger.info(
            f"Updated status {character_status_id} intensity by {intensity_change:+d} "
            f"(new: {new_intensity})"
        )

        return new_intensity

    @staticmethod
    def remove_status(
        db_session,
        character_status_id: UUID
    ) -> bool:
        """
        Remove (deactivate) a specific status.

        Args:
            db_session: SQLAlchemy session
            character_status_id: UUID of the status to remove

        Returns:
            True if successful
        """
        result = db_session.execute(text("""
            SELECT character_status_remove(
                p_character_status_id := :character_status_id
            )
        """), {
            "character_status_id": str(character_status_id)
        })

        success = result.scalar()
        db_session.commit()

        if success:
            logger.info(f"Removed status {character_status_id}")

        return success

    @staticmethod
    def remove_status_by_type(
        db_session,
        character_id: UUID,
        status_type_code: str
    ) -> int:
        """
        Remove all statuses of a specific type for a character.

        Args:
            db_session: SQLAlchemy session
            character_id: UUID of the character
            status_type_code: Type of status to remove (e.g., 'angry')

        Returns:
            Number of statuses removed
        """
        result = db_session.execute(text("""
            SELECT character_status_remove_by_type(
                p_character_id := :character_id,
                p_status_type_code := :status_type_code
            )
        """), {
            "character_id": str(character_id),
            "status_type_code": status_type_code
        })

        count = result.scalar()
        db_session.commit()

        logger.info(
            f"Removed {count} '{status_type_code}' statuses from character {character_id}"
        )

        return count

    @staticmethod
    def expire_old_statuses(
        db_session,
        current_turn: int
    ) -> List[Dict[str, Any]]:
        """
        Expire statuses that have reached their expiry turn.
        Should be called at the end of each game turn.

        Args:
            db_session: SQLAlchemy session
            current_turn: Current game turn number

        Returns:
            List of expired statuses (for logging/narration)
        """
        result = db_session.execute(text("""
            SELECT * FROM character_status_expire_old(
                p_current_turn := :current_turn
            )
        """), {
            "current_turn": current_turn
        })

        expired = []
        for row in result.fetchall():
            expired.append({
                "character_status_id": row.character_status_id,
                "character_id": row.character_id,
                "status_type_code": row.status_type_code,
                "display_name": row.display_name
            })

        db_session.commit()

        if expired:
            logger.info(f"Expired {len(expired)} statuses at turn {current_turn}")

        return expired

    @staticmethod
    def get_statuses_by_category(
        db_session,
        character_id: UUID,
        category: str,
        current_turn: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get active statuses of a specific category.

        Args:
            db_session: SQLAlchemy session
            character_id: UUID of the character
            category: Status category ('physical', 'emotional', 'mental', 'social')
            current_turn: Current game turn

        Returns:
            List of matching status dictionaries
        """
        result = db_session.execute(text("""
            SELECT * FROM character_status_list_by_category(
                p_character_id := :character_id,
                p_category := :category,
                p_current_turn := :current_turn
            )
        """), {
            "character_id": str(character_id),
            "category": category,
            "current_turn": current_turn
        })

        statuses = []
        for row in result.fetchall():
            statuses.append({
                "character_status_id": row.character_status_id,
                "status_type_code": row.status_type_code,
                "display_name": row.display_name,
                "intensity": row.intensity,
                "onset_turn": row.onset_turn,
                "expiry_turn": row.expiry_turn,
                "source": row.source,
                "notes": row.notes
            })

        return statuses


class StatusType:
    """Wrapper for status type reference operations"""

    @staticmethod
    def list_all(db_session) -> List[Dict[str, Any]]:
        """
        Get all available status types.

        Returns:
            List of status type dictionaries
        """
        result = db_session.execute(text("""
            SELECT * FROM status_type_list()
        """))

        types = []
        for row in result.fetchall():
            types.append({
                "status_type_code": row.status_type_code,
                "display_name": row.display_name,
                "description": row.description,
                "default_duration_turns": row.default_duration_turns,
                "category": row.category,
                "stackable": row.stackable
            })

        return types

    @staticmethod
    def get(db_session, status_type_code: str) -> Optional[Dict[str, Any]]:
        """
        Get details for a specific status type.

        Args:
            db_session: SQLAlchemy session
            status_type_code: Code of the status type

        Returns:
            Status type dictionary or None
        """
        result = db_session.execute(text("""
            SELECT * FROM status_type_get(
                p_status_type_code := :status_type_code
            )
        """), {
            "status_type_code": status_type_code
        })

        row = result.fetchone()
        if row:
            return {
                "status_type_code": row.status_type_code,
                "display_name": row.display_name,
                "description": row.description,
                "default_duration_turns": row.default_duration_turns,
                "category": row.category,
                "stackable": row.stackable
            }
        return None
