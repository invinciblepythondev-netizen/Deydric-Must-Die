-- Content Settings Stored Procedures
-- Manages per-game content boundaries and NSFW handling

-- ============================================================================
-- GET: Retrieve content settings for a game
-- ============================================================================

CREATE OR REPLACE FUNCTION content_settings_get(
    p_game_state_id UUID
)
RETURNS TABLE(
    game_state_id UUID,
    content_rating TEXT,
    violence_max_level INTEGER,
    romance_max_level INTEGER,
    intimacy_max_level INTEGER,
    language_max_level INTEGER,
    horror_max_level INTEGER,
    allow_graphic_violence BOOLEAN,
    allow_sexual_content BOOLEAN,
    allow_substance_use BOOLEAN,
    allow_psychological_horror BOOLEAN,
    allow_death BOOLEAN,
    fade_to_black_violence BOOLEAN,
    fade_to_black_intimacy BOOLEAN,
    fade_to_black_death BOOLEAN,
    preferred_nsfw_provider TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        cs.game_state_id,
        cs.content_rating,
        cs.violence_max_level,
        cs.romance_max_level,
        cs.intimacy_max_level,
        cs.language_max_level,
        cs.horror_max_level,
        cs.allow_graphic_violence,
        cs.allow_sexual_content,
        cs.allow_substance_use,
        cs.allow_psychological_horror,
        cs.allow_death,
        cs.fade_to_black_violence,
        cs.fade_to_black_intimacy,
        cs.fade_to_black_death,
        cs.preferred_nsfw_provider,
        cs.created_at,
        cs.updated_at
    FROM game.content_settings cs
    WHERE cs.game_state_id = p_game_state_id;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION content_settings_get IS 'Get content settings for a game';

-- ============================================================================
-- UPSERT: Create or update content settings
-- ============================================================================

CREATE OR REPLACE FUNCTION content_settings_upsert(
    p_game_state_id UUID,
    p_content_rating TEXT DEFAULT 'pg13',
    p_violence_max_level INTEGER DEFAULT 2,
    p_romance_max_level INTEGER DEFAULT 1,
    p_intimacy_max_level INTEGER DEFAULT 0,
    p_language_max_level INTEGER DEFAULT 2,
    p_horror_max_level INTEGER DEFAULT 2,
    p_allow_graphic_violence BOOLEAN DEFAULT FALSE,
    p_allow_sexual_content BOOLEAN DEFAULT FALSE,
    p_allow_substance_use BOOLEAN DEFAULT TRUE,
    p_allow_psychological_horror BOOLEAN DEFAULT TRUE,
    p_allow_death BOOLEAN DEFAULT TRUE,
    p_fade_to_black_violence BOOLEAN DEFAULT FALSE,
    p_fade_to_black_intimacy BOOLEAN DEFAULT TRUE,
    p_fade_to_black_death BOOLEAN DEFAULT FALSE,
    p_preferred_nsfw_provider TEXT DEFAULT NULL
)
RETURNS UUID AS $$
BEGIN
    INSERT INTO game.content_settings (
        game_state_id,
        content_rating,
        violence_max_level,
        romance_max_level,
        intimacy_max_level,
        language_max_level,
        horror_max_level,
        allow_graphic_violence,
        allow_sexual_content,
        allow_substance_use,
        allow_psychological_horror,
        allow_death,
        fade_to_black_violence,
        fade_to_black_intimacy,
        fade_to_black_death,
        preferred_nsfw_provider
    ) VALUES (
        p_game_state_id,
        p_content_rating,
        p_violence_max_level,
        p_romance_max_level,
        p_intimacy_max_level,
        p_language_max_level,
        p_horror_max_level,
        p_allow_graphic_violence,
        p_allow_sexual_content,
        p_allow_substance_use,
        p_allow_psychological_horror,
        p_allow_death,
        p_fade_to_black_violence,
        p_fade_to_black_intimacy,
        p_fade_to_black_death,
        p_preferred_nsfw_provider
    )
    ON CONFLICT (game_state_id)
    DO UPDATE SET
        content_rating = EXCLUDED.content_rating,
        violence_max_level = EXCLUDED.violence_max_level,
        romance_max_level = EXCLUDED.romance_max_level,
        intimacy_max_level = EXCLUDED.intimacy_max_level,
        language_max_level = EXCLUDED.language_max_level,
        horror_max_level = EXCLUDED.horror_max_level,
        allow_graphic_violence = EXCLUDED.allow_graphic_violence,
        allow_sexual_content = EXCLUDED.allow_sexual_content,
        allow_substance_use = EXCLUDED.allow_substance_use,
        allow_psychological_horror = EXCLUDED.allow_psychological_horror,
        allow_death = EXCLUDED.allow_death,
        fade_to_black_violence = EXCLUDED.fade_to_black_violence,
        fade_to_black_intimacy = EXCLUDED.fade_to_black_intimacy,
        fade_to_black_death = EXCLUDED.fade_to_black_death,
        preferred_nsfw_provider = EXCLUDED.preferred_nsfw_provider,
        updated_at = NOW();

    RETURN p_game_state_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION content_settings_upsert IS 'Create or update content settings for a game';

-- ============================================================================
-- SET FROM PRESET: Apply preset content rating
-- ============================================================================

CREATE OR REPLACE FUNCTION content_settings_set_preset(
    p_game_state_id UUID,
    p_content_rating TEXT
)
RETURNS UUID AS $$
BEGIN
    -- Apply preset based on rating
    CASE p_content_rating
        WHEN 'g' THEN
            PERFORM content_settings_upsert(
                p_game_state_id,
                'g',
                0, 0, 0, 0, 0,  -- All max levels 0
                FALSE, FALSE, FALSE, FALSE, FALSE,  -- No mature content
                FALSE, TRUE, FALSE  -- Fade to black for intimacy only
            );
        WHEN 'pg' THEN
            PERFORM content_settings_upsert(
                p_game_state_id,
                'pg',
                1, 1, 0, 1, 1,  -- Mild/implied content
                FALSE, FALSE, TRUE, TRUE, TRUE,
                FALSE, TRUE, FALSE
            );
        WHEN 'pg13' THEN
            PERFORM content_settings_upsert(
                p_game_state_id,
                'pg13',
                2, 2, 1, 2, 2,  -- Moderate content, kissing allowed
                FALSE, FALSE, TRUE, TRUE, TRUE,
                FALSE, TRUE, FALSE
            );
        WHEN 'r' THEN
            PERFORM content_settings_upsert(
                p_game_state_id,
                'r',
                3, 3, 2, 3, 3,  -- Intense content, implied sexual
                TRUE, FALSE, TRUE, TRUE, TRUE,
                FALSE, TRUE, FALSE,
                'aiml'  -- Use permissive provider
            );
        WHEN 'nc17' THEN
            PERFORM content_settings_upsert(
                p_game_state_id,
                'nc17',
                4, 4, 3, 4, 4,  -- Graphic content, sexual content
                TRUE, TRUE, TRUE, TRUE, TRUE,
                FALSE, FALSE, FALSE,
                'aiml'  -- Use permissive provider
            );
        WHEN 'unrestricted' THEN
            PERFORM content_settings_upsert(
                p_game_state_id,
                'unrestricted',
                4, 4, 4, 4, 4,  -- Everything allowed
                TRUE, TRUE, TRUE, TRUE, TRUE,
                FALSE, FALSE, FALSE,
                'local'  -- Use local model if available
            );
    END CASE;

    RETURN p_game_state_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION content_settings_set_preset IS 'Apply preset content settings based on standard rating (g, pg, pg13, r, nc17, unrestricted)';

-- ============================================================================
-- GET EMOTION MAX LEVEL: Helper to get max level for specific emotion category
-- ============================================================================

CREATE OR REPLACE FUNCTION content_settings_get_emotion_max_level(
    p_game_state_id UUID,
    p_emotion_category TEXT
)
RETURNS INTEGER AS $$
DECLARE
    v_max_level INTEGER;
BEGIN
    -- Map emotion categories to content setting limits
    SELECT CASE
        WHEN p_emotion_category IN ('violence', 'hostility', 'anger', 'aggression') THEN
            violence_max_level
        WHEN p_emotion_category IN ('romance', 'attraction', 'affection') THEN
            romance_max_level
        WHEN p_emotion_category IN ('intimacy', 'desire', 'lust') THEN
            intimacy_max_level
        WHEN p_emotion_category IN ('fear', 'terror', 'dread') THEN
            horror_max_level
        ELSE
            4  -- Default: no limit for other emotions (joy, sadness, etc.)
    END INTO v_max_level
    FROM game.content_settings
    WHERE game_state_id = p_game_state_id;

    -- If no settings found, use default PG-13 limits
    IF v_max_level IS NULL THEN
        v_max_level := CASE
            WHEN p_emotion_category IN ('violence', 'hostility', 'anger', 'aggression') THEN 2
            WHEN p_emotion_category IN ('romance', 'attraction', 'affection') THEN 2
            WHEN p_emotion_category IN ('intimacy', 'desire', 'lust') THEN 1
            WHEN p_emotion_category IN ('fear', 'terror', 'dread') THEN 2
            ELSE 4
        END;
    END IF;

    RETURN v_max_level;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION content_settings_get_emotion_max_level IS 'Get maximum allowed intensity level for a specific emotion category based on content settings';

-- ============================================================================
-- CAN ESCALATE: Check if emotion can escalate to target level
-- ============================================================================

CREATE OR REPLACE FUNCTION content_settings_can_escalate(
    p_game_state_id UUID,
    p_emotion_category TEXT,
    p_target_level INTEGER
)
RETURNS TABLE(
    can_escalate BOOLEAN,
    reason TEXT
) AS $$
DECLARE
    v_max_level INTEGER;
BEGIN
    v_max_level := content_settings_get_emotion_max_level(p_game_state_id, p_emotion_category);

    IF p_target_level <= v_max_level THEN
        RETURN QUERY SELECT TRUE, NULL::TEXT;
    ELSE
        RETURN QUERY SELECT FALSE, format('Content rating limit: %s emotions capped at level %s', p_emotion_category, v_max_level);
    END IF;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION content_settings_can_escalate IS 'Check if an emotion can escalate to target level without violating content boundaries';

-- ============================================================================
-- GET FADE TO BLACK INSTRUCTIONS: Generate LLM instructions for content handling
-- ============================================================================

CREATE OR REPLACE FUNCTION content_settings_get_fade_instructions(
    p_game_state_id UUID
)
RETURNS TEXT AS $$
DECLARE
    v_settings RECORD;
    v_instructions TEXT := '';
BEGIN
    SELECT * INTO v_settings
    FROM game.content_settings
    WHERE game_state_id = p_game_state_id;

    IF NOT FOUND THEN
        -- Default PG-13 instructions
        RETURN 'Keep content appropriate for PG-13 audiences. Imply intimate moments rather than describing explicitly.';
    END IF;

    -- Build instructions based on settings
    IF v_settings.fade_to_black_violence THEN
        v_instructions := v_instructions || E'\n- For violent actions, describe the intent and aftermath, not graphic details of injuries.';
    END IF;

    IF v_settings.fade_to_black_intimacy THEN
        v_instructions := v_instructions || E'\n- For intimate actions, imply what happens rather than describing explicitly. Use phrases like "they draw closer" or "the moment becomes private".';
    END IF;

    IF v_settings.fade_to_black_death THEN
        v_instructions := v_instructions || E'\n- For death scenes, fade to black before the moment of death, describing only the lead-up.';
    END IF;

    IF NOT v_settings.allow_graphic_violence THEN
        v_instructions := v_instructions || E'\n- Avoid graphic descriptions of violence, blood, or gore.';
    END IF;

    IF NOT v_settings.allow_sexual_content THEN
        v_instructions := v_instructions || E'\n- Do not include sexual content. Keep romantic interactions at kissing/affection level.';
    END IF;

    RETURN TRIM(v_instructions);
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION content_settings_get_fade_instructions IS 'Generate LLM prompt instructions for handling fade-to-black and content boundaries';

-- ============================================================================
-- DELETE: Remove content settings (reset to defaults)
-- ============================================================================

CREATE OR REPLACE FUNCTION content_settings_delete(
    p_game_state_id UUID
)
RETURNS BOOLEAN AS $$
BEGIN
    DELETE FROM game.content_settings
    WHERE game_state_id = p_game_state_id;

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION content_settings_delete IS 'Delete content settings (game will use default PG-13)';
