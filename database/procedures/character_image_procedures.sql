-- Character Image Stored Procedures
-- Manages character images stored in Google Cloud Storage

-- Get a specific character image by ID
CREATE OR REPLACE FUNCTION character_image_get(p_image_id UUID)
RETURNS TABLE (
    image_id UUID,
    character_id UUID,
    image_type TEXT,
    image_url TEXT,
    gcs_path TEXT,
    file_name TEXT,
    file_size INTEGER,
    mime_type TEXT,
    display_name TEXT,
    description TEXT,
    is_primary BOOLEAN,
    display_order INTEGER,
    uploaded_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ci.image_id,
        ci.character_id,
        ci.image_type,
        ci.image_url,
        ci.gcs_path,
        ci.file_name,
        ci.file_size,
        ci.mime_type,
        ci.display_name,
        ci.description,
        ci.is_primary,
        ci.display_order,
        ci.uploaded_at,
        ci.created_at,
        ci.updated_at
    FROM character.character_image ci
    WHERE ci.image_id = p_image_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION character_image_get(UUID) IS 'Retrieve a specific character image by ID';

-- List all images for a character
CREATE OR REPLACE FUNCTION character_image_list_by_character(p_character_id UUID)
RETURNS TABLE (
    image_id UUID,
    character_id UUID,
    image_type TEXT,
    image_url TEXT,
    gcs_path TEXT,
    file_name TEXT,
    file_size INTEGER,
    mime_type TEXT,
    display_name TEXT,
    description TEXT,
    is_primary BOOLEAN,
    display_order INTEGER,
    uploaded_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ci.image_id,
        ci.character_id,
        ci.image_type,
        ci.image_url,
        ci.gcs_path,
        ci.file_name,
        ci.file_size,
        ci.mime_type,
        ci.display_name,
        ci.description,
        ci.is_primary,
        ci.display_order,
        ci.uploaded_at,
        ci.created_at,
        ci.updated_at
    FROM character.character_image ci
    WHERE ci.character_id = p_character_id
    ORDER BY ci.image_type, ci.is_primary DESC, ci.display_order, ci.created_at;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION character_image_list_by_character(UUID) IS 'List all images for a character, ordered by type and primary status';

-- Get images by type for a character
CREATE OR REPLACE FUNCTION character_image_get_by_type(
    p_character_id UUID,
    p_image_type TEXT
)
RETURNS TABLE (
    image_id UUID,
    character_id UUID,
    image_type TEXT,
    image_url TEXT,
    gcs_path TEXT,
    file_name TEXT,
    file_size INTEGER,
    mime_type TEXT,
    display_name TEXT,
    description TEXT,
    is_primary BOOLEAN,
    display_order INTEGER,
    uploaded_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ci.image_id,
        ci.character_id,
        ci.image_type,
        ci.image_url,
        ci.gcs_path,
        ci.file_name,
        ci.file_size,
        ci.mime_type,
        ci.display_name,
        ci.description,
        ci.is_primary,
        ci.display_order,
        ci.uploaded_at,
        ci.created_at,
        ci.updated_at
    FROM character.character_image ci
    WHERE ci.character_id = p_character_id
        AND ci.image_type = p_image_type
    ORDER BY ci.is_primary DESC, ci.display_order, ci.created_at;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION character_image_get_by_type(UUID, TEXT) IS 'Get all images of a specific type for a character';

-- Get primary image for a character by type
CREATE OR REPLACE FUNCTION character_image_get_primary(
    p_character_id UUID,
    p_image_type TEXT
)
RETURNS TABLE (
    image_id UUID,
    character_id UUID,
    image_type TEXT,
    image_url TEXT,
    gcs_path TEXT,
    file_name TEXT,
    file_size INTEGER,
    mime_type TEXT,
    display_name TEXT,
    description TEXT,
    is_primary BOOLEAN,
    display_order INTEGER,
    uploaded_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ci.image_id,
        ci.character_id,
        ci.image_type,
        ci.image_url,
        ci.gcs_path,
        ci.file_name,
        ci.file_size,
        ci.mime_type,
        ci.display_name,
        ci.description,
        ci.is_primary,
        ci.display_order,
        ci.uploaded_at,
        ci.created_at,
        ci.updated_at
    FROM character.character_image ci
    WHERE ci.character_id = p_character_id
        AND ci.image_type = p_image_type
        AND ci.is_primary = true
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION character_image_get_primary(UUID, TEXT) IS 'Get the primary image for a character by type';

-- Insert or update a character image
CREATE OR REPLACE FUNCTION character_image_upsert(
    p_image_id UUID,
    p_character_id UUID,
    p_image_type TEXT,
    p_image_url TEXT,
    p_gcs_path TEXT,
    p_file_name TEXT,
    p_file_size INTEGER,
    p_mime_type TEXT,
    p_display_name TEXT DEFAULT NULL,
    p_description TEXT DEFAULT NULL,
    p_is_primary BOOLEAN DEFAULT false,
    p_display_order INTEGER DEFAULT 0
)
RETURNS UUID AS $$
DECLARE
    v_image_id UUID;
BEGIN
    -- If this is being set as primary, unset other primary images of this type
    IF p_is_primary THEN
        UPDATE character.character_image
        SET is_primary = false
        WHERE character_id = p_character_id
            AND image_type = p_image_type
            AND is_primary = true
            AND image_id != COALESCE(p_image_id, '00000000-0000-0000-0000-000000000000'::uuid);
    END IF;

    -- Insert or update the image
    INSERT INTO character.character_image (
        image_id,
        character_id,
        image_type,
        image_url,
        gcs_path,
        file_name,
        file_size,
        mime_type,
        display_name,
        description,
        is_primary,
        display_order
    ) VALUES (
        COALESCE(p_image_id, gen_random_uuid()),
        p_character_id,
        p_image_type,
        p_image_url,
        p_gcs_path,
        p_file_name,
        p_file_size,
        p_mime_type,
        p_display_name,
        p_description,
        p_is_primary,
        p_display_order
    )
    ON CONFLICT (image_id) DO UPDATE SET
        image_url = EXCLUDED.image_url,
        gcs_path = EXCLUDED.gcs_path,
        file_name = EXCLUDED.file_name,
        file_size = EXCLUDED.file_size,
        mime_type = EXCLUDED.mime_type,
        display_name = EXCLUDED.display_name,
        description = EXCLUDED.description,
        is_primary = EXCLUDED.is_primary,
        display_order = EXCLUDED.display_order,
        updated_at = NOW()
    RETURNING image_id INTO v_image_id;

    RETURN v_image_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION character_image_upsert IS 'Insert or update a character image. Handles primary image logic.';

-- Delete a character image
CREATE OR REPLACE FUNCTION character_image_delete(p_image_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
    v_deleted BOOLEAN := false;
BEGIN
    DELETE FROM character.character_image
    WHERE image_id = p_image_id;

    GET DIAGNOSTICS v_deleted = ROW_COUNT;
    RETURN v_deleted > 0;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION character_image_delete(UUID) IS 'Delete a character image by ID';

-- Set an image as primary for its type
CREATE OR REPLACE FUNCTION character_image_set_primary(p_image_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
    v_character_id UUID;
    v_image_type TEXT;
BEGIN
    -- Get the character and type for this image
    SELECT character_id, image_type
    INTO v_character_id, v_image_type
    FROM character.character_image
    WHERE image_id = p_image_id;

    IF NOT FOUND THEN
        RETURN false;
    END IF;

    -- Unset all other primary images of this type for this character
    UPDATE character.character_image
    SET is_primary = false
    WHERE character_id = v_character_id
        AND image_type = v_image_type
        AND is_primary = true
        AND image_id != p_image_id;

    -- Set this image as primary
    UPDATE character.character_image
    SET is_primary = true
    WHERE image_id = p_image_id;

    RETURN true;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION character_image_set_primary(UUID) IS 'Set an image as the primary image for its type';

-- Get all primary images for a character
CREATE OR REPLACE FUNCTION character_image_get_all_primary(p_character_id UUID)
RETURNS TABLE (
    image_id UUID,
    character_id UUID,
    image_type TEXT,
    image_url TEXT,
    gcs_path TEXT,
    file_name TEXT,
    file_size INTEGER,
    mime_type TEXT,
    display_name TEXT,
    description TEXT,
    is_primary BOOLEAN,
    display_order INTEGER,
    uploaded_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ci.image_id,
        ci.character_id,
        ci.image_type,
        ci.image_url,
        ci.gcs_path,
        ci.file_name,
        ci.file_size,
        ci.mime_type,
        ci.display_name,
        ci.description,
        ci.is_primary,
        ci.display_order,
        ci.uploaded_at,
        ci.created_at,
        ci.updated_at
    FROM character.character_image ci
    WHERE ci.character_id = p_character_id
        AND ci.is_primary = true
    ORDER BY ci.image_type;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION character_image_get_all_primary(UUID) IS 'Get all primary images for a character (one per type)';
