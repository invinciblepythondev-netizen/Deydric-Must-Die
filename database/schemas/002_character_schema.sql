-- Character Schema
-- Contains all character-related data: profiles, relationships, wounds, inventory

-- Create schema
CREATE SCHEMA IF NOT EXISTS character;

-- Main character table
CREATE TABLE IF NOT EXISTS character.character (
    character_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    short_name TEXT,
    is_player BOOLEAN NOT NULL DEFAULT false,

    -- Demographics
    gender TEXT,
    age INTEGER CHECK (age > 0 AND age < 200),

    -- Core identity
    backstory TEXT,
    physical_appearance TEXT,
    current_clothing TEXT,
    appearance_state_detailed TEXT, -- Dynamic appearance changes (clothing condition, positioning, dishevelment, etc.)
    appearance_state_summary TEXT, -- Brief version for small context models
    role_responsibilities TEXT,
    intro_summary TEXT,

    -- Personality
    personality_traits JSONB DEFAULT '[]'::jsonb,
    speech_style TEXT,
    education_level TEXT,
    current_emotional_state TEXT,

    -- Motivations (JSONB arrays)
    motivations_short_term JSONB DEFAULT '[]'::jsonb,
    motivations_long_term JSONB DEFAULT '[]'::jsonb,

    -- Preferences (JSONB objects)
    preferences JSONB DEFAULT '{}'::jsonb, -- food, clothing_style, attraction_types, activities, locations

    -- Knowledge and skills
    skills JSONB DEFAULT '{}'::jsonb,
    superstitions TEXT[],
    hobbies TEXT[],

    -- Social
    social_class TEXT,
    reputation JSONB DEFAULT '{}'::jsonb, -- Per-faction reputation

    -- Secrets (never revealed in dialogue)
    secrets JSONB DEFAULT '[]'::jsonb,

    -- Psychological
    fears JSONB DEFAULT '[]'::jsonb,
    inner_conflict TEXT,
    core_values JSONB DEFAULT '[]'::jsonb,

    -- Physical state
    current_stance TEXT,
    current_location_id INTEGER, -- FK to world.location
    fatigue INTEGER DEFAULT 0 CHECK (fatigue >= 0 AND fatigue <= 100),
    hunger INTEGER DEFAULT 0 CHECK (hunger >= 0 AND hunger <= 100),

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE character.character IS 'Full character profiles including personality, skills, motivations';
COMMENT ON COLUMN character.character.short_name IS 'Shortened/nickname version of name';
COMMENT ON COLUMN character.character.gender IS 'Gender identity (Male, Female, Non-binary, etc.)';
COMMENT ON COLUMN character.character.age IS 'Character age in years';
COMMENT ON COLUMN character.character.intro_summary IS 'Optional introductory scene/summary text';
COMMENT ON COLUMN character.character.personality_traits IS 'Array of trait strings, quirks, and flaws';
COMMENT ON COLUMN character.character.preferences IS 'JSONB object with food, clothing, attraction, activities, locations, sexuality, etc.';
COMMENT ON COLUMN character.character.skills IS 'JSONB object with skill names as keys and proficiency levels as values';
COMMENT ON COLUMN character.character.secrets IS 'Array of secrets - never revealed in character dialogue/actions';
COMMENT ON COLUMN character.character.fears IS 'JSONB array of things the character fears';
COMMENT ON COLUMN character.character.inner_conflict IS 'Internal struggle or tension driving character decisions';
COMMENT ON COLUMN character.character.core_values IS 'JSONB array of core values/beliefs';

-- Character relationships table
CREATE TABLE IF NOT EXISTS character.character_relationship (
    relationship_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_character_id UUID NOT NULL REFERENCES character.character(character_id) ON DELETE CASCADE,
    target_character_id UUID NOT NULL REFERENCES character.character(character_id) ON DELETE CASCADE,

    -- Relationship metrics
    trust FLOAT DEFAULT 0.5 CHECK (trust >= 0 AND trust <= 1),
    fear FLOAT DEFAULT 0.0 CHECK (fear >= 0 AND fear <= 1),
    respect FLOAT DEFAULT 0.5 CHECK (respect >= 0 AND respect <= 1),

    -- History
    relationship_type TEXT, -- friend, enemy, neutral, family, romantic, etc.
    interaction_count INTEGER DEFAULT 0,
    last_interaction_turn INTEGER,
    notes TEXT, -- Narrative notes about relationship

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Prevent self-relationships
    CHECK (source_character_id != target_character_id),

    -- Ensure unique directional relationships
    UNIQUE(source_character_id, target_character_id)
);

COMMENT ON TABLE character.character_relationship IS 'Directed graph edges representing character relationships';
COMMENT ON COLUMN character.character_relationship.trust IS 'How much source trusts target (0-1)';
COMMENT ON COLUMN character.character_relationship.fear IS 'How much source fears target (0-1)';
COMMENT ON COLUMN character.character_relationship.respect IS 'How much source respects target (0-1)';

-- Character wounds table
CREATE TABLE IF NOT EXISTS character.character_wound (
    wound_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    character_id UUID NOT NULL REFERENCES character.character(character_id) ON DELETE CASCADE,

    -- Wound details
    body_part TEXT NOT NULL, -- head, torso, left_arm, right_arm, left_leg, right_leg
    wound_type TEXT NOT NULL, -- cut, stab, blunt_trauma, burn, infection
    severity TEXT NOT NULL, -- minor, moderate, severe, critical, mortal

    -- Status
    is_bleeding BOOLEAN DEFAULT false,
    is_infected BOOLEAN DEFAULT false,
    is_treated BOOLEAN DEFAULT false,

    -- Progression
    turns_since_injury INTEGER DEFAULT 0,
    treatment_history JSONB DEFAULT '[]'::jsonb, -- Array of treatment attempts

    -- Description
    description TEXT,
    caused_by TEXT, -- What/who caused the wound

    -- Metadata
    occurred_at_turn INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CHECK (body_part IN ('head', 'torso', 'left_arm', 'right_arm', 'left_leg', 'right_leg')),
    CHECK (wound_type IN ('cut', 'stab', 'blunt_trauma', 'burn', 'infection')),
    CHECK (severity IN ('minor', 'moderate', 'severe', 'critical', 'mortal'))
);

COMMENT ON TABLE character.character_wound IS 'Specific injuries with body part, severity, bleeding/infection status';
COMMENT ON COLUMN character.character_wound.treatment_history IS 'JSON array of treatment attempts with turn, treater, success';

-- Character inventory table
CREATE TABLE IF NOT EXISTS character.character_inventory (
    inventory_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    character_id UUID NOT NULL REFERENCES character.character(character_id) ON DELETE CASCADE,
    item_id INTEGER, -- FK to world.item (when implemented)

    -- Item details (for now, simple text)
    item_name TEXT NOT NULL,
    item_description TEXT,
    quantity INTEGER DEFAULT 1 CHECK (quantity > 0),

    -- Properties
    is_equipped BOOLEAN DEFAULT false,
    item_properties JSONB DEFAULT '{}'::jsonb, -- weapon stats, consumable effects, etc.

    -- Metadata
    acquired_at_turn INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE character.character_inventory IS 'Items carried by each character';
COMMENT ON COLUMN character.character_inventory.item_properties IS 'JSONB for weapon damage, healing effects, etc.';

-- Character images table
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

-- Status type reference table (defines available status types)
CREATE TABLE IF NOT EXISTS character.status_type (
    status_type_code TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    description TEXT,
    default_duration_turns INTEGER, -- NULL means indefinite/until manually removed
    category TEXT, -- 'physical', 'emotional', 'mental', 'magical', 'social'
    stackable BOOLEAN DEFAULT false, -- Can multiple instances exist simultaneously?
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE character.status_type IS 'Reference table defining types of statuses that can affect characters';
COMMENT ON COLUMN character.status_type.status_type_code IS 'Unique code for the status (e.g., intoxicated, angry, frightened)';
COMMENT ON COLUMN character.status_type.default_duration_turns IS 'Default number of turns this status lasts (NULL = indefinite)';
COMMENT ON COLUMN character.status_type.stackable IS 'Whether multiple instances can exist (e.g., multiple anger sources)';

-- Active character statuses
CREATE TABLE IF NOT EXISTS character.character_status (
    character_status_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    character_id UUID NOT NULL REFERENCES character.character(character_id) ON DELETE CASCADE,
    status_type_code TEXT NOT NULL REFERENCES character.status_type(status_type_code),
    intensity INTEGER NOT NULL DEFAULT 50 CHECK (intensity >= 0 AND intensity <= 100),
    onset_turn INTEGER NOT NULL, -- Turn number when status began
    duration_turns INTEGER, -- How many turns it lasts (NULL = indefinite)
    expiry_turn INTEGER, -- Calculated: onset_turn + duration_turns (NULL if indefinite)
    source TEXT, -- What caused this status (e.g., "drank ale", "witnessed death")
    notes TEXT, -- Additional context for LLM
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(character_id, status_type_code, source) -- Prevent exact duplicates
);

COMMENT ON TABLE character.character_status IS 'Active statuses affecting characters (intoxication, emotions, conditions)';
COMMENT ON COLUMN character.character_status.intensity IS 'Strength of the effect (0-100): 0-25=mild, 26-50=moderate, 51-75=strong, 76-100=severe';
COMMENT ON COLUMN character.character_status.onset_turn IS 'Game turn when this status began';
COMMENT ON COLUMN character.character_status.expiry_turn IS 'Turn when status expires (NULL for indefinite)';
COMMENT ON COLUMN character.character_status.source IS 'Description of what caused this status';

-- Seed common status types
INSERT INTO character.status_type (status_type_code, display_name, description, default_duration_turns, category, stackable) VALUES
    ('intoxicated', 'Intoxicated', 'Under the influence of alcohol or drugs. Impaired judgment, slurred speech, reduced coordination.', 8, 'physical', false),
    ('angry', 'Angry', 'Feeling intense displeasure or rage. May act impulsively, speak harshly, seek confrontation.', NULL, 'emotional', true),
    ('frightened', 'Frightened', 'Experiencing fear or terror. May flee, freeze, or act defensively. Reduced courage.', 5, 'emotional', true),
    ('exhausted', 'Exhausted', 'Severely fatigued. Reduced physical and mental performance. May need rest urgently.', NULL, 'physical', false),
    ('poisoned', 'Poisoned', 'Suffering from poison or toxin. May experience pain, weakness, or impaired senses.', 12, 'physical', true),
    ('in_pain', 'In Pain', 'Experiencing significant physical pain from wounds or injuries. Distracted, irritable.', NULL, 'physical', true),
    ('grieving', 'Grieving', 'Mourning a loss. Emotionally withdrawn, sad, may avoid social interaction.', NULL, 'emotional', false),
    ('euphoric', 'Euphoric', 'Experiencing intense happiness or excitement. May be overly optimistic or carefree.', 4, 'emotional', false),
    ('suspicious', 'Suspicious', 'Distrusting others or a specific person. Cautious, questioning, paranoid.', NULL, 'mental', true),
    ('focused', 'Focused', 'Intensely concentrated on a task or goal. Enhanced mental clarity but tunnel vision.', 6, 'mental', false),
    ('aroused', 'Aroused', 'Sexually or romantically attracted. May act flirtatiously or seek intimacy.', NULL, 'emotional', true),
    ('humiliated', 'Humiliated', 'Feeling shame or embarrassment. May avoid eye contact, seek isolation, or lash out.', 10, 'social', true),
    ('confident', 'Confident', 'Feeling self-assured and capable. More likely to take risks or lead.', 8, 'mental', false),
    ('starving', 'Starving', 'Suffering from severe hunger. Weak, irritable, obsessed with finding food.', NULL, 'physical', false),
    ('bleeding', 'Bleeding', 'Actively losing blood from wounds. Weakening over time. Requires medical attention.', NULL, 'physical', true),
    ('feverish', 'Feverish', 'Running a fever from infection or illness. Delirious, weak, impaired thinking.', NULL, 'physical', false)
ON CONFLICT (status_type_code) DO NOTHING;

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_character_location ON character.character(current_location_id) WHERE current_location_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_character_is_player ON character.character(is_player);
CREATE INDEX IF NOT EXISTS idx_character_age ON character.character(age) WHERE age IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_character_gender ON character.character(gender) WHERE gender IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_character_short_name ON character.character(short_name) WHERE short_name IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_relationship_source ON character.character_relationship(source_character_id);
CREATE INDEX IF NOT EXISTS idx_relationship_target ON character.character_relationship(target_character_id);
CREATE INDEX IF NOT EXISTS idx_wound_character ON character.character_wound(character_id);
CREATE INDEX IF NOT EXISTS idx_wound_severity ON character.character_wound(severity) WHERE severity IN ('critical', 'mortal');
CREATE INDEX IF NOT EXISTS idx_inventory_character ON character.character_inventory(character_id);
CREATE INDEX IF NOT EXISTS idx_character_image_character ON character.character_image(character_id);
CREATE INDEX IF NOT EXISTS idx_character_image_type ON character.character_image(character_id, image_type);
CREATE INDEX IF NOT EXISTS idx_character_image_primary ON character.character_image(character_id, is_primary) WHERE is_primary = true;
-- Partial unique index to enforce only one primary image per character per type
CREATE UNIQUE INDEX IF NOT EXISTS idx_character_image_unique_primary ON character.character_image(character_id, image_type) WHERE is_primary = true;
CREATE INDEX IF NOT EXISTS idx_character_status_character ON character.character_status(character_id);
CREATE INDEX IF NOT EXISTS idx_character_status_active ON character.character_status(is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_character_status_expiry ON character.character_status(expiry_turn) WHERE expiry_turn IS NOT NULL;

-- Updated_at triggers
CREATE TRIGGER character_updated_at
    BEFORE UPDATE ON character.character
    FOR EACH ROW
    EXECUTE FUNCTION game.update_timestamp();

CREATE TRIGGER character_relationship_updated_at
    BEFORE UPDATE ON character.character_relationship
    FOR EACH ROW
    EXECUTE FUNCTION game.update_timestamp();

CREATE TRIGGER character_wound_updated_at
    BEFORE UPDATE ON character.character_wound
    FOR EACH ROW
    EXECUTE FUNCTION game.update_timestamp();

CREATE TRIGGER character_image_updated_at
    BEFORE UPDATE ON character.character_image
    FOR EACH ROW
    EXECUTE FUNCTION game.update_timestamp();

-- Character status trigger (using its own function since it's created in migration)
CREATE OR REPLACE FUNCTION character.update_character_status_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_character_status_timestamp
    BEFORE UPDATE ON character.character_status
    FOR EACH ROW
    EXECUTE FUNCTION character.update_character_status_timestamp();
