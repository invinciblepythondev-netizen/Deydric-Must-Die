# Location JSON Import Guide

## Overview

This guide documents how to incorporate data from `locations.json` into the current location model, identifying field mappings, gaps, and recommended additions.

## Data Summary

- **Total Locations**: 42
- **Location ID Range**: 1-40 (some IDs skipped)
- **Average Description Length**: ~1000-1500 characters
- **All locations have**: Name, description, exits, coordinates

## Field Mapping Analysis

### Direct Mappings

| JSON Field | Current Model Field | Type | Notes |
|------------|---------------------|------|-------|
| `locationname` | `name` | TEXT | Location name |
| `description` | `description` | TEXT | Full description |

### Fields Requiring Transformation

| JSON Field | Current Model Field | Transformation Required |
|------------|---------------------|-------------------------|
| `locationid` | `location_id` | Convert string to integer |
| `exits` | `connections` | Array of IDs → JSONB direction mapping |
| `loc_x`, `loc_y`, `loc_z` | NEW fields needed | Add coordinate fields |

### Fields to Skip (Mostly Null/Unused)

| JSON Field | Usage | Reason to Skip |
|------------|-------|----------------|
| `gamerealmid` | 100% populated | Not needed (single game) |
| `region` | 0% populated | Always null |
| `country` | 0% populated | Always null |
| `continent` | 0% populated | Always null |
| `terrain` | 0% populated | Always null |
| `microclimate` | 0% populated | Always null |
| `shapefile` | 0% populated | Always null |
| `size_x`, `size_y`, `size_z` | 0% populated | Always null |
| `Setting` | 2.4% populated | Only 1 location uses it |
| `createdAt`, `updatedAt` | 100% populated | Use model timestamps |

### Missing Data (In Model But Not JSON)

| Current Model Field | Notes |
|---------------------|-------|
| `environment_type` | Will need to infer (indoor/outdoor) |
| `lighting` | Will need to infer from description |
| `temperature` | Will need to infer from description |
| `is_public` | Will need to infer from location type |
| `items` | Empty for now |
| `properties` | Empty for now, or infer from description |

## Recommended Schema Changes

### Migration: Add Location Coordinates

```sql
-- database/migrations/009_add_location_coordinates.sql

-- Add coordinate fields to location table
ALTER TABLE world.location
ADD COLUMN IF NOT EXISTS loc_x INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS loc_y INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS loc_z INTEGER DEFAULT 0;

-- Add comments
COMMENT ON COLUMN world.location.loc_x IS 'X coordinate (west-east)';
COMMENT ON COLUMN world.location.loc_y IS 'Y coordinate (south-north)';
COMMENT ON COLUMN world.location.loc_z IS 'Z coordinate (floor/level)';

-- Add index for spatial queries
CREATE INDEX IF NOT EXISTS idx_location_coordinates ON world.location(loc_x, loc_y, loc_z);
```

## Exit/Connection Mapping Challenge

The JSON has an `exits` array with just location IDs:
```json
"exits": ["35", "36"]
```

The current model uses a `connections` JSONB object with directions:
```json
{"north": 2, "south": 1, "east": 3}
```

### Solution Options:

**Option 1: Infer directions from coordinates**
- Calculate relative positions using `loc_x`, `loc_y`, `loc_z`
- Auto-assign directions (north, south, east, west, up, down)

**Option 2: Import as generic exits**
- Store as `{"exit_1": 35, "exit_2": 36}` initially
- Manually update later with proper directions

**Option 3: Manual direction mapping**
- Create a mapping file for each location's exit directions
- Most accurate but labor-intensive

**Recommended: Option 1** (automatic inference with manual correction later)

## Exit Direction Inference Logic

```python
def infer_direction(from_loc, to_loc):
    """Infer direction from coordinate differences."""
    dx = to_loc['loc_x'] - from_loc['loc_x']
    dy = to_loc['loc_y'] - from_loc['loc_y']
    dz = to_loc['loc_z'] - from_loc['loc_z']

    # Vertical movement (stairs, etc.)
    if dz > 0:
        return "up"
    elif dz < 0:
        return "down"

    # Horizontal movement
    if abs(dx) > abs(dy):
        return "east" if dx > 0 else "west"
    else:
        return "north" if dy > 0 else "south"
```

## Environment Type Inference

Based on location names and descriptions:

```python
def infer_environment(location):
    """Infer environment type from name and description."""
    name_lower = location['locationname'].lower()
    desc_lower = location['description'].lower()

    # Outdoor indicators
    outdoor_keywords = ['grounds', 'courtyard', 'garden', 'path', 'road']
    if any(kw in name_lower for kw in outdoor_keywords):
        return 'outdoor'

    # Underground indicators
    underground_keywords = ['dungeon', 'vault', 'cellar', 'passage', 'tunnel']
    if any(kw in name_lower for kw in underground_keywords):
        return 'underground'

    # Default to indoor
    return 'indoor'
```

## Lighting Inference

```python
def infer_lighting(location):
    """Infer lighting from description."""
    desc_lower = location['description'].lower()

    if any(word in desc_lower for word in ['dimly', 'dark', 'shadowy', 'gloom']):
        return 'dim'
    elif any(word in desc_lower for word in ['torch', 'lamp', 'candle', 'lit']):
        return 'dim'  # Artificial light
    elif 'outdoor' in infer_environment(location):
        return 'bright'  # Daylight
    else:
        return 'dim'  # Default for indoor
```

