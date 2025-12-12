"""Verify the actual game state."""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app import app
from database import db
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

with app.app_context():
    print('\n=== ACTIVE GAME STATE ===')

    # Get active game
    game = db.session.execute(
        text("SELECT game_state_id, current_turn FROM game.game_state WHERE is_active = TRUE LIMIT 1")
    ).fetchone()

    if game:
        print(f'Game ID: {game[0]}')
        print(f'Current Turn: {game[1]}')
    else:
        print('No active game found!')

    # Get player character
    player = db.session.execute(
        text("""
            SELECT character_id, name, current_location_id
            FROM character.character
            WHERE is_player = TRUE
            LIMIT 1
        """)
    ).fetchone()

    if player:
        print(f'\nPlayer Character: {player[1]}')
        print(f'  ID: {player[0]}')
        print(f'  Location ID: {player[2]}')
    else:
        print('\nNo player character found!')

    # Get location details
    if player and player[2]:
        location = db.session.execute(
            text("SELECT location_id, name FROM world.location WHERE location_id = :loc_id"),
            {"loc_id": player[2]}
        ).fetchone()

        if location:
            print(f'\nPlayer Location: {location[1]} (ID: {location[0]})')

    # Get other characters at that location
    if player and player[2]:
        print(f'\n=== CHARACTERS AT LOCATION {player[2]} ===')
        characters = db.session.execute(
            text("""
                SELECT
                    c.character_id,
                    c.name,
                    c.current_stance,
                    c.current_clothing,
                    ci.image_url
                FROM character.character c
                LEFT JOIN character.character_image ci
                    ON c.character_id = ci.character_id
                    AND ci.image_type = 'profile'
                    AND ci.is_primary = TRUE
                WHERE c.current_location_id = :loc_id
            """),
            {"loc_id": player[2]}
        ).fetchall()

        for char in characters:
            is_player = (char[0] == player[0])
            print(f'\n  {"[PLAYER] " if is_player else ""}Character: {char[1]}')
            print(f'    ID: {char[0]}')
            print(f'    Stance: {char[2]}')
            print(f'    Clothing: {char[3]}')
            print(f'    Image URL: {char[4]}')
