-- Migration: Add intensity tracking to scene_mood
-- Description: Add intensity level, points, dominant arc, and scene phase to group emotional tracking
-- Dependencies: Requires game.scene_mood table from migration 003

-- Add intensity tracking columns
ALTER TABLE game.scene_mood
ADD COLUMN IF NOT EXISTS intensity_level INTEGER DEFAULT 0 CHECK (intensity_level >= 0 AND intensity_level <= 4);

ALTER TABLE game.scene_mood
ADD COLUMN IF NOT EXISTS intensity_points INTEGER DEFAULT 0 CHECK (intensity_points >= 0 AND intensity_points <= 120);

-- Add dominant arc tracking (which emotional progression is strongest)
ALTER TABLE game.scene_mood
ADD COLUMN IF NOT EXISTS dominant_arc TEXT CHECK (dominant_arc IN ('conflict', 'intimacy', 'fear', 'social', 'neutral'));

-- Add scene phase tracking (narrative structure)
ALTER TABLE game.scene_mood
ADD COLUMN IF NOT EXISTS scene_phase TEXT DEFAULT 'building' CHECK (scene_phase IN ('building', 'climax', 'resolution', 'aftermath'));

-- Add last level change tracking
ALTER TABLE game.scene_mood
ADD COLUMN IF NOT EXISTS last_level_change_turn INTEGER;

-- Comments
COMMENT ON COLUMN game.scene_mood.intensity_level IS 'Scene emotional intensity tier: 0=NEUTRAL(0-24pts), 1=ENGAGED(25-49pts), 2=PASSIONATE(50-74pts), 3=EXTREME(75-99pts), 4=BREAKING(100+pts)';
COMMENT ON COLUMN game.scene_mood.intensity_points IS 'Point accumulation 0-120, determines intensity_level progression';
COMMENT ON COLUMN game.scene_mood.dominant_arc IS 'Strongest emotional progression: conflict (tension→hostility→violence), intimacy (attraction→romance→intimacy), fear (unease→fear→terror), social (cooperation→camaraderie→devotion)';
COMMENT ON COLUMN game.scene_mood.scene_phase IS 'Narrative phase: building (tension rising), climax (peak intensity), resolution (winding down), aftermath (consequences)';
COMMENT ON COLUMN game.scene_mood.last_level_change_turn IS 'Turn number when intensity_level last changed';

-- Create index on intensity level for queries
CREATE INDEX IF NOT EXISTS idx_scene_mood_intensity
    ON game.scene_mood(intensity_level);

CREATE INDEX IF NOT EXISTS idx_scene_mood_arc
    ON game.scene_mood(dominant_arc);
