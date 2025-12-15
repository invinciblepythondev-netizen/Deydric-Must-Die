"""
Create scene_mood table in the database.

This script creates the scene_mood table that tracks emotional dynamics
and tension for each location in a game.
"""

import os
import sys
from pathlib import Path
import psycopg2
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv('NEON_DATABASE_URL')

if not DATABASE_URL:
    print("ERROR: NEON_DATABASE_URL not found in environment variables")
    print("Please set this in your .env file")
    sys.exit(1)


def create_mood_table():
    """Create the scene_mood table."""

    print("\n" + "="*60)
    print("Creating scene_mood Table")
    print("="*60 + "\n")

    # Connect to database
    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        cursor = conn.cursor()
        print("[OK] Connected to database\n")
    except psycopg2.Error as e:
        print(f"[ERROR] Failed to connect to database:")
        print(f"  {e}")
        sys.exit(1)

    try:
        # Read and execute mood schema
        schema_file = project_root / "database" / "schemas" / "005_mood_schema.sql"

        print(f"Executing: {schema_file.name}")
        with open(schema_file, 'r', encoding='utf-8') as f:
            sql = f.read()
            cursor.execute(sql)
            print(f"[OK] Created scene_mood table\n")

        conn.commit()

        print("="*60)
        print("[SUCCESS] scene_mood table created!")
        print("="*60 + "\n")

    except psycopg2.Error as e:
        print(f"[ERROR] Error creating table:")
        print(f"  {e}")
        conn.rollback()
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"[ERROR] Schema file not found:")
        print(f"  {e}")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    create_mood_table()
