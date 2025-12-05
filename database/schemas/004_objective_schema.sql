-- ============================================================================
-- Objective System Schema
-- ============================================================================
-- Hierarchical objective/goal system for character decision-making
-- Supports: nested objectives, priorities, deadlines, delegation, decay

-- Create schema if it doesn't exist
CREATE SCHEMA IF NOT EXISTS objective;

-- ============================================================================
-- ENUMS
-- ============================================================================

-- Objective type categorization
CREATE TYPE objective.objective_type AS ENUM (
    'main',        -- Top-level character goals
    'child',       -- Sub-objectives that contribute to parent
    'recurring',   -- Daily/periodic needs (eating, sleeping)
    'delegated'    -- Assigned by another character
);

-- Objective status
CREATE TYPE objective.objective_status AS ENUM (
    'active',              -- Currently being pursued
    'completed',           -- Successfully achieved
    'blocked',             -- Cannot be completed (obstacle exists)
    'abandoned',           -- Character gave up
    'waiting_confirmation' -- Delegated task awaiting confirmation
);

-- Priority levels
CREATE TYPE objective.priority_level AS ENUM (
    'critical',    -- Survival, urgent threats
    'high',        -- Important goals, near deadlines
    'medium',      -- Normal objectives
    'low'          -- Nice-to-have, background goals
);

-- Source of objective
CREATE TYPE objective.objective_source AS ENUM (
    'initial',     -- From character creation
    'delegated',   -- Given by another character
    'internal',    -- Generated from character thoughts
    'recurring',   -- Auto-generated daily need
    'event'        -- Triggered by game event
);

-- ============================================================================
-- TABLES
-- ============================================================================

-- Main objective table
CREATE TABLE IF NOT EXISTS objective.character_objective (
    objective_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    character_id UUID NOT NULL REFERENCES character.character(character_id) ON DELETE CASCADE,
    game_id UUID NOT NULL REFERENCES game.game_state(game_state_id) ON DELETE CASCADE,

    -- Hierarchy
    parent_objective_id UUID REFERENCES objective.character_objective(objective_id) ON DELETE CASCADE,
    depth INTEGER NOT NULL DEFAULT 0 CHECK (depth >= 0 AND depth <= 5), -- Max 5 levels deep

    -- Core data
    objective_type objective.objective_type NOT NULL,
    description TEXT NOT NULL,
    success_criteria TEXT, -- What does completion look like?
    priority objective.priority_level NOT NULL DEFAULT 'medium',
    status objective.objective_status NOT NULL DEFAULT 'active',
    source objective.objective_source NOT NULL,

    -- Delegation tracking
    delegated_from_character_id UUID REFERENCES character.character(character_id),
    delegated_to_character_id UUID REFERENCES character.character(character_id),
    confirmation_required BOOLEAN DEFAULT FALSE,
    confirmation_received BOOLEAN DEFAULT FALSE,
    confirmation_turn INTEGER, -- When was confirmation received

    -- Deadlines
    deadline_soft TIMESTAMP, -- "Should complete by" - affects priority
    deadline_hard TIMESTAMP, -- "Must complete by" - failure if missed

    -- Lifecycle
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_turn INTEGER NOT NULL, -- Game turn when created
    completed_at TIMESTAMP,
    completed_turn INTEGER,
    last_evaluated_turn INTEGER, -- Last time LLM evaluated this objective

    -- Decay/forgetting
    decay_after_turns INTEGER, -- Auto-abandon after N inactive turns
    turns_inactive INTEGER DEFAULT 0, -- Consecutive turns without progress

    -- Completion tracking
    partial_completion FLOAT DEFAULT 0 CHECK (partial_completion >= 0 AND partial_completion <= 1),
    is_atomic BOOLEAN DEFAULT FALSE, -- Can be completed in single turn

    -- Metadata (flexible storage)
    metadata JSONB DEFAULT '{}'::jsonb,
    -- Examples:
    -- For sleep: {"hours_needed": 8, "hours_completed": 0}
    -- For food: {"hunger_threshold": 80}
    -- For navigation: {"target_location_id": "uuid"}

    -- Mood impact on completion
    mood_impact_positive INTEGER DEFAULT 0, -- Boost to mood if completed
    mood_impact_negative INTEGER DEFAULT 0, -- Penalty to mood if failed/blocked

    created_at_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Indexes for common queries
    CONSTRAINT valid_delegation CHECK (
        (objective_type = 'delegated' AND delegated_from_character_id IS NOT NULL) OR
        (objective_type != 'delegated')
    ),
    CONSTRAINT valid_completion CHECK (
        (status = 'completed' AND completed_at IS NOT NULL AND completed_turn IS NOT NULL) OR
        (status != 'completed')
    )
);

