-- Character Wound Procedures

-- List all wounds for a character
CREATE OR REPLACE FUNCTION character_wound_list(p_character_id UUID)
RETURNS TABLE (
    wound_id UUID,
    character_id UUID,
    body_part TEXT,
    wound_type TEXT,
    severity TEXT,
    is_bleeding BOOLEAN,
    is_infected BOOLEAN,
    is_treated BOOLEAN,
    turns_since_injury INTEGER,
    treatment_history JSONB,
    description TEXT,
    caused_by TEXT,
    occurred_at_turn INTEGER,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        w.wound_id, w.character_id, w.body_part, w.wound_type, w.severity,
        w.is_bleeding, w.is_infected, w.is_treated, w.turns_since_injury,
        w.treatment_history, w.description, w.caused_by, w.occurred_at_turn,
        w.created_at, w.updated_at
    FROM character.character_wound w
    WHERE w.character_id = p_character_id
    ORDER BY w.severity DESC, w.occurred_at_turn DESC;
END;
$$ LANGUAGE plpgsql;

-- Get a specific wound
CREATE OR REPLACE FUNCTION character_wound_get(p_wound_id UUID)
RETURNS TABLE (
    wound_id UUID,
    character_id UUID,
    body_part TEXT,
    wound_type TEXT,
    severity TEXT,
    is_bleeding BOOLEAN,
    is_infected BOOLEAN,
    is_treated BOOLEAN,
    turns_since_injury INTEGER,
    treatment_history JSONB,
    description TEXT,
    caused_by TEXT,
    occurred_at_turn INTEGER,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        w.wound_id, w.character_id, w.body_part, w.wound_type, w.severity,
        w.is_bleeding, w.is_infected, w.is_treated, w.turns_since_injury,
        w.treatment_history, w.description, w.caused_by, w.occurred_at_turn,
        w.created_at, w.updated_at
    FROM character.character_wound w
    WHERE w.wound_id = p_wound_id;
END;
$$ LANGUAGE plpgsql;

-- Create a new wound
CREATE OR REPLACE FUNCTION character_wound_create(
    p_character_id UUID,
    p_body_part TEXT,
    p_wound_type TEXT,
    p_severity TEXT,
    p_is_bleeding BOOLEAN DEFAULT false,
    p_description TEXT DEFAULT NULL,
    p_caused_by TEXT DEFAULT NULL,
    p_occurred_at_turn INTEGER DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    v_wound_id UUID;
BEGIN
    INSERT INTO character.character_wound (
        character_id, body_part, wound_type, severity,
        is_bleeding, description, caused_by, occurred_at_turn
    ) VALUES (
        p_character_id, p_body_part, p_wound_type, p_severity,
        p_is_bleeding, p_description, p_caused_by, p_occurred_at_turn
    )
    RETURNING wound_id INTO v_wound_id;

    RETURN v_wound_id;
END;
$$ LANGUAGE plpgsql;

-- Update wound status
CREATE OR REPLACE FUNCTION character_wound_update(
    p_wound_id UUID,
    p_is_bleeding BOOLEAN DEFAULT NULL,
    p_is_infected BOOLEAN DEFAULT NULL,
    p_is_treated BOOLEAN DEFAULT NULL,
    p_severity TEXT DEFAULT NULL,
    p_turns_since_injury INTEGER DEFAULT NULL
)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE character.character_wound
    SET
        is_bleeding = COALESCE(p_is_bleeding, is_bleeding),
        is_infected = COALESCE(p_is_infected, is_infected),
        is_treated = COALESCE(p_is_treated, is_treated),
        severity = COALESCE(p_severity, severity),
        turns_since_injury = COALESCE(p_turns_since_injury, turns_since_injury),
        updated_at = CURRENT_TIMESTAMP
    WHERE wound_id = p_wound_id;

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

-- Add treatment to wound history
CREATE OR REPLACE FUNCTION character_wound_add_treatment(
    p_wound_id UUID,
    p_treater_character_id UUID,
    p_treatment_type TEXT,
    p_was_successful BOOLEAN,
    p_turn_number INTEGER
)
RETURNS BOOLEAN AS $$
DECLARE
    v_treatment JSONB;
BEGIN
    -- Build treatment record
    v_treatment := jsonb_build_object(
        'treater_id', p_treater_character_id,
        'treatment_type', p_treatment_type,
        'successful', p_was_successful,
        'turn', p_turn_number,
        'timestamp', CURRENT_TIMESTAMP
    );

    -- Append to treatment history
    UPDATE character.character_wound
    SET
        treatment_history = treatment_history || v_treatment,
        is_treated = true,
        updated_at = CURRENT_TIMESTAMP
    WHERE wound_id = p_wound_id;

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

-- Increment turns since injury (called each turn)
CREATE OR REPLACE FUNCTION character_wound_age_all()
RETURNS INTEGER AS $$
DECLARE
    v_count INTEGER;
BEGIN
    UPDATE character.character_wound
    SET turns_since_injury = turns_since_injury + 1,
        updated_at = CURRENT_TIMESTAMP;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;

-- Delete wound (healed)
CREATE OR REPLACE FUNCTION character_wound_delete(p_wound_id UUID)
RETURNS BOOLEAN AS $$
BEGIN
    DELETE FROM character.character_wound
    WHERE wound_id = p_wound_id;

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;
