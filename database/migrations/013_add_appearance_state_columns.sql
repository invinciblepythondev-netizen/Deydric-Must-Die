-- Migration: Add appearance state tracking columns to character table
-- These columns track dynamic changes to character appearance during gameplay

ALTER TABLE character.character
ADD COLUMN IF NOT EXISTS appearance_state_detailed TEXT,
ADD COLUMN IF NOT EXISTS appearance_state_summary TEXT;

COMMENT ON COLUMN character.character.appearance_state_detailed IS 'Detailed description of current appearance state (clothing condition, positioning, dishevelment, removed items, etc.) for large context models';
COMMENT ON COLUMN character.character.appearance_state_summary IS 'Brief description of current appearance state for small context models';

-- Set default values for existing characters (initially matches base appearance)
UPDATE character.character
SET
    appearance_state_detailed = COALESCE(current_clothing, physical_appearance),
    appearance_state_summary = COALESCE(current_clothing, physical_appearance)
WHERE appearance_state_detailed IS NULL OR appearance_state_summary IS NULL;
