"""Check character locations."""
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
    chars = db.session.execute(text("SELECT name, current_location_id FROM character.character")).fetchall()
    print('\nCharacter locations:')
    for c in chars:
        print(f'  {c[0]}: location_id={c[1]}')
