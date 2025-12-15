-- Turn History and Memory Procedures

-- Create a new turn record (supports multiple actions per turn via sequence_number)
CREATE OR REPLACE FUNCTION turn_history_create(
    p_game_state_id UUID,
    p_turn_number INTEGER,
    p_character_id UUID,
    p_action_type TEXT,
    p_action_description TEXT,
    p_location_id INTEGER,
    p_sequence_number INTEGER DEFAULT 0,
    p_is_private BOOLEAN DEFAULT false,
    p_action_target_character_id UUID DEFAULT NULL,
    p_action_target_location_id INTEGER DEFAULT NULL,
    p_witnesses JSONB DEFAULT '[]'::jsonb,
    p_outcome_description TEXT DEFAULT NULL,
    p_was_successful BOOLEAN DEFAULT NULL,
    p_significance_score FLOAT DEFAULT 0.5
)
RETURNS UUID AS $$
DECLARE
    v_turn_id UUID;
BEGIN
    -- For private actions (thoughts), ensure witnesses is empty
    IF p_is_private THEN
        p_witnesses := '[]'::jsonb;
    END IF;

    INSERT INTO memory.turn_history (
        game_state_id, turn_number, character_id, sequence_number,
        action_type, action_description, location_id, is_private,
        action_target_character_id, action_target_location_id,
        witnesses, outcome_description, was_successful, significance_score
    ) VALUES (
        p_game_state_id, p_turn_number, p_character_id, p_sequence_number,
        p_action_type, p_action_description, p_location_id, p_is_private,
        p_action_target_character_id, p_action_target_location_id,
        p_witnesses, p_outcome_description, p_was_successful, p_significance_score
    )
    RETURNING turn_id INTO v_turn_id;

    RETURN v_turn_id;
END;
$$ LANGUAGE plpgsql;

