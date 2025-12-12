"""Backfill memory summaries for existing game turns."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from database import db
from sqlalchemy import text
from uuid import uuid4
from services.llm_service import get_unified_llm_service
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def backfill_summaries():
    """Create memory summaries for all past 10-turn windows."""
    with app.app_context():
        # Get active game
        game = db.session.execute(
            text("SELECT game_state_id, current_turn FROM game.game_state WHERE is_active = TRUE LIMIT 1")
        ).fetchone()

        if not game:
            print("No active game found")
            return

        game_id = game[0]
        current_turn = game[1]

        print(f"Game ID: {game_id}")
        print(f"Current turn: {current_turn}")

        # Calculate which summaries should exist
        summaries_needed = []
        for turn in range(10, current_turn + 1, 10):
            summaries_needed.append(turn)

        print(f"Summaries needed for turns ending at: {summaries_needed}")

        # Check which summaries already exist
        existing = db.session.execute(
            text("SELECT end_turn FROM memory.memory_summary WHERE game_state_id = :game_id ORDER BY end_turn"),
            {"game_id": str(game_id)}
        ).fetchall()

        existing_turns = [e[0] for e in existing]
        print(f"Existing summaries for turns: {existing_turns}")

        # Create missing summaries
        llm_service = get_unified_llm_service()

        for end_turn in summaries_needed:
            if end_turn in existing_turns:
                print(f"Summary for turns {end_turn-9}-{end_turn} already exists, skipping")
                continue

            start_turn = max(1, end_turn - 9)
            print(f"\nCreating summary for turns {start_turn}-{end_turn}...")

            # Fetch turn history
            turns = db.session.execute(
                text("""
                    SELECT
                        th.turn_number,
                        c.name as character_name,
                        th.action_type,
                        th.action_description
                    FROM memory.turn_history th
                    JOIN character.character c ON th.character_id = c.character_id
                    WHERE th.game_state_id = :game_id
                        AND th.turn_number >= :start_turn
                        AND th.turn_number <= :end_turn
                        AND th.action_type != 'atmospheric'
                    ORDER BY th.turn_number ASC, th.sequence_number ASC
                """),
                {"game_id": str(game_id), "start_turn": start_turn, "end_turn": end_turn}
            ).fetchall()

            if not turns:
                print(f"  No turns found, skipping")
                continue

            # Format turns for summarization
            turn_data = []
            for turn in turns:
                turn_data.append({
                    'turn_number': turn[0],
                    'action_description': f"{turn[1]} ({turn[2]}): {turn[3]}"
                })

            print(f"  Found {len(turn_data)} action entries")

            # Generate summary using LLM
            try:
                summary = llm_service.summarize_memory(turn_data, importance="routine")
                print(f"  Generated summary ({len(summary)} chars)")

                # Store summary in database
                summary_id = uuid4()
                db.session.execute(
                    text("""
                        INSERT INTO memory.memory_summary (
                            summary_id, game_state_id, start_turn, end_turn,
                            summary_text, importance, created_at
                        ) VALUES (
                            :summary_id, :game_id, :start_turn, :end_turn,
                            :summary_text, :importance, NOW()
                        )
                    """),
                    {
                        "summary_id": str(summary_id),
                        "game_id": str(game_id),
                        "start_turn": start_turn,
                        "end_turn": end_turn,
                        "summary_text": summary,
                        "importance": "routine"
                    }
                )
                db.session.commit()
                print(f"  Saved summary {summary_id}")

            except Exception as e:
                print(f"  Error generating summary: {e}")
                import traceback
                traceback.print_exc()

        print("\nBackfill complete!")

        # Show final count
        final_count = db.session.execute(
            text("SELECT COUNT(*) FROM memory.memory_summary WHERE game_state_id = :game_id"),
            {"game_id": str(game_id)}
        ).fetchone()[0]

        print(f"Total summaries now: {final_count}")


if __name__ == "__main__":
    backfill_summaries()
