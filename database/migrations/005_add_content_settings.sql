-- Migration: Add content rating and NSFW boundary system
-- Description: Per-game content boundaries for violence, romance, intimacy with fade-to-black options
-- Dependencies: Requires game.game_state table

CREATE TABLE IF NOT EXISTS game.content_settings (
    game_state_id UUID PRIMARY KEY REFERENCES game.game_state(game_state_id) ON DELETE CASCADE,

    -- Overall content rating
    content_rating TEXT DEFAULT 'pg13' CHECK (content_rating IN ('g', 'pg', 'pg13', 'r', 'nc17', 'unrestricted')),

    -- Category-specific limits (each category has max intensity level allowed: 0-4)
    violence_max_level INTEGER DEFAULT 2 CHECK (violence_max_level >= 0 AND violence_max_level <= 4),
    romance_max_level INTEGER DEFAULT 1 CHECK (romance_max_level >= 0 AND romance_max_level <= 4),
    intimacy_max_level INTEGER DEFAULT 0 CHECK (intimacy_max_level >= 0 AND intimacy_max_level <= 4),
    language_max_level INTEGER DEFAULT 2 CHECK (language_max_level >= 0 AND language_max_level <= 4),
    horror_max_level INTEGER DEFAULT 2 CHECK (horror_max_level >= 0 AND horror_max_level <= 4),

    -- Content flags
    allow_graphic_violence BOOLEAN DEFAULT FALSE,
    allow_sexual_content BOOLEAN DEFAULT FALSE,
    allow_substance_use BOOLEAN DEFAULT TRUE,
    allow_psychological_horror BOOLEAN DEFAULT TRUE,
    allow_death BOOLEAN DEFAULT TRUE,

    -- Fade-to-black preferences
    fade_to_black_violence BOOLEAN DEFAULT FALSE, -- Describe aftermath, not details
    fade_to_black_intimacy BOOLEAN DEFAULT TRUE,  -- Imply, don't describe
    fade_to_black_death BOOLEAN DEFAULT FALSE,    -- Show death scene vs fade before

    -- Provider preferences for mature content
    preferred_nsfw_provider TEXT, -- 'aiml', 'together', 'local', 'anthropic', etc.

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_content_settings_rating
    ON game.content_settings(content_rating);

-- Comments
COMMENT ON TABLE game.content_settings IS 'Per-game content boundaries and NSFW handling. Controls emotional intensity progression limits.';
COMMENT ON COLUMN game.content_settings.content_rating IS 'Overall rating: g, pg, pg13, r, nc17, unrestricted';
COMMENT ON COLUMN game.content_settings.violence_max_level IS 'Max violence intensity: 0=none, 1=implied, 2=moderate, 3=intense, 4=graphic';
COMMENT ON COLUMN game.content_settings.romance_max_level IS 'Max romance intensity: 0=none, 1=attraction, 2=romantic, 3=passionate, 4=explicit';
COMMENT ON COLUMN game.content_settings.intimacy_max_level IS 'Max intimacy intensity: 0=none, 1=kissing, 2=implied sexual, 3=sexual, 4=explicit sexual';
COMMENT ON COLUMN game.content_settings.language_max_level IS 'Max language intensity: 0=none, 1=mild, 2=moderate, 3=strong, 4=unrestricted';
COMMENT ON COLUMN game.content_settings.horror_max_level IS 'Max horror intensity: 0=none, 1=mild tension, 2=scary, 3=disturbing, 4=extreme horror';
COMMENT ON COLUMN game.content_settings.fade_to_black_violence IS 'If true, describe violent outcomes not graphic details';
COMMENT ON COLUMN game.content_settings.fade_to_black_intimacy IS 'If true, imply intimate moments rather than describe explicitly';
COMMENT ON COLUMN game.content_settings.preferred_nsfw_provider IS 'LLM provider to use when mature content generation is needed (aiml, together, local)';

-- Insert default settings for existing games (if any)
INSERT INTO game.content_settings (game_state_id, content_rating)
SELECT game_state_id, 'pg13'
FROM game.game_state
WHERE game_state_id NOT IN (SELECT game_state_id FROM game.content_settings)
ON CONFLICT (game_state_id) DO NOTHING;
