-- Add in-game time tracking to game_state
-- 10 turns = 1 hour (6 minutes per turn)
-- Days are 24 hours, sun up at 7am, sun down at 7pm

-- Add game day number (starting from 1)
ALTER TABLE game.game_state
ADD COLUMN IF NOT EXISTS game_day INTEGER DEFAULT 1 CHECK (game_day >= 1);

-- Add minutes since midnight (0-1439)
-- Default to 7:00 AM (420 minutes since midnight)
ALTER TABLE game.game_state
ADD COLUMN IF NOT EXISTS minutes_since_midnight INTEGER DEFAULT 420 CHECK (minutes_since_midnight >= 0 AND minutes_since_midnight <= 1439);

-- Add minutes per turn configuration (default 6 = 10 turns per hour)
ALTER TABLE game.game_state
ADD COLUMN IF NOT EXISTS minutes_per_turn INTEGER DEFAULT 6 CHECK (minutes_per_turn > 0);

-- Add comments
COMMENT ON COLUMN game.game_state.game_day IS 'Current in-game day number (starts at 1)';
COMMENT ON COLUMN game.game_state.minutes_since_midnight IS 'Current time of day in minutes (0-1439, where 0 = midnight, 420 = 7am, 1140 = 7pm)';
COMMENT ON COLUMN game.game_state.minutes_per_turn IS 'How many in-game minutes pass per turn (default 6 = 10 turns per hour)';

-- Create index for querying by time of day
CREATE INDEX IF NOT EXISTS idx_game_state_time
ON game.game_state(game_day, minutes_since_midnight);
