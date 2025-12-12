"""List all characters in the database."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app import app
from database import db
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

with app.app_context():
    chars = db.session.execute(text("SELECT character_id, name FROM character.character")).fetchall()
    print("\nExisting characters in database:")
    print("=" * 60)
    for c in chars:
        print(f"  - {c[1]} (ID: {c[0]})")
    print("=" * 60)
    print(f"Total: {len(chars)} characters\n")
