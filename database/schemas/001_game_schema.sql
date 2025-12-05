-- Game Schema
-- Contains core game state and session management

-- Create schema
CREATE SCHEMA IF NOT EXISTS game;

-- Game state table
CREATE TABLE IF NOT EXISTS game.game_state (
    game_state_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    current_turn INTEGER NOT NULL DEFAULT 1,
    turn_order JSONB, -- Array of character IDs in turn order
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    game_settings JSONB DEFAULT '{}'::jsonb,
    -- Time tracking (10 turns = 1 hour)
    game_day INTEGER DEFAULT 1 CHECK (game_day >= 1),
    minutes_since_midnight INTEGER DEFAULT 420 CHECK (minutes_since_midnight >= 0 AND minutes_since_midnight <= 1439),
    minutes_per_turn INTEGER DEFAULT 6 CHECK (minutes_per_turn > 0)
);

COMMENT ON TABLE game.game_state IS 'Tracks the current state of an active game session';
COMMENT ON COLUMN game.game_state.turn_order IS 'JSON array of character_ids representing turn order';
COMMENT ON COLUMN game.game_state.game_settings IS 'Configurable game settings (difficulty, permadeath, etc.)';
COMMENT ON COLUMN game.game_state.game_day IS 'Current in-game day number (starts at 1)';
COMMENT ON COLUMN game.game_state.minutes_since_midnight IS 'Current time of day in minutes (0-1439, where 0 = midnight, 420 = 7am, 1140 = 7pm)';
COMMENT ON COLUMN game.game_state.minutes_per_turn IS 'How many in-game minutes pass per turn (default 6 = 10 turns per hour)';

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION game.update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update updated_at
CREATE TRIGGER game_state_updated_at
    BEFORE UPDATE ON game.game_state
    FOR EACH ROW
    EXECUTE FUNCTION game.update_timestamp();

-- Index for active games
CREATE INDEX IF NOT EXISTS idx_game_state_active ON game.game_state(is_active) WHERE is_active = true;

-- Index for time tracking
CREATE INDEX IF NOT EXISTS idx_game_state_time ON game.game_state(game_day, minutes_since_midnight);
