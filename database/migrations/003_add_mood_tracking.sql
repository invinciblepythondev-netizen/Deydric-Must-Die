-- Add mood tracking system for dynamic action generation
-- Tracks the general emotional/tension state between characters in a location

-- Create mood tracking table
CREATE TABLE IF NOT EXISTS game.scene_mood (
    scene_mood_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_state_id UUID NOT NULL REFERENCES game.game_state(game_state_id) ON DELETE CASCADE,
    location_id INTEGER NOT NULL,

    -- Mood dimensions (all range -100 to +100)
    tension_level INTEGER DEFAULT 0 CHECK (tension_level >= -100 AND tension_level <= 100),
    romance_level INTEGER DEFAULT 0 CHECK (romance_level >= -100 AND romance_level <= 100),
    hostility_level INTEGER DEFAULT 0 CHECK (hostility_level >= -100 AND hostility_level <= 100),
    cooperation_level INTEGER DEFAULT 0 CHECK (cooperation_level >= -100 AND cooperation_level <= 100),

    -- Mood trajectory (rising, falling, stable)
    tension_trajectory TEXT DEFAULT 'stable' CHECK (tension_trajectory IN ('rising', 'falling', 'stable')),

    -- Last action that affected mood
    last_mood_change_turn INTEGER,
    last_mood_change_description TEXT,

    -- Characters involved in the scene
    character_ids JSONB DEFAULT '[]'::jsonb,

    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- One mood per location per game
    UNIQUE(game_state_id, location_id)
);

COMMENT ON TABLE game.scene_mood IS 'Tracks emotional/tension dynamics in a location between characters';
COMMENT ON COLUMN game.scene_mood.tension_level IS 'General tension/stress level (-100 = very relaxed, +100 = extreme tension)';
COMMENT ON COLUMN game.scene_mood.romance_level IS 'Romantic/intimate atmosphere (-100 = hostile, +100 = very romantic)';
COMMENT ON COLUMN game.scene_mood.hostility_level IS 'Antagonism between characters (-100 = friendly, +100 = violent conflict)';
COMMENT ON COLUMN game.scene_mood.cooperation_level IS 'Willingness to work together (-100 = competitive, +100 = cooperative)';
COMMENT ON COLUMN game.scene_mood.tension_trajectory IS 'Direction mood is heading (rising = escalating, falling = de-escalating)';

-- Index for quick lookups
CREATE INDEX IF NOT EXISTS idx_scene_mood_game_location ON game.scene_mood(game_state_id, location_id);
CREATE INDEX IF NOT EXISTS idx_scene_mood_updated ON game.scene_mood(updated_at);

-- Add trigger to update timestamp
CREATE TRIGGER scene_mood_updated_at
    BEFORE UPDATE ON game.scene_mood
    FOR EACH ROW
    EXECUTE FUNCTION game.update_timestamp();
