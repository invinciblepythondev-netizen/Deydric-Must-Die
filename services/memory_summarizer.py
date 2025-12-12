"""
Memory Summarization Service

Summarizes recent turn history into compressed narrative summaries.
Uses Claude Haiku for cost efficiency (10x cheaper than Sonnet).
"""

import logging
from typing import Dict, List, Optional, Any
from uuid import UUID
from datetime import datetime
from database import db
from sqlalchemy import text
from .llm.provider import LLMProvider

logger = logging.getLogger(__name__)


class MemorySummarizer:
    """
    Summarizes turn history into narrative summaries for LLM context.

    Uses cheap models (Claude Haiku) since summarization doesn't require
    the full capability of more expensive models.
    """

    def __init__(self, llm_provider: LLMProvider):
        """
        Args:
            llm_provider: LLM provider to use (should be cheap model like Haiku)
        """
        self.llm = llm_provider

    def summarize_recent_turns(
        self,
        game_id: UUID,
        start_turn: int,
        end_turn: int,
        summary_type: str = "short_term"
    ) -> UUID:
        """
        Summarize a range of turns into a narrative summary.

        Args:
            game_id: Game state ID
            start_turn: Starting turn number
            end_turn: Ending turn number
            summary_type: Type of summary (short_term, session, game)

        Returns:
            UUID of created summary

        Raises:
            ValueError: If no turns found in range
        """
        # Get turn history for this range
        turns = self._get_turns_for_range(game_id, start_turn, end_turn)

        if not turns:
            raise ValueError(
                f"No turns found for game {game_id} between turns {start_turn}-{end_turn}"
            )

        logger.info(
            f"Summarizing {len(turns)} turn records from turns {start_turn}-{end_turn}"
        )

        # Build prompt for summarization
        prompt = self._build_summarization_prompt(turns, start_turn, end_turn)

        # Generate summary using LLM (Claude Haiku)
        try:
            summary_text = self.llm.generate(
                system_prompt=self._get_system_prompt(),
                user_prompt=prompt,
                model="claude-3-5-haiku-20241022"  # Explicitly use Haiku
            )
        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
            # Fallback: create basic bullet-point summary
            summary_text = self._create_fallback_summary(turns)

        # Store summary in database
        summary_id = self._store_summary(
            game_id, start_turn, end_turn, summary_text, summary_type
        )

        logger.info(
            f"Created summary {summary_id} for turns {start_turn}-{end_turn} "
            f"({len(summary_text)} chars)"
        )

        return summary_id

    def get_recent_summaries(
        self,
        game_id: UUID,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get recent summaries for a game.

        Args:
            game_id: Game state ID
            limit: Maximum number of summaries to return

        Returns:
            List of summary dictionaries
        """
        result = db.session.execute(
            text("""
                SELECT summary_id, start_turn, end_turn, summary_text,
                       summary_type, created_at
                FROM memory.memory_summary
                WHERE game_state_id = :game_id
                ORDER BY end_turn DESC
                LIMIT :limit
            """),
            {"game_id": str(game_id), "limit": limit}
        )

        summaries = []
        for row in result:
            summaries.append({
                "summary_id": row.summary_id,
                "start_turn": row.start_turn,
                "end_turn": row.end_turn,
                "summary_text": row.summary_text,
                "summary_type": row.summary_type,
                "created_at": row.created_at
            })

        return summaries

    def _get_turns_for_range(
        self,
        game_id: UUID,
        start_turn: int,
        end_turn: int
    ) -> List[Dict[str, Any]]:
        """
        Get all turn records for a range.

        Args:
            game_id: Game state ID
            start_turn: Starting turn number
            end_turn: Ending turn number

        Returns:
            List of turn records
        """
        result = db.session.execute(
            text("""
                SELECT
                    th.turn_number,
                    th.sequence_number,
                    c.name as character_name,
                    th.action_type,
                    th.action_description,
                    th.is_private,
                    th.outcome_description,
                    th.was_successful,
                    l.name as location_name
                FROM memory.turn_history th
                JOIN character.character c ON c.character_id = th.character_id
                LEFT JOIN world.location l ON l.location_id = th.location_id
                WHERE th.game_state_id = :game_id
                  AND th.turn_number >= :start_turn
                  AND th.turn_number <= :end_turn
                ORDER BY th.turn_number ASC, th.sequence_number ASC
            """),
            {
                "game_id": str(game_id),
                "start_turn": start_turn,
                "end_turn": end_turn
            }
        )

        turns = []
        for row in result:
            turns.append({
                "turn_number": row.turn_number,
                "sequence_number": row.sequence_number,
                "character_name": row.character_name,
                "action_type": row.action_type,
                "action_description": row.action_description,
                "is_private": row.is_private,
                "outcome_description": row.outcome_description,
                "was_successful": row.was_successful,
                "location_name": row.location_name
            })

        return turns

    def _store_summary(
        self,
        game_id: UUID,
        start_turn: int,
        end_turn: int,
        summary_text: str,
        summary_type: str
    ) -> UUID:
        """
        Store summary in database.

        Args:
            game_id: Game state ID
            start_turn: Starting turn number
            end_turn: Ending turn number
            summary_text: Summary text
            summary_type: Type of summary

        Returns:
            UUID of created summary
        """
        result = db.session.execute(
            text("""
                INSERT INTO memory.memory_summary (
                    game_state_id, start_turn, end_turn,
                    summary_text, summary_type
                )
                VALUES (
                    :game_id, :start_turn, :end_turn,
                    :summary_text, :summary_type
                )
                RETURNING summary_id
            """),
            {
                "game_id": str(game_id),
                "start_turn": start_turn,
                "end_turn": end_turn,
                "summary_text": summary_text,
                "summary_type": summary_type
            }
        )

        db.session.commit()
        summary_id = result.scalar()

        return UUID(summary_id)

    def _build_summarization_prompt(
        self,
        turns: List[Dict[str, Any]],
        start_turn: int,
        end_turn: int
    ) -> str:
        """
        Build prompt for LLM summarization.

        Args:
            turns: List of turn records
            start_turn: Starting turn number
            end_turn: Ending turn number

        Returns:
            Formatted prompt string
        """
        # Format turns as narrative
        turn_text_blocks = []

        for turn in turns:
            turn_num = turn["turn_number"]
            seq_num = turn["sequence_number"]
            char_name = turn["character_name"]
            action = turn["action_description"]
            outcome = turn["outcome_description"]
            location = turn["location_name"] or "unknown location"
            is_private = turn["is_private"]

            # Format the turn entry
            entry = f"Turn {turn_num}"
            if seq_num > 0:
                entry += f".{seq_num}"
            entry += f" - {char_name} at {location}"

            if is_private:
                entry += " (private thought)"

            entry += f":\n  {action}"

            if outcome:
                entry += f"\n  Outcome: {outcome}"

            turn_text_blocks.append(entry)

        turn_text = "\n\n".join(turn_text_blocks)

        prompt = f"""
Summarize the following game events from turns {start_turn} to {end_turn}.

Create a concise narrative summary (2-4 paragraphs) that captures:
1. Major events and character actions
2. Important outcomes and consequences
3. Changes in character relationships or situations
4. Significant plot developments

DO NOT include:
- Private thoughts (marked as "private thought")
- Minor routine actions (basic movement, waiting)
- Excessive detail

Turn History:
{turn_text}

Provide a clear, coherent narrative summary:
"""
        return prompt

    def _get_system_prompt(self) -> str:
        """Get system prompt for summarization."""
        return (
            "You are a narrative summarizer for a dark fantasy role-playing game. "
            "Create concise, coherent summaries of game events that preserve important "
            "plot points and character developments while condensing routine actions. "
            "Write in past tense, third person. Focus on what happened and why it matters."
        )

    def _create_fallback_summary(self, turns: List[Dict[str, Any]]) -> str:
        """
        Create basic fallback summary if LLM fails.

        Args:
            turns: List of turn records

        Returns:
            Basic bullet-point summary
        """
        logger.warning("Using fallback summary generation (LLM failed)")

        summary_lines = ["Summary of recent events:\n"]

        # Group by turn number
        turns_by_number: Dict[int, List[Dict]] = {}
        for turn in turns:
            turn_num = turn["turn_number"]
            if turn_num not in turns_by_number:
                turns_by_number[turn_num] = []
            turns_by_number[turn_num].append(turn)

        # Create bullet points
        for turn_num in sorted(turns_by_number.keys()):
            turn_actions = turns_by_number[turn_num]
            for action in turn_actions:
                if not action["is_private"]:  # Skip private thoughts
                    char_name = action["character_name"]
                    action_desc = action["action_description"]
                    summary_lines.append(
                        f"- Turn {turn_num}: {char_name} - {action_desc}"
                    )

        return "\n".join(summary_lines)


# Example usage
if __name__ == "__main__":
    from uuid import uuid4
    logging.basicConfig(level=logging.INFO)

    # This would need to be run in Flask context
    print("Memory Summarizer Service")
    print("Run this within Flask application context to test")
