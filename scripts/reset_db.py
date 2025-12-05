"""
Database Reset Script (DEVELOPMENT ONLY)

WARNING: This script will DROP ALL SCHEMAS and data, then reinitialize.
Only use this during development when you want a clean slate.

Usage:
    python scripts/reset_db.py
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
FLASK_ENV = os.getenv('FLASK_ENV', 'development')

if not DATABASE_URL:
    print("ERROR: NEON_DATABASE_URL not found in environment variables")
    sys.exit(1)


def reset_database():
    """Drop all schemas and reinitialize the database."""

    # Safety check
    if FLASK_ENV == 'production':
        print("✗ ERROR: This script cannot be run in production!")
        print("  FLASK_ENV is set to 'production'")
        sys.exit(1)

    print("\n" + "="*70)
    print("⚠  DATABASE RESET - DEVELOPMENT ONLY ⚠")
    print("="*70)
    print("\nThis will DELETE ALL DATA in the following schemas:")
    print("  - game")
    print("  - character")
    print("  - world")
    print("  - memory")
    print("  - public.schema_migration table")
    print()

    # Confirm
    response = input("Are you sure you want to continue? Type 'YES' to confirm: ")
    if response != 'YES':
        print("Aborted.")
        return

    print("\nConnecting to database...")

    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        cursor = conn.cursor()
        print("✓ Connected\n")
    except psycopg2.Error as e:
        print(f"✗ Failed to connect:")
        print(f"  {e}")
        sys.exit(1)

    try:
        # Drop all schemas
        print("Dropping schemas...")
        schemas_to_drop = ['game', 'character', 'world', 'memory']

        for schema in schemas_to_drop:
            print(f"  Dropping schema: {schema}")
            cursor.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")

        # Drop migration tracking table
        print("  Dropping migration tracking table")
        cursor.execute("DROP TABLE IF EXISTS public.schema_migration CASCADE")

        conn.commit()
        print("✓ All schemas dropped\n")

        # Reinitialize
        print("Reinitializing database...")
        cursor.close()
        conn.close()

        # Call init_db.py
        from init_db import init_database
        init_database()

    except Exception as e:
        print(f"\n✗ Reset failed: {e}")
        conn.rollback()
        sys.exit(1)

    finally:
        if not cursor.closed:
            cursor.close()
        if not conn.closed:
            conn.close()


if __name__ == "__main__":
    reset_database()
