-- Migration: Add content_settings table for rating/content control
-- This table controls maximum intensity levels for different content types

-- Create content_settings table
CREATE TABLE IF NOT EXISTS game.content_settings (
    content_settings_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_state_id UUID NOT NULL UNIQUE, -- FK to game.game_state (one settings per game)

    -- Content intensity limits (0-4)
    -- 0 = None, 1 = Mild, 2 = Moderate, 3 = Strong, 4 = Unrestricted
    violence_max_level INTEGER DEFAULT 2 CHECK (violence_max_level BETWEEN 0 AND 4),
    intimacy_max_level INTEGER DEFAULT 1 CHECK (intimacy_max_level BETWEEN 0 AND 4),
    horror_max_level INTEGER DEFAULT 2 CHECK (horror_max_level BETWEEN 0 AND 4),
    profanity_max_level INTEGER DEFAULT 2 CHECK (profanity_max_level BETWEEN 0 AND 4),

    -- Overall rating preset (optional convenience field)
    rating_preset TEXT DEFAULT 'PG-13',
    -- Presets: 'G', 'PG', 'PG-13', 'R', 'Mature', 'Unrestricted'

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE game.content_settings IS 'Content rating controls per game state';
COMMENT ON COLUMN game.content_settings.violence_max_level IS 'Max violence intensity: 0=None, 1=Mild, 2=Moderate (PG-13), 3=Strong (R), 4=Unrestricted';
COMMENT ON COLUMN game.content_settings.intimacy_max_level IS 'Max intimacy intensity: 0=None, 1=Mild (kissing), 2=Moderate (fade-to-black), 3=Strong (explicit), 4=Unrestricted';
COMMENT ON COLUMN game.content_settings.horror_max_level IS 'Max horror intensity: 0=None, 1=Mild, 2=Moderate, 3=Strong, 4=Unrestricted';
COMMENT ON COLUMN game.content_settings.profanity_max_level IS 'Max profanity level: 0=None, 1=Mild, 2=Moderate, 3=Strong, 4=Unrestricted';
COMMENT ON COLUMN game.content_settings.rating_preset IS 'Overall rating preset for convenience (G, PG, PG-13, R, Mature, Unrestricted)';

-- Index for lookups
CREATE INDEX IF NOT EXISTS idx_content_settings_game_state
ON game.content_settings(game_state_id);

-- Create stored procedures

-- Get content settings for a game
CREATE OR REPLACE FUNCTION content_settings_get(
    p_game_state_id UUID
)
RETURNS TABLE(
    content_settings_id UUID,
    game_state_id UUID,
    violence_max_level INTEGER,
    intimacy_max_level INTEGER,
    horror_max_level INTEGER,
    profanity_max_level INTEGER,
    rating_preset TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        cs.content_settings_id,
        cs.game_state_id,
        cs.violence_max_level,
        cs.intimacy_max_level,
        cs.horror_max_level,
        cs.profanity_max_level,
        cs.rating_preset,
        cs.created_at,
        cs.updated_at
    FROM game.content_settings cs
    WHERE cs.game_state_id = p_game_state_id;
END;
$$ LANGUAGE plpgsql STABLE;

-- Create or update content settings
CREATE OR REPLACE FUNCTION content_settings_upsert(
    p_game_state_id UUID,
    p_violence_max_level INTEGER DEFAULT 2,
    p_intimacy_max_level INTEGER DEFAULT 1,
    p_horror_max_level INTEGER DEFAULT 2,
    p_profanity_max_level INTEGER DEFAULT 2,
    p_rating_preset TEXT DEFAULT 'PG-13'
)
RETURNS UUID AS $$
DECLARE
    v_content_settings_id UUID;
BEGIN
    INSERT INTO game.content_settings (
        game_state_id,
        violence_max_level,
        intimacy_max_level,
        horror_max_level,
        profanity_max_level,
        rating_preset
    ) VALUES (
        p_game_state_id,
        p_violence_max_level,
        p_intimacy_max_level,
        p_horror_max_level,
        p_profanity_max_level,
        p_rating_preset
    )
    ON CONFLICT (game_state_id) DO UPDATE SET
        violence_max_level = EXCLUDED.violence_max_level,
        intimacy_max_level = EXCLUDED.intimacy_max_level,
        horror_max_level = EXCLUDED.horror_max_level,
        profanity_max_level = EXCLUDED.profanity_max_level,
        rating_preset = EXCLUDED.rating_preset,
        updated_at = CURRENT_TIMESTAMP
    RETURNING content_settings_id INTO v_content_settings_id;

    RETURN v_content_settings_id;
END;
$$ LANGUAGE plpgsql;

-- Set content settings from rating preset
CREATE OR REPLACE FUNCTION content_settings_set_from_preset(
    p_game_state_id UUID,
    p_rating_preset TEXT
)
RETURNS UUID AS $$
DECLARE
    v_violence INTEGER;
    v_intimacy INTEGER;
    v_horror INTEGER;
    v_profanity INTEGER;
BEGIN
    -- Set levels based on preset
    CASE p_rating_preset
        WHEN 'G' THEN
            v_violence := 0;
            v_intimacy := 0;
            v_horror := 0;
            v_profanity := 0;
        WHEN 'PG' THEN
            v_violence := 1;
            v_intimacy := 0;
            v_horror := 1;
            v_profanity := 1;
        WHEN 'PG-13' THEN
            v_violence := 2;
            v_intimacy := 1;
            v_horror := 2;
            v_profanity := 2;
        WHEN 'R' THEN
            v_violence := 3;
            v_intimacy := 2;
            v_horror := 3;
            v_profanity := 3;
        WHEN 'Mature' THEN
            v_violence := 3;
            v_intimacy := 3;
            v_horror := 3;
            v_profanity := 3;
        WHEN 'Unrestricted' THEN
            v_violence := 4;
            v_intimacy := 4;
            v_horror := 4;
            v_profanity := 4;
        ELSE
            -- Default to PG-13
            v_violence := 2;
            v_intimacy := 1;
            v_horror := 2;
            v_profanity := 2;
    END CASE;

    RETURN content_settings_upsert(
        p_game_state_id,
        v_violence,
        v_intimacy,
        v_horror,
        v_profanity,
        p_rating_preset
    );
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION content_settings_get IS 'Get content settings for a game';
COMMENT ON FUNCTION content_settings_upsert IS 'Create or update content settings with specific levels';
COMMENT ON FUNCTION content_settings_set_from_preset IS 'Set content settings using a rating preset (G, PG, PG-13, R, Mature, Unrestricted)';
