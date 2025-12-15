"""
Create Qdrant Indexes for Item System

Creates necessary payload indexes for efficient querying.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import PayloadSchemaType

load_dotenv()

def create_indexes():
    """Create payload indexes on Qdrant collection."""

    print("="*70)
    print("Creating Qdrant Payload Indexes")
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

    # Check if collection exists
    try:
        collections = client.get_collections().collections
        exists = any(c.name == collection_name for c in collections)

        if not exists:
            print(f"ERROR: Collection '{collection_name}' does not exist!")
            print("Run populate_west_guest_room_items.py or populate_character_items.py first.")
            sys.exit(1)

        print(f"✓ Collection '{collection_name}' found")
        print()

    except Exception as e:
        print(f"✗ Error checking collection: {e}")
        sys.exit(1)

    # Create indexes for common query fields
    indexes_to_create = [
        ("location_id", PayloadSchemaType.INTEGER),
        ("carried_by_character_id", PayloadSchemaType.KEYWORD),
        ("contained_by_item_id", PayloadSchemaType.KEYWORD),
        ("item_type", PayloadSchemaType.KEYWORD),
        ("importance_level", PayloadSchemaType.KEYWORD),
        ("visibility_level", PayloadSchemaType.KEYWORD),
        ("carry_method", PayloadSchemaType.KEYWORD),
        ("worn_slot", PayloadSchemaType.KEYWORD),
    ]

    print("Creating payload indexes...")
    print("-"*70)

    for field_name, field_type in indexes_to_create:
        try:
            client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=field_type
            )
            print(f"  ✓ {field_name} ({field_type})")

        except Exception as e:
            # Check if index already exists
            if "already exists" in str(e).lower() or "existing field" in str(e).lower():
                print(f"  ⚠ {field_name} - already exists")
            else:
                print(f"  ✗ {field_name} - error: {e}")

    print()
    print("="*70)
    print("✓ Payload indexes created")
    print("="*70)
    print()

    # Verify indexes
    print("Verifying collection info...")
    try:
        info = client.get_collection(collection_name)
        print(f"Collection: {info.config.params.vectors.size} dimensional vectors")
        print(f"Total points: {info.points_count}")

        if info.payload_schema:
            print(f"\nPayload schema:")
            for field_name, field_info in info.payload_schema.items():
                print(f"  - {field_name}: {field_info.data_type}")
        else:
            print("\nPayload schema: (indexes will be created dynamically on first query)")

    except Exception as e:
        print(f"Could not retrieve collection info: {e}")

    print()


if __name__ == "__main__":
    try:
        create_indexes()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
