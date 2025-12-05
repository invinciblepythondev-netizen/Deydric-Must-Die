-- World Schema
-- Contains locations, items, and environmental data

-- Create schema
CREATE SCHEMA IF NOT EXISTS world;

-- Location table
CREATE TABLE IF NOT EXISTS world.location (
    location_id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,

    -- Coordinates
    loc_x INTEGER DEFAULT 0,
    loc_y INTEGER DEFAULT 0,
    loc_z INTEGER DEFAULT 0,

    -- Connections to other locations (JSONB)
    connections JSONB DEFAULT '{}'::jsonb, -- {"north": 2, "south": 1, "east": 3}

    -- Environmental properties
    environment_type TEXT, -- indoor, outdoor, underground
    lighting TEXT, -- bright, dim, dark
    temperature TEXT, -- cold, cool, comfortable, warm, hot
    is_public BOOLEAN DEFAULT true,

    -- Items in location (separate from character inventory)
    items JSONB DEFAULT '[]'::jsonb, -- Array of item objects

    -- Properties
    properties JSONB DEFAULT '{}'::jsonb, -- locked, hidden, dangerous, etc.

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE world.location IS 'Rooms/areas with descriptions, connections, items, and environmental properties';
COMMENT ON COLUMN world.location.loc_x IS 'X coordinate (west-east axis, negative = west, positive = east)';
COMMENT ON COLUMN world.location.loc_y IS 'Y coordinate (south-north axis, negative = south, positive = north)';
COMMENT ON COLUMN world.location.loc_z IS 'Z coordinate (vertical axis, floor/level number)';
COMMENT ON COLUMN world.location.connections IS 'JSONB object mapping direction to location_id';
COMMENT ON COLUMN world.location.items IS 'Array of items present in the location (not in character inventory)';
COMMENT ON COLUMN world.location.properties IS 'Additional properties like locked, hidden_exit, etc.';

-- Item catalog table (optional - for defining item templates)
CREATE TABLE IF NOT EXISTS world.item_catalog (
    item_id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    item_type TEXT, -- weapon, consumable, tool, quest_item, misc

    -- Base properties
    base_properties JSONB DEFAULT '{}'::jsonb, -- damage, healing, weight, value

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE world.item_catalog IS 'Catalog of item templates with base properties';
COMMENT ON COLUMN world.item_catalog.base_properties IS 'Default properties for this item type';

-- Indexes
CREATE INDEX IF NOT EXISTS idx_location_environment ON world.location(environment_type);
CREATE INDEX IF NOT EXISTS idx_location_coordinates ON world.location(loc_x, loc_y, loc_z);
CREATE INDEX IF NOT EXISTS idx_location_z_level ON world.location(loc_z);
CREATE INDEX IF NOT EXISTS idx_item_catalog_type ON world.item_catalog(item_type);

-- Updated_at trigger
CREATE TRIGGER location_updated_at
    BEFORE UPDATE ON world.location
    FOR EACH ROW
    EXECUTE FUNCTION game.update_timestamp();
