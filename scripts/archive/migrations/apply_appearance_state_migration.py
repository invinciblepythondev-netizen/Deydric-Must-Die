"""
Apply appearance state columns migration.

Adds appearance_state_detailed and appearance_state_summary columns to character table,
then updates character procedures.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables
load_dotenv()

def apply_migration():
    """Apply the appearance state migration."""

    database_url = os.getenv('NEON_DATABASE_URL')
    if not database_url:
        print("ERROR: NEON_DATABASE_URL not found in environment variables")
        sys.exit(1)

    # Ensure psycopg driver
    if 'postgresql://' in database_url:
        database_url = database_url.replace('postgresql://', 'postgresql+psycopg://')

    engine = create_engine(database_url)

    print("=" * 70)
    print("Applying Appearance State Migration")
    print("=" * 70)
    print()

    try:
        with engine.connect() as conn:
            # Read migration file
            migration_path = project_root / 'database' / 'migrations' / '013_add_appearance_state_columns.sql'
            print(f"Reading migration: {migration_path.name}")

            with open(migration_path, 'r') as f:
                migration_sql = f.read()

            # Execute migration
            print("Executing migration...")
            conn.execute(text(migration_sql))
            conn.commit()
            print("✓ Migration applied successfully")
            print()

            # Update procedures
            procedures_path = project_root / 'database' / 'procedures' / 'character_procedures.sql'
            print(f"Updating procedures: {procedures_path.name}")

            with open(procedures_path, 'r') as f:
                procedures_sql = f.read()

            # Execute procedure updates
            print("Updating character procedures...")
            conn.execute(text(procedures_sql))
            conn.commit()
            print("✓ Procedures updated successfully")
            print()

            # Verify columns exist
            print("Verifying new columns...")
            result = conn.execute(text("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'character'
                  AND table_name = 'character'
                  AND column_name IN ('appearance_state_detailed', 'appearance_state_summary')
                ORDER BY column_name
            """))

            columns = result.fetchall()
            if len(columns) == 2:
                print("✓ Verified columns exist:")
                for col in columns:
                    print(f"  - {col[0]} ({col[1]})")
            else:
                print("⚠ Warning: Expected 2 columns, found", len(columns))

            print()
            print("=" * 70)
            print("✓ Migration completed successfully!")
            print("=" * 70)

    except Exception as e:
        print(f"\n✗ Error applying migration: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    apply_migration()
