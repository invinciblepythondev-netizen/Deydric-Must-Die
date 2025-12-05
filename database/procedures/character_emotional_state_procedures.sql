-- Character Emotional State Stored Procedures
-- Manages individual character emotional intensity and progression

-- ============================================================================
-- GET: Retrieve character emotional state
-- ============================================================================

CREATE OR REPLACE FUNCTION character_emotional_state_get(
    p_character_id UUID,
    p_game_state_id UUID
)
RETURNS TABLE(
    state_id UUID,
    character_id UUID,
    game_state_id UUID,
    primary_emotion TEXT,
    intensity_level INTEGER,
    intensity_points INTEGER,
    emotion_scores JSONB,
    last_intensity_change_turn INTEGER,
    emotional_trajectory TEXT,
    triggered_by_character_id UUID,
    trigger_description TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ces.state_id,
        ces.character_id,
        ces.game_state_id,
        ces.primary_emotion,
        ces.intensity_level,
        ces.intensity_points,
        ces.emotion_scores,
        ces.last_intensity_change_turn,
        ces.emotional_trajectory,
        ces.triggered_by_character_id,
        ces.trigger_description,
        ces.created_at,
        ces.updated_at
    FROM character.character_emotional_state ces
    WHERE ces.character_id = p_character_id
      AND ces.game_state_id = p_game_state_id;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION character_emotional_state_get IS 'Get individual character emotional state for a specific game';

-- ============================================================================
-- UPSERT: Create or update character emotional state
-- ============================================================================

CREATE OR REPLACE FUNCTION character_emotional_state_upsert(
    p_character_id UUID,
    p_game_state_id UUID,
    p_primary_emotion TEXT DEFAULT 'calm',
    p_intensity_level INTEGER DEFAULT 0,
    p_intensity_points INTEGER DEFAULT 0,
    p_emotion_scores JSONB DEFAULT '{}'::jsonb,
    p_emotional_trajectory TEXT DEFAULT 'stable',
    p_triggered_by_character_id UUID DEFAULT NULL,
    p_trigger_description TEXT DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    v_state_id UUID;
    v_current_turn INTEGER;
BEGIN
    -- Get current turn
    SELECT current_turn INTO v_current_turn
    FROM game.game_state
    WHERE game_state_id = p_game_state_id;

    INSERT INTO character.character_emotional_state (
        character_id,
        game_state_id,
        primary_emotion,
        intensity_level,
        intensity_points,
        emotion_scores,
        emotional_trajectory,
        triggered_by_character_id,
        trigger_description,
        last_intensity_change_turn
    ) VALUES (
        p_character_id,
        p_game_state_id,
        p_primary_emotion,
        p_intensity_level,
        p_intensity_points,
        p_emotion_scores,
        p_emotional_trajectory,
        p_triggered_by_character_id,
        p_trigger_description,
        v_current_turn
    )
    ON CONFLICT (character_id, game_state_id)
    DO UPDATE SET
        primary_emotion = EXCLUDED.primary_emotion,
        intensity_level = EXCLUDED.intensity_level,
        intensity_points = EXCLUDED.intensity_points,
        emotion_scores = EXCLUDED.emotion_scores,
        emotional_trajectory = EXCLUDED.emotional_trajectory,
        triggered_by_character_id = EXCLUDED.triggered_by_character_id,
        trigger_description = EXCLUDED.trigger_description,
        last_intensity_change_turn = v_current_turn,
        updated_at = NOW()
    RETURNING state_id INTO v_state_id;

    RETURN v_state_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION character_emotional_state_upsert IS 'Create or update character emotional state';

-- ============================================================================
-- ADJUST: Modify emotional state by delta (with content boundary checking)
-- ============================================================================

CREATE OR REPLACE FUNCTION character_emotional_state_adjust(
    p_character_id UUID,
    p_game_state_id UUID,
    p_emotion TEXT,
    p_points_delta INTEGER,
    p_triggered_by_character_id UUID DEFAULT NULL,
    p_trigger_description TEXT DEFAULT NULL
)
RETURNS TABLE(
    new_intensity_level INTEGER,
    new_intensity_points INTEGER,
    level_changed BOOLEAN,
    content_boundary_hit BOOLEAN,
    previous_level INTEGER
) AS $$
DECLARE
    v_current_points INTEGER;
    v_current_level INTEGER;
    v_new_points INTEGER;
    v_new_level INTEGER;
    v_max_allowed_level INTEGER;
    v_content_boundary BOOLEAN := FALSE;
    v_state_exists BOOLEAN;
    v_current_turn INTEGER;
    v_emotion_scores JSONB;
    v_emotion_score INTEGER;
BEGIN
    -- Check if state exists
    SELECT EXISTS(
        SELECT 1 FROM character.character_emotional_state
        WHERE character_id = p_character_id AND game_state_id = p_game_state_id
    ) INTO v_state_exists;

    -- Get current turn
    SELECT current_turn INTO v_current_turn
    FROM game.game_state
    WHERE game_state_id = p_game_state_id;

    -- Get or create state
    IF NOT v_state_exists THEN
        -- Create initial state
        PERFORM character_emotional_state_upsert(
            p_character_id,
            p_game_state_id,
            p_primary_emotion := 'calm',
            p_intensity_level := 0,
            p_intensity_points := 0,
            p_emotion_scores := '{}'::jsonb
        );
        v_current_points := 0;
        v_current_level := 0;
        v_emotion_scores := '{}'::jsonb;
    ELSE
        -- Get current state
        SELECT intensity_points, intensity_level, emotion_scores
        INTO v_current_points, v_current_level, v_emotion_scores
        FROM character.character_emotional_state
        WHERE character_id = p_character_id AND game_state_id = p_game_state_id;
    END IF;

    -- Update emotion score in JSONB
    v_emotion_score := COALESCE((v_emotion_scores->p_emotion)::INTEGER, 0);
    v_emotion_score := GREATEST(0, LEAST(120, v_emotion_score + p_points_delta));
    v_emotion_scores := jsonb_set(v_emotion_scores, ARRAY[p_emotion], to_jsonb(v_emotion_score), true);

    -- Calculate new total points (use highest emotion score as overall intensity)
    SELECT MAX((value)::INTEGER) INTO v_new_points
    FROM jsonb_each_text(v_emotion_scores);

    v_new_points := COALESCE(v_new_points, 0);

    -- Determine new level based on points
    v_new_level := CASE
        WHEN v_new_points >= 100 THEN 4
        WHEN v_new_points >= 75 THEN 3
        WHEN v_new_points >= 50 THEN 2
        WHEN v_new_points >= 25 THEN 1
        ELSE 0
    END;

    -- Check content settings for this emotion category
    SELECT content_settings_get_emotion_max_level(p_game_state_id, p_emotion)
    INTO v_max_allowed_level;

    -- Apply content boundary if needed
    IF v_new_level > v_max_allowed_level THEN
        v_content_boundary := TRUE;
        v_new_level := v_max_allowed_level;

        -- Cap points at the maximum for this level
        v_new_points := CASE v_max_allowed_level
            WHEN 0 THEN 24
            WHEN 1 THEN 49
            WHEN 2 THEN 74
            WHEN 3 THEN 99
            ELSE 120
        END;

        -- Cap the specific emotion score too
        v_emotion_scores := jsonb_set(v_emotion_scores, ARRAY[p_emotion], to_jsonb(v_new_points), true);
    END IF;

    -- Update state
    UPDATE character.character_emotional_state
    SET
        intensity_points = v_new_points,
        intensity_level = v_new_level,
        emotion_scores = v_emotion_scores,
        primary_emotion = CASE
            WHEN v_new_level > v_current_level THEN p_emotion
            ELSE primary_emotion
        END,
        emotional_trajectory = CASE
            WHEN v_new_level > v_current_level THEN 'rising'
            WHEN v_new_level < v_current_level THEN 'falling'
            WHEN ABS(p_points_delta) >= 15 THEN 'volatile'
            ELSE 'stable'
        END,
        triggered_by_character_id = p_triggered_by_character_id,
        trigger_description = p_trigger_description,
        last_intensity_change_turn = CASE
            WHEN v_new_level != v_current_level THEN v_current_turn
            ELSE last_intensity_change_turn
        END,
        updated_at = NOW()
    WHERE character_id = p_character_id AND game_state_id = p_game_state_id;

    RETURN QUERY SELECT
        v_new_level,
        v_new_points,
        v_new_level != v_current_level,
        v_content_boundary,
        v_current_level;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION character_emotional_state_adjust IS 'Adjust character emotional state by delta, respecting content boundaries. Returns new state and whether level changed.';

-- ============================================================================
-- RESET: Reset character emotional state to neutral
-- ============================================================================

CREATE OR REPLACE FUNCTION character_emotional_state_reset(
    p_character_id UUID,
    p_game_state_id UUID
)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE character.character_emotional_state
    SET
        primary_emotion = 'calm',
        intensity_level = 0,
        intensity_points = 0,
        emotion_scores = '{}'::jsonb,
        emotional_trajectory = 'stable',
        triggered_by_character_id = NULL,
        trigger_description = NULL,
        updated_at = NOW()
    WHERE character_id = p_character_id AND game_state_id = p_game_state_id;

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION character_emotional_state_reset IS 'Reset character emotional state to neutral/calm';

-- ============================================================================
-- GET DESCRIPTION: Natural language summary of emotional state
-- ============================================================================

CREATE OR REPLACE FUNCTION character_emotional_state_get_description(
    p_character_id UUID,
    p_game_state_id UUID
)
RETURNS TEXT AS $$
DECLARE
    v_state RECORD;
    v_level_name TEXT;
    v_trajectory_desc TEXT;
BEGIN
    SELECT * INTO v_state
    FROM character.character_emotional_state
    WHERE character_id = p_character_id AND game_state_id = p_game_state_id;

    IF NOT FOUND THEN
        RETURN 'Emotionally stable';
    END IF;

    -- Map intensity level to name
    v_level_name := CASE v_state.intensity_level
        WHEN 0 THEN 'neutral'
        WHEN 1 THEN 'engaged'
        WHEN 2 THEN 'passionate'
        WHEN 3 THEN 'extreme'
        WHEN 4 THEN 'at breaking point'
    END;

    -- Map trajectory to description
    v_trajectory_desc := CASE v_state.emotional_trajectory
        WHEN 'rising' THEN 'escalating'
        WHEN 'falling' THEN 'calming'
        WHEN 'volatile' THEN 'unstable'
        ELSE 'steady'
    END;

    RETURN format(
        'Feeling %s (%s intensity, %s) - %s points',
        v_state.primary_emotion,
        v_level_name,
        v_trajectory_desc,
        v_state.intensity_points
    );
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION character_emotional_state_get_description IS 'Get natural language description of character emotional state';

-- ============================================================================
-- LIST BY LOCATION: Get emotional states for all characters at a location
-- ============================================================================

CREATE OR REPLACE FUNCTION character_emotional_state_list_by_location(
    p_game_state_id UUID,
    p_location_id INTEGER
)
RETURNS TABLE(
    character_id UUID,
    character_name TEXT,
    primary_emotion TEXT,
    intensity_level INTEGER,
    intensity_points INTEGER,
    emotional_trajectory TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.character_id,
        c.name,
        ces.primary_emotion,
        ces.intensity_level,
        ces.intensity_points,
        ces.emotional_trajectory
    FROM character.character c
    LEFT JOIN character.character_emotional_state ces
        ON ces.character_id = c.character_id
        AND ces.game_state_id = p_game_state_id
    WHERE c.current_location_id = p_location_id;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION character_emotional_state_list_by_location IS 'Get emotional states for all characters at a location';

-- ============================================================================
-- DELETE: Remove character emotional state
-- ============================================================================

CREATE OR REPLACE FUNCTION character_emotional_state_delete(
    p_character_id UUID,
    p_game_state_id UUID
)
RETURNS BOOLEAN AS $$
BEGIN
    DELETE FROM character.character_emotional_state
    WHERE character_id = p_character_id AND game_state_id = p_game_state_id;

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION character_emotional_state_delete IS 'Delete character emotional state';
