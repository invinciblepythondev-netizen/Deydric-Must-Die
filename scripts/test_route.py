"""Test the route query."""
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
    player_id = 'f3807eaf-6d3a-425c-8916-32fd226d899f'  # Sir Gelarthon
    location_id = 7  # West Guest Room

    print('\nTesting exact route query:')
    other_characters = db.session.execute(
        text("""
            SELECT
                c.character_id,
                c.name,
                c.current_stance,
                c.physical_appearance,
                c.current_clothing,
                ci.image_url
            FROM character.character c
            LEFT JOIN character.character_image ci
                ON c.character_id = ci.character_id
                AND ci.image_type = 'profile'
                AND ci.is_primary = TRUE
            WHERE c.current_location_id = :loc_id
            AND c.character_id != :player_id
        """),
        {"loc_id": location_id, "player_id": str(player_id)}
    ).fetchall()

    print(f'\nFound {len(other_characters)} characters')

    for c in other_characters:
        print(f'\n  Character: {c[1]}')
        print(f'    ID: {c[0]}')
        print(f'    Stance: {c[2]}')
        print(f'    Clothing: {c[4]}')
        print(f'    Image URL: {c[5]}')

        # Simulate the dictionary creation
        char_dict = {
            'character_id': str(c[0]),
            'name': c[1],
            'stance': c[2] or 'standing',
            'appearance': c[3],
            'clothing': c[4],
            'image_url': c[5]
        }

        print(f'    Dict image_url: {char_dict["image_url"]}')
        print(f'    Bool value: {bool(char_dict["image_url"])}')
