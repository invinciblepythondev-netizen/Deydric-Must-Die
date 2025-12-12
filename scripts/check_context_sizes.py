"""Check context sizes for atmospheric descriptions and action generation."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from database import db
from sqlalchemy import text

with app.app_context():
    # Check location descriptions
    print("=" * 60)
    print("LOCATION DESCRIPTIONS")
    print("=" * 60)
    locations = db.session.execute(
        text("SELECT name, description FROM world.location")
    ).fetchall()

    for loc in locations:
        print(f"\n{loc[0]}:")
        print(f"  Length: {len(loc[1])} characters")
        print(f"  Preview: {loc[1][:150]}...")

    # Check character info
    print("\n" + "=" * 60)
    print("CHARACTER CURRENT STATE")
    print("=" * 60)
    characters = db.session.execute(
        text("""
            SELECT name, current_stance, current_clothing, physical_appearance
            FROM character.character
        """)
    ).fetchall()

    for char in characters:
        print(f"\n{char[0]}:")
        print(f"  Stance: {char[1]}")
        print(f"  Clothing: {len(char[2]) if char[2] else 0} chars")
        print(f"  Appearance: {len(char[3]) if char[3] else 0} chars")

    # Check recent history size
    print("\n" + "=" * 60)
    print("RECENT HISTORY SIZE")
    print("=" * 60)
    game = db.session.execute(
        text("SELECT game_state_id FROM game.game_state WHERE is_active = TRUE LIMIT 1")
    ).fetchone()

    if game:
        history = db.session.execute(
            text("""
                SELECT c.name, th.action_description
                FROM memory.turn_history th
                JOIN character.character c ON th.character_id = c.character_id
                WHERE th.game_state_id = :game_id
                ORDER BY th.turn_number DESC, th.sequence_number DESC
                LIMIT 3
            """),
            {"game_id": str(game[0])}
        ).fetchall()

        recent_history = " ".join([f"{h[0]}: {h[1]}" for h in reversed(history)])
        print(f"Recent history length: {len(recent_history)} characters")
        print(f"Preview: {recent_history[:200]}...")

    # Check if memory summaries exist
    print("\n" + "=" * 60)
    print("MEMORY SUMMARIES")
    print("=" * 60)
    summaries = db.session.execute(
        text("SELECT COUNT(*) FROM memory.memory_summary")
    ).fetchone()
    print(f"Total memory summaries: {summaries[0]}")

    # Check turn count
    if game:
        turn_count = db.session.execute(
            text("""
                SELECT COUNT(DISTINCT turn_number)
                FROM memory.turn_history
                WHERE game_state_id = :game_id
            """),
            {"game_id": str(game[0])}
        ).fetchone()
        print(f"Total turns in game: {turn_count[0]}")
