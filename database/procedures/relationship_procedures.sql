-- Character Relationship Procedures

-- Get relationship between two characters
CREATE OR REPLACE FUNCTION character_relationship_get(
    p_source_character_id UUID,
    p_target_character_id UUID
)
RETURNS TABLE (
    relationship_id UUID,
    source_character_id UUID,
    target_character_id UUID,
    trust FLOAT,
    fear FLOAT,
    respect FLOAT,
    relationship_type TEXT,
    interaction_count INTEGER,
    last_interaction_turn INTEGER,
    notes TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        r.relationship_id, r.source_character_id, r.target_character_id,
        r.trust, r.fear, r.respect, r.relationship_type,
        r.interaction_count, r.last_interaction_turn, r.notes,
        r.created_at, r.updated_at
    FROM character.character_relationship r
    WHERE r.source_character_id = p_source_character_id
      AND r.target_character_id = p_target_character_id;
END;
$$ LANGUAGE plpgsql;

-- List all relationships for a character (outgoing)
CREATE OR REPLACE FUNCTION character_relationship_list(p_character_id UUID)
RETURNS TABLE (
    relationship_id UUID,
    target_character_id UUID,
    target_name TEXT,
    trust FLOAT,
    fear FLOAT,
    respect FLOAT,
    relationship_type TEXT,
    interaction_count INTEGER,
    last_interaction_turn INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        r.relationship_id, r.target_character_id, c.name,
        r.trust, r.fear, r.respect, r.relationship_type,
        r.interaction_count, r.last_interaction_turn
    FROM character.character_relationship r
    JOIN character.character c ON c.character_id = r.target_character_id
    WHERE r.source_character_id = p_character_id;
END;
$$ LANGUAGE plpgsql;

-- Upsert relationship
CREATE OR REPLACE FUNCTION character_relationship_upsert(
    p_source_character_id UUID,
    p_target_character_id UUID,
    p_trust FLOAT DEFAULT 0.5,
    p_fear FLOAT DEFAULT 0.0,
    p_respect FLOAT DEFAULT 0.5,
    p_relationship_type TEXT DEFAULT 'neutral',
    p_last_interaction_turn INTEGER DEFAULT NULL,
    p_notes TEXT DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    v_relationship_id UUID;
BEGIN
    -- Prevent self-relationships
    IF p_source_character_id = p_target_character_id THEN
        RAISE EXCEPTION 'Cannot create relationship with self';
    END IF;

    INSERT INTO character.character_relationship (
        source_character_id, target_character_id,
        trust, fear, respect, relationship_type,
        interaction_count, last_interaction_turn, notes
    ) VALUES (
        p_source_character_id, p_target_character_id,
        p_trust, p_fear, p_respect, p_relationship_type,
        1, p_last_interaction_turn, p_notes
    )
    ON CONFLICT (source_character_id, target_character_id) DO UPDATE SET
        trust = EXCLUDED.trust,
        fear = EXCLUDED.fear,
        respect = EXCLUDED.respect,
        relationship_type = EXCLUDED.relationship_type,
        interaction_count = character.character_relationship.interaction_count + 1,
        last_interaction_turn = EXCLUDED.last_interaction_turn,
        notes = EXCLUDED.notes,
        updated_at = CURRENT_TIMESTAMP
    RETURNING relationship_id INTO v_relationship_id;

    RETURN v_relationship_id;
END;
$$ LANGUAGE plpgsql;

-- Update relationship metrics (incremental changes)
CREATE OR REPLACE FUNCTION character_relationship_adjust(
    p_source_character_id UUID,
    p_target_character_id UUID,
    p_trust_delta FLOAT DEFAULT 0.0,
    p_fear_delta FLOAT DEFAULT 0.0,
    p_respect_delta FLOAT DEFAULT 0.0,
    p_interaction_turn INTEGER DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    v_relationship_id UUID;
    v_new_trust FLOAT;
    v_new_fear FLOAT;
    v_new_respect FLOAT;
BEGIN
    -- Get current values or defaults
    SELECT relationship_id, trust, fear, respect
    INTO v_relationship_id, v_new_trust, v_new_fear, v_new_respect
    FROM character.character_relationship
    WHERE source_character_id = p_source_character_id
      AND target_character_id = p_target_character_id;

    -- If relationship doesn't exist, create with defaults
    IF v_relationship_id IS NULL THEN
        v_new_trust := 0.5;
        v_new_fear := 0.0;
        v_new_respect := 0.5;
    END IF;

    -- Apply deltas and clamp to 0-1
    v_new_trust := GREATEST(0.0, LEAST(1.0, v_new_trust + p_trust_delta));
    v_new_fear := GREATEST(0.0, LEAST(1.0, v_new_fear + p_fear_delta));
    v_new_respect := GREATEST(0.0, LEAST(1.0, v_new_respect + p_respect_delta));

    -- Upsert with new values
    RETURN character_relationship_upsert(
        p_source_character_id,
        p_target_character_id,
        v_new_trust,
        v_new_fear,
        v_new_respect,
        'neutral', -- Keep existing type or default
        p_interaction_turn,
        NULL
    );
END;
$$ LANGUAGE plpgsql;

-- Delete relationship
CREATE OR REPLACE FUNCTION character_relationship_delete(
    p_source_character_id UUID,
    p_target_character_id UUID
)
RETURNS BOOLEAN AS $$
BEGIN
    DELETE FROM character.character_relationship
    WHERE source_character_id = p_source_character_id
      AND target_character_id = p_target_character_id;

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;
