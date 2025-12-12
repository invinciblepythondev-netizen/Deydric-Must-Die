-- Stored procedures for managing character intents

-- Get active intent for a character
CREATE OR REPLACE FUNCTION character_intent_get_active(
    p_character_id UUID,
    p_game_state_id UUID,
    p_intent_type TEXT DEFAULT NULL
)
RETURNS TABLE (
    intent_id UUID,
    character_id UUID,
    game_state_id UUID,
    intent_type TEXT,
    intent_description TEXT,
    target_character_id UUID,
    target_character_name TEXT,
    target_object TEXT,
    progress_level INTEGER,
    current_stage TEXT,
    intensity TEXT,
    approach_style TEXT,
    started_turn INTEGER,
    last_action_turn INTEGER,
    is_active BOOLEAN,
    completion_status TEXT,
    completion_turn INTEGER
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        ci.intent_id,
        ci.character_id,
        ci.game_state_id,
        ci.intent_type,
        ci.intent_description,
        ci.target_character_id,
        tc.name AS target_character_name,
        ci.target_object,
        ci.progress_level,
        ci.current_stage,
        ci.intensity,
        ci.approach_style,
        ci.started_turn,
        ci.last_action_turn,
        ci.is_active,
        ci.completion_status,
        ci.completion_turn
    FROM character.character_intent ci
    LEFT JOIN character.character tc ON ci.target_character_id = tc.character_id
    WHERE ci.character_id = p_character_id
        AND ci.game_state_id = p_game_state_id
        AND ci.is_active = TRUE
        AND (p_intent_type IS NULL OR ci.intent_type = p_intent_type)
    ORDER BY ci.last_action_turn DESC
    LIMIT 1;
END;
$$;

-- Create or update an intent
CREATE OR REPLACE FUNCTION character_intent_upsert(
    p_intent_id UUID DEFAULT NULL,
    p_character_id UUID DEFAULT NULL,
    p_game_state_id UUID DEFAULT NULL,
    p_intent_type TEXT DEFAULT NULL,
    p_intent_description TEXT DEFAULT NULL,
    p_target_character_id UUID DEFAULT NULL,
    p_target_object TEXT DEFAULT NULL,
    p_progress_level INTEGER DEFAULT 0,
    p_current_stage TEXT DEFAULT NULL,
    p_intensity TEXT DEFAULT 'moderate',
    p_approach_style TEXT DEFAULT NULL,
    p_started_turn INTEGER DEFAULT NULL,
    p_last_action_turn INTEGER DEFAULT NULL,
    p_is_active BOOLEAN DEFAULT TRUE
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    v_intent_id UUID;
BEGIN
    -- If intent_id provided, update existing
    IF p_intent_id IS NOT NULL THEN
        UPDATE character.character_intent
        SET
            intent_description = COALESCE(p_intent_description, intent_description),
            progress_level = COALESCE(p_progress_level, progress_level),
            current_stage = COALESCE(p_current_stage, current_stage),
            intensity = COALESCE(p_intensity, intensity),
            approach_style = COALESCE(p_approach_style, approach_style),
            last_action_turn = COALESCE(p_last_action_turn, last_action_turn),
            is_active = COALESCE(p_is_active, is_active),
            updated_at = NOW()
        WHERE intent_id = p_intent_id
        RETURNING intent_id INTO v_intent_id;

        RETURN v_intent_id;
    END IF;

    -- Otherwise, deactivate any existing active intent of the same type/target
    UPDATE character.character_intent
    SET is_active = FALSE, updated_at = NOW()
    WHERE character_id = p_character_id
        AND game_state_id = p_game_state_id
        AND intent_type = p_intent_type
        AND (target_character_id = p_target_character_id OR (target_character_id IS NULL AND p_target_character_id IS NULL))
        AND is_active = TRUE;

    -- Insert new intent
    INSERT INTO character.character_intent (
        character_id,
        game_state_id,
        intent_type,
        intent_description,
        target_character_id,
        target_object,
        progress_level,
        current_stage,
        intensity,
        approach_style,
        started_turn,
        last_action_turn,
        is_active
    )
    VALUES (
        p_character_id,
        p_game_state_id,
        p_intent_type,
        p_intent_description,
        p_target_character_id,
        p_target_object,
        p_progress_level,
        p_current_stage,
        p_intensity,
        p_approach_style,
        p_started_turn,
        p_last_action_turn,
        p_is_active
    )
    RETURNING intent_id INTO v_intent_id;

    RETURN v_intent_id;
END;
$$;

-- Update intent progress
CREATE OR REPLACE FUNCTION character_intent_update_progress(
    p_intent_id UUID,
    p_progress_delta INTEGER,
    p_current_stage TEXT DEFAULT NULL,
    p_current_turn INTEGER DEFAULT NULL
)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_new_progress INTEGER;
BEGIN
    UPDATE character.character_intent
    SET
        progress_level = LEAST(100, GREATEST(0, progress_level + p_progress_delta)),
        current_stage = COALESCE(p_current_stage, current_stage),
        last_action_turn = COALESCE(p_current_turn, last_action_turn),
        updated_at = NOW()
    WHERE intent_id = p_intent_id
    RETURNING progress_level INTO v_new_progress;

    RETURN v_new_progress;
END;
$$;

-- Complete an intent
CREATE OR REPLACE FUNCTION character_intent_complete(
    p_intent_id UUID,
    p_completion_status TEXT,
    p_completion_turn INTEGER
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE character.character_intent
    SET
        is_active = FALSE,
        completion_status = p_completion_status,
        completion_turn = p_completion_turn,
        updated_at = NOW()
    WHERE intent_id = p_intent_id;
END;
$$;

-- Get all intents involving a character (as actor or target)
CREATE OR REPLACE FUNCTION character_intent_list_involving(
    p_character_id UUID,
    p_game_state_id UUID,
    p_only_active BOOLEAN DEFAULT TRUE
)
RETURNS TABLE (
    intent_id UUID,
    actor_character_id UUID,
    actor_character_name TEXT,
    target_character_id UUID,
    target_character_name TEXT,
    intent_type TEXT,
    progress_level INTEGER,
    current_stage TEXT,
    intensity TEXT,
    approach_style TEXT,
    is_actor BOOLEAN
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        ci.intent_id,
        ci.character_id AS actor_character_id,
        ac.name AS actor_character_name,
        ci.target_character_id,
        tc.name AS target_character_name,
        ci.intent_type,
        ci.progress_level,
        ci.current_stage,
        ci.intensity,
        ci.approach_style,
        (ci.character_id = p_character_id) AS is_actor
    FROM character.character_intent ci
    JOIN character.character ac ON ci.character_id = ac.character_id
    LEFT JOIN character.character tc ON ci.target_character_id = tc.character_id
    WHERE ci.game_state_id = p_game_state_id
        AND (ci.character_id = p_character_id OR ci.target_character_id = p_character_id)
        AND (NOT p_only_active OR ci.is_active = TRUE)
    ORDER BY ci.last_action_turn DESC;
END;
$$;

-- Deactivate stale intents (not pursued for N turns)
CREATE OR REPLACE FUNCTION character_intent_deactivate_stale(
    p_game_state_id UUID,
    p_current_turn INTEGER,
    p_stale_threshold INTEGER DEFAULT 3
)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_deactivated_count INTEGER;
BEGIN
    UPDATE character.character_intent
    SET
        is_active = FALSE,
        completion_status = 'abandoned',
        completion_turn = p_current_turn,
        updated_at = NOW()
    WHERE game_state_id = p_game_state_id
        AND is_active = TRUE
        AND (p_current_turn - last_action_turn) >= p_stale_threshold;

    GET DIAGNOSTICS v_deactivated_count = ROW_COUNT;
    RETURN v_deactivated_count;
END;
$$;

-- Get intent statistics for debugging/analysis
CREATE OR REPLACE FUNCTION character_intent_get_stats(
    p_game_state_id UUID
)
RETURNS TABLE (
    total_intents BIGINT,
    active_intents BIGINT,
    completed_intents BIGINT,
    avg_progress NUMERIC,
    most_common_intent_type TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    WITH stats AS (
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE is_active = TRUE) AS active,
            COUNT(*) FILTER (WHERE completion_status IS NOT NULL) AS completed,
            AVG(progress_level) AS avg_prog
        FROM character.character_intent
        WHERE game_state_id = p_game_state_id
    ),
    most_common AS (
        SELECT intent_type
        FROM character.character_intent
        WHERE game_state_id = p_game_state_id
        GROUP BY intent_type
        ORDER BY COUNT(*) DESC
        LIMIT 1
    )
    SELECT
        s.total,
        s.active,
        s.completed,
        s.avg_prog,
        mc.intent_type
    FROM stats s
    CROSS JOIN most_common mc;
END;
$$;

-- Comments
COMMENT ON FUNCTION character_intent_get_active IS 'Get the active intent for a character, optionally filtered by intent type';
COMMENT ON FUNCTION character_intent_upsert IS 'Create a new intent or update an existing one';
COMMENT ON FUNCTION character_intent_update_progress IS 'Update the progress level and stage of an intent';
COMMENT ON FUNCTION character_intent_complete IS 'Mark an intent as complete with a status (achieved, abandoned, interrupted, rejected)';
COMMENT ON FUNCTION character_intent_list_involving IS 'List all intents where the character is either the actor or target';
COMMENT ON FUNCTION character_intent_deactivate_stale IS 'Deactivate intents that havent been pursued for N turns';
COMMENT ON FUNCTION character_intent_get_stats IS 'Get statistics about intents in the current game for debugging';
