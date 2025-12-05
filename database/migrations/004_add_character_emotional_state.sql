-- Migration: Add character emotional state tracking
-- Description: Individual character emotional intensity and progression tracking
-- Dependencies: Requires character.character table

CREATE TABLE IF NOT EXISTS character.character_emotional_state (
    state_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    character_id UUID NOT NULL REFERENCES character.character(character_id) ON DELETE CASCADE,
    game_state_id UUID NOT NULL REFERENCES game.game_state(game_state_id) ON DELETE CASCADE,

    -- Current dominant emotion and intensity
    primary_emotion TEXT NOT NULL DEFAULT 'calm', -- anger, fear, attraction, joy, sadness, calm, etc.
    intensity_level INTEGER DEFAULT 0 CHECK (intensity_level >= 0 AND intensity_level <= 4),
    intensity_points INTEGER DEFAULT 0 CHECK (intensity_points >= 0 AND intensity_points <= 120),

    -- Emotion breakdown (JSONB for flexibility)
    -- Example: {"anger": 45, "fear": 20, "attraction": 5}
    emotion_scores JSONB DEFAULT '{}'::jsonb,

    -- Progression tracking
    last_intensity_change_turn INTEGER,
    emotional_trajectory TEXT DEFAULT 'stable' CHECK (emotional_trajectory IN ('rising', 'falling', 'stable', 'volatile')),

    -- Trigger tracking
    triggered_by_character_id UUID REFERENCES character.character(character_id),
    trigger_description TEXT,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Ensure one emotional state per character per game
    UNIQUE(character_id, game_state_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_character_emotional_state_character
    ON character.character_emotional_state(character_id);

CREATE INDEX IF NOT EXISTS idx_character_emotional_state_game
    ON character.character_emotional_state(game_state_id);

CREATE INDEX IF NOT EXISTS idx_character_emotional_state_intensity
    ON character.character_emotional_state(intensity_level);

-- Comments
COMMENT ON TABLE character.character_emotional_state IS 'Tracks individual character emotional intensity with 5-level progression system (0=NEUTRAL, 1=ENGAGED, 2=PASSIONATE, 3=EXTREME, 4=BREAKING)';
COMMENT ON COLUMN character.character_emotional_state.primary_emotion IS 'Dominant emotion driving character behavior (anger, fear, attraction, joy, etc.)';
COMMENT ON COLUMN character.character_emotional_state.intensity_level IS 'Emotional intensity tier: 0=NEUTRAL(0-24pts), 1=ENGAGED(25-49pts), 2=PASSIONATE(50-74pts), 3=EXTREME(75-99pts), 4=BREAKING(100+pts)';
COMMENT ON COLUMN character.character_emotional_state.intensity_points IS 'Point accumulation 0-120, determines intensity_level thresholds';
COMMENT ON COLUMN character.character_emotional_state.emotion_scores IS 'JSONB object tracking multiple emotion scores simultaneously';
COMMENT ON COLUMN character.character_emotional_state.emotional_trajectory IS 'Direction of emotional change: rising, falling, stable, volatile';
