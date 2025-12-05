# Database Structure

This directory contains all database schemas, stored procedures, and migration files for **Deydric Must Die**.

## Directory Structure

```
database/
├── schemas/              # Table definitions organized by domain
│   ├── 001_game_schema.sql
│   ├── 002_character_schema.sql
│   ├── 003_world_schema.sql
│   └── 004_memory_schema.sql
├── procedures/           # Stored procedures for data access
│   ├── character_procedures.sql
│   ├── relationship_procedures.sql
│   ├── wound_procedures.sql
│   ├── location_procedures.sql
│   └── turn_procedures.sql
└── migrations/           # Sequential schema changes
    ├── 000_schema_migration_table.sql
    ├── 001_example_migration.sql
    └── ...
```

## Quick Start

### First Time Setup

```bash
# Initialize the database (creates all schemas, tables, and procedures)
python scripts/init_db.py
```

### Apply Migrations

```bash
# Apply pending migrations
python scripts/migrate_db.py

# Check migration status
python scripts/migrate_db.py --list

# Dry run (see what would be applied)
python scripts/migrate_db.py --dry-run
```

### Development Reset

```bash
# Drop everything and recreate (DEVELOPMENT ONLY)
python scripts/reset_db.py
```

## Schema Organization

### `game` schema
- `game_state`: Current game session state, turn counter, turn order

### `character` schema
- `character`: Full character profiles
- `character_relationship`: Relationship graph (trust/fear/respect)
- `character_wound`: Specific injuries with deterioration tracking
- `character_inventory`: Items carried by characters

### `world` schema
- `location`: Rooms/areas with connections and environmental properties
- `item_catalog`: Item templates (optional)

### `memory` schema
- `turn_history`: Every action taken in the game
- `memory_summary`: Compressed narrative summaries
- `character_thought`: Private character thoughts

## Database Conventions

### Table Naming
- **Singular names**: `character` (not `characters`)
- **ID columns**: `tablename_id` format
- **ID types**: UUID for user-facing tables, INTEGER for internal

### Stored Procedures
All database access goes through stored procedures:

- `tablename_get(id)` - Get single record
- `tablename_list(...)` - Get multiple records
- `tablename_upsert(...)` - Insert or update
- `tablename_delete(id)` - Delete record

### Example Usage

```python
# Python code using stored procedures
from sqlalchemy import text

# Get character
result = db.session.execute(
    text("SELECT * FROM character_get(:id)"),
    {"id": character_id}
).fetchone()

# Update location
db.session.execute(
    text("SELECT character_update_location(:char_id, :loc_id)"),
    {"char_id": character_id, "loc_id": new_location_id}
)
db.session.commit()
```

## Migration Workflow

### Creating a Migration

1. Create new file: `database/migrations/00X_description.sql`
2. Write migration SQL (ALTER TABLE, CREATE TABLE, etc.)
3. Run: `python scripts/migrate_db.py`
4. Update corresponding schema file to match

### Updating Procedures

Procedures don't need migrations:

1. Edit procedure file: `database/procedures/xxx_procedures.sql`
2. Run: `python scripts/init_db.py`

Procedures use `CREATE OR REPLACE FUNCTION`, so they're updated in place.

## Important Rules

1. **Never access tables directly** - Always use stored procedures
2. **Never modify applied migrations** - Create new corrective migrations
3. **Keep schema files updated** - They should match the current state after migrations
4. **Test locally first** - Use `reset_db.py` freely in development
5. **Procedures are idempotent** - Safe to re-run `init_db.py` anytime

## Need Help?

See [CLAUDE.md](../CLAUDE.md) for comprehensive documentation on:
- Database conventions
- Migration workflow
- Stored procedure patterns
- How Claude handles schema changes
