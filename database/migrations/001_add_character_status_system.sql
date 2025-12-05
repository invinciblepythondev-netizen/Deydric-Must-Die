-- Migration: Add character status system
-- Tracks conditions affecting characters (intoxication, emotions, temporary effects)
-- A character can have multiple active statuses simultaneously

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

-- Indexes for performance
CREATE INDEX idx_character_status_character ON character.character_status(character_id);
CREATE INDEX idx_character_status_active ON character.character_status(is_active) WHERE is_active = true;
CREATE INDEX idx_character_status_expiry ON character.character_status(expiry_turn) WHERE expiry_turn IS NOT NULL;

-- Trigger to update updated_at timestamp
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
