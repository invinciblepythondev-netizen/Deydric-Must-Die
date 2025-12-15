#!/usr/bin/env python3
"""
Apply summary embedding migration and procedures.
"""
import os
import sys
from pathlib import Path

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Config
import psycopg2

def apply_migration():
    """Apply the summary embedding migration."""
    print("Applying summary embedding migration...")

    # Connect to database
    conn = psycopg2.connect(Config.SQLALCHEMY_DATABASE_URI)
    conn.autocommit = False
    cursor = conn.cursor()

    try:
        # Apply migration
        migration_file = Path(__file__).parent.parent / "database" / "migrations" / "012_add_summary_embeddings.sql"
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
              AND column_name IN ('is_embedded', 'embedding_id', 'embedding_version')
        """)
        col_count = cursor.fetchone()[0]

        if col_count == 3:
            print(f"[OK] All 3 new columns exist in memory.memory_summary")
        else:
            print(f"[WARNING] Expected 3 new columns, found {col_count}")

        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.routines
            WHERE routine_schema = 'public'
              AND routine_name IN (
                  'memory_summary_mark_embedded',
                  'memory_summary_get_not_embedded',
                  'memory_summary_get_by_embedding_id'
              )
        """)
        proc_count = cursor.fetchone()[0]
        print(f"[OK] {proc_count}/3 new embedding procedures installed")

        # Check indexes
        cursor.execute("""
            SELECT COUNT(*) FROM pg_indexes
            WHERE schemaname = 'memory'
              AND tablename = 'memory_summary'
              AND indexname IN ('idx_memory_summary_not_embedded', 'idx_memory_summary_embedding_id')
        """)
        idx_count = cursor.fetchone()[0]
        print(f"[OK] {idx_count}/2 new indexes created")

        print("\n[SUCCESS] Summary embedding migration complete!")
        print("\nNext steps:")
        print("  1. Backfill existing summaries: python scripts/backfill_summary_embeddings.py")
        print("  2. New summaries will be automatically embedded when created")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    apply_migration()