-- Index for character queries
CREATE INDEX IF NOT EXISTS idx_character_objective_character_id ON objective.character_objective(character_id);
CREATE INDEX IF NOT EXISTS idx_character_objective_game_id ON objective.character_objective(game_id);
CREATE INDEX IF NOT EXISTS idx_character_objective_status ON objective.character_objective(status);
CREATE INDEX IF NOT EXISTS idx_character_objective_priority ON objective.character_objective(priority);
CREATE INDEX IF NOT EXISTS idx_character_objective_parent ON objective.character_objective(parent_objective_id);

-- Composite index for active objectives by priority
CREATE INDEX IF NOT EXISTS idx_character_objective_active_priority
    ON objective.character_objective(character_id, status, priority)
    WHERE status = 'active';

-- Index for delegation queries
CREATE INDEX IF NOT EXISTS idx_character_objective_delegated_to
    ON objective.character_objective(delegated_to_character_id)
    WHERE delegated_to_character_id IS NOT NULL;

-- Index for evaluation scheduling
CREATE INDEX IF NOT EXISTS idx_character_objective_evaluation
    ON objective.character_objective(character_id, last_evaluated_turn, priority)
    WHERE status = 'active';

-- ============================================================================
-- Progress tracking
CREATE TABLE IF NOT EXISTS objective.objective_progress_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    objective_id UUID NOT NULL REFERENCES objective.character_objective(objective_id) ON DELETE CASCADE,
    turn_number INTEGER NOT NULL,

    -- What happened
    action_taken TEXT, -- Description of action that advanced objective
    progress_delta FLOAT, -- Change in partial_completion (e.g., +0.25)
    new_status objective.objective_status,

    -- Context
    notes TEXT, -- Additional notes about progress
    related_turn_history_id UUID, -- Link to turn_history if applicable

    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_objective_progress_objective ON objective.objective_progress_log(objective_id);

