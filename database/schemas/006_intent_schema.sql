-- Schema for multi-turn action intent tracking
-- Tracks character intents that span multiple turns

-- Create character_intent table
CREATE TABLE IF NOT EXISTS character.character_intent (
    intent_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    character_id UUID NOT NULL REFERENCES character.character(character_id) ON DELETE CASCADE,
    game_state_id UUID NOT NULL REFERENCES game.game_state(game_state_id) ON DELETE CASCADE,

    -- What they're doing
    intent_type TEXT NOT NULL, -- 'seduce', 'intimidate', 'persuade', 'investigate', 'combat', etc.
    intent_description TEXT, -- Human-readable description

    -- Who/what they're targeting
    target_character_id UUID REFERENCES character.character(character_id) ON DELETE CASCADE,
    target_object TEXT, -- For non-character targets (e.g., 'search the desk', 'open the door')

    -- Progress tracking
    progress_level INTEGER DEFAULT 0 CHECK (progress_level >= 0 AND progress_level <= 100),
    current_stage TEXT, -- Current stage name (e.g., 'flirting', 'escalating_touch', 'verbal_threat')

    -- Style and intensity
    intensity TEXT DEFAULT 'moderate' CHECK (intensity IN ('subtle', 'moderate', 'aggressive', 'desperate')),
    approach_style TEXT, -- 'gentle', 'forceful', 'playful', 'serious', 'romantic', 'lustful', etc.

    -- Temporal tracking
    started_turn INTEGER NOT NULL,
    last_action_turn INTEGER NOT NULL,

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    completion_status TEXT CHECK (completion_status IN ('achieved', 'abandoned', 'interrupted', 'rejected')),
    completion_turn INTEGER,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Constraints
    -- One active intent per character per type per target
    CONSTRAINT unique_active_intent UNIQUE(character_id, game_state_id, intent_type, target_character_id, is_active)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_character_intent_active
    ON character.character_intent(character_id, game_state_id, is_active)
    WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_character_intent_target
    ON character.character_intent(target_character_id)
    WHERE target_character_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_character_intent_turn
    ON character.character_intent(game_state_id, last_action_turn);

-- Comments for documentation
COMMENT ON TABLE character.character_intent IS 'Tracks character intents that span multiple turns (e.g., seduction, intimidation, persuasion)';
COMMENT ON COLUMN character.character_intent.intent_type IS 'Type of multi-turn action: seduce, intimidate, persuade, investigate, combat, etc.';
COMMENT ON COLUMN character.character_intent.progress_level IS 'Progress toward completion (0-100%)';
COMMENT ON COLUMN character.character_intent.current_stage IS 'Current stage in the action chain (e.g., show_interest, flirt, escalate_touch)';
COMMENT ON COLUMN character.character_intent.intensity IS 'How strongly they pursue the intent: subtle, moderate, aggressive, desperate';
COMMENT ON COLUMN character.character_intent.approach_style IS 'How they execute the intent: gentle, forceful, playful, serious, romantic, lustful';
COMMENT ON COLUMN character.character_intent.is_active IS 'True if currently being pursued, false if dormant or completed';
COMMENT ON COLUMN character.character_intent.completion_status IS 'How the intent ended: achieved, abandoned, interrupted, or rejected';
