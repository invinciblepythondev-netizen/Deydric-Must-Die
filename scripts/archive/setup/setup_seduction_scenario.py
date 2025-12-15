"""
Setup script for the seduction scenario.

Scenario:
- Location: West Guest Room (Deydric's castle)
- Player Character: Sir Gelathorn Findraell
- AI Character: Fizrae (sent to seduce Sir Gelathorn and get his allegiance)
- Time: Middle of the night
- Initial objectives: Fizrae tries to seduce, Gelathorn decides how to respond
"""

import os
import sys
import json
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


def setup_scenario():
    """Set up the seduction scenario."""

    print("=" * 60)
    print("Setting Up Seduction Scenario")
    print("=" * 60)

    with app.app_context():
        try:
            # Get or create game state
            existing_game = db.session.execute(
                text("SELECT game_state_id FROM game.game_state WHERE is_active = TRUE LIMIT 1")
            ).fetchone()

            if existing_game:
                game_id = existing_game[0]
                print(f"\n[INFO] Using existing game: {game_id}")
            else:
                game_id = uuid4()
                print(f"\n[INFO] Creating new game: {game_id}")
                db.session.execute(
                    text("""
                        INSERT INTO game.game_state (game_state_id, current_turn, is_active)
                        VALUES (:game_id, 0, TRUE)
                    """),
                    {"game_id": str(game_id)}
                )
                db.session.commit()

            # Get West Guest Room location
            location = db.session.execute(
                text("""
                    SELECT location_id, name FROM world.location
                    WHERE LOWER(name) LIKE '%west guest room%'
                    LIMIT 1
                """)
            ).fetchone()

            if not location:
                print("\n[WARN] West Guest Room not found in database")
                print("Creating West Guest Room...")
                location_id = 3  # Use integer ID
                db.session.execute(
                    text("""
                        INSERT INTO world.location (
                            location_id, name, description,
                            connected_locations, time_of_day, created_at
                        ) VALUES (
                            :location_id,
                            'West Guest Room',
                            'A comfortable guest chamber in Deydric''s castle. The room features a canopied bed with velvet curtains, a writing desk by the window, and a small fireplace. Moonlight filters through tall windows, casting pale light across the stone floor. The air is cool and quiet in the depths of night.',
                            '{"hallway": "door", "balcony": "window"}',
                            'night',
                            CURRENT_TIMESTAMP
                        )
                    """),
                    {"location_id": location_id}
                )
                db.session.commit()
                print(f"  [OK] Created West Guest Room (ID: {location_id})")
            else:
                location_id = location[0]
                print(f"\n[OK] Found location: {location[1]} (ID: {location_id})")

            # Get Sir Gelarthon
            gelathorn = db.session.execute(
                text("""
                    SELECT character_id, name FROM character.character
                    WHERE LOWER(name) LIKE '%gelarthon%'
                    LIMIT 1
                """)
            ).fetchone()

            if not gelathorn:
                print("\n[ERROR] Sir Gelarthon not found in database!")
                print("Please run import_characters_json.py first to import characters")
                return False

            gelathorn_id = gelathorn[0]
            print(f"[OK] Found {gelathorn[1]} (ID: {gelathorn_id})")

            # Get Fizrae
            fizrae = db.session.execute(
                text("""
                    SELECT character_id, name FROM character.character
                    WHERE LOWER(name) LIKE '%fizrae%'
                    LIMIT 1
                """)
            ).fetchone()

            if not fizrae:
                print("\n[ERROR] Fizrae not found in database!")
                print("Please run import_characters_json.py first to import characters")
                return False

            fizrae_id = fizrae[0]
            print(f"[OK] Found {fizrae[1]} (ID: {fizrae_id})")

            # Place both characters in West Guest Room
            print(f"\n[INFO] Placing characters in West Guest Room...")

            db.session.execute(
                text("""
                    UPDATE character.character
                    SET current_location_id = :location_id
                    WHERE character_id = :gelathorn_id
                """),
                {"location_id": location_id, "gelathorn_id": str(gelathorn_id)}
            )

            db.session.execute(
                text("""
                    UPDATE character.character
                    SET current_location_id = :location_id
                    WHERE character_id = :fizrae_id
                """),
                {"location_id": location_id, "fizrae_id": str(fizrae_id)}
            )

            db.session.commit()
            print("  [OK] Characters placed in West Guest Room")

            # Set Sir Gelarthon as player-controlled
            print("\n[INFO] Setting Sir Gelarthon as player-controlled...")
            db.session.execute(
                text("""
                    UPDATE character.character
                    SET is_player = TRUE
                    WHERE character_id = :gelathorn_id
                """),
                {"gelathorn_id": str(gelathorn_id)}
            )
            db.session.commit()
            print("  [OK] Sir Gelarthon is now player-controlled")

            # Note: Objectives table not set up yet - skipping for now
            print("\n[INFO] Note: Objectives not configured yet (table doesn't exist)")

            # Create initial narrative setup
            print("\n[INFO] Creating initial narrative...")

            turn_id = uuid4()
            witnesses_json = json.dumps([str(gelathorn_id)])
            db.session.execute(
                text("""
                    INSERT INTO memory.turn_history (
                        turn_id, game_state_id, turn_number,
                        character_id, sequence_number, action_type,
                        action_description, location_id, is_private, witnesses
                    ) VALUES (
                        :turn_id, :game_id, 0,
                        :fizrae_id, 0, 'arrive',
                        'Fizrae quietly enters the West Guest Room in the dead of night. Sir Gelarthon Findraell stirs in his bed, awakened by the soft sound of the door opening. Moonlight illuminates Fizrae''s silhouette as she closes the door behind her.',
                        :location_id, FALSE, CAST(:witnesses AS jsonb)
                    )
                """),
                {
                    "turn_id": str(turn_id),
                    "game_id": str(game_id),
                    "fizrae_id": str(fizrae_id),
                    "location_id": location_id,
                    "witnesses": witnesses_json
                }
            )

            db.session.commit()
            print("  [OK] Initial narrative created")

            print("\n" + "=" * 60)
            print("SCENARIO SETUP COMPLETE")
            print("=" * 60)
            print(f"\nGame ID: {game_id}")
            print(f"Location: West Guest Room (ID: {location_id})")
            print(f"Player Character: Sir Gelathorn Findraell (ID: {gelathorn_id})")
            print(f"AI Character: Fizrae (ID: {fizrae_id})")
            print(f"\nFizrae's Objective: Seduce Sir Gelathorn and secure his allegiance")
            print(f"\nReady to play! Start the Flask app with: flask run --debug")
            print("=" * 60)

            return True

        except Exception as e:
            print(f"\n[ERROR] Failed to set up scenario: {str(e)}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            return False


if __name__ == '__main__':
    success = setup_scenario()
    exit(0 if success else 1)
