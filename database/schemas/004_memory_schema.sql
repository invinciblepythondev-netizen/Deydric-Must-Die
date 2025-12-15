-- Memory Schema
-- Contains turn history, memory summaries, and narrative events

-- Create schema
CREATE SCHEMA IF NOT EXISTS memory;

-- Turn history table
CREATE TABLE IF NOT EXISTS memory.turn_history (
    turn_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_state_id UUID NOT NULL, -- FK to game.game_state
    turn_number INTEGER NOT NULL,
    sequence_number INTEGER DEFAULT 0, -- Order within a turn (0, 1, 2...)

    -- Action details
    character_id UUID NOT NULL, -- FK to character.character
    action_type TEXT NOT NULL, -- think, speak, move, attack, use_item, examine, wait, interact
    action_description TEXT NOT NULL,
    action_target_character_id UUID, -- FK to character.character (if action targets another character)
    action_target_location_id INTEGER, -- FK to world.location (if moving)

    -- Visibility
    is_private BOOLEAN DEFAULT false, -- If true, only character knows (thoughts, internal decisions)
    location_id INTEGER NOT NULL, -- FK to world.location (where action occurred)
    witnesses JSONB DEFAULT '[]'::jsonb, -- Array of character_ids who witnessed this (empty for private)

    -- Outcome
    outcome_description TEXT,
    was_successful BOOLEAN,

    -- Significance (for embedding in vector DB)
    significance_score FLOAT DEFAULT 0.5, -- 0-1, higher = more important
    is_embedded BOOLEAN DEFAULT false, -- Has this been embedded in vector DB?
    embedding_id TEXT, -- ID in vector database

    -- Turn duration tracking
    turn_duration INTEGER DEFAULT 1 CHECK (turn_duration >= 1), -- Total turns this action takes (1 turn = ~30 seconds)
    remaining_duration INTEGER DEFAULT 0 CHECK (remaining_duration >= 0), -- Turns remaining for action completion

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Unique constraint includes sequence_number
    CONSTRAINT turn_history_game_turn_sequence UNIQUE(game_state_id, turn_number, character_id, sequence_number)
);

COMMENT ON TABLE memory.turn_history IS 'Every action taken in the game with witnesses and outcomes. Multiple actions per turn via sequence_number.';
COMMENT ON COLUMN memory.turn_history.sequence_number IS 'Order of actions within a single turn (0, 1, 2...) - allows think->speak->act';
COMMENT ON COLUMN memory.turn_history.is_private IS 'If true, only the character knows this (thoughts, internal decisions)';
COMMENT ON COLUMN memory.turn_history.action_type IS 'Action type: think, speak, move, attack, use_item, examine, wait, interact, etc.';
COMMENT ON COLUMN memory.turn_history.witnesses IS 'Array of character_ids who were in the same location (empty for private actions)';
COMMENT ON COLUMN memory.turn_history.significance_score IS 'How important this event is (0-1) for LLM context';
COMMENT ON COLUMN memory.turn_history.is_embedded IS 'Whether this turn has been embedded in the vector database';
COMMENT ON COLUMN memory.turn_history.turn_duration IS 'Total number of turns this action takes (1 turn = ~30 seconds)';
COMMENT ON COLUMN memory.turn_history.remaining_duration IS 'Number of turns remaining for this action to complete (0 = action complete this turn)';

-- Memory summaries table
CREATE TABLE IF NOT EXISTS memory.memory_summary (
    summary_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_state_id UUID NOT NULL, -- FK to game.game_state

    -- Turn range
    start_turn INTEGER NOT NULL,
    end_turn INTEGER NOT NULL,

    -- Summary content
    summary_text TEXT NOT NULL,
    summary_type TEXT DEFAULT 'short_term', -- short_term, session, game

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CHECK (end_turn >= start_turn)
);

COMMENT ON TABLE memory.memory_summary IS 'Compressed narrative summaries of turn ranges';
COMMENT ON COLUMN memory.memory_summary.summary_type IS 'short_term (10 turns), session (full session), game (entire game)';

-- Character thoughts/internal state log
CREATE TABLE IF NOT EXISTS memory.character_thought (
    thought_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    character_id UUID NOT NULL REFERENCES character.character(character_id) ON DELETE CASCADE,
    turn_number INTEGER NOT NULL,

    -- Thought content
    thought_text TEXT NOT NULL, -- Private internal monologue
    emotional_state TEXT, -- Current emotion

    -- Context
    triggered_by_turn_id UUID, -- FK to memory.turn_history (what prompted this thought)

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE memory.character_thought IS 'Private thoughts and internal state of characters (never revealed to others)';
COMMENT ON COLUMN memory.character_thought.thought_text IS 'Internal monologue only the character knows';

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_turn_history_game ON memory.turn_history(game_state_id, turn_number);
CREATE INDEX IF NOT EXISTS idx_turn_history_sequence ON memory.turn_history(game_state_id, turn_number, character_id, sequence_number);
CREATE INDEX IF NOT EXISTS idx_turn_history_character ON memory.turn_history(character_id);
CREATE INDEX IF NOT EXISTS idx_turn_history_location ON memory.turn_history(location_id);
CREATE INDEX IF NOT EXISTS idx_turn_history_significance ON memory.turn_history(significance_score DESC) WHERE significance_score > 0.7;
CREATE INDEX IF NOT EXISTS idx_turn_history_not_embedded ON memory.turn_history(is_embedded) WHERE is_embedded = false;
CREATE INDEX IF NOT EXISTS idx_turn_history_ongoing_actions ON memory.turn_history(character_id, remaining_duration) WHERE remaining_duration > 0;
CREATE INDEX IF NOT EXISTS idx_memory_summary_game ON memory.memory_summary(game_state_id, start_turn, end_turn);
CREATE INDEX IF NOT EXISTS idx_character_thought_character ON memory.character_thought(character_id, turn_number);
