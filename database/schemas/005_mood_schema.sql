-- Scene Mood Schema
-- Tracks emotional dynamics and tension in locations

-- Create scene_mood table in game schema
CREATE TABLE IF NOT EXISTS game.scene_mood (
    scene_mood_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_state_id UUID NOT NULL REFERENCES game.game_state(game_state_id) ON DELETE CASCADE,
    location_id INTEGER NOT NULL REFERENCES world.location(location_id) ON DELETE CASCADE,

    -- Emotional dimensions (-100 to +100)
    tension_level INTEGER DEFAULT 0 CHECK (tension_level >= -100 AND tension_level <= 100),
    romance_level INTEGER DEFAULT 0 CHECK (romance_level >= -100 AND romance_level <= 100),
    hostility_level INTEGER DEFAULT 0 CHECK (hostility_level >= -100 AND hostility_level <= 100),
    cooperation_level INTEGER DEFAULT 0 CHECK (cooperation_level >= -100 AND cooperation_level <= 100),

    -- Tension trajectory
    tension_trajectory TEXT DEFAULT 'stable' CHECK (tension_trajectory IN ('rising', 'falling', 'stable')),

    -- Intensity tracking
    intensity_level INTEGER DEFAULT 0 CHECK (intensity_level >= 0 AND intensity_level <= 4),
    intensity_points INTEGER DEFAULT 0 CHECK (intensity_points >= 0 AND intensity_points <= 120),

    -- Scene narrative
    dominant_arc TEXT CHECK (dominant_arc IN ('conflict', 'intimacy', 'fear', 'social', 'neutral')),
    scene_phase TEXT DEFAULT 'building' CHECK (scene_phase IN ('building', 'climax', 'resolution', 'aftermath')),

    -- Change tracking
    last_mood_change_turn INTEGER,
    last_mood_change_description TEXT,
    last_level_change_turn INTEGER,

    -- Participants
    character_ids JSONB DEFAULT '[]'::jsonb,

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Unique constraint: one mood per game/location
    UNIQUE(game_state_id, location_id)
);

-- Create index for fast lookups
CREATE INDEX IF NOT EXISTS idx_scene_mood_game_location
ON game.scene_mood(game_state_id, location_id);

CREATE INDEX IF NOT EXISTS idx_scene_mood_intensity
ON game.scene_mood(intensity_level);

-- Add comments
COMMENT ON TABLE game.scene_mood IS 'Tracks emotional dynamics and tension for each location in a game';
COMMENT ON COLUMN game.scene_mood.tension_level IS 'Overall tension/anticipation -100 to +100';
COMMENT ON COLUMN game.scene_mood.romance_level IS 'Romantic/sexual tension -100 to +100';
COMMENT ON COLUMN game.scene_mood.hostility_level IS 'Hostility/aggression -100 to +100';
COMMENT ON COLUMN game.scene_mood.cooperation_level IS 'Cooperation/trust -100 to +100';
COMMENT ON COLUMN game.scene_mood.intensity_level IS 'Intensity tier: 0=NEUTRAL, 1=ENGAGED, 2=PASSIONATE, 3=EXTREME, 4=BREAKING';
COMMENT ON COLUMN game.scene_mood.intensity_points IS 'Point accumulation 0-120 that determines intensity level';
COMMENT ON COLUMN game.scene_mood.dominant_arc IS 'Strongest emotional progression: conflict, intimacy, fear, social, neutral';
COMMENT ON COLUMN game.scene_mood.scene_phase IS 'Narrative phase: building, climax, resolution, aftermath';
