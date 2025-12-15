"""
Populate content_settings table for existing game states.

This script creates default content settings (PG-13) for all existing game states
that don't have content settings yet.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Load environment variables
load_dotenv()

def get_database_url():
    """Get database URL from environment."""
    url = os.getenv('NEON_DATABASE_URL')
    if not url:
        raise ValueError("NEON_DATABASE_URL not found in environment")

    # Convert to psycopg3 format
    if 'postgresql://' in url:
        url = url.replace('postgresql://', 'postgresql+psycopg://')

    return url

def populate_content_settings(preset='PG-13'):
    """
    Populate content settings for all existing game states.

    Args:
        preset: Rating preset to use (G, PG, PG-13, R, Mature, Unrestricted)
    """
    # Create engine
    engine = create_engine(get_database_url())
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        print(f"Populating content settings with preset: {preset}")
        print("=" * 60)

        # Get all game states
        result = session.execute(text("""
            SELECT game_state_id, created_at
            FROM game.game_state
            ORDER BY created_at DESC
        """))

        game_states = result.fetchall()

        if not game_states:
            print("No game states found.")
            return

        print(f"Found {len(game_states)} game state(s)\n")

        # For each game state, create content settings if not exists
        created_count = 0
        existing_count = 0

        for game_state in game_states:
            game_state_id = game_state.game_state_id

            # Check if settings already exist
            existing = session.execute(text("""
                SELECT content_settings_id
                FROM game.content_settings
                WHERE game_state_id = :game_state_id
            """), {"game_state_id": str(game_state_id)}).fetchone()

            if existing:
                print(f"[OK] Game state {game_state_id} - already has content settings")
                existing_count += 1
            else:
                # Create settings using preset
                session.execute(text("""
                    SELECT content_settings_set_from_preset(
                        :game_state_id,
                        :preset
                    )
                """), {
                    "game_state_id": str(game_state_id),
                    "preset": preset
                })

                print(f"[OK] Game state {game_state_id} - created {preset} settings")
                created_count += 1

        # Commit changes
        session.commit()

        print("\n" + "=" * 60)
        print(f"Summary:")
        print(f"  Created: {created_count}")
        print(f"  Already existed: {existing_count}")
        print(f"  Total: {len(game_states)}")
        print("=" * 60)

    except Exception as e:
        session.rollback()
        print(f"\n[ERROR] {e}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Populate content settings for game states')
    parser.add_argument(
        '--preset',
        type=str,
        default='PG-13',
        choices=['G', 'PG', 'PG-13', 'R', 'Mature', 'Unrestricted'],
        help='Rating preset to use (default: PG-13)'
    )

    args = parser.parse_args()

    populate_content_settings(preset=args.preset)
