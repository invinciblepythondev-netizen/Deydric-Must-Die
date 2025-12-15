"""
Update memory summary procedures to fix summary_text NOT NULL constraint issue.
"""

import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, text

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Config

def update_procedures():
    """Update memory summary procedures."""

    # Get database URL
    db_url = Config.SQLALCHEMY_DATABASE_URI
    if not db_url:
        print("Error: NEON_DATABASE_URL not set in environment")
        return False

    # Create engine
    engine = create_engine(db_url)

    # Read procedure file
    procedure_file = Path(__file__).parent.parent / 'database' / 'procedures' / 'memory_summary_procedures.sql'

    if not procedure_file.exists():
        print(f"Error: Procedure file not found: {procedure_file}")
        return False

    print(f"Reading procedure file: {procedure_file}")
    with open(procedure_file, 'r', encoding='utf-8') as f:
        sql = f.read()

    # Execute
    print("Applying memory summary procedures...")
    try:
        with engine.begin() as conn:
            conn.execute(text(sql))
        print("[SUCCESS] Memory summary procedures updated successfully")
        return True
    except Exception as e:
        print(f"[ERROR] Error applying procedures: {e}")
        return False

if __name__ == '__main__':
    success = update_procedures()
    sys.exit(0 if success else 1)
