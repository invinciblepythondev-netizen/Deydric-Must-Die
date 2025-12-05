"""
Migration script to add objective system to existing database.
Run this to apply the objective schema and procedures.
"""

import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv('NEON_DATABASE_URL')

if not DATABASE_URL:
    print("Error: NEON_DATABASE_URL not found in environment variables")
    sys.exit(1)


def run_sql_file(engine, file_path):
    """Execute SQL file against database."""
    print(f"Running {file_path}...")

    with open(file_path, 'r', encoding='utf-8') as f:
        sql = f.read()

    with engine.connect() as conn:
        # Split by statement separator and execute
        # Note: This is a simple approach; complex scripts may need psql
        try:
            conn.execute(text(sql))
            conn.commit()
            print(f"✓ {file_path} completed successfully")
        except Exception as e:
            print(f"✗ Error in {file_path}:")
            print(f"  {str(e)}")
            raise


def main():
    print("=" * 60)
    print("Objective System Migration")
    print("=" * 60)

    engine = create_engine(DATABASE_URL)

    # Check if objective schema already exists
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name = 'objective'
        """))

        if result.fetchone():
            print("\n⚠ Warning: 'objective' schema already exists!")
            response = input("Do you want to continue? This may cause errors. (y/N): ")
            if response.lower() != 'y':
                print("Migration cancelled.")
                return

    print("\n1. Applying objective schema...")
    try:
        run_sql_file(engine, 'database/schemas/004_objective_schema.sql')
    except Exception as e:
        print("\n✗ Schema migration failed!")
        print("If the schema already exists, you may need to manually drop it first.")
        sys.exit(1)

    print("\n2. Applying objective procedures...")
    try:
        run_sql_file(engine, 'database/procedures/objective_procedures.sql')
    except Exception as e:
        print("\n✗ Procedure migration failed!")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("✓ Migration completed successfully!")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Run seed_cognitive_traits.py to create trait definitions")
    print("  2. Run init_recurring_templates.py to create recurring objective templates")
    print("  3. Test with test_objective_system.py")


if __name__ == '__main__':
    main()
