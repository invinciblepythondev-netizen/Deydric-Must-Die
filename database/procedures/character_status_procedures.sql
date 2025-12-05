-- Stored Procedures for Character Status Management

-- ============================================================================
-- STATUS TYPE PROCEDURES
-- ============================================================================

-- Get all available status types
CREATE OR REPLACE FUNCTION status_type_list()
RETURNS TABLE (
    status_type_code TEXT,
    display_name TEXT,
    description TEXT,
    default_duration_turns INTEGER,
    category TEXT,
    stackable BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        st.status_type_code,
        st.display_name,
        st.description,
        st.default_duration_turns,
        st.category,
        st.stackable
    FROM character.status_type st
    ORDER BY st.category, st.display_name;
END;
$$ LANGUAGE plpgsql;

-- Get a specific status type
CREATE OR REPLACE FUNCTION status_type_get(p_status_type_code TEXT)
RETURNS TABLE (
    status_type_code TEXT,
    display_name TEXT,
    description TEXT,
    default_duration_turns INTEGER,
    category TEXT,
    stackable BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        st.status_type_code,
        st.display_name,
        st.description,
        st.default_duration_turns,
        st.category,
        st.stackable
    FROM character.status_type st
    WHERE st.status_type_code = p_status_type_code;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- CHARACTER STATUS PROCEDURES
-- ============================================================================

-- Add or update a character status
CREATE OR REPLACE FUNCTION character_status_upsert(
    p_character_id UUID,
    p_status_type_code TEXT,
    p_intensity INTEGER DEFAULT 50,
    p_onset_turn INTEGER DEFAULT 0,
    p_duration_turns INTEGER DEFAULT NULL,
    p_source TEXT DEFAULT NULL,
    p_notes TEXT DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    v_character_status_id UUID;
    v_expiry_turn INTEGER;
    v_stackable BOOLEAN;
BEGIN
    -- Check if status type is stackable
    SELECT stackable INTO v_stackable
    FROM character.status_type
    WHERE status_type_code = p_status_type_code;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Status type % does not exist', p_status_type_code;
    END IF;

    -- Calculate expiry turn
    IF p_duration_turns IS NOT NULL THEN
        v_expiry_turn := p_onset_turn + p_duration_turns;
    ELSE
        v_expiry_turn := NULL;
    END IF;

    -- If not stackable, update existing or insert
    IF NOT v_stackable THEN
        INSERT INTO character.character_status (
            character_id,
            status_type_code,
            intensity,
            onset_turn,
            duration_turns,
            expiry_turn,
            source,
            notes,
            is_active
        ) VALUES (
            p_character_id,
            p_status_type_code,
            p_intensity,
            p_onset_turn,
            p_duration_turns,
            v_expiry_turn,
            p_source,
            p_notes,
            true
        )
        ON CONFLICT (character_id, status_type_code, source)
        DO UPDATE SET
            intensity = EXCLUDED.intensity,
            onset_turn = EXCLUDED.onset_turn,
            duration_turns = EXCLUDED.duration_turns,
            expiry_turn = EXCLUDED.expiry_turn,
            notes = EXCLUDED.notes,
            is_active = true,
            updated_at = NOW()
        RETURNING character_status_id INTO v_character_status_id;
    ELSE
        -- Stackable: always insert new
        INSERT INTO character.character_status (
            character_id,
            status_type_code,
            intensity,
            onset_turn,
            duration_turns,
            expiry_turn,
            source,
            notes,
            is_active
        ) VALUES (
            p_character_id,
            p_status_type_code,
            p_intensity,
            p_onset_turn,
            p_duration_turns,
            v_expiry_turn,
            p_source,
            p_notes,
            true
        )
        ON CONFLICT (character_id, status_type_code, source)
        DO UPDATE SET
            intensity = character.character_status.intensity + EXCLUDED.intensity,
            updated_at = NOW()
        RETURNING character_status_id INTO v_character_status_id;
    END IF;

    RETURN v_character_status_id;
END;
$$ LANGUAGE plpgsql;

-- Get all active statuses for a character
CREATE OR REPLACE FUNCTION character_status_list_active(
    p_character_id UUID,
    p_current_turn INTEGER DEFAULT NULL
)
RETURNS TABLE (
    character_status_id UUID,
    status_type_code TEXT,
    display_name TEXT,
    category TEXT,
    intensity INTEGER,
    onset_turn INTEGER,
    duration_turns INTEGER,
    expiry_turn INTEGER,
    turns_remaining INTEGER,
    source TEXT,
    notes TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        cs.character_status_id,
        cs.status_type_code,
        st.display_name,
        st.category,
        cs.intensity,
        cs.onset_turn,
        cs.duration_turns,
        cs.expiry_turn,
        CASE
            WHEN cs.expiry_turn IS NULL THEN NULL
            WHEN p_current_turn IS NULL THEN NULL
            ELSE GREATEST(0, cs.expiry_turn - p_current_turn)
        END AS turns_remaining,
        cs.source,
        cs.notes
    FROM character.character_status cs
    JOIN character.status_type st ON cs.status_type_code = st.status_type_code
    WHERE cs.character_id = p_character_id
      AND cs.is_active = true
      AND (cs.expiry_turn IS NULL OR p_current_turn IS NULL OR cs.expiry_turn > p_current_turn)
    ORDER BY st.category, cs.intensity DESC;
END;
$$ LANGUAGE plpgsql;

-- Get a specific character status
CREATE OR REPLACE FUNCTION character_status_get(p_character_status_id UUID)
RETURNS TABLE (
    character_status_id UUID,
    character_id UUID,
    status_type_code TEXT,
    display_name TEXT,
    category TEXT,
    intensity INTEGER,
    onset_turn INTEGER,
    duration_turns INTEGER,
    expiry_turn INTEGER,
    source TEXT,
    notes TEXT,
    is_active BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        cs.character_status_id,
        cs.character_id,
        cs.status_type_code,
        st.display_name,
        st.category,
        cs.intensity,
        cs.onset_turn,
        cs.duration_turns,
        cs.expiry_turn,
        cs.source,
        cs.notes,
        cs.is_active
    FROM character.character_status cs
    JOIN character.status_type st ON cs.status_type_code = st.status_type_code
    WHERE cs.character_status_id = p_character_status_id;
END;
$$ LANGUAGE plpgsql;

-- Update intensity of a status (e.g., getting more drunk, anger intensifying)
CREATE OR REPLACE FUNCTION character_status_update_intensity(
    p_character_status_id UUID,
    p_intensity_change INTEGER
)
RETURNS INTEGER AS $$
DECLARE
    v_new_intensity INTEGER;
BEGIN
    UPDATE character.character_status
    SET intensity = LEAST(100, GREATEST(0, intensity + p_intensity_change)),
        updated_at = NOW()
    WHERE character_status_id = p_character_status_id
    RETURNING intensity INTO v_new_intensity;

    -- If intensity reaches 0, deactivate
    IF v_new_intensity = 0 THEN
        UPDATE character.character_status
        SET is_active = false
        WHERE character_status_id = p_character_status_id;
    END IF;

    RETURN v_new_intensity;
END;
$$ LANGUAGE plpgsql;

-- Remove (deactivate) a specific status
CREATE OR REPLACE FUNCTION character_status_remove(
    p_character_status_id UUID
)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE character.character_status
    SET is_active = false,
        updated_at = NOW()
    WHERE character_status_id = p_character_status_id;

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

-- Remove all statuses of a specific type for a character
CREATE OR REPLACE FUNCTION character_status_remove_by_type(
    p_character_id UUID,
    p_status_type_code TEXT
)
RETURNS INTEGER AS $$
DECLARE
    v_count INTEGER;
BEGIN
    UPDATE character.character_status
    SET is_active = false,
        updated_at = NOW()
    WHERE character_id = p_character_id
      AND status_type_code = p_status_type_code
      AND is_active = true;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;

-- Expire old statuses (should be called at the end of each turn)
CREATE OR REPLACE FUNCTION character_status_expire_old(
    p_current_turn INTEGER
)
RETURNS TABLE (
    character_status_id UUID,
    character_id UUID,
    status_type_code TEXT,
    display_name TEXT
) AS $$
BEGIN
    -- Deactivate expired statuses and return them
    UPDATE character.character_status cs
    SET is_active = false,
        updated_at = NOW()
    FROM character.status_type st
    WHERE cs.status_type_code = st.status_type_code
      AND cs.is_active = true
      AND cs.expiry_turn IS NOT NULL
      AND cs.expiry_turn <= p_current_turn
    RETURNING cs.character_status_id, cs.character_id, cs.status_type_code, st.display_name
    INTO character_status_id, character_id, status_type_code, display_name;

    RETURN QUERY
    SELECT * FROM (VALUES (character_status_id, character_id, status_type_code, display_name)) AS expired(csi, ci, stc, dn)
    WHERE csi IS NOT NULL;
END;
$$ LANGUAGE plpgsql;

-- Get statuses by category for a character
CREATE OR REPLACE FUNCTION character_status_list_by_category(
    p_character_id UUID,
    p_category TEXT,
    p_current_turn INTEGER DEFAULT NULL
)
RETURNS TABLE (
    character_status_id UUID,
    status_type_code TEXT,
    display_name TEXT,
    intensity INTEGER,
    onset_turn INTEGER,
    expiry_turn INTEGER,
    source TEXT,
    notes TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        cs.character_status_id,
        cs.status_type_code,
        st.display_name,
        cs.intensity,
        cs.onset_turn,
        cs.expiry_turn,
        cs.source,
        cs.notes
    FROM character.character_status cs
    JOIN character.status_type st ON cs.status_type_code = st.status_type_code
    WHERE cs.character_id = p_character_id
      AND st.category = p_category
      AND cs.is_active = true
      AND (cs.expiry_turn IS NULL OR p_current_turn IS NULL OR cs.expiry_turn > p_current_turn)
    ORDER BY cs.intensity DESC;
END;
$$ LANGUAGE plpgsql;

-- Get combined status summary for LLM context
CREATE OR REPLACE FUNCTION character_status_get_summary(
    p_character_id UUID,
    p_current_turn INTEGER DEFAULT NULL
)
RETURNS TEXT AS $$
DECLARE
    v_summary TEXT := '';
    v_status RECORD;
    v_intensity_text TEXT;
BEGIN
    FOR v_status IN
        SELECT
            st.display_name,
            cs.intensity,
            cs.source,
            cs.notes,
            CASE
                WHEN cs.expiry_turn IS NULL THEN NULL
                WHEN p_current_turn IS NULL THEN NULL
                ELSE GREATEST(0, cs.expiry_turn - p_current_turn)
            END AS turns_remaining
        FROM character.character_status cs
        JOIN character.status_type st ON cs.status_type_code = st.status_type_code
        WHERE cs.character_id = p_character_id
          AND cs.is_active = true
          AND (cs.expiry_turn IS NULL OR p_current_turn IS NULL OR cs.expiry_turn > p_current_turn)
        ORDER BY cs.intensity DESC
    LOOP
        -- Determine intensity description
        v_intensity_text := CASE
            WHEN v_status.intensity <= 25 THEN 'mildly'
            WHEN v_status.intensity <= 50 THEN 'moderately'
            WHEN v_status.intensity <= 75 THEN 'strongly'
            ELSE 'severely'
        END;

        -- Build status line
        v_summary := v_summary || v_intensity_text || ' ' || LOWER(v_status.display_name);

        IF v_status.source IS NOT NULL THEN
            v_summary := v_summary || ' (' || v_status.source || ')';
        END IF;

        IF v_status.turns_remaining IS NOT NULL THEN
            v_summary := v_summary || ' [' || v_status.turns_remaining || ' turns remaining]';
        END IF;

        IF v_status.notes IS NOT NULL THEN
            v_summary := v_summary || ' - ' || v_status.notes;
        END IF;

        v_summary := v_summary || E'\n';
    END LOOP;

    IF v_summary = '' THEN
        RETURN 'No active statuses';
    END IF;

    RETURN TRIM(v_summary);
END;
$$ LANGUAGE plpgsql;
