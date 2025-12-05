"""
Import locations from locations.json into the database.

This script reads the locations.json file, transforms the data to match
the current location model, infers properties, and imports them.

Usage:
    python scripts/import_locations_json.py [--dry-run]
"""

import json
import os
import sys
import argparse
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv('NEON_DATABASE_URL')

if not DATABASE_URL:
    print("ERROR: NEON_DATABASE_URL not found in environment variables")
    sys.exit(1)


def infer_environment_type(location: dict) -> str:
    """
    Infer environment type from location name and description.

    Returns: 'indoor', 'outdoor', or 'underground'
    """
    name_lower = location['locationname'].lower()
    desc_lower = location.get('description', '').lower()

    # Outdoor indicators
    outdoor_keywords = ['grounds', 'courtyard', 'garden', 'path', 'road', 'field']
    if any(kw in name_lower for kw in outdoor_keywords):
        return 'outdoor'

    # Underground indicators
    underground_keywords = ['dungeon', 'vault', 'cellar', 'passage', 'tunnel', 'crypt', 'cave']
    if any(kw in name_lower for kw in underground_keywords):
        return 'underground'

    # Default to indoor for rooms, chambers, halls
    return 'indoor'


def infer_lighting(location: dict, env_type: str) -> str:
    """
    Infer lighting level from description and environment.

    Returns: 'bright', 'dim', or 'dark'
    """
    desc_lower = location.get('description', '').lower()

    # Dark indicators
    if any(word in desc_lower for word in ['pitch black', 'darkness', 'no light', 'completely dark']):
        return 'dark'

    # Dim indicators (torches, candles, shadows)
    if any(word in desc_lower for word in ['dimly', 'dim', 'shadowy', 'gloom', 'torch', 'lamp', 'candle', 'flicker']):
        return 'dim'

    # Bright outdoor during day
    if env_type == 'outdoor':
        return 'bright'

    # Underground is usually dim or dark
    if env_type == 'underground':
        if 'torch' in desc_lower or 'lamp' in desc_lower:
            return 'dim'
        return 'dark'

    # Default for indoor
    return 'dim'


def infer_temperature(location: dict, env_type: str) -> str:
    """
    Infer temperature from description and environment.

    Returns: 'cold', 'cool', 'comfortable', 'warm', or 'hot'
    """
    desc_lower = location.get('description', '').lower()
    name_lower = location['locationname'].lower()

    # Cold indicators
    if any(word in desc_lower for word in ['freezing', 'icy', 'frigid', 'frost', 'cold']):
        return 'cold'

    # Hot indicators
    if any(word in desc_lower for word in ['sweltering', 'scorching', 'hot', 'heat', 'forge', 'kiln', 'fire']):
        return 'hot'

    # Warm indicators
    if any(word in desc_lower for word in ['warm', 'cozy', 'fireplace', 'hearth']):
        return 'warm'

    # Cool indicators (underground, dungeons)
    if env_type == 'underground' or 'dungeon' in name_lower or 'cellar' in name_lower:
        return 'cool'

    # Default comfortable
    return 'comfortable'


def infer_is_public(location: dict) -> bool:
    """
    Infer if location is public from name and description.

    Returns: True if public, False if private/restricted
    """
    name_lower = location['locationname'].lower()
    desc_lower = location.get('description', '').lower()

    # Private/restricted indicators
    private_keywords = ['secret', 'passage', 'private', 'bedchamber', 'lord\'s', 'lady\'s', 'vault', 'dungeon']
    if any(kw in name_lower for kw in private_keywords):
        return False

    if any(word in desc_lower for word in ['secret', 'hidden', 'concealed', 'restricted', 'private']):
        return False

    # Public by default
    return True


def infer_direction(from_loc: dict, to_loc: dict, locations_by_id: dict) -> str:
    """
    Infer direction from one location to another based on coordinates.

    Returns: Direction string ('north', 'south', 'east', 'west', 'up', 'down', or 'exit')
    """
    try:
        from_x = int(from_loc.get('loc_x', 0))
        from_y = int(from_loc.get('loc_y', 0))
        from_z = int(from_loc.get('loc_z', 0))

        to_x = int(to_loc.get('loc_x', 0))
        to_y = int(to_loc.get('loc_y', 0))
        to_z = int(to_loc.get('loc_z', 0))

        # Check if coordinates are valid (not -1)
        if from_x == -1 or to_x == -1:
            return 'exit'  # Fallback for unmapped coordinates

        dx = to_x - from_x
        dy = to_y - from_y
        dz = to_z - from_z

        # Vertical movement takes priority
        if dz > 0:
            return 'up'
        elif dz < 0:
            return 'down'

        # Horizontal movement
        if abs(dx) > abs(dy):
            return 'east' if dx > 0 else 'west'
        elif abs(dy) > abs(dx):
            return 'north' if dy > 0 else 'south'
        else:
            # Equal or zero movement - use generic exit
            return 'exit'

    except (ValueError, KeyError):
        return 'exit'


