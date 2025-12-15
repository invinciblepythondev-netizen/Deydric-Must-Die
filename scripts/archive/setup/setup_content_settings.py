"""
Setup content_settings table and populate it for existing game states.

This script:
1. Creates the content_settings table
2. Creates the stored procedures
3. Populates default settings for existing game states
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

def run_migration():
    """Run the content_settings migration."""
    engine = create_engine(get_database_url())
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        print("=" * 60)
        print("STEP 1: Creating content_settings table and procedures")
        print("=" * 60)

        # Read migration file
        migration_file = Path(__file__).parent.parent / 'database' / 'migrations' / '001_add_content_settings.sql'

        if not migration_file.exists():
            raise FileNotFoundError(f"Migration file not found: {migration_file}")

        with open(migration_file, 'r') as f:
            migration_sql = f.read()

        # Execute migration
        session.execute(text(migration_sql))
        session.commit()

        print("✓ Table and procedures created successfully\n")

    except Exception as e:
        session.rollback()
        print(f"❌ Error creating table: {e}")
        raise
    finally:
        session.close()

def populate_settings(preset='Unrestricted'):
    """Populate content settings for existing game states."""
    engine = create_engine(get_database_url())
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        print("=" * 60)
        print(f"STEP 2: Populating content settings (preset: {preset})")
        print("=" * 60)

        # Get all game states
        result = session.execute(text("""
            SELECT game_state_id, created_at
            FROM game.game_state
            ORDER BY created_at DESC
        """))

        game_states = result.fetchall()

        if not game_states:
            print("No game states found - nothing to populate.\n")
            return

        print(f"Found {len(game_states)} game state(s)\n")

        # For each game state, create content settings
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
                print(f"  ✓ Game state {game_state_id} - already has settings")
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

                print(f"  ✓ Game state {game_state_id} - created {preset} settings")
                created_count += 1

        # Commit changes
        session.commit()

        print(f"\nSummary:")
        print(f"  Created: {created_count}")
        print(f"  Already existed: {existing_count}")
        print(f"  Total: {len(game_states)}\n")

    except Exception as e:
        session.rollback()
        print(f"❌ Error populating settings: {e}")
        raise
    finally:
        session.close()

def update_mood_procedure():
    """Update the mood procedure to handle missing content_settings."""
    engine = create_engine(get_database_url())
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        print("=" * 60)
        print("STEP 3: Updating mood procedure")
        print("=" * 60)

        # Read mood procedures file
        procedures_file = Path(__file__).parent.parent / 'database' / 'procedures' / 'mood_procedures.sql'

        if not procedures_file.exists():
            raise FileNotFoundError(f"Procedures file not found: {procedures_file}")

        with open(procedures_file, 'r') as f:
            procedures_sql = f.read()

        # Execute procedures
        session.execute(text(procedures_sql))
        session.commit()

        print("✓ Mood procedure updated successfully\n")

    except Exception as e:
        session.rollback()
        print(f"❌ Error updating procedure: {e}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Setup content_settings table')
    parser.add_argument(
        '--preset',
        type=str,
        default='Unrestricted',
        choices=['G', 'PG', 'PG-13', 'R', 'Mature', 'Unrestricted'],
        help='Rating preset for existing games (default: Unrestricted for development)'
    )

    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("Content Settings Setup")
    print("=" * 60 + "\n")

    try:
        # Step 1: Run migration
        run_migration()

        # Step 2: Populate settings for existing games
        populate_settings(preset=args.preset)

        # Step 3: Update mood procedure
        update_mood_procedure()

        print("=" * 60)
        print("✓ Setup completed successfully!")
        print("=" * 60 + "\n")

    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ Setup failed: {e}")
        print("=" * 60 + "\n")
        sys.exit(1)