## Sample Locations

### Location 32: East Castle Grounds
```json
{
  "locationid": "32",
  "locationname": "East Castle Grounds",
  "description": "The East Castle Grounds consist of a meticulously maintained garden...",
  "exits": ["35", "36"],
  "loc_x": "-1",
  "loc_y": "-1",
  "loc_z": "1"
}
```

**Inferred Properties:**
- `environment_type`: "outdoor"
- `lighting`: "bright"
- `temperature`: "comfortable"
- `is_public`: true
- `connections`: Infer from coordinates

### Location 30: North Secret Passage
```json
{
  "locationid": "30",
  "locationname": "North Secret Passage",
  "description": "Tucked within the thick northern walls...",
  "exits": ["29", "4", "2"],
  "loc_x": "1001",
  "loc_y": "1001",
  "loc_z": "1"
}
```

**Inferred Properties:**
- `environment_type`: "underground" or "indoor"
- `lighting`: "dim"
- `temperature`: "cool"
- `is_public`: false (secret passage)

## Import Strategy

### Step 1: Add Coordinates to Schema
```sql
ALTER TABLE world.location
ADD COLUMN loc_x INTEGER DEFAULT 0,
ADD COLUMN loc_y INTEGER DEFAULT 0,
ADD COLUMN loc_z INTEGER DEFAULT 0;
```

### Step 2: Import Locations
1. Parse location from JSON
2. Convert `locationid` (string) to integer
3. Add coordinates (`loc_x`, `loc_y`, `loc_z`)
4. Infer `environment_type`, `lighting`, `temperature`
5. Set `is_public` based on location name
6. Build connection map from exits + coordinates

### Step 3: Create Bidirectional Connections
- Ensure all connections are bidirectional
- If Location A exits to B, Location B should exit to A

## Data Quality Considerations

### Issues in locations.json:

1. **Coordinate inconsistency**: Some locations use `-1` for coordinates (means "not set")
2. **Exit array only**: No direction information in JSON
3. **Missing reverse exits**: Need to verify all exits are bidirectional
4. **ID gaps**: IDs go from 1-40 but only 42 locations (some IDs missing)

### Recommendations:

1. **Handle -1 coordinates**: Assign sequential coordinates for unmapped locations
2. **Infer directions**: Use coordinate math for automatic direction assignment
3. **Verify bidirectionality**: Check that A→B implies B→A
4. **Preserve original IDs**: Keep the JSON IDs even though they're not sequential

## Updated Location Model Structure

```sql
CREATE TABLE world.location (
    location_id INTEGER PRIMARY KEY,  -- Use JSON IDs directly
    name TEXT NOT NULL,
    description TEXT NOT NULL,

    -- Coordinates (NEW)
    loc_x INTEGER DEFAULT 0,
    loc_y INTEGER DEFAULT 0,
    loc_z INTEGER DEFAULT 0,

    -- Connections (existing)
    connections JSONB DEFAULT '{}'::jsonb,

    -- Environmental properties (inferred)
    environment_type TEXT,  -- indoor, outdoor, underground
    lighting TEXT,  -- bright, dim, dark
    temperature TEXT,  -- cold, cool, comfortable, warm, hot
    is_public BOOLEAN DEFAULT true,

    -- Items and properties
    items JSONB DEFAULT '[]'::jsonb,
    properties JSONB DEFAULT '{}'::jsonb,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Example Import Result

### Input (JSON):
```json
{
  "locationid": "32",
  "locationname": "East Castle Grounds",
  "description": "The East Castle Grounds consist of...",
  "exits": ["35", "36"],
  "loc_x": "-1",
  "loc_y": "-1",
  "loc_z": "1"
}
```

### Output (Database):
```python
{
    'location_id': 32,
    'name': 'East Castle Grounds',
    'description': 'The East Castle Grounds consist of...',
    'loc_x': -1,  # Or assign new coordinate
    'loc_y': -1,
    'loc_z': 1,
    'connections': {
        'exit_1': 35,  # Direction inferred later
        'exit_2': 36
    },
    'environment_type': 'outdoor',
    'lighting': 'bright',
    'temperature': 'comfortable',
    'is_public': True,
    'items': [],
    'properties': {}
}
```

## Next Steps

1. ✅ Create migration (009_add_location_coordinates.sql)
2. ✅ Update location stored procedures
3. ✅ Create import script (scripts/import_locations_json.py)
4. ⏳ Import locations with inferred properties
5. ⏳ Manually review and correct connection directions
6. ⏳ Update location procedures to handle coordinates
7. ⏳ Test location navigation

## Summary

**Fields to Add**: `loc_x`, `loc_y`, `loc_z` (coordinates)

**Fields to Infer**: `environment_type`, `lighting`, `temperature`, `is_public`

**Complex Transformation**: `exits` array → `connections` JSONB with directions

**Fields to Skip**: region, country, continent, terrain, microclimate, shapefile, size_x/y/z, Setting

**Total Locations**: 42 locations ready to import

**Key Challenge**: Converting exit array to directional connections
