-- Location Procedures

-- Get a location by ID
CREATE OR REPLACE FUNCTION location_get(p_location_id INTEGER)
RETURNS TABLE (
    location_id INTEGER,
    name TEXT,
    description TEXT,
    connections JSONB,
    environment_type TEXT,
    lighting TEXT,
    temperature TEXT,
    is_public BOOLEAN,
    items JSONB,
    properties JSONB,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        l.location_id, l.name, l.description, l.connections,
        l.environment_type, l.lighting, l.temperature, l.is_public,
        l.items, l.properties, l.created_at, l.updated_at
    FROM world.location l
    WHERE l.location_id = p_location_id;
END;
$$ LANGUAGE plpgsql;

-- List all locations
CREATE OR REPLACE FUNCTION location_list()
RETURNS TABLE (
    location_id INTEGER,
    name TEXT,
    description TEXT,
    environment_type TEXT,
    is_public BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        l.location_id, l.name, l.description, l.environment_type, l.is_public
    FROM world.location l
    ORDER BY l.location_id;
END;
$$ LANGUAGE plpgsql;

-- Create or update location
CREATE OR REPLACE FUNCTION location_upsert(
    p_location_id INTEGER,
    p_name TEXT,
    p_description TEXT,
    p_connections JSONB DEFAULT '{}'::jsonb,
    p_environment_type TEXT DEFAULT NULL,
    p_lighting TEXT DEFAULT 'bright',
    p_temperature TEXT DEFAULT 'comfortable',
    p_is_public BOOLEAN DEFAULT true,
    p_items JSONB DEFAULT '[]'::jsonb,
    p_properties JSONB DEFAULT '{}'::jsonb
)
RETURNS INTEGER AS $$
DECLARE
    v_location_id INTEGER;
BEGIN
    INSERT INTO world.location (
        location_id, name, description, connections, environment_type,
        lighting, temperature, is_public, items, properties
    ) VALUES (
        p_location_id, p_name, p_description, p_connections, p_environment_type,
        p_lighting, p_temperature, p_is_public, p_items, p_properties
    )
    ON CONFLICT (location_id) DO UPDATE SET
        name = EXCLUDED.name,
        description = EXCLUDED.description,
        connections = EXCLUDED.connections,
        environment_type = EXCLUDED.environment_type,
        lighting = EXCLUDED.lighting,
        temperature = EXCLUDED.temperature,
        is_public = EXCLUDED.is_public,
        items = EXCLUDED.items,
        properties = EXCLUDED.properties,
        updated_at = CURRENT_TIMESTAMP
    RETURNING location_id INTO v_location_id;

    RETURN v_location_id;
END;
$$ LANGUAGE plpgsql;

-- Get connected locations (for movement)
CREATE OR REPLACE FUNCTION location_get_connections(p_location_id INTEGER)
RETURNS TABLE (
    direction TEXT,
    connected_location_id INTEGER,
    location_name TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        conn.key AS direction,
        (conn.value::text)::integer AS connected_location_id,
        l.name AS location_name
    FROM world.location loc,
         jsonb_each(loc.connections) AS conn
    LEFT JOIN world.location l ON l.location_id = (conn.value::text)::integer
    WHERE loc.location_id = p_location_id;
END;
$$ LANGUAGE plpgsql;

-- Delete location
CREATE OR REPLACE FUNCTION location_delete(p_location_id INTEGER)
RETURNS BOOLEAN AS $$
BEGIN
    DELETE FROM world.location
    WHERE location_id = p_location_id;

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;
