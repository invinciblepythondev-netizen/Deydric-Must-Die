-- ============================================================================
-- Objective System Stored Procedures
-- ============================================================================

-- ============================================================================
-- COGNITIVE TRAIT MANAGEMENT
-- ============================================================================

-- Get cognitive trait by ID or name
CREATE OR REPLACE FUNCTION objective.cognitive_trait_get(
    p_trait_id UUID DEFAULT NULL,
    p_trait_name TEXT DEFAULT NULL
)
RETURNS TABLE (
    trait_id UUID,
    trait_name TEXT,
    description TEXT,
    planning_capacity_modifier FLOAT,
    focus_modifier FLOAT,
    max_depth_modifier FLOAT,
    planning_frequency_modifier FLOAT,
    min_score INTEGER,
    max_score INTEGER,
    effects JSONB,
    is_active BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ct.trait_id, ct.trait_name, ct.description,
        ct.planning_capacity_modifier, ct.focus_modifier,
        ct.max_depth_modifier, ct.planning_frequency_modifier,
        ct.min_score, ct.max_score, ct.effects, ct.is_active
    FROM objective.cognitive_trait ct
    WHERE (p_trait_id IS NULL OR ct.trait_id = p_trait_id)
      AND (p_trait_name IS NULL OR ct.trait_name = p_trait_name)
      AND ct.is_active = TRUE;
END;
$$ LANGUAGE plpgsql;

-- Upsert cognitive trait
CREATE OR REPLACE FUNCTION objective.cognitive_trait_upsert(
    p_trait_id UUID,
    p_trait_name TEXT,
    p_description TEXT,
    p_planning_capacity_modifier FLOAT DEFAULT 0,
    p_focus_modifier FLOAT DEFAULT 0,
    p_max_depth_modifier FLOAT DEFAULT 0,
    p_planning_frequency_modifier FLOAT DEFAULT 0,
    p_min_score INTEGER DEFAULT 0,
    p_max_score INTEGER DEFAULT 10,
    p_effects JSONB DEFAULT '{}'::jsonb,
    p_is_active BOOLEAN DEFAULT TRUE
)
RETURNS UUID AS $$
DECLARE
    v_trait_id UUID;
BEGIN
    INSERT INTO objective.cognitive_trait (
        trait_id, trait_name, description,
        planning_capacity_modifier, focus_modifier,
        max_depth_modifier, planning_frequency_modifier,
        min_score, max_score, effects, is_active
    ) VALUES (
        COALESCE(p_trait_id, gen_random_uuid()),
        p_trait_name, p_description,
        p_planning_capacity_modifier, p_focus_modifier,
        p_max_depth_modifier, p_planning_frequency_modifier,
        p_min_score, p_max_score, p_effects, p_is_active
    )
    ON CONFLICT (trait_name) DO UPDATE SET
        description = EXCLUDED.description,
        planning_capacity_modifier = EXCLUDED.planning_capacity_modifier,
        focus_modifier = EXCLUDED.focus_modifier,
        max_depth_modifier = EXCLUDED.max_depth_modifier,
        planning_frequency_modifier = EXCLUDED.planning_frequency_modifier,
        min_score = EXCLUDED.min_score,
        max_score = EXCLUDED.max_score,
        effects = EXCLUDED.effects,
        is_active = EXCLUDED.is_active
    RETURNING trait_id INTO v_trait_id;

    RETURN v_trait_id;
END;
$$ LANGUAGE plpgsql;

-- Set character's cognitive trait score
CREATE OR REPLACE FUNCTION objective.character_cognitive_trait_set(
    p_character_id UUID,
    p_trait_id UUID,
    p_score INTEGER
)
RETURNS VOID AS $$
BEGIN
    INSERT INTO objective.character_cognitive_trait_score (character_id, trait_id, score)
    VALUES (p_character_id, p_trait_id, p_score)
    ON CONFLICT (character_id, trait_id) DO UPDATE SET
        score = EXCLUDED.score,
        updated_at = NOW();
END;
$$ LANGUAGE plpgsql;

-- Get all cognitive traits for a character with scores
CREATE OR REPLACE FUNCTION objective.character_cognitive_traits_get(
    p_character_id UUID
)
RETURNS TABLE (
    trait_id UUID,
    trait_name TEXT,
    score INTEGER,
    planning_capacity_modifier FLOAT,
    focus_modifier FLOAT,
    max_depth_modifier FLOAT,
    planning_frequency_modifier FLOAT,
    effects JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ct.trait_id, ct.trait_name, ccts.score,
        ct.planning_capacity_modifier, ct.focus_modifier,
        ct.max_depth_modifier, ct.planning_frequency_modifier,
        ct.effects
    FROM objective.character_cognitive_trait_score ccts
    JOIN objective.cognitive_trait ct ON ccts.trait_id = ct.trait_id
    WHERE ccts.character_id = p_character_id
      AND ct.is_active = TRUE
    ORDER BY ct.trait_name;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- PLANNING STATE MANAGEMENT
-- ============================================================================

-- Recalculate and update character's planning capacity based on traits
CREATE OR REPLACE FUNCTION objective.character_planning_state_recalculate(
    p_character_id UUID,
    p_capacity_multiplier FLOAT DEFAULT 1.0,
    p_focus_multiplier FLOAT DEFAULT 1.0
)
RETURNS VOID AS $$
DECLARE
    v_base_capacity INTEGER := 3;
    v_base_depth INTEGER := 3;
    v_base_frequency INTEGER := 5;
    v_base_focus FLOAT := 5.0;
    v_total_capacity FLOAT;
    v_total_depth FLOAT;
    v_total_frequency FLOAT;
    v_total_focus FLOAT;
BEGIN
    -- Sum up all trait modifiers weighted by character's scores
    SELECT
        v_base_capacity + COALESCE(SUM(ct.planning_capacity_modifier * ccts.score), 0),
        v_base_depth + COALESCE(SUM(ct.max_depth_modifier * ccts.score), 0),
        v_base_frequency + COALESCE(SUM(ct.planning_frequency_modifier * ccts.score), 0),
        v_base_focus + COALESCE(SUM(ct.focus_modifier * ccts.score), 0)
    INTO v_total_capacity, v_total_depth, v_total_frequency, v_total_focus
    FROM objective.character_cognitive_trait_score ccts
    JOIN objective.cognitive_trait ct ON ccts.trait_id = ct.trait_id
    WHERE ccts.character_id = p_character_id
      AND ct.is_active = TRUE;

    -- Apply multipliers and bounds
    v_total_capacity := GREATEST(1, FLOOR(v_total_capacity * p_capacity_multiplier));
    v_total_depth := GREATEST(1, LEAST(5, FLOOR(v_total_depth)));
    v_total_frequency := GREATEST(1, FLOOR(v_total_frequency));
    v_total_focus := GREATEST(0, LEAST(10, v_total_focus * p_focus_multiplier));

    -- Upsert planning state
    INSERT INTO objective.character_planning_state (
        character_id, max_active_high_priority, max_objective_depth,
        planning_frequency_turns, focus_score,
        capacity_multiplier, focus_multiplier
    ) VALUES (
        p_character_id, v_total_capacity::INTEGER, v_total_depth::INTEGER,
        v_total_frequency::INTEGER, v_total_focus,
        p_capacity_multiplier, p_focus_multiplier
    )
    ON CONFLICT (character_id) DO UPDATE SET
        max_active_high_priority = EXCLUDED.max_active_high_priority,
        max_objective_depth = EXCLUDED.max_objective_depth,
        planning_frequency_turns = EXCLUDED.planning_frequency_turns,
        focus_score = EXCLUDED.focus_score,
        capacity_multiplier = EXCLUDED.capacity_multiplier,
        focus_multiplier = EXCLUDED.focus_multiplier,
        updated_at = NOW();
END;
$$ LANGUAGE plpgsql;

-- Get character's current planning state
CREATE OR REPLACE FUNCTION objective.character_planning_state_get(
    p_character_id UUID
)
RETURNS TABLE (
    max_active_high_priority INTEGER,
    max_objective_depth INTEGER,
    planning_frequency_turns INTEGER,
    focus_score FLOAT,
    current_high_priority_count INTEGER,
    current_critical_priority_count INTEGER,
    current_total_objective_count INTEGER,
    last_full_planning_turn INTEGER,
    next_planning_turn INTEGER,
    capacity_multiplier FLOAT,
    focus_multiplier FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        cps.max_active_high_priority, cps.max_objective_depth,
        cps.planning_frequency_turns, cps.focus_score,
        cps.current_high_priority_count, cps.current_critical_priority_count,
        cps.current_total_objective_count,
        cps.last_full_planning_turn, cps.next_planning_turn,
        cps.capacity_multiplier, cps.focus_multiplier
    FROM objective.character_planning_state cps
    WHERE cps.character_id = p_character_id;
END;
$$ LANGUAGE plpgsql;

-- Update planning state counters (called when objectives added/removed)
CREATE OR REPLACE FUNCTION objective.character_planning_state_update_counts(
    p_character_id UUID
)
RETURNS VOID AS $$
DECLARE
    v_high_count INTEGER;
    v_critical_count INTEGER;
    v_total_count INTEGER;
BEGIN
    -- Count active objectives by priority
    SELECT
        COUNT(*) FILTER (WHERE priority IN ('high', 'critical')),
        COUNT(*) FILTER (WHERE priority = 'critical'),
        COUNT(*)
    INTO v_high_count, v_critical_count, v_total_count
    FROM objective.character_objective
    WHERE character_id = p_character_id
      AND status = 'active';

    -- Update counts
    UPDATE objective.character_planning_state
    SET
        current_high_priority_count = v_high_count,
        current_critical_priority_count = v_critical_count,
        current_total_objective_count = v_total_count,
        updated_at = NOW()
    WHERE character_id = p_character_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- OBJECTIVE CRUD
-- ============================================================================

-- Create or update objective
CREATE OR REPLACE FUNCTION objective.character_objective_upsert(
    p_objective_id UUID,
    p_character_id UUID,
    p_game_id UUID,
    p_parent_objective_id UUID DEFAULT NULL,
    p_objective_type objective.objective_type DEFAULT 'main',
    p_description TEXT DEFAULT '',
    p_success_criteria TEXT DEFAULT NULL,
    p_priority objective.priority_level DEFAULT 'medium',
    p_status objective.objective_status DEFAULT 'active',
    p_source objective.objective_source DEFAULT 'internal',
    p_delegated_from_character_id UUID DEFAULT NULL,
    p_delegated_to_character_id UUID DEFAULT NULL,
    p_confirmation_required BOOLEAN DEFAULT FALSE,
    p_deadline_soft TIMESTAMP DEFAULT NULL,
    p_deadline_hard TIMESTAMP DEFAULT NULL,
    p_created_turn INTEGER DEFAULT 0,
    p_decay_after_turns INTEGER DEFAULT NULL,
    p_is_atomic BOOLEAN DEFAULT FALSE,
    p_metadata JSONB DEFAULT '{}'::jsonb,
    p_mood_impact_positive INTEGER DEFAULT 0,
    p_mood_impact_negative INTEGER DEFAULT 0
)
RETURNS UUID AS $$
DECLARE
    v_objective_id UUID;
    v_depth INTEGER := 0;
    v_max_depth INTEGER;
BEGIN
    -- Calculate depth from parent
    IF p_parent_objective_id IS NOT NULL THEN
        SELECT depth + 1 INTO v_depth
        FROM objective.character_objective
        WHERE objective_id = p_parent_objective_id;

        -- Check against character's max depth
        SELECT max_objective_depth INTO v_max_depth
        FROM objective.character_planning_state
        WHERE character_id = p_character_id;

        IF v_depth > v_max_depth THEN
            RAISE EXCEPTION 'Objective depth % exceeds character max depth %', v_depth, v_max_depth;
        END IF;
    END IF;

    -- Insert or update
    INSERT INTO objective.character_objective (
        objective_id, character_id, game_id, parent_objective_id, depth,
        objective_type, description, success_criteria, priority, status, source,
        delegated_from_character_id, delegated_to_character_id, confirmation_required,
        deadline_soft, deadline_hard, created_turn, decay_after_turns,
        is_atomic, metadata, mood_impact_positive, mood_impact_negative
    ) VALUES (
        COALESCE(p_objective_id, gen_random_uuid()),
        p_character_id, p_game_id, p_parent_objective_id, v_depth,
        p_objective_type, p_description, p_success_criteria, p_priority, p_status, p_source,
        p_delegated_from_character_id, p_delegated_to_character_id, p_confirmation_required,
        p_deadline_soft, p_deadline_hard, p_created_turn, p_decay_after_turns,
        p_is_atomic, p_metadata, p_mood_impact_positive, p_mood_impact_negative
    )
    ON CONFLICT (objective_id) DO UPDATE SET
        description = EXCLUDED.description,
        success_criteria = EXCLUDED.success_criteria,
        priority = EXCLUDED.priority,
        status = EXCLUDED.status,
        deadline_soft = EXCLUDED.deadline_soft,
        deadline_hard = EXCLUDED.deadline_hard,
        decay_after_turns = EXCLUDED.decay_after_turns,
        metadata = EXCLUDED.metadata,
        updated_at = NOW()
    RETURNING objective_id INTO v_objective_id;

    -- Update planning state counters
    PERFORM objective.character_planning_state_update_counts(p_character_id);

    RETURN v_objective_id;
END;
$$ LANGUAGE plpgsql;

-- Get objective by ID
CREATE OR REPLACE FUNCTION objective.character_objective_get(
    p_objective_id UUID
)
RETURNS TABLE (
    objective_id UUID,
    character_id UUID,
    game_id UUID,
    parent_objective_id UUID,
    depth INTEGER,
    objective_type objective.objective_type,
    description TEXT,
    success_criteria TEXT,
    priority objective.priority_level,
    status objective.objective_status,
    source objective.objective_source,
    delegated_from_character_id UUID,
    delegated_to_character_id UUID,
    confirmation_required BOOLEAN,
    confirmation_received BOOLEAN,
    confirmation_turn INTEGER,
    deadline_soft TIMESTAMP,
    deadline_hard TIMESTAMP,
    created_turn INTEGER,
    completed_turn INTEGER,
    last_evaluated_turn INTEGER,
    decay_after_turns INTEGER,
    turns_inactive INTEGER,
    partial_completion FLOAT,
    is_atomic BOOLEAN,
    metadata JSONB,
    mood_impact_positive INTEGER,
    mood_impact_negative INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        co.objective_id, co.character_id, co.game_id, co.parent_objective_id, co.depth,
        co.objective_type, co.description, co.success_criteria, co.priority, co.status, co.source,
        co.delegated_from_character_id, co.delegated_to_character_id,
        co.confirmation_required, co.confirmation_received, co.confirmation_turn,
        co.deadline_soft, co.deadline_hard, co.created_turn, co.completed_turn,
        co.last_evaluated_turn, co.decay_after_turns, co.turns_inactive,
        co.partial_completion, co.is_atomic, co.metadata,
        co.mood_impact_positive, co.mood_impact_negative
    FROM objective.character_objective co
    WHERE co.objective_id = p_objective_id;
END;
$$ LANGUAGE plpgsql;

-- List objectives for character with filtering
CREATE OR REPLACE FUNCTION objective.character_objectives_list(
    p_character_id UUID,
    p_status objective.objective_status DEFAULT NULL,
    p_priority objective.priority_level DEFAULT NULL,
    p_parent_objective_id UUID DEFAULT NULL,
    p_include_children BOOLEAN DEFAULT TRUE
)
RETURNS TABLE (
    objective_id UUID,
    parent_objective_id UUID,
    depth INTEGER,
    objective_type objective.objective_type,
    description TEXT,
    priority objective.priority_level,
    status objective.objective_status,
    partial_completion FLOAT,
    is_atomic BOOLEAN,
    created_turn INTEGER,
    last_evaluated_turn INTEGER,
    deadline_soft TIMESTAMP,
    deadline_hard TIMESTAMP,
    metadata JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        co.objective_id, co.parent_objective_id, co.depth, co.objective_type,
        co.description, co.priority, co.status, co.partial_completion,
        co.is_atomic, co.created_turn, co.last_evaluated_turn,
        co.deadline_soft, co.deadline_hard, co.metadata
    FROM objective.character_objective co
    WHERE co.character_id = p_character_id
      AND (p_status IS NULL OR co.status = p_status)
      AND (p_priority IS NULL OR co.priority = p_priority)
      AND (p_parent_objective_id IS NULL OR co.parent_objective_id = p_parent_objective_id OR p_include_children = FALSE)
    ORDER BY
        co.priority DESC,
        co.created_turn ASC;
END;
$$ LANGUAGE plpgsql;

-- Get full objective tree (parent + all descendants)
CREATE OR REPLACE FUNCTION objective.character_objective_tree(
    p_objective_id UUID
)
RETURNS TABLE (
    objective_id UUID,
    parent_objective_id UUID,
    depth INTEGER,
    description TEXT,
    priority objective.priority_level,
    status objective.objective_status,
    partial_completion FLOAT,
    is_atomic BOOLEAN,
    path TEXT
) AS $$
BEGIN
    RETURN QUERY
    WITH RECURSIVE objective_tree AS (
        -- Root objective
        SELECT
            co.objective_id, co.parent_objective_id, co.depth,
            co.description, co.priority, co.status,
            co.partial_completion, co.is_atomic,
            co.description::TEXT as path
        FROM objective.character_objective co
        WHERE co.objective_id = p_objective_id

        UNION ALL

        -- Children
        SELECT
            co.objective_id, co.parent_objective_id, co.depth,
            co.description, co.priority, co.status,
            co.partial_completion, co.is_atomic,
            (ot.path || ' > ' || co.description)::TEXT
        FROM objective.character_objective co
        JOIN objective_tree ot ON co.parent_objective_id = ot.objective_id
    )
    SELECT * FROM objective_tree
    ORDER BY depth, objective_id;
END;
$$ LANGUAGE plpgsql;

-- Update objective status
CREATE OR REPLACE FUNCTION objective.character_objective_update_status(
    p_objective_id UUID,
    p_new_status objective.objective_status,
    p_completed_turn INTEGER DEFAULT NULL
)
RETURNS VOID AS $$
DECLARE
    v_character_id UUID;
BEGIN
    UPDATE objective.character_objective
    SET
        status = p_new_status,
        completed_at = CASE WHEN p_new_status = 'completed' THEN NOW() ELSE completed_at END,
        completed_turn = CASE WHEN p_new_status = 'completed' THEN p_completed_turn ELSE completed_turn END,
        updated_at = NOW()
    WHERE objective_id = p_objective_id
    RETURNING character_id INTO v_character_id;

    -- Update planning state counters
    PERFORM objective.character_planning_state_update_counts(v_character_id);
END;
$$ LANGUAGE plpgsql;

-- Update objective progress
CREATE OR REPLACE FUNCTION objective.character_objective_update_progress(
    p_objective_id UUID,
    p_progress_delta FLOAT,
    p_turn_number INTEGER,
    p_action_taken TEXT DEFAULT NULL,
    p_notes TEXT DEFAULT NULL
)
RETURNS VOID AS $$
DECLARE
    v_new_completion FLOAT;
BEGIN
    -- Update partial completion
    UPDATE objective.character_objective
    SET
        partial_completion = LEAST(1.0, partial_completion + p_progress_delta),
        turns_inactive = 0, -- Reset inactivity counter
        updated_at = NOW()
    WHERE objective_id = p_objective_id
    RETURNING partial_completion INTO v_new_completion;

    -- Log progress
    INSERT INTO objective.objective_progress_log (
        objective_id, turn_number, action_taken, progress_delta, notes
    ) VALUES (
        p_objective_id, p_turn_number, p_action_taken, p_progress_delta, p_notes
    );

    -- Auto-complete if reached 1.0
    IF v_new_completion >= 1.0 THEN
        PERFORM objective.character_objective_update_status(p_objective_id, 'completed', p_turn_number);
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Increment inactivity counter for all active objectives
CREATE OR REPLACE FUNCTION objective.character_objectives_increment_inactivity(
    p_character_id UUID,
    p_current_turn INTEGER
)
RETURNS VOID AS $$
BEGIN
    UPDATE objective.character_objective
    SET
        turns_inactive = turns_inactive + 1,
        updated_at = NOW()
    WHERE character_id = p_character_id
      AND status = 'active';

    -- Auto-abandon objectives that exceeded decay limit
    UPDATE objective.character_objective
    SET status = 'abandoned'
    WHERE character_id = p_character_id
      AND status = 'active'
      AND decay_after_turns IS NOT NULL
      AND turns_inactive >= decay_after_turns;
END;
$$ LANGUAGE plpgsql;

-- Delete objective and all children
CREATE OR REPLACE FUNCTION objective.character_objective_delete(
    p_objective_id UUID
)
RETURNS VOID AS $$
DECLARE
    v_character_id UUID;
BEGIN
    -- Get character_id before deletion
    SELECT character_id INTO v_character_id
    FROM objective.character_objective
    WHERE objective_id = p_objective_id;

    -- Delete (CASCADE will handle children)
    DELETE FROM objective.character_objective
    WHERE objective_id = p_objective_id;

    -- Update planning state counters
    IF v_character_id IS NOT NULL THEN
        PERFORM objective.character_planning_state_update_counts(v_character_id);
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- DELEGATION MANAGEMENT
-- ============================================================================

-- Confirm objective completion (for delegated tasks)
CREATE OR REPLACE FUNCTION objective.character_objective_confirm(
    p_objective_id UUID,
    p_confirmation_turn INTEGER
)
RETURNS VOID AS $$
BEGIN
    UPDATE objective.character_objective
    SET
        confirmation_received = TRUE,
        confirmation_turn = p_confirmation_turn,
        updated_at = NOW()
    WHERE objective_id = p_objective_id
      AND confirmation_required = TRUE;
END;
$$ LANGUAGE plpgsql;

-- Get delegated objectives awaiting confirmation
CREATE OR REPLACE FUNCTION objective.character_objectives_awaiting_confirmation(
    p_character_id UUID
)
RETURNS TABLE (
    objective_id UUID,
    delegated_to_character_id UUID,
    description TEXT,
    completed_turn INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        co.objective_id, co.delegated_to_character_id,
        co.description, co.completed_turn
    FROM objective.character_objective co
    WHERE co.delegated_from_character_id = p_character_id
      AND co.confirmation_required = TRUE
      AND co.confirmation_received = FALSE
      AND co.status = 'waiting_confirmation';
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- RECURRING OBJECTIVES
-- ============================================================================

-- Create recurring objective from template
CREATE OR REPLACE FUNCTION objective.recurring_objective_create_from_template(
    p_template_id UUID,
    p_character_id UUID,
    p_game_id UUID,
    p_current_turn INTEGER
)
RETURNS UUID AS $$
DECLARE
    v_template RECORD;
    v_objective_id UUID;
BEGIN
    -- Get template
    SELECT * INTO v_template
    FROM objective.recurring_objective_template
    WHERE template_id = p_template_id AND is_active = TRUE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Template not found: %', p_template_id;
    END IF;

    -- Create objective
    SELECT objective.character_objective_upsert(
        NULL, -- Generate new ID
        p_character_id,
        p_game_id,
        NULL, -- No parent
        'recurring',
        v_template.description_template,
        v_template.success_criteria_template,
        v_template.default_priority,
        'active',
        'recurring',
        NULL, NULL, FALSE, NULL, NULL,
        p_current_turn,
        v_template.decay_after_turns,
        FALSE,
        v_template.metadata_template
    ) INTO v_objective_id;

    RETURN v_objective_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON FUNCTION objective.character_planning_state_recalculate IS 'Recalculates character planning capacity from cognitive trait scores';
COMMENT ON FUNCTION objective.character_objective_tree IS 'Returns hierarchical tree of objective and all descendants';
COMMENT ON FUNCTION objective.character_objectives_increment_inactivity IS 'Increments inactivity counter and auto-abandons decayed objectives';
