"""
Create initial game state for character integration.

This script creates a game state record which is required for
associating objectives with characters.
"""

import os
import sys
from pathlib import Path
from uuid import uuid4
from sqlalchemy import text
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Must import after adding to path
from app import app
from database import db

# Load environment variables
load_dotenv()


def create_game_state():
    """Create initial game state."""

    print("=" * 60)
    print("Creating Initial Game State")
    print("=" * 60)

    with app.app_context():
        try:
            # Check if a game already exists
            existing = db.session.execute(
                text("SELECT game_state_id FROM game.game_state LIMIT 1")
            ).fetchone()

            if existing:
                game_id = existing[0]
                print(f"\n[INFO] Game state already exists: {game_id}")
                print("Using existing game state for character integration")
                return game_id

            # Create new game state
            game_id = uuid4()

            print(f"\nCreating new game state...")
            print(f"  Game ID: {game_id}")

            db.session.execute(
                text("""
                    INSERT INTO game.game_state (
                        game_state_id,
                        current_turn,
                        is_active,
                        created_at
                    ) VALUES (
                        :game_id,
                        0,
                        TRUE,
                        CURRENT_TIMESTAMP
                    )
                """),
                {"game_id": str(game_id)}
            )

            db.session.commit()

            print(f"  [OK] Game state created successfully")

            # Verify creation
            result = db.session.execute(
                text("""
                    SELECT game_state_id, current_turn, is_active, created_at
                    FROM game.game_state
                    WHERE game_state_id = :game_id
                """),
                {"game_id": str(game_id)}
            ).fetchone()

            if result:
                print(f"\n  Verification:")
                print(f"    Game ID: {result[0]}")
                print(f"    Turn: {result[1]}")
                print(f"    Active: {result[2]}")
                print(f"    Created: {result[3]}")

            print("\n" + "=" * 60)
            print("[OK] Game state ready for character integration")
            print("=" * 60)

            return game_id

        except Exception as e:
            print(f"\n[FAIL] Error creating game state: {str(e)}")
            db.session.rollback()
            raise


if __name__ == '__main__':
    try:
        game_id = create_game_state()
        print(f"\nGame ID to use for character integration: {game_id}")
        exit(0)
    except Exception as e:
        print(f"\nFailed to create game state: {e}")
        exit(1)
