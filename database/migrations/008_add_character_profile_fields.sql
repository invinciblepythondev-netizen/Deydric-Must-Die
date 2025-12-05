-- Migration: Add additional character profile fields from characters.json

-- Add new character profile fields
ALTER TABLE character.character
ADD COLUMN IF NOT EXISTS short_name TEXT,
ADD COLUMN IF NOT EXISTS gender TEXT,
ADD COLUMN IF NOT EXISTS age INTEGER CHECK (age > 0 AND age < 200),
ADD COLUMN IF NOT EXISTS fears JSONB DEFAULT '[]'::jsonb,
ADD COLUMN IF NOT EXISTS inner_conflict TEXT,
ADD COLUMN IF NOT EXISTS core_values JSONB DEFAULT '[]'::jsonb,
ADD COLUMN IF NOT EXISTS intro_summary TEXT;

-- Add comments
COMMENT ON COLUMN character.character.short_name IS 'Shortened/nickname version of name (e.g., "Lysa" for "Lysa Darnog")';
COMMENT ON COLUMN character.character.gender IS 'Gender identity (Male, Female, Non-binary, etc.)';
COMMENT ON COLUMN character.character.age IS 'Character age in years';
COMMENT ON COLUMN character.character.fears IS 'JSONB array of things the character fears';
COMMENT ON COLUMN character.character.inner_conflict IS 'Internal struggle or tension driving character decisions';
COMMENT ON COLUMN character.character.core_values IS 'JSONB array of core values/beliefs (e.g., ["Justice", "Loyalty", "Freedom"])';
COMMENT ON COLUMN character.character.intro_summary IS 'Optional introductory scene/summary text for character entrance';

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_character_age ON character.character(age) WHERE age IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_character_gender ON character.character(gender) WHERE gender IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_character_short_name ON character.character(short_name) WHERE short_name IS NOT NULL;