def build_connections(location: dict, all_locations: dict) -> dict:
    """
    Build connections JSONB from exits array and coordinates.

    Returns: Dictionary mapping directions to location IDs
    """
    connections = {}
    exits = location.get('exits', [])

    for i, exit_id in enumerate(exits):
        target_loc = all_locations.get(exit_id)

        if target_loc:
            direction = infer_direction(location, target_loc, all_locations)

            # Handle multiple exits in same direction
            dir_key = direction
            counter = 1
            while dir_key in connections:
                counter += 1
                dir_key = f"{direction}_{counter}"

            connections[dir_key] = int(exit_id)
        else:
            # Unknown target, use generic exit name
            connections[f"exit_{i+1}"] = int(exit_id)

    return connections


def transform_location(loc_data: dict, all_locations: dict) -> dict:
    """
    Transform a location from locations.json format to database format.
    """
    # Infer environment properties
    env_type = infer_environment_type(loc_data)
    lighting = infer_lighting(loc_data, env_type)
    temperature = infer_temperature(loc_data, env_type)
    is_public = infer_is_public(loc_data)

    # Build connections from exits
    connections = build_connections(loc_data, all_locations)

    # Parse coordinates
    loc_x = int(loc_data.get('loc_x', 0))
    loc_y = int(loc_data.get('loc_y', 0))
    loc_z = int(loc_data.get('loc_z', 0))

    transformed = {
        'location_id': int(loc_data['locationid']),
        'name': loc_data['locationname'],
        'description': loc_data.get('description', ''),
        'loc_x': loc_x,
        'loc_y': loc_y,
        'loc_z': loc_z,
        'connections': connections,
        'environment_type': env_type,
        'lighting': lighting,
        'temperature': temperature,
        'is_public': is_public,
        'items': [],
        'properties': {}
    }

    return transformed


def import_location(session, loc_data: dict, dry_run: bool = False) -> bool:
    """
    Import a single location into the database.

    Returns True if successful, False otherwise.
    """
    try:
        print(f"\n{'[DRY RUN] ' if dry_run else ''}Importing: [{loc_data['location_id']:3d}] {loc_data['name']}")
        print(f"  Environment: {loc_data['environment_type']}, Lighting: {loc_data['lighting']}")
        print(f"  Coordinates: ({loc_data['loc_x']}, {loc_data['loc_y']}, {loc_data['loc_z']})")
        print(f"  Connections: {len(loc_data['connections'])} exits")
        if loc_data['connections']:
            for direction, target_id in loc_data['connections'].items():
                print(f"    - {direction} → {target_id}")

        if dry_run:
            print("  [SKIPPED - Dry Run]")
            return True

        # Insert location (using explicit ID)
        session.execute(text("""
            INSERT INTO world.location (
                location_id, name, description,
                loc_x, loc_y, loc_z,
                connections, environment_type, lighting,
                temperature, is_public, items, properties
            ) VALUES (
                :location_id, :name, :description,
                :loc_x, :loc_y, :loc_z,
                CAST(:connections AS jsonb), :environment_type, :lighting,
                :temperature, :is_public, CAST(:items AS jsonb), CAST(:properties AS jsonb)
            )
            ON CONFLICT (location_id) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                loc_x = EXCLUDED.loc_x,
                loc_y = EXCLUDED.loc_y,
                loc_z = EXCLUDED.loc_z,
                connections = EXCLUDED.connections,
                environment_type = EXCLUDED.environment_type,
                lighting = EXCLUDED.lighting,
                temperature = EXCLUDED.temperature,
                is_public = EXCLUDED.is_public,
                updated_at = CURRENT_TIMESTAMP
        """), {
            **loc_data,
            'connections': json.dumps(loc_data['connections']),
            'items': json.dumps(loc_data['items']),
            'properties': json.dumps(loc_data['properties'])
        })

        session.commit()
        print(f"  ✓ Imported successfully")
        return True

    except Exception as e:
        print(f"  ✗ Error: {e}")
        session.rollback()
        return False


def main():
    parser = argparse.ArgumentParser(description='Import locations from locations.json')
    parser.add_argument('--dry-run', action='store_true', help='Preview import without making changes')
    parser.add_argument('--file', default='locations.json', help='Path to locations.json file')
    args = parser.parse_args()

    print("=" * 70)
    print("Location Import from locations.json")
    print("=" * 70)

    if args.dry_run:
        print("\n[DRY RUN MODE - No changes will be made]\n")

    # Load locations.json
    json_path = project_root / args.file
    if not json_path.exists():
        print(f"ERROR: {args.file} not found")
        sys.exit(1)

    with open(json_path, 'r', encoding='utf-8') as f:
        locations = json.load(f)

    print(f"Loaded {len(locations)} locations from {args.file}\n")

    # Build lookup dictionary for coordinate calculations
    locations_by_id = {loc['locationid']: loc for loc in locations}

    # Transform all locations first
    transformed_locations = []
    for loc in locations:
        transformed = transform_location(loc, locations_by_id)
        transformed_locations.append(transformed)

    # Connect to database
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        success_count = 0

        # Sort by location_id for ordered import
        for loc_data in sorted(transformed_locations, key=lambda x: x['location_id']):
            success = import_location(session, loc_data, dry_run=args.dry_run)
            if success:
                success_count += 1

        print("\n" + "=" * 70)
        print(f"Import {'preview' if args.dry_run else 'complete'}: {success_count}/{len(locations)} locations")
        print("=" * 70)

    finally:
        session.close()


if __name__ == '__main__':
    main()
