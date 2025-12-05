"""
Database Initialization Script

This script initializes the database by:
1. Creating all schemas from database/schemas/
2. Creating all stored procedures from database/procedures/

Run this script when setting up the database for the first time.
For incremental changes, use migrate_db.py instead.
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


def execute_sql_file(cursor, filepath):
    """Execute a SQL file."""
    print(f"  Executing: {filepath.name}")
    with open(filepath, 'r', encoding='utf-8') as f:
        sql = f.read()
        try:
            cursor.execute(sql)
            print(f"  ✓ Success: {filepath.name}")
            return True
        except psycopg2.Error as e:
            print(f"  ✗ Error in {filepath.name}:")
            print(f"    {e}")
            return False


def init_database():
    """Initialize the database with all schemas and procedures."""

    print("\n" + "="*60)
    print("Database Initialization")
    print("="*60 + "\n")

    # Connect to database
    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False  # Use transactions
        cursor = conn.cursor()
        print("✓ Connected to database\n")
    except psycopg2.Error as e:
        print(f"✗ Failed to connect to database:")
        print(f"  {e}")
        sys.exit(1)

    try:
        # Step 1: Create migration tracking table
        print("Step 1: Creating migration tracking table...")
        migration_table_file = project_root / "database" / "migrations" / "000_schema_migration_table.sql"
        if migration_table_file.exists():
            if not execute_sql_file(cursor, migration_table_file):
                raise Exception("Failed to create migration tracking table")
            conn.commit()
        else:
            print("  ⚠ Warning: Migration tracking table file not found")
        print()

        # Step 2: Execute schema files in order
        print("Step 2: Creating schemas and tables...")
        schema_dir = project_root / "database" / "schemas"
        schema_files = sorted(schema_dir.glob("*.sql"))

        if not schema_files:
            print("  ⚠ Warning: No schema files found")

        for schema_file in schema_files:
            if not execute_sql_file(cursor, schema_file):
                raise Exception(f"Failed to execute schema file: {schema_file.name}")

        conn.commit()
        print(f"✓ Created {len(schema_files)} schemas\n")

        # Step 3: Execute procedure files
        print("Step 3: Creating stored procedures...")
        procedure_dir = project_root / "database" / "procedures"
        procedure_files = sorted(procedure_dir.glob("*.sql"))

        if not procedure_files:
            print("  ⚠ Warning: No procedure files found")

        for procedure_file in procedure_files:
            if not execute_sql_file(cursor, procedure_file):
                raise Exception(f"Failed to execute procedure file: {procedure_file.name}")

        conn.commit()
        print(f"✓ Created procedures from {len(procedure_files)} files\n")

        # Success!
        print("="*60)
        print("✓ Database initialization complete!")
        print("="*60 + "\n")

    except Exception as e:
        print(f"\n✗ Initialization failed: {e}")
        print("Rolling back changes...")
        conn.rollback()
        sys.exit(1)

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    init_database()