-- ============================================================================
-- Objective templates for recurring needs
CREATE TABLE IF NOT EXISTS objective.recurring_objective_template (
    template_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Template definition
    name TEXT NOT NULL, -- e.g., "Daily Sleep", "Hunger", "Hygiene"
    description_template TEXT NOT NULL, -- e.g., "Get at least {hours} hours of sleep"
    success_criteria_template TEXT,

    -- Default values
    default_priority objective.priority_level NOT NULL DEFAULT 'medium',
    decay_after_turns INTEGER,

    -- Recurrence rules
    recurs_every_turns INTEGER, -- Create new instance every N turns
    recurs_daily BOOLEAN DEFAULT FALSE, -- Create at start of each in-game day

    -- Metadata template
    metadata_template JSONB DEFAULT '{}'::jsonb,

    -- Trigger rules (when does priority increase?)
    priority_increase_rules JSONB DEFAULT '{}'::jsonb,
    -- Example: {"hunger": {"thresholds": [{"turns_inactive": 10, "new_priority": "high"}, {"turns_inactive": 20, "new_priority": "critical"}]}}

    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- Cognitive/Planning Trait System (Hybrid Approach)
-- ============================================================================

-- Reference table: Define cognitive traits and what they affect
CREATE TABLE IF NOT EXISTS objective.cognitive_trait (
    trait_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trait_name TEXT NOT NULL UNIQUE, -- e.g., "Methodical Planner", "Impulsive", "Detail-Oriented"
    description TEXT NOT NULL,

    -- How this trait affects planning behavior (per point of trait score)
    planning_capacity_modifier FLOAT DEFAULT 0, -- ± max simultaneous objectives
    focus_modifier FLOAT DEFAULT 0, -- + higher = sticks with objectives, - lower = easily distracted
    max_depth_modifier FLOAT DEFAULT 0, -- ± levels of child objective breakdown
    planning_frequency_modifier FLOAT DEFAULT 0, -- + plans more often, - plans less often (in turns)

    -- Trait intensity scale
    min_score INTEGER DEFAULT 0,
    max_score INTEGER DEFAULT 10,

    -- Additional effects (flexible)
    effects JSONB DEFAULT '{}'::jsonb,
    -- Examples:
    -- {"abandonment_threshold": 0.8} - impulsive characters abandon blocked objectives faster
    -- {"deadline_sensitivity": 1.5} - anxious characters react stronger to approaching deadlines
    -- {"multitask_penalty": 0.1} - scattered characters lose focus with too many objectives

    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Character's cognitive trait scores (stored as JSONB on character or junction table)
-- Option 1: Junction table (recommended for querying/analytics)
CREATE TABLE IF NOT EXISTS objective.character_cognitive_trait_score (
    character_id UUID NOT NULL REFERENCES character.character(character_id) ON DELETE CASCADE,
    trait_id UUID NOT NULL REFERENCES objective.cognitive_trait(trait_id) ON DELETE CASCADE,
    score INTEGER NOT NULL CHECK (score >= 0 AND score <= 10),

    PRIMARY KEY (character_id, trait_id),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_character_cognitive_trait_character ON objective.character_cognitive_trait_score(character_id);

-- Computed planning capacity for each character (denormalized for performance)
-- This gets recalculated when traits change or character state changes
CREATE TABLE IF NOT EXISTS objective.character_planning_state (
    character_id UUID PRIMARY KEY REFERENCES character.character(character_id) ON DELETE CASCADE,

    -- Computed cognitive limits (sum of base + trait modifiers)
    max_active_high_priority INTEGER DEFAULT 3,
    max_objective_depth INTEGER DEFAULT 3,
    planning_frequency_turns INTEGER DEFAULT 5, -- Re-evaluate every N turns
    focus_score FLOAT DEFAULT 5.0, -- 0-10 scale, affects abandonment/distraction

    -- Current load (updated as objectives are added/removed)
    current_high_priority_count INTEGER DEFAULT 0,
    current_critical_priority_count INTEGER DEFAULT 0,
    current_total_objective_count INTEGER DEFAULT 0,

    -- Planning behavior state
    last_full_planning_turn INTEGER, -- Last turn character did deep planning
    next_planning_turn INTEGER, -- When should next planning session occur

    -- Cognitive load multipliers (affected by mood, fatigue, wounds)
    capacity_multiplier FLOAT DEFAULT 1.0, -- 0.5 = half capacity, 2.0 = double capacity
    focus_multiplier FLOAT DEFAULT 1.0,

    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON SCHEMA objective IS 'Hierarchical objective/goal system for character decision-making';

COMMENT ON TABLE objective.character_objective IS 'Stores all character objectives in hierarchical tree structure';
COMMENT ON COLUMN objective.character_objective.depth IS 'Depth in objective tree (0 = main objective, 1+ = child)';
COMMENT ON COLUMN objective.character_objective.is_atomic IS 'TRUE if objective can be completed in a single turn';
COMMENT ON COLUMN objective.character_objective.decay_after_turns IS 'Auto-abandon if no progress for N turns';
COMMENT ON COLUMN objective.character_objective.metadata IS 'Flexible JSONB for objective-specific data';

COMMENT ON TABLE objective.objective_progress_log IS 'Tracks incremental progress toward objective completion';
COMMENT ON TABLE objective.recurring_objective_template IS 'Templates for auto-generated recurring objectives (sleep, eat, etc.)';

COMMENT ON TABLE objective.cognitive_trait IS 'Defines personality traits that affect planning behavior and objective management';
COMMENT ON TABLE objective.character_cognitive_trait_score IS 'Character scores for each cognitive trait (0-10 scale)';
COMMENT ON TABLE objective.character_planning_state IS 'Computed planning capacity and current cognitive load for each character';

COMMENT ON COLUMN objective.cognitive_trait.planning_capacity_modifier IS 'Change to max simultaneous objectives per trait point';
COMMENT ON COLUMN objective.cognitive_trait.focus_modifier IS 'Affects ability to maintain focus on objectives (higher = better focus)';
COMMENT ON COLUMN objective.cognitive_trait.max_depth_modifier IS 'Change to max objective breakdown depth per trait point';
COMMENT ON COLUMN objective.cognitive_trait.planning_frequency_modifier IS 'Change to turns between planning sessions per trait point';

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Update timestamp on modification
CREATE OR REPLACE FUNCTION objective.update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER character_objective_updated_at
    BEFORE UPDATE ON objective.character_objective
    FOR EACH ROW
    EXECUTE FUNCTION objective.update_updated_at();

CREATE TRIGGER character_cognitive_trait_score_updated_at
    BEFORE UPDATE ON objective.character_cognitive_trait_score
    FOR EACH ROW
    EXECUTE FUNCTION objective.update_updated_at();

CREATE TRIGGER character_planning_state_updated_at
    BEFORE UPDATE ON objective.character_planning_state
    FOR EACH ROW
    EXECUTE FUNCTION objective.update_updated_at();

-- ============================================================================
-- SAMPLE COGNITIVE TRAITS
-- ============================================================================
-- These would typically be inserted via a seed script, included here for reference

-- INSERT INTO objective.cognitive_trait (trait_name, description, planning_capacity_modifier, focus_modifier, max_depth_modifier, planning_frequency_modifier, effects) VALUES
-- ('Methodical Planner', 'Carefully plans multiple steps ahead', 0.5, 1.0, 0.3, -0.5, '{"deadline_sensitivity": 1.2}'),
-- ('Impulsive', 'Acts on immediate desires without extensive planning', -0.3, -1.0, -0.2, 1.0, '{"abandonment_threshold": 0.6, "immediate_gratification_bonus": 1.5}'),
-- ('Detail-Oriented', 'Breaks objectives into fine-grained steps', 0, 0.5, 0.5, -0.3, '{"completion_threshold": 0.95}'),
-- ('Scattered', 'Difficulty maintaining focus, jumps between objectives', 0.2, -1.5, 0, 0.5, '{"multitask_penalty": 0.15}'),
-- ('Single-Minded', 'Laser focus on one goal at a time', -0.5, 2.0, 0.1, 0, '{"secondary_objective_penalty": 0.5}'),
-- ('Anxious', 'Highly aware of deadlines and consequences', 0, 0.2, 0.1, -0.8, '{"deadline_sensitivity": 2.0, "blocked_objective_stress": 1.5}'),
-- ('Laid-Back', 'Relaxed approach to planning and deadlines', 0, -0.5, -0.1, 1.5, '{"deadline_sensitivity": 0.5, "abandonment_ease": 0.3}'),
-- ('Strategic Thinker', 'Long-term planning with contingencies', 0.8, 0.5, 0.4, -1.0, '{"contingency_planning": true, "blocked_reroute": 1.5}');
