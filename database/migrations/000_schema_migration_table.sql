-- Migration tracking table
-- This must be run first to track all subsequent migrations

CREATE TABLE IF NOT EXISTS public.schema_migration (
    migration_id INTEGER PRIMARY KEY,
    filename TEXT NOT NULL UNIQUE,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    checksum TEXT NOT NULL,
    description TEXT
);

-- Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_schema_migration_filename ON public.schema_migration(filename);

COMMENT ON TABLE public.schema_migration IS 'Tracks which database migrations have been applied';
COMMENT ON COLUMN public.schema_migration.migration_id IS 'Sequential ID extracted from migration filename';
COMMENT ON COLUMN public.schema_migration.filename IS 'Name of the migration file';
COMMENT ON COLUMN public.schema_migration.checksum IS 'SHA256 hash of the migration file contents';
COMMENT ON COLUMN public.schema_migration.description IS 'Human-readable description of the migration';
