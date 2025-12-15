#!/usr/bin/env python3
"""
Apply memory summary migration and procedures.
"""
import os
import sys
from pathlib import Path

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Config
import psycopg2

def apply_migration():
    """Apply the tiered memory summary migration."""
    print("Applying tiered memory summary migration...")

    # Connect to database
    conn = psycopg2.connect(Config.SQLALCHEMY_DATABASE_URI)
    conn.autocommit = False
    cursor = conn.cursor()

    try:
        # Apply migration
        migration_file = Path(__file__).parent.parent / "database" / "migrations" / "011_add_tiered_memory_summaries.sql"
        print(f"Reading migration: {migration_file}")

        with open(migration_file, 'r') as f:
            migration_sql = f.read()

        print("Executing migration...")
        cursor.execute(migration_sql)
        conn.commit()
        print("[OK] Migration applied successfully")

        # Apply procedures
        procedures_file = Path(__file__).parent.parent / "database" / "procedures" / "memory_summary_procedures.sql"
        print(f"\nReading procedures: {procedures_file}")

        with open(procedures_file, 'r') as f:
            procedures_sql = f.read()

        print("Executing procedures...")
        cursor.execute(procedures_sql)
        conn.commit()
        print("[OK] Procedures created successfully")

        # Verify installation
        print("\nVerifying installation...")
        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_schema = 'memory'
              AND table_name = 'memory_summary'
              AND column_name IN ('character_id', 'window_type', 'descriptive_summary', 'condensed_summary')
        """)
        col_count = cursor.fetchone()[0]

        if col_count == 4:
            print(f"[OK] All 4 new columns exist in memory.memory_summary")
        else:
            print(f"[WARNING] Expected 4 new columns, found {col_count}")

        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.routines
            WHERE routine_schema = 'public'
              AND routine_name LIKE 'memory_summary%'
        """)
        proc_count = cursor.fetchone()[0]
        print(f"[OK] {proc_count} memory summary procedures installed")

        print("\n[SUCCESS] Memory summary migration complete!")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    apply_migration()
