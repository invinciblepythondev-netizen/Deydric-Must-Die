-- Mood Tracking Stored Procedures
-- Procedures for managing scene mood/tension dynamics

-- Get mood for a location
CREATE OR REPLACE FUNCTION scene_mood_get(
    p_game_state_id UUID,
    p_location_id INTEGER
)
RETURNS TABLE(
    scene_mood_id UUID,
    game_state_id UUID,
    location_id INTEGER,
    tension_level INTEGER,
    romance_level INTEGER,
    hostility_level INTEGER,
    cooperation_level INTEGER,
    tension_trajectory TEXT,
    intensity_level INTEGER,
    intensity_points INTEGER,
    dominant_arc TEXT,
    scene_phase TEXT,
    last_mood_change_turn INTEGER,
    last_mood_change_description TEXT,
    last_level_change_turn INTEGER,
    character_ids JSONB,
    updated_at TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        sm.scene_mood_id,
        sm.game_state_id,
        sm.location_id,
        sm.tension_level,
        sm.romance_level,
        sm.hostility_level,
        sm.cooperation_level,
        sm.tension_trajectory,
        sm.intensity_level,
        sm.intensity_points,
        sm.dominant_arc,
        sm.scene_phase,
        sm.last_mood_change_turn,
        sm.last_mood_change_description,
        sm.last_level_change_turn,
        sm.character_ids,
        sm.updated_at
    FROM game.scene_mood sm
    WHERE sm.game_state_id = p_game_state_id
      AND sm.location_id = p_location_id;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION scene_mood_get IS 'Get current mood for a specific location with intensity tracking';

-- Create or update scene mood
CREATE OR REPLACE FUNCTION scene_mood_upsert(
    p_game_state_id UUID,
    p_location_id INTEGER,
    p_tension_level INTEGER DEFAULT 0,
    p_romance_level INTEGER DEFAULT 0,
    p_hostility_level INTEGER DEFAULT 0,
    p_cooperation_level INTEGER DEFAULT 0,
    p_tension_trajectory TEXT DEFAULT 'stable',
    p_intensity_level INTEGER DEFAULT 0,
    p_intensity_points INTEGER DEFAULT 0,
    p_dominant_arc TEXT DEFAULT NULL,
    p_scene_phase TEXT DEFAULT 'building',
    p_last_mood_change_turn INTEGER DEFAULT NULL,
    p_last_mood_change_description TEXT DEFAULT NULL,
    p_character_ids JSONB DEFAULT '[]'::jsonb
)
RETURNS UUID AS $$
DECLARE
    v_scene_mood_id UUID;
    v_current_turn INTEGER;
BEGIN
    -- Get current turn
    SELECT current_turn INTO v_current_turn
    FROM game.game_state
    WHERE game_state_id = p_game_state_id;

    INSERT INTO game.scene_mood (
        game_state_id,
        location_id,
        tension_level,
        romance_level,
        hostility_level,
        cooperation_level,
        tension_trajectory,
        intensity_level,
        intensity_points,
        dominant_arc,
        scene_phase,
        last_mood_change_turn,
        last_mood_change_description,
        last_level_change_turn,
        character_ids
    ) VALUES (
        p_game_state_id,
        p_location_id,
        p_tension_level,
        p_romance_level,
        p_hostility_level,
        p_cooperation_level,
        p_tension_trajectory,
        p_intensity_level,
        p_intensity_points,
        p_dominant_arc,
        p_scene_phase,
        p_last_mood_change_turn,
        p_last_mood_change_description,
        v_current_turn,
        p_character_ids
    )
    ON CONFLICT (game_state_id, location_id) DO UPDATE SET
        tension_level = EXCLUDED.tension_level,
        romance_level = EXCLUDED.romance_level,
        hostility_level = EXCLUDED.hostility_level,
        cooperation_level = EXCLUDED.cooperation_level,
        tension_trajectory = EXCLUDED.tension_trajectory,
        intensity_level = EXCLUDED.intensity_level,
        intensity_points = EXCLUDED.intensity_points,
        dominant_arc = EXCLUDED.dominant_arc,
        scene_phase = EXCLUDED.scene_phase,
        last_mood_change_turn = COALESCE(EXCLUDED.last_mood_change_turn, scene_mood.last_mood_change_turn),
        last_mood_change_description = COALESCE(EXCLUDED.last_mood_change_description, scene_mood.last_mood_change_description),
        last_level_change_turn = CASE
            WHEN EXCLUDED.intensity_level != scene_mood.intensity_level THEN v_current_turn
            ELSE scene_mood.last_level_change_turn
        END,
        character_ids = EXCLUDED.character_ids,
        updated_at = CURRENT_TIMESTAMP
    RETURNING scene_mood_id INTO v_scene_mood_id;

    RETURN v_scene_mood_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION scene_mood_upsert IS 'Create or update mood for a location with intensity tracking';

-- Adjust mood levels (add delta to existing values)
CREATE OR REPLACE FUNCTION scene_mood_adjust(
    p_game_state_id UUID,
    p_location_id INTEGER,
    p_tension_delta INTEGER DEFAULT 0,
    p_romance_delta INTEGER DEFAULT 0,
    p_hostility_delta INTEGER DEFAULT 0,
    p_cooperation_delta INTEGER DEFAULT 0,
    p_current_turn INTEGER DEFAULT NULL,
    p_mood_change_description TEXT DEFAULT NULL
)
RETURNS TABLE(
    new_tension INTEGER,
    new_romance INTEGER,
    new_hostility INTEGER,
    new_cooperation INTEGER,
    new_intensity_level INTEGER,
    new_intensity_points INTEGER,
    dominant_arc TEXT,
    tension_trajectory TEXT,
    level_changed BOOLEAN
) AS $$
DECLARE
    v_old_tension INTEGER;
    v_old_level INTEGER;
    v_new_tension INTEGER;
    v_new_romance INTEGER;
    v_new_hostility INTEGER;
    v_new_cooperation INTEGER;
    v_new_intensity_points INTEGER;
    v_new_intensity_level INTEGER;
    v_trajectory TEXT;
    v_dominant_arc TEXT;
    v_level_changed BOOLEAN;
    v_current_turn INTEGER;
BEGIN
    -- Get current values
    SELECT tension_level, intensity_level INTO v_old_tension, v_old_level
    FROM game.scene_mood
    WHERE game_state_id = p_game_state_id AND location_id = p_location_id;

    -- Get current turn if not provided
    IF p_current_turn IS NULL THEN
        SELECT current_turn INTO v_current_turn
        FROM game.game_state
        WHERE game_state_id = p_game_state_id;
    ELSE
        v_current_turn := p_current_turn;
    END IF;

    -- If no mood exists, create default first
    IF v_old_tension IS NULL THEN
        PERFORM scene_mood_upsert(p_game_state_id, p_location_id);
        v_old_tension := 0;
        v_old_level := 0;
    END IF;

    -- Apply deltas with bounds checking
    v_new_tension := GREATEST(-100, LEAST(100, v_old_tension + p_tension_delta));

    SELECT
        GREATEST(-100, LEAST(100, romance_level + p_romance_delta)),
        GREATEST(-100, LEAST(100, hostility_level + p_hostility_delta)),
        GREATEST(-100, LEAST(100, cooperation_level + p_cooperation_delta))
    INTO v_new_romance, v_new_hostility, v_new_cooperation
    FROM game.scene_mood
    WHERE game_state_id = p_game_state_id AND location_id = p_location_id;

    -- Calculate intensity points from highest absolute emotion value
    -- Convert -100 to +100 scale to 0-120 points
    v_new_intensity_points := GREATEST(
        ABS(v_new_tension),
        ABS(v_new_romance),
        ABS(v_new_hostility),
        ABS(v_new_cooperation)
    );

    -- Cap at 120
    v_new_intensity_points := LEAST(120, v_new_intensity_points);

    -- Determine intensity level from points
    v_new_intensity_level := CASE
        WHEN v_new_intensity_points >= 100 THEN 4
        WHEN v_new_intensity_points >= 75 THEN 3
        WHEN v_new_intensity_points >= 50 THEN 2
        WHEN v_new_intensity_points >= 25 THEN 1
        ELSE 0
    END;

    -- Determine dominant arc based on which emotion is strongest
    v_dominant_arc := CASE
        WHEN ABS(v_new_hostility) >= GREATEST(ABS(v_new_tension), ABS(v_new_romance), ABS(v_new_cooperation)) THEN 'conflict'
        WHEN ABS(v_new_romance) >= GREATEST(ABS(v_new_tension), ABS(v_new_hostility), ABS(v_new_cooperation)) THEN 'intimacy'
        WHEN ABS(v_new_tension) >= GREATEST(ABS(v_new_romance), ABS(v_new_hostility), ABS(v_new_cooperation)) THEN 'fear'
        WHEN ABS(v_new_cooperation) >= GREATEST(ABS(v_new_tension), ABS(v_new_romance), ABS(v_new_hostility)) THEN 'social'
        ELSE 'neutral'
    END;

    -- Determine trajectory
    v_trajectory := CASE
        WHEN p_tension_delta > 5 THEN 'rising'
        WHEN p_tension_delta < -5 THEN 'falling'
        ELSE 'stable'
    END;

    -- Check if level changed
    v_level_changed := v_new_intensity_level != v_old_level;

    -- Update scene mood
    UPDATE game.scene_mood
    SET
        tension_level = v_new_tension,
        romance_level = v_new_romance,
        hostility_level = v_new_hostility,
        cooperation_level = v_new_cooperation,
        intensity_level = v_new_intensity_level,
        intensity_points = v_new_intensity_points,
        dominant_arc = v_dominant_arc,
        tension_trajectory = v_trajectory,
        last_mood_change_turn = v_current_turn,
        last_mood_change_description = COALESCE(p_mood_change_description, last_mood_change_description),
        last_level_change_turn = CASE
            WHEN v_level_changed THEN v_current_turn
            ELSE last_level_change_turn
        END,
        updated_at = CURRENT_TIMESTAMP
    WHERE game_state_id = p_game_state_id AND location_id = p_location_id;

    RETURN QUERY SELECT
        v_new_tension,
        v_new_romance,
        v_new_hostility,
        v_new_cooperation,
        v_new_intensity_level,
        v_new_intensity_points,
        v_dominant_arc,
        v_trajectory,
        v_level_changed;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION scene_mood_adjust IS 'Adjust mood levels by delta amounts with automatic intensity tracking and dominant arc detection';

-- Get mood description for LLM context
CREATE OR REPLACE FUNCTION scene_mood_get_description(
    p_game_state_id UUID,
    p_location_id INTEGER
)
RETURNS TEXT AS $$
DECLARE
    v_mood RECORD;
    v_description TEXT;
    v_intensity_desc TEXT;
    v_arc_desc TEXT;
    v_phase_desc TEXT;
    v_hostility_desc TEXT;
    v_romance_desc TEXT;
    v_cooperation_desc TEXT;
    v_trajectory_desc TEXT;
BEGIN
    SELECT * INTO v_mood
    FROM game.scene_mood
    WHERE game_state_id = p_game_state_id AND location_id = p_location_id;

    -- If no mood tracked, return neutral
    IF v_mood IS NULL THEN
        RETURN 'General mood: Neutral (Level 0). The atmosphere is calm and unremarkable.';
    END IF;

    -- Describe intensity level
    v_intensity_desc := CASE v_mood.intensity_level
        WHEN 0 THEN 'Neutral'
        WHEN 1 THEN 'Engaged'
        WHEN 2 THEN 'Passionate'
        WHEN 3 THEN 'Extreme'
        WHEN 4 THEN 'At Breaking Point'
    END;

    -- Describe dominant arc
    v_arc_desc := CASE v_mood.dominant_arc
        WHEN 'conflict' THEN 'conflict escalating'
        WHEN 'intimacy' THEN 'romantic tension building'
        WHEN 'fear' THEN 'fear and unease growing'
        WHEN 'social' THEN 'social dynamics strengthening'
        ELSE 'emotionally balanced'
    END;

    -- Describe phase
    v_phase_desc := CASE v_mood.scene_phase
        WHEN 'building' THEN 'tensions are building'
        WHEN 'climax' THEN 'at a critical moment'
        WHEN 'resolution' THEN 'winding down'
        WHEN 'aftermath' THEN 'dealing with consequences'
        ELSE ''
    END;

    -- Describe specific emotions
    v_hostility_desc := CASE
        WHEN v_mood.hostility_level >= 75 THEN 'Violence feels imminent.'
        WHEN v_mood.hostility_level >= 50 THEN 'Hostility is high.'
        WHEN v_mood.hostility_level >= 25 THEN 'There is underlying antagonism.'
        WHEN v_mood.hostility_level <= -25 THEN 'The atmosphere is friendly.'
        ELSE ''
    END;

    v_romance_desc := CASE
        WHEN v_mood.romance_level >= 75 THEN 'There is intense romantic chemistry.'
        WHEN v_mood.romance_level >= 50 THEN 'There is romantic tension in the air.'
        WHEN v_mood.romance_level >= 25 THEN 'There are hints of attraction.'
        ELSE ''
    END;

    v_cooperation_desc := CASE
        WHEN v_mood.cooperation_level >= 50 THEN 'Characters seem willing to work together.'
        WHEN v_mood.cooperation_level <= -50 THEN 'Characters are competitive and distrustful.'
        ELSE ''
    END;

    -- Describe trajectory
    v_trajectory_desc := CASE v_mood.tension_trajectory
        WHEN 'rising' THEN 'The situation is escalating.'
        WHEN 'falling' THEN 'The situation is calming down.'
        ELSE ''
    END;

    -- Combine descriptions
    v_description := format('Emotional Intensity: %s (Level %s, %s points)',
        v_intensity_desc,
        v_mood.intensity_level,
        v_mood.intensity_points
    );

    IF v_arc_desc != 'emotionally balanced' THEN
        v_description := v_description || format('. Dominant theme: %s', v_arc_desc);
    END IF;

    IF v_phase_desc != '' THEN
        v_description := v_description || format(' (%s)', v_phase_desc);
    END IF;

    v_description := v_description || '.';

    IF v_trajectory_desc != '' THEN
        v_description := v_description || ' ' || v_trajectory_desc;
    END IF;

    IF v_hostility_desc != '' THEN
        v_description := v_description || ' ' || v_hostility_desc;
    END IF;

    IF v_romance_desc != '' THEN
        v_description := v_description || ' ' || v_romance_desc;
    END IF;

    IF v_cooperation_desc != '' THEN
        v_description := v_description || ' ' || v_cooperation_desc;
    END IF;

    RETURN v_description;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION scene_mood_get_description IS 'Get natural language mood description with intensity tracking for LLM prompts';

-- Get escalation/de-escalation guidance for action generation
CREATE OR REPLACE FUNCTION scene_mood_get_action_guidance(
    p_game_state_id UUID,
    p_location_id INTEGER
)
RETURNS TABLE(
    should_generate_escalation BOOLEAN,
    escalation_weight FLOAT,
    deescalation_required BOOLEAN,
    intensity_level INTEGER,
    intensity_points INTEGER,
    dominant_arc TEXT,
    scene_phase TEXT,
    can_escalate_further BOOLEAN,
    content_boundary_near BOOLEAN,
    mood_category TEXT
) AS $$
DECLARE
    v_mood RECORD;
    v_content_settings RECORD;
    v_should_escalate BOOLEAN;
    v_escalation_weight FLOAT;
    v_deescalation_req BOOLEAN;
    v_category TEXT;
    v_can_escalate BOOLEAN;
    v_boundary_near BOOLEAN;
    v_max_allowed_level INTEGER;
BEGIN
    SELECT * INTO v_mood
    FROM game.scene_mood
    WHERE game_state_id = p_game_state_id AND location_id = p_location_id;

    -- Get content settings
    SELECT * INTO v_content_settings
    FROM game.content_settings
    WHERE game_state_id = p_game_state_id;

    -- Default values for neutral mood
    v_should_escalate := FALSE;
    v_escalation_weight := 0.5;
    v_deescalation_req := TRUE;
    v_category := 'neutral';
    v_can_escalate := TRUE;
    v_boundary_near := FALSE;

    IF v_mood IS NOT NULL THEN
        -- Determine max allowed level based on dominant arc and content settings
        IF v_content_settings IS NOT NULL THEN
            v_max_allowed_level := CASE v_mood.dominant_arc
                WHEN 'conflict' THEN v_content_settings.violence_max_level
                WHEN 'intimacy' THEN v_content_settings.intimacy_max_level
                WHEN 'fear' THEN v_content_settings.horror_max_level
                ELSE 4  -- No limit for social/neutral
            END;
        ELSE
            -- Default PG-13 limits if no settings
            v_max_allowed_level := CASE v_mood.dominant_arc
                WHEN 'conflict' THEN 2
                WHEN 'intimacy' THEN 1
                WHEN 'fear' THEN 2
                ELSE 4
            END;
        END IF;

        -- Check if we can escalate further
        v_can_escalate := v_mood.intensity_level < v_max_allowed_level;

        -- Check if we're near content boundary
        v_boundary_near := v_mood.intensity_level >= (v_max_allowed_level - 1);

        -- Determine if we should generate escalation options
        v_should_escalate := (v_mood.tension_trajectory = 'rising' OR v_mood.intensity_points > 20)
            AND v_can_escalate;

        -- Calculate weight for escalation options (0-1)
        -- Based on intensity points, capped at content boundary
        IF v_can_escalate THEN
            v_escalation_weight := GREATEST(0.0, LEAST(0.8,
                v_mood.intensity_points / 100.0
            ));
        ELSE
            -- Can't escalate, reduce escalation weight
            v_escalation_weight := 0.1;
        END IF;

        -- Always require at least one de-escalation option
        v_deescalation_req := TRUE;

        -- Categorize mood based on intensity level and dominant arc
        v_category := CASE
            WHEN v_mood.dominant_arc = 'conflict' AND v_mood.intensity_level >= 3 THEN 'violent'
            WHEN v_mood.dominant_arc = 'conflict' AND v_mood.intensity_level >= 2 THEN 'antagonistic'
            WHEN v_mood.dominant_arc = 'intimacy' AND v_mood.intensity_level >= 3 THEN 'intimate'
            WHEN v_mood.dominant_arc = 'intimacy' AND v_mood.intensity_level >= 2 THEN 'romantic'
            WHEN v_mood.dominant_arc = 'intimacy' AND v_mood.intensity_level >= 1 THEN 'flirtatious'
            WHEN v_mood.dominant_arc = 'fear' AND v_mood.intensity_level >= 3 THEN 'terrifying'
            WHEN v_mood.dominant_arc = 'fear' AND v_mood.intensity_level >= 2 THEN 'frightening'
            WHEN v_mood.intensity_level >= 2 THEN 'intense'
            WHEN v_mood.intensity_level >= 1 THEN 'engaged'
            ELSE 'neutral'
        END;
    ELSE
        -- No mood tracked - defaults
        v_max_allowed_level := 4;
    END IF;

    RETURN QUERY SELECT
        v_should_escalate,
        v_escalation_weight,
        v_deescalation_req,
        COALESCE(v_mood.intensity_level, 0),
        COALESCE(v_mood.intensity_points, 0),
        v_mood.dominant_arc,
        v_mood.scene_phase,
        v_can_escalate,
        v_boundary_near,
        v_category;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION scene_mood_get_action_guidance IS 'Get guidance for action generation with intensity tracking and content boundary awareness';
