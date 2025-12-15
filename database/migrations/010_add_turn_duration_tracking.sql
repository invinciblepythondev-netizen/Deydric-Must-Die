-- Migration: Add turn_duration and remaining_duration to turn_history
-- Description: Track how many turns an action takes to complete and how many remain
-- Date: 2025-12-12

-- Add turn_duration column to track total action duration
ALTER TABLE memory.turn_history
ADD COLUMN IF NOT EXISTS turn_duration INTEGER DEFAULT 1 CHECK (turn_duration >= 1);

-- Add remaining_duration column to track how many turns remain
ALTER TABLE memory.turn_history
ADD COLUMN IF NOT EXISTS remaining_duration INTEGER DEFAULT 0 CHECK (remaining_duration >= 0);

-- Add comments
COMMENT ON COLUMN memory.turn_history.turn_duration IS 'Total number of turns this action takes (1 turn = ~30 seconds)';
COMMENT ON COLUMN memory.turn_history.remaining_duration IS 'Number of turns remaining for this action to complete (0 = action complete this turn)';

-- Create index for querying ongoing actions
CREATE INDEX IF NOT EXISTS idx_turn_history_ongoing_actions
ON memory.turn_history(character_id, remaining_duration)
WHERE remaining_duration > 0;
