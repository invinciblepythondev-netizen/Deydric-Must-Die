-- Migration: Add tiered memory summaries with descriptive and condensed versions
-- Each character gets their own summaries at different time windows

-- Add new columns to memory_summary table
ALTER TABLE memory.memory_summary
ADD COLUMN IF NOT EXISTS character_id UUID REFERENCES character.character(character_id) ON DELETE CASCADE,
ADD COLUMN IF NOT EXISTS window_type TEXT DEFAULT 'recent_10', -- recent_10, rolling_50, rolling_100, deep_720, etc.
ADD COLUMN IF NOT EXISTS descriptive_summary TEXT, -- Detailed version for large context models
ADD COLUMN IF NOT EXISTS condensed_summary TEXT; -- Concise version for small context models

-- Migrate existing data: move summary_text to both descriptive and condensed
UPDATE memory.memory_summary
SET descriptive_summary = summary_text,
    condensed_summary = summary_text
WHERE descriptive_summary IS NULL;

-- Update comments
COMMENT ON COLUMN memory.memory_summary.character_id IS 'Character this summary is for (each character has their own perspective)';
COMMENT ON COLUMN memory.memory_summary.window_type IS 'Time window: recent_10 (last 10 turns), rolling_50 (11-60), rolling_100 (61-160), deep_720 (161-880), etc.';
COMMENT ON COLUMN memory.memory_summary.descriptive_summary IS 'Detailed narrative summary for large context models (200K+ tokens)';
COMMENT ON COLUMN memory.memory_summary.condensed_summary IS 'Concise summary for small context models (8-32K tokens)';

-- Add index for efficient character+window queries
CREATE INDEX IF NOT EXISTS idx_memory_summary_character_window
ON memory.memory_summary(character_id, game_state_id, window_type, end_turn DESC);

-- Create a view for easy querying of latest summaries
CREATE OR REPLACE VIEW memory.latest_character_summaries AS
SELECT DISTINCT ON (character_id, game_state_id, window_type)
    summary_id,
    game_state_id,
    character_id,
    window_type,
    start_turn,
    end_turn,
    descriptive_summary,
    condensed_summary,
    created_at
FROM memory.memory_summary
WHERE character_id IS NOT NULL
ORDER BY character_id, game_state_id, window_type, end_turn DESC;

COMMENT ON VIEW memory.latest_character_summaries IS 'Latest summary for each character at each time window tier';
