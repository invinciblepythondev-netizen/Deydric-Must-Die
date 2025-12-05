-- Add sequence number to support multiple actions per turn
-- This allows a character's turn to contain: think -> speak -> act (in order)

-- Add sequence_number column
ALTER TABLE memory.turn_history
ADD COLUMN sequence_number INTEGER DEFAULT 0;

-- Add is_private flag (for thoughts and internal actions)
ALTER TABLE memory.turn_history
ADD COLUMN is_private BOOLEAN DEFAULT false;

-- Update the unique constraint to include sequence_number
ALTER TABLE memory.turn_history
DROP CONSTRAINT IF EXISTS turn_history_game_turn;

ALTER TABLE memory.turn_history
ADD CONSTRAINT turn_history_game_turn_sequence
UNIQUE(game_state_id, turn_number, character_id, sequence_number);

-- Add index for querying actions in order
CREATE INDEX IF NOT EXISTS idx_turn_history_sequence
ON memory.turn_history(game_state_id, turn_number, character_id, sequence_number);

-- Add comments
COMMENT ON COLUMN memory.turn_history.sequence_number IS 'Order of actions within a single turn (0, 1, 2...)';
COMMENT ON COLUMN memory.turn_history.is_private IS 'If true, only the character knows this (thoughts, internal decisions)';

-- Expand action_type to include 'think'
COMMENT ON COLUMN memory.turn_history.action_type IS 'Action type: think, speak, move, attack, use_item, examine, wait, interact, etc.';