-- Get working memory (last N turns, including all sequenced actions)
CREATE OR REPLACE FUNCTION turn_history_get_working_memory(
    p_game_state_id UUID,
    p_last_n_turns INTEGER DEFAULT 10
)
RETURNS TABLE (
    turn_id UUID,
    turn_number INTEGER,
    sequence_number INTEGER,
    character_id UUID,
    character_name TEXT,
    action_type TEXT,
    action_description TEXT,
    location_id INTEGER,
    location_name TEXT,
    is_private BOOLEAN,
    outcome_description TEXT,
    was_successful BOOLEAN,
    witnesses JSONB,
    created_at TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        th.turn_id, th.turn_number, th.sequence_number, th.character_id, c.name,
        th.action_type, th.action_description, th.location_id, l.name,
        th.is_private, th.outcome_description, th.was_successful,
        th.witnesses, th.created_at
    FROM memory.turn_history th
    JOIN character.character c ON c.character_id = th.character_id
    LEFT JOIN world.location l ON l.location_id = th.location_id
    WHERE th.game_state_id = p_game_state_id
      AND th.action_type != 'atmospheric' -- Exclude atmospheric descriptions from context
    ORDER BY th.turn_number DESC, th.sequence_number DESC
    LIMIT p_last_n_turns * 5; -- Multiply to account for multiple actions per turn
END;
$$ LANGUAGE plpgsql;

-- Get turns witnessed by a specific character (includes their own actions and what they saw)
-- Private actions of OTHER characters are excluded
CREATE OR REPLACE FUNCTION turn_history_get_witnessed(
    p_game_state_id UUID,
    p_character_id UUID,
    p_last_n_turns INTEGER DEFAULT 10
)
RETURNS TABLE (
    turn_id UUID,
    turn_number INTEGER,
    sequence_number INTEGER,
    character_id UUID,
    character_name TEXT,
    action_type TEXT,
    action_description TEXT,
    is_private BOOLEAN,
    outcome_description TEXT,
    turn_duration INTEGER,
    remaining_duration INTEGER,
    created_at TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        th.turn_id, th.turn_number, th.sequence_number, th.character_id, c.name,
        th.action_type, th.action_description, th.is_private,
        th.outcome_description, th.turn_duration, th.remaining_duration, th.created_at
    FROM memory.turn_history th
    JOIN character.character c ON c.character_id = th.character_id
    WHERE th.game_state_id = p_game_state_id
      AND th.action_type != 'atmospheric' -- Exclude atmospheric descriptions from context
      AND (
          -- Character's own actions (including private thoughts)
          th.character_id = p_character_id
          -- OR actions they witnessed (must not be private)
          OR (th.is_private = false AND th.witnesses @> to_jsonb(p_character_id::text))
      )
    ORDER BY th.turn_number DESC, th.sequence_number DESC
    LIMIT p_last_n_turns * 5; -- Account for multiple actions per turn
END;
$$ LANGUAGE plpgsql;

-- Mark turn as embedded in vector DB
CREATE OR REPLACE FUNCTION turn_history_mark_embedded(
    p_turn_id UUID,
    p_embedding_id TEXT
)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE memory.turn_history
    SET is_embedded = true,
        embedding_id = p_embedding_id
    WHERE turn_id = p_turn_id;

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

-- Get turns that need embedding (high significance, not yet embedded)
CREATE OR REPLACE FUNCTION turn_history_get_unembedded(
    p_min_significance FLOAT DEFAULT 0.7,
    p_limit INTEGER DEFAULT 100
)
RETURNS TABLE (
    turn_id UUID,
    game_state_id UUID,
    turn_number INTEGER,
    character_id UUID,
    action_description TEXT,
    outcome_description TEXT,
    significance_score FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        th.turn_id, th.game_state_id, th.turn_number, th.character_id,
        th.action_description, th.outcome_description, th.significance_score
    FROM memory.turn_history th
    WHERE th.is_embedded = false
      AND th.significance_score >= p_min_significance
    ORDER BY th.significance_score DESC, th.created_at ASC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Create memory summary
CREATE OR REPLACE FUNCTION memory_summary_create(
    p_game_state_id UUID,
    p_start_turn INTEGER,
    p_end_turn INTEGER,
    p_summary_text TEXT,
    p_summary_type TEXT DEFAULT 'short_term'
)
RETURNS UUID AS $$
DECLARE
    v_summary_id UUID;
BEGIN
    INSERT INTO memory.memory_summary (
        game_state_id, start_turn, end_turn, summary_text, summary_type
    ) VALUES (
        p_game_state_id, p_start_turn, p_end_turn, p_summary_text, p_summary_type
    )
    RETURNING summary_id INTO v_summary_id;

    RETURN v_summary_id;
END;
$$ LANGUAGE plpgsql;

-- Get memory summaries for a game
CREATE OR REPLACE FUNCTION memory_summary_get(
    p_game_state_id UUID,
    p_summary_type TEXT DEFAULT NULL
)
RETURNS TABLE (
    summary_id UUID,
    start_turn INTEGER,
    end_turn INTEGER,
    summary_text TEXT,
    summary_type TEXT,
    created_at TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ms.summary_id, ms.start_turn, ms.end_turn,
        ms.summary_text, ms.summary_type, ms.created_at
    FROM memory.memory_summary ms
    WHERE ms.game_state_id = p_game_state_id
      AND (p_summary_type IS NULL OR ms.summary_type = p_summary_type)
    ORDER BY ms.start_turn ASC;
END;
$$ LANGUAGE plpgsql;

-- Add character thought
CREATE OR REPLACE FUNCTION character_thought_create(
    p_character_id UUID,
    p_turn_number INTEGER,
    p_thought_text TEXT,
    p_emotional_state TEXT DEFAULT NULL,
    p_triggered_by_turn_id UUID DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    v_thought_id UUID;
BEGIN
    INSERT INTO memory.character_thought (
        character_id, turn_number, thought_text,
        emotional_state, triggered_by_turn_id
    ) VALUES (
        p_character_id, p_turn_number, p_thought_text,
        p_emotional_state, p_triggered_by_turn_id
    )
    RETURNING thought_id INTO v_thought_id;

    RETURN v_thought_id;
END;
$$ LANGUAGE plpgsql;

-- Get character thoughts
CREATE OR REPLACE FUNCTION character_thought_get(
    p_character_id UUID,
    p_last_n_turns INTEGER DEFAULT 10
)
RETURNS TABLE (
    thought_id UUID,
    turn_number INTEGER,
    thought_text TEXT,
    emotional_state TEXT,
    created_at TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ct.thought_id, ct.turn_number, ct.thought_text,
        ct.emotional_state, ct.created_at
    FROM memory.character_thought ct
    WHERE ct.character_id = p_character_id
    ORDER BY ct.turn_number DESC
    LIMIT p_last_n_turns;
END;
$$ LANGUAGE plpgsql;
