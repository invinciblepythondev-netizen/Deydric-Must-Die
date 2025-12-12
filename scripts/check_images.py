"""Check character images."""
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
    print('\nCharacter Images:')
    images = db.session.execute(text("""
        SELECT character_id, image_type, image_url, is_primary
        FROM character.character_image
    """)).fetchall()

    for img in images:
        print(f'  Character ID: {img[0]}')
        print(f'    Type: {img[1]}')
        print(f'    URL: {img[2]}')
        print(f'    Is Primary: {img[3]}')
        print()

    print(f'\nTotal images: {len(images)}')

    # Check Fizrae specifically
    fizrae_id = 'e6212f28-1081-4e8e-89e3-49e26a4a4372'
    print(f'\nChecking images for Fizrae ({fizrae_id}):')
    fizrae_images = db.session.execute(text("""
        SELECT image_type, image_url, is_primary
        FROM character.character_image
        WHERE character_id = :char_id
    """), {"char_id": fizrae_id}).fetchall()

    for img in fizrae_images:
        print(f'  Type: {img[0]}, URL: {img[1]}, Primary: {img[2]}')

    # Test the actual query from the route
    print('\n\nTesting the actual route query:')
    result = db.session.execute(text("""
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
        WHERE c.character_id = :char_id
    """), {"char_id": fizrae_id}).fetchone()

    if result:
        print(f'  Character: {result[1]}')
        print(f'  Image URL: {result[5]}')
    else:
        print('  No result found')
