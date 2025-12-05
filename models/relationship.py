"""
Relationship Model - Thin wrapper for character relationship stored procedures

Handles character-to-character relationships (trust, fear, respect).
All operations use stored procedures from database/procedures/relationship_procedures.sql
"""

from sqlalchemy import text
from typing import List, Dict, Any, Optional
from uuid import UUID
import logging

logger = logging.getLogger(__name__)


class Relationship:
    """Thin wrapper for relationship operations via stored procedures"""

    @staticmethod
    def get(
        db_session,
        source_character_id: UUID,
        target_character_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """
        Get relationship from source to target character.

        Note: Relationships are directional. A→B may differ from B→A.

        Args:
            db_session: SQLAlchemy session
            source_character_id: Character viewing the relationship
            target_character_id: Character being viewed

        Returns:
            Relationship dictionary or None if doesn't exist
        """
        result = db_session.execute(text("""
            SELECT * FROM character_relationship_get(
                p_source_character_id := :source_id,
                p_target_character_id := :target_id
            )
        """), {
            "source_id": str(source_character_id),
            "target_id": str(target_character_id)
        })

        row = result.fetchone()
        if not row:
            return None

        return {
            'relationship_id': row.relationship_id,
            'source_character_id': row.source_character_id,
            'target_character_id': row.target_character_id,
            'trust': row.trust,
            'fear': row.fear,
            'respect': row.respect,
            'relationship_type': row.relationship_type,
            'interaction_count': row.interaction_count,
            'last_interaction_turn': row.last_interaction_turn,
            'notes': row.notes,
            'created_at': row.created_at,
            'updated_at': row.updated_at
        }

    @staticmethod
    def list_for_character(db_session, character_id: UUID) -> List[Dict[str, Any]]:
        """
        Get all relationships where character is the source.

        Args:
            db_session: SQLAlchemy session
            character_id: Character UUID

        Returns:
            List of relationship dictionaries
        """
        result = db_session.execute(text("""
            SELECT * FROM character_relationship_list(:character_id)
        """), {
            "character_id": str(character_id)
        })

        relationships = []
        for row in result.fetchall():
            relationships.append({
                'relationship_id': row.relationship_id,
                'target_character_id': row.target_character_id,
                'target_name': row.target_name,
                'trust': row.trust,
                'fear': row.fear,
                'respect': row.respect,
                'relationship_type': row.relationship_type,
                'interaction_count': row.interaction_count,
                'last_interaction_turn': row.last_interaction_turn
            })

        return relationships

    @staticmethod
    def create_or_update(
        db_session,
        source_character_id: UUID,
        target_character_id: UUID,
        trust: float = 0.5,
        fear: float = 0.0,
        respect: float = 0.5,
        relationship_type: str = 'neutral',
        last_interaction_turn: Optional[int] = None,
        notes: Optional[str] = None
    ) -> UUID:
        """
        Create or update a relationship.

        Args:
            db_session: SQLAlchemy session
            source_character_id: Character viewing the relationship
            target_character_id: Character being viewed
            trust: Trust level (0.0-1.0)
            fear: Fear level (0.0-1.0)
            respect: Respect level (0.0-1.0)
            relationship_type: Type (friend, enemy, family, romantic, professional, neutral, stranger)
            last_interaction_turn: Turn of last interaction
            notes: Additional notes

        Returns:
            Relationship UUID
        """
        result = db_session.execute(text("""
            SELECT character_relationship_upsert(
                p_source_character_id := :source_id,
                p_target_character_id := :target_id,
                p_trust := :trust,
                p_fear := :fear,
                p_respect := :respect,
                p_relationship_type := :relationship_type,
                p_last_interaction_turn := :last_interaction_turn,
                p_notes := :notes
            )
        """), {
            "source_id": str(source_character_id),
            "target_id": str(target_character_id),
            "trust": trust,
            "fear": fear,
            "respect": respect,
            "relationship_type": relationship_type,
            "last_interaction_turn": last_interaction_turn,
            "notes": notes
        })

        relationship_id = result.scalar()
        db_session.commit()

        logger.info(
            f"Updated relationship: {source_character_id} → {target_character_id} "
            f"(trust={trust:.2f}, fear={fear:.2f}, respect={respect:.2f})"
        )

        return UUID(relationship_id)

    @staticmethod
    def adjust(
        db_session,
        source_character_id: UUID,
        target_character_id: UUID,
        trust_delta: float = 0.0,
        fear_delta: float = 0.0,
        respect_delta: float = 0.0,
        interaction_turn: Optional[int] = None
    ) -> UUID:
        """
        Adjust relationship metrics by delta amounts.

        Creates relationship if it doesn't exist (starts at neutral defaults).

        Args:
            db_session: SQLAlchemy session
            source_character_id: Character viewing the relationship
            target_character_id: Character being viewed
            trust_delta: Amount to add/subtract from trust (-1.0 to +1.0)
            fear_delta: Amount to add/subtract from fear
            respect_delta: Amount to add/subtract from respect
            interaction_turn: Turn number when this interaction occurred

        Returns:
            Relationship UUID
        """
        result = db_session.execute(text("""
            SELECT character_relationship_adjust(
                p_source_character_id := :source_id,
                p_target_character_id := :target_id,
                p_trust_delta := :trust_delta,
                p_fear_delta := :fear_delta,
                p_respect_delta := :respect_delta,
                p_interaction_turn := :interaction_turn
            )
        """), {
            "source_id": str(source_character_id),
            "target_id": str(target_character_id),
            "trust_delta": trust_delta,
            "fear_delta": fear_delta,
            "respect_delta": respect_delta,
            "interaction_turn": interaction_turn
        })

        relationship_id = result.scalar()
        db_session.commit()

        logger.info(
            f"Adjusted relationship: {source_character_id} → {target_character_id} "
            f"(Δtrust={trust_delta:+.2f}, Δfear={fear_delta:+.2f}, Δrespect={respect_delta:+.2f})"
        )

        return UUID(relationship_id)

    @staticmethod
    def delete(
        db_session,
        source_character_id: UUID,
        target_character_id: UUID
    ) -> bool:
        """
        Delete a relationship.

        Args:
            db_session: SQLAlchemy session
            source_character_id: Source character
            target_character_id: Target character

        Returns:
            True if deleted
        """
        result = db_session.execute(text("""
            SELECT character_relationship_delete(
                p_source_character_id := :source_id,
                p_target_character_id := :target_id
            )
        """), {
            "source_id": str(source_character_id),
            "target_id": str(target_character_id)
        })

        success = result.scalar()
        db_session.commit()

        if success:
            logger.info(f"Deleted relationship: {source_character_id} → {target_character_id}")

        return success

    @staticmethod
    def get_summary(
        db_session,
        source_character_id: UUID,
        target_character_id: UUID
    ) -> str:
        """
        Get a natural language summary of the relationship.

        Args:
            db_session: SQLAlchemy session
            source_character_id: Source character
            target_character_id: Target character

        Returns:
            Summary string like "Trusting (70%), Fearful (40%), Respectful (60%)"
        """
        rel = Relationship.get(db_session, source_character_id, target_character_id)

        if not rel:
            return "No established relationship (strangers)"

        # Convert 0-1 to percentages
        trust_pct = int(rel['trust'] * 100)
        fear_pct = int(rel['fear'] * 100)
        respect_pct = int(rel['respect'] * 100)

        # Categorize trust
        if trust_pct >= 70:
            trust_label = "Trusting"
        elif trust_pct >= 40:
            trust_label = "Neutral"
        else:
            trust_label = "Distrustful"

        # Categorize fear
        if fear_pct >= 70:
            fear_label = "Very fearful"
        elif fear_pct >= 40:
            fear_label = "Wary"
        else:
            fear_label = "Unafraid"

        # Categorize respect
        if respect_pct >= 70:
            respect_label = "Respectful"
        elif respect_pct >= 40:
            respect_label = "Neutral"
        else:
            respect_label = "Disrespectful"

        parts = [
            f"{trust_label} ({trust_pct}%)",
            f"{fear_label} ({fear_pct}%)",
            f"{respect_label} ({respect_pct}%)"
        ]

        return ", ".join(parts)

    @staticmethod
    def get_relationships_for_location(
        db_session,
        character_id: UUID,
        location_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get character's relationships with all other characters at a location.

        Args:
            db_session: SQLAlchemy session
            character_id: Character UUID
            location_id: Location ID

        Returns:
            List of relationship dictionaries with character info
        """
        from models.character import Character
        from models.location import Location

        # Get all characters at location
        characters_at_location = Location.get_characters_at(db_session, location_id)

        # Get relationships with each
        relationships = []
        for char in characters_at_location:
            # Skip self
            if char['character_id'] == character_id:
                continue

            rel = Relationship.get(db_session, character_id, char['character_id'])

            relationships.append({
                'target_character_id': char['character_id'],
                'target_name': char['name'],
                'target_appearance': char['physical_appearance'],
                'target_stance': char['current_stance'],
                'trust': rel['trust'] if rel else 0.5,
                'fear': rel['fear'] if rel else 0.0,
                'respect': rel['respect'] if rel else 0.5,
                'relationship_type': rel['relationship_type'] if rel else 'stranger',
                'interaction_count': rel['interaction_count'] if rel else 0
            })

        return relationships
