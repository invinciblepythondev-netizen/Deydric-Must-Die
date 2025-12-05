"""
Turn Model - Thin wrapper for turn history stored procedures

Handles turn/action recording and memory retrieval.
All operations use stored procedures from database/procedures/turn_procedures.sql
"""

from sqlalchemy import text
from typing import List, Dict, Any, Optional
from uuid import UUID
import logging
import json

logger = logging.getLogger(__name__)


class Turn:
    """Thin wrapper for turn history operations via stored procedures"""

    @staticmethod
    def create_action(
        db_session,
        game_state_id: UUID,
        turn_number: int,
        character_id: UUID,
        action_type: str,
        action_description: str,
        location_id: int,
        sequence_number: int = 0,
        is_private: bool = False,
        action_target_character_id: Optional[UUID] = None,
        action_target_location_id: Optional[int] = None,
        witnesses: Optional[List[UUID]] = None,
        outcome_description: Optional[str] = None,
        was_successful: Optional[bool] = None,
        significance_score: float = 0.5
    ) -> UUID:
        """
        Record a single action in turn history.

        Args:
            db_session: SQLAlchemy session
            game_state_id: Game state UUID
            turn_number: Turn number
            character_id: Character who performed action
            action_type: Type of action (think, speak, move, etc.)
            action_description: Description of the action
            location_id: Where action occurred
            sequence_number: Order within turn (0, 1, 2, ...)
            is_private: If True, only character knows (thoughts)
            action_target_character_id: Target character if applicable
            action_target_location_id: Target location if movement
            witnesses: List of character UUIDs who saw this action
            outcome_description: Result of the action
            was_successful: Success/failure if applicable
            significance_score: 0-1, for embedding priority

        Returns:
            Turn history UUID
        """
        # Convert witnesses to JSONB format
        witnesses_json = json.dumps([str(w) for w in witnesses]) if witnesses else '[]'

        result = db_session.execute(text("""
            SELECT turn_history_create(
                p_game_state_id := :game_state_id,
                p_turn_number := :turn_number,
                p_character_id := :character_id,
                p_action_type := :action_type,
                p_action_description := :action_description,
                p_location_id := :location_id,
                p_sequence_number := :sequence_number,
                p_is_private := :is_private,
                p_action_target_character_id := :action_target_character_id,
                p_action_target_location_id := :action_target_location_id,
                p_witnesses := :witnesses::jsonb,
                p_outcome_description := :outcome_description,
                p_was_successful := :was_successful,
                p_significance_score := :significance_score
            )
        """), {
            "game_state_id": str(game_state_id),
            "turn_number": turn_number,
            "character_id": str(character_id),
            "action_type": action_type,
            "action_description": action_description,
            "location_id": location_id,
            "sequence_number": sequence_number,
            "is_private": is_private,
            "action_target_character_id": str(action_target_character_id) if action_target_character_id else None,
            "action_target_location_id": action_target_location_id,
            "witnesses": witnesses_json,
            "outcome_description": outcome_description,
            "was_successful": was_successful,
            "significance_score": significance_score
        })

        turn_id = result.scalar()
        db_session.commit()

        logger.debug(
            f"Recorded action: Turn {turn_number}, Seq {sequence_number}, "
            f"Type: {action_type}, Private: {is_private}"
        )

        return UUID(turn_id)

    @staticmethod
    def get_working_memory(
        db_session,
        game_state_id: UUID,
        last_n_turns: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get working memory (last N turns, all actions).

        Args:
            db_session: SQLAlchemy session
            game_state_id: Game state UUID
            last_n_turns: Number of turns to retrieve

        Returns:
            List of action dictionaries, ordered by turn_number DESC, sequence ASC
        """
        result = db_session.execute(text("""
            SELECT * FROM turn_history_get_working_memory(
                p_game_state_id := :game_state_id,
                p_last_n_turns := :last_n_turns
            )
        """), {
            "game_state_id": str(game_state_id),
            "last_n_turns": last_n_turns
        })

        actions = []
        for row in result.fetchall():
            actions.append({
                'turn_id': row.turn_id,
                'turn_number': row.turn_number,
                'sequence_number': row.sequence_number,
                'character_id': row.character_id,
                'character_name': row.character_name,
                'action_type': row.action_type,
                'action_description': row.action_description,
                'location_id': row.location_id,
                'location_name': row.location_name,
                'is_private': row.is_private,
                'outcome_description': row.outcome_description,
                'was_successful': row.was_successful,
                'witnesses': row.witnesses,
                'created_at': row.created_at
            })

        return actions

    @staticmethod
    def get_witnessed_memory(
        db_session,
        game_state_id: UUID,
        character_id: UUID,
        last_n_turns: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get memory from character's perspective (their actions + what they witnessed).

        Excludes private actions of other characters.

        Args:
            db_session: SQLAlchemy session
            game_state_id: Game state UUID
            character_id: Character UUID
            last_n_turns: Number of turns to retrieve

        Returns:
            List of action dictionaries this character knows about
        """
        result = db_session.execute(text("""
            SELECT * FROM turn_history_get_witnessed(
                p_game_state_id := :game_state_id,
                p_character_id := :character_id,
                p_last_n_turns := :last_n_turns
            )
        """), {
            "game_state_id": str(game_state_id),
            "character_id": str(character_id),
            "last_n_turns": last_n_turns
        })

        actions = []
        for row in result.fetchall():
            actions.append({
                'turn_id': row.turn_id,
                'turn_number': row.turn_number,
                'sequence_number': row.sequence_number,
                'character_id': row.character_id,
                'character_name': row.character_name,
                'action_type': row.action_type,
                'action_description': row.action_description,
                'is_private': row.is_private,
                'outcome_description': row.outcome_description,
                'created_at': row.created_at
            })

        return actions

    @staticmethod
    def mark_as_embedded(
        db_session,
        turn_id: UUID,
        embedding_id: str
    ) -> bool:
        """
        Mark turn as embedded in vector database.

        Args:
            db_session: SQLAlchemy session
            turn_id: Turn UUID
            embedding_id: Vector DB identifier

        Returns:
            True if successful
        """
        result = db_session.execute(text("""
            SELECT turn_history_mark_embedded(
                p_turn_id := :turn_id,
                p_embedding_id := :embedding_id
            )
        """), {
            "turn_id": str(turn_id),
            "embedding_id": embedding_id
        })

        success = result.scalar()
        db_session.commit()

        return success

    @staticmethod
    def get_unembedded(
        db_session,
        min_significance: float = 0.7,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get high-significance actions that need embedding.

        Args:
            db_session: SQLAlchemy session
            min_significance: Minimum significance score (0-1)
            limit: Maximum number to return

        Returns:
            List of turn dictionaries needing embedding
        """
        result = db_session.execute(text("""
            SELECT * FROM turn_history_get_unembedded(
                p_min_significance := :min_significance,
                p_limit := :limit
            )
        """), {
            "min_significance": min_significance,
            "limit": limit
        })

        turns = []
        for row in result.fetchall():
            turns.append({
                'turn_id': row.turn_id,
                'game_state_id': row.game_state_id,
                'turn_number': row.turn_number,
                'character_id': row.character_id,
                'action_description': row.action_description,
                'outcome_description': row.outcome_description,
                'significance_score': row.significance_score
            })

        return turns


class MemorySummary:
    """Wrapper for memory summary operations"""

    @staticmethod
    def create(
        db_session,
        game_state_id: UUID,
        start_turn: int,
        end_turn: int,
        summary_text: str,
        summary_type: str = 'short_term'
    ) -> UUID:
        """
        Create a memory summary for a range of turns.

        Args:
            db_session: SQLAlchemy session
            game_state_id: Game state UUID
            start_turn: Starting turn number
            end_turn: Ending turn number
            summary_text: Summarized narrative
            summary_type: 'short_term' or 'long_term'

        Returns:
            Summary UUID
        """
        result = db_session.execute(text("""
            SELECT memory_summary_create(
                p_game_state_id := :game_state_id,
                p_start_turn := :start_turn,
                p_end_turn := :end_turn,
                p_summary_text := :summary_text,
                p_summary_type := :summary_type
            )
        """), {
            "game_state_id": str(game_state_id),
            "start_turn": start_turn,
            "end_turn": end_turn,
            "summary_text": summary_text,
            "summary_type": summary_type
        })

        summary_id = result.scalar()
        db_session.commit()

        logger.info(
            f"Created memory summary for turns {start_turn}-{end_turn} "
            f"({summary_type})"
        )

        return UUID(summary_id)

    @staticmethod
    def get_summaries(
        db_session,
        game_state_id: UUID,
        summary_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get memory summaries for a game.

        Args:
            db_session: SQLAlchemy session
            game_state_id: Game state UUID
            summary_type: Filter by type ('short_term' or 'long_term'), or None for all

        Returns:
            List of summary dictionaries
        """
        result = db_session.execute(text("""
            SELECT * FROM memory_summary_get(
                p_game_state_id := :game_state_id,
                p_summary_type := :summary_type
            )
        """), {
            "game_state_id": str(game_state_id),
            "summary_type": summary_type
        })

        summaries = []
        for row in result.fetchall():
            summaries.append({
                'summary_id': row.summary_id,
                'start_turn': row.start_turn,
                'end_turn': row.end_turn,
                'summary_text': row.summary_text,
                'summary_type': row.summary_type,
                'created_at': row.created_at
            })

        return summaries
