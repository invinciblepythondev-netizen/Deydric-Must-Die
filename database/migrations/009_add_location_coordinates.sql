-- Migration: Add location coordinates and enhance location model

-- Add coordinate fields to location table
ALTER TABLE world.location
ADD COLUMN IF NOT EXISTS loc_x INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS loc_y INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS loc_z INTEGER DEFAULT 0;

-- Add comments
COMMENT ON COLUMN world.location.loc_x IS 'X coordinate (west-east axis, negative = west, positive = east)';
COMMENT ON COLUMN world.location.loc_y IS 'Y coordinate (south-north axis, negative = south, positive = north)';
COMMENT ON COLUMN world.location.loc_z IS 'Z coordinate (vertical axis, floor/level number)';

-- Add index for spatial queries
CREATE INDEX IF NOT EXISTS idx_location_coordinates ON world.location(loc_x, loc_y, loc_z);
CREATE INDEX IF NOT EXISTS idx_location_z_level ON world.location(loc_z);
