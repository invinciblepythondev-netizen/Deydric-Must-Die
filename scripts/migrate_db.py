"""
Database Migration Script

This script applies incremental database migrations from database/migrations/
and tracks which migrations have been applied using the schema_migration table.

Usage:
    python scripts/migrate_db.py           # Apply all pending migrations
    python scripts/migrate_db.py --list    # List migration status
    python scripts/migrate_db.py --dry-run # Show what would be applied
"""

import os
import sys
import re
import hashlib
import argparse
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


def calculate_checksum(filepath):
    """Calculate SHA256 checksum of a file."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def extract_migration_id(filename):
    """Extract migration ID from filename (e.g., '001' from '001_initial_setup.sql')."""
    match = re.match(r'^(\d+)_', filename)
    if match:
        return int(match.group(1))
    return None


def get_applied_migrations(cursor):
    """Get set of applied migration filenames and their checksums."""
    cursor.execute("SELECT filename, checksum FROM public.schema_migration")
    return {row[0]: row[1] for row in cursor.fetchall()}


def get_pending_migrations(migrations_dir, applied_migrations):
    """Get list of migrations that haven't been applied yet."""
    all_migrations = sorted(migrations_dir.glob("*.sql"))
    pending = []

    for migration_file in all_migrations:
        filename = migration_file.name

        # Skip the migration tracking table itself
        if filename == "000_schema_migration_table.sql":
            continue

        migration_id = extract_migration_id(filename)
        if migration_id is None:
            print(f"⚠ Warning: Skipping {filename} (invalid format)")
            continue

        checksum = calculate_checksum(migration_file)

        if filename not in applied_migrations:
            # New migration
            pending.append((migration_id, filename, migration_file, checksum, 'new'))
        elif applied_migrations[filename] != checksum:
            # Modified migration (dangerous!)
            pending.append((migration_id, filename, migration_file, checksum, 'modified'))

    return sorted(pending, key=lambda x: x[0])


def extract_description(filepath):
    """Extract description from migration filename."""
    filename = filepath.stem
    match = re.match(r'^\d+_(.*)', filename)
    if match:
        return match.group(1).replace('_', ' ').title()
    return "No description"


def apply_migration(cursor, migration_id, filename, filepath, checksum):
    """Apply a single migration and record it."""
    print(f"  Applying: {filename}")

    # Read and execute migration
    with open(filepath, 'r', encoding='utf-8') as f:
        sql = f.read()

    try:
        cursor.execute(sql)

        # Record in migration table
        description = extract_description(filepath)
        cursor.execute("""
            INSERT INTO public.schema_migration (migration_id, filename, checksum, description)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (filename) DO UPDATE
            SET checksum = EXCLUDED.checksum,
                applied_at = CURRENT_TIMESTAMP
        """, (migration_id, filename, checksum, description))

        print(f"  ✓ Success: {filename}")
        return True

    except psycopg2.Error as e:
        print(f"  ✗ Error applying {filename}:")
        print(f"    {e}")
        return False


def list_migrations(cursor, migrations_dir):
    """List all migrations and their status."""
    applied_migrations = get_applied_migrations(cursor)
    all_migrations = sorted(migrations_dir.glob("*.sql"))

    print("\n" + "="*70)
    print("Migration Status")
    print("="*70 + "\n")
    print(f"{'ID':<6} {'Status':<12} {'Migration'}")
    print("-"*70)

    for migration_file in all_migrations:
        filename = migration_file.name

        if filename == "000_schema_migration_table.sql":
            continue

        migration_id = extract_migration_id(filename)
        if migration_id is None:
            continue

        checksum = calculate_checksum(migration_file)

        if filename in applied_migrations:
            if applied_migrations[filename] == checksum:
                status = "✓ Applied"
            else:
                status = "⚠ Modified"
        else:
            status = "○ Pending"

        print(f"{migration_id:<6} {status:<12} {filename}")

    print()


def migrate_database(dry_run=False):
    """Apply all pending migrations."""

    print("\n" + "="*70)
    print("Database Migration")
    print("="*70 + "\n")

    # Connect to database
    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        cursor = conn.cursor()
        print("✓ Connected to database\n")
    except psycopg2.Error as e:
        print(f"✗ Failed to connect to database:")
        print(f"  {e}")
        sys.exit(1)

    try:
        # Get migrations directory
        migrations_dir = project_root / "database" / "migrations"

        if not migrations_dir.exists():
            print("✗ Migrations directory not found")
            sys.exit(1)

        # Get applied and pending migrations
        applied_migrations = get_applied_migrations(cursor)
        pending_migrations = get_pending_migrations(migrations_dir, applied_migrations)

        if not pending_migrations:
            print("✓ No pending migrations. Database is up to date.\n")
            return

        # Display pending migrations
        print(f"Found {len(pending_migrations)} pending migration(s):\n")
        for migration_id, filename, filepath, checksum, status in pending_migrations:
            status_symbol = "⚠" if status == 'modified' else "○"
            print(f"  {status_symbol} {filename}")
            if status == 'modified':
                print(f"    WARNING: This migration was already applied but has been modified!")

        print()

        if dry_run:
            print("Dry run mode - no changes will be applied.\n")
            return

        # Confirm before proceeding
        if any(m[4] == 'modified' for m in pending_migrations):
            print("⚠ WARNING: Some migrations have been modified after being applied!")
            print("This is dangerous and may cause data inconsistencies.")
            response = input("Do you want to continue? (yes/no): ")
            if response.lower() != 'yes':
                print("Aborted.")
                return

        # Apply migrations
        print("Applying migrations...\n")
        success_count = 0

        for migration_id, filename, filepath, checksum, status in pending_migrations:
            if apply_migration(cursor, migration_id, filename, filepath, checksum):
                success_count += 1
            else:
                raise Exception(f"Migration failed: {filename}")

        # Commit all changes
        conn.commit()

        print()
        print("="*70)
        print(f"✓ Applied {success_count} migration(s) successfully!")
        print("="*70 + "\n")

    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        print("Rolling back all changes...")
        conn.rollback()
        sys.exit(1)

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Apply database migrations")
    parser.add_argument('--list', action='store_true', help='List migration status')
    parser.add_argument('--dry-run', action='store_true', help='Show pending migrations without applying')

    args = parser.parse_args()

    if args.list:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        migrations_dir = project_root / "database" / "migrations"
        list_migrations(cursor, migrations_dir)
        cursor.close()
        conn.close()
    else:
        migrate_database(dry_run=args.dry_run)
