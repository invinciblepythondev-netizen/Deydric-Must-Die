-- Migration: Add character image storage
-- Creates table for storing character image URLs from Google Cloud Storage

CREATE TABLE IF NOT EXISTS character.character_image (
    image_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    character_id UUID NOT NULL REFERENCES character.character(character_id) ON DELETE CASCADE,

    -- Image metadata
    image_type TEXT NOT NULL, -- 'profile', 'outfit_casual', 'outfit_formal', 'outfit_combat', 'outfit_work', etc.
    image_url TEXT NOT NULL, -- Full GCS URL
    gcs_path TEXT NOT NULL, -- Path in GCS bucket (e.g., 'characters/{character_id}/{image_type}_{timestamp}.jpg')

    -- File details
    file_name TEXT NOT NULL,
    file_size INTEGER, -- Size in bytes
    mime_type TEXT DEFAULT 'image/jpeg',

    -- Display metadata
    display_name TEXT, -- Human-readable name (e.g., "Tavern Outfit", "Winter Clothes")
    description TEXT, -- Optional description of the outfit/image
    is_primary BOOLEAN DEFAULT false, -- Is this the primary image for this type?

    -- Ordering
    display_order INTEGER DEFAULT 0, -- For ordering multiple images of same type

    -- Metadata
    uploaded_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CHECK (image_type IN ('profile', 'portrait', 'outfit_casual', 'outfit_formal', 'outfit_combat', 'outfit_work', 'outfit_sleep', 'outfit_travel', 'outfit_custom')),
    CHECK (mime_type IN ('image/jpeg', 'image/png', 'image/webp', 'image/gif'))
);

COMMENT ON TABLE character.character_image IS 'Stores character image URLs from Google Cloud Storage';
COMMENT ON COLUMN character.character_image.image_type IS 'Type of image: profile, portrait, or various outfit types';
COMMENT ON COLUMN character.character_image.image_url IS 'Full publicly accessible GCS URL';
COMMENT ON COLUMN character.character_image.gcs_path IS 'Path within GCS bucket for management';
COMMENT ON COLUMN character.character_image.is_primary IS 'Whether this is the default image for this type';
COMMENT ON COLUMN character.character_image.display_order IS 'Order for displaying multiple images of same type';

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_character_image_character ON character.character_image(character_id);
CREATE INDEX IF NOT EXISTS idx_character_image_type ON character.character_image(character_id, image_type);
CREATE INDEX IF NOT EXISTS idx_character_image_primary ON character.character_image(character_id, is_primary) WHERE is_primary = true;
-- Partial unique index to enforce only one primary image per character per type
CREATE UNIQUE INDEX IF NOT EXISTS idx_character_image_unique_primary ON character.character_image(character_id, image_type) WHERE is_primary = true;

-- Updated_at trigger
CREATE TRIGGER character_image_updated_at
    BEFORE UPDATE ON character.character_image
    FOR EACH ROW
    EXECUTE FUNCTION character.update_character_status_timestamp();
