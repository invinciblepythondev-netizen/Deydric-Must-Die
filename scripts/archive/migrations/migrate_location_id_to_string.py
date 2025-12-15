"""
Migrate existing items in Qdrant to use string location_id instead of integer.

This script updates all existing points in the game_items collection to convert
integer location_id values to strings for consistency with the keyword index.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

load_dotenv()

def migrate_location_ids():
    """Convert all location_id values from integers to strings."""

    print("="*70)
    print("Migrating location_id values to strings")
    print("="*70)
    print()

    # Get Qdrant configuration
    qdrant_host = os.getenv('QDRANT_HOST')
    qdrant_api_key = os.getenv('QDRANT_API_KEY')

    if not qdrant_host:
        print("ERROR: QDRANT_HOST not found in environment variables")
        sys.exit(1)

    # Initialize client
    client = QdrantClient(
        url=qdrant_host,
        api_key=qdrant_api_key,
        timeout=30
    )

    collection_name = "game_items"

    print(f"Fetching all points from '{collection_name}'...")

    # Scroll through all points
    offset = None
    total_updated = 0
    batch_size = 100

    while True:
        result = client.scroll(
            collection_name=collection_name,
            limit=batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=True
        )

        points, offset = result

        if not points:
            break

        print(f"Processing batch of {len(points)} items...")

        # Update each point that has an integer location_id
        updated_points = []
        for point in points:
            payload = point.payload
            location_id = payload.get('location_id')

            # Convert integer location_id to string
            if location_id is not None and isinstance(location_id, int):
                payload['location_id'] = str(location_id)

                updated_point = PointStruct(
                    id=point.id,
                    vector=point.vector,
                    payload=payload
                )
                updated_points.append(updated_point)

        # Upsert updated points
        if updated_points:
            client.upsert(
                collection_name=collection_name,
                points=updated_points
            )
            total_updated += len(updated_points)
            print(f"  Updated {len(updated_points)} items in this batch")

        if offset is None:
            break

    print()
    print("="*70)
    print(f"Migration complete! Updated {total_updated} items")
    print("="*70)
    print()

if __name__ == "__main__":
    try:
        migrate_location_ids()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
