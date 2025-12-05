"""
Wound Model - Thin wrapper for wound tracking stored procedures

Handles injury creation, tracking, and treatment.
All operations use stored procedures from database/procedures/wound_procedures.sql
"""

from sqlalchemy import text
from typing import List, Dict, Any, Optional
from uuid import UUID
import logging

logger = logging.getLogger(__name__)


class Wound:
    """Thin wrapper for wound operations via stored procedures"""

    @staticmethod
    def list_by_character(db_session, character_id: UUID) -> List[Dict[str, Any]]:
        """
        Get all wounds for a character, ordered by severity.

        Args:
            db_session: SQLAlchemy session
            character_id: Character UUID

        Returns:
            List of wound dictionaries
        """
        result = db_session.execute(text("""
            SELECT * FROM character_wound_list(:character_id)
        """), {
            "character_id": str(character_id)
        })

        wounds = []
        for row in result.fetchall():
            wounds.append({
                'wound_id': row.wound_id,
                'character_id': row.character_id,
                'body_part': row.body_part,
                'wound_type': row.wound_type,
                'severity': row.severity,
                'is_bleeding': row.is_bleeding,
                'is_infected': row.is_infected,
                'is_treated': row.is_treated,
                'turns_since_injury': row.turns_since_injury,
                'treatment_history': row.treatment_history,
                'description': row.description,
                'caused_by': row.caused_by,
                'occurred_at_turn': row.occurred_at_turn,
                'created_at': row.created_at,
                'updated_at': row.updated_at
            })

        return wounds

    @staticmethod
    def get(db_session, wound_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get a specific wound.

        Args:
            db_session: SQLAlchemy session
            wound_id: Wound UUID

        Returns:
            Wound dictionary or None
        """
        result = db_session.execute(text("""
            SELECT * FROM character_wound_get(:wound_id)
        """), {
            "wound_id": str(wound_id)
        })

        row = result.fetchone()
        if not row:
            return None

        return {
            'wound_id': row.wound_id,
            'character_id': row.character_id,
            'body_part': row.body_part,
            'wound_type': row.wound_type,
            'severity': row.severity,
            'is_bleeding': row.is_bleeding,
            'is_infected': row.is_infected,
            'is_treated': row.is_treated,
            'turns_since_injury': row.turns_since_injury,
            'treatment_history': row.treatment_history,
            'description': row.description,
            'caused_by': row.caused_by,
            'occurred_at_turn': row.occurred_at_turn,
            'created_at': row.created_at,
            'updated_at': row.updated_at
        }

    @staticmethod
    def create(
        db_session,
        character_id: UUID,
        body_part: str,
        wound_type: str,
        severity: str,
        is_bleeding: bool = False,
        description: Optional[str] = None,
        caused_by: Optional[str] = None,
        occurred_at_turn: Optional[int] = None
    ) -> UUID:
        """
        Create a new wound.

        Args:
            db_session: SQLAlchemy session
            character_id: Character UUID
            body_part: Where (head, torso, left_arm, right_arm, left_leg, right_leg)
            wound_type: Type (cut, stab, blunt_trauma, burn, infection)
            severity: Severity (minor, moderate, severe, critical, mortal)
            is_bleeding: Whether actively bleeding
            description: Detailed description
            caused_by: What/who caused it
            occurred_at_turn: Turn number when it occurred

        Returns:
            Wound UUID
        """
        result = db_session.execute(text("""
            SELECT character_wound_create(
                p_character_id := :character_id,
                p_body_part := :body_part,
                p_wound_type := :wound_type,
                p_severity := :severity,
                p_is_bleeding := :is_bleeding,
                p_description := :description,
                p_caused_by := :caused_by,
                p_occurred_at_turn := :occurred_at_turn
            )
        """), {
            "character_id": str(character_id),
            "body_part": body_part,
            "wound_type": wound_type,
            "severity": severity,
            "is_bleeding": is_bleeding,
            "description": description,
            "caused_by": caused_by,
            "occurred_at_turn": occurred_at_turn
        })

        wound_id = result.scalar()
        db_session.commit()

        logger.info(
            f"Created wound for character {character_id}: "
            f"{severity} {wound_type} on {body_part}"
        )

        return UUID(wound_id)

    @staticmethod
    def update(
        db_session,
        wound_id: UUID,
        is_bleeding: Optional[bool] = None,
        is_infected: Optional[bool] = None,
        is_treated: Optional[bool] = None,
        severity: Optional[str] = None,
        turns_since_injury: Optional[int] = None
    ) -> bool:
        """
        Update wound status.

        Args:
            db_session: SQLAlchemy session
            wound_id: Wound UUID
            is_bleeding: Update bleeding status
            is_infected: Update infection status
            is_treated: Update treatment status
            severity: Update severity level
            turns_since_injury: Update turn counter

        Returns:
            True if successful
        """
        result = db_session.execute(text("""
            SELECT character_wound_update(
                p_wound_id := :wound_id,
                p_is_bleeding := :is_bleeding,
                p_is_infected := :is_infected,
                p_is_treated := :is_treated,
                p_severity := :severity,
                p_turns_since_injury := :turns_since_injury
            )
        """), {
            "wound_id": str(wound_id),
            "is_bleeding": is_bleeding,
            "is_infected": is_infected,
            "is_treated": is_treated,
            "severity": severity,
            "turns_since_injury": turns_since_injury
        })

        success = result.scalar()
        db_session.commit()

        if success:
            logger.debug(f"Updated wound {wound_id}")

        return success

    @staticmethod
    def add_treatment(
        db_session,
        wound_id: UUID,
        treater_character_id: UUID,
        treatment_type: str,
        was_successful: bool,
        turn_number: int
    ) -> bool:
        """
        Add a treatment record to wound history.

        Args:
            db_session: SQLAlchemy session
            wound_id: Wound UUID
            treater_character_id: Who treated it
            treatment_type: Type of treatment (bandage, herbs, surgery, etc.)
            was_successful: Whether treatment worked
            turn_number: When it was treated

        Returns:
            True if successful
        """
        result = db_session.execute(text("""
            SELECT character_wound_add_treatment(
                p_wound_id := :wound_id,
                p_treater_character_id := :treater_character_id,
                p_treatment_type := :treatment_type,
                p_was_successful := :was_successful,
                p_turn_number := :turn_number
            )
        """), {
            "wound_id": str(wound_id),
            "treater_character_id": str(treater_character_id),
            "treatment_type": treatment_type,
            "was_successful": was_successful,
            "turn_number": turn_number
        })

        success = result.scalar()
        db_session.commit()

        if success:
            logger.info(
                f"Wound {wound_id} treated by {treater_character_id} "
                f"({treatment_type}, success={was_successful})"
            )

        return success

    @staticmethod
    def age_all_wounds(db_session) -> int:
        """
        Increment turns_since_injury for all wounds.
        Call this once per turn.

        Args:
            db_session: SQLAlchemy session

        Returns:
            Number of wounds aged
        """
        result = db_session.execute(text("""
            SELECT character_wound_age_all()
        """))

        count = result.scalar()
        db_session.commit()

        logger.debug(f"Aged {count} wounds")

        return count

    @staticmethod
    def delete(db_session, wound_id: UUID) -> bool:
        """
        Delete a wound (healed).

        Args:
            db_session: SQLAlchemy session
            wound_id: Wound UUID

        Returns:
            True if deleted
        """
        result = db_session.execute(text("""
            SELECT character_wound_delete(:wound_id)
        """), {
            "wound_id": str(wound_id)
        })

        success = result.scalar()
        db_session.commit()

        if success:
            logger.info(f"Deleted wound {wound_id} (healed)")

        return success

    @staticmethod
    def get_summary(db_session, character_id: UUID) -> str:
        """
        Get a natural language summary of character's wounds.

        Args:
            db_session: SQLAlchemy session
            character_id: Character UUID

        Returns:
            Summary string like "Healthy" or "Wounded: 2 injuries (1 severe)"
        """
        wounds = Wound.list_by_character(db_session, character_id)

        if not wounds:
            return "Healthy"

        # Count by severity
        severity_counts = {}
        for wound in wounds:
            sev = wound['severity']
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        # Build summary
        total = len(wounds)
        if total == 1:
            wound = wounds[0]
            return f"Wounded: {wound['severity']} {wound['wound_type']} on {wound['body_part']}"

        # Multiple wounds
        parts = [f"{count} {sev}" for sev, count in severity_counts.items()]
        return f"Wounded: {total} injuries ({', '.join(parts)})"
