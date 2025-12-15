"""
Fix Location ID Index in Qdrant

Recreate location_id index as keyword type instead of integer for better filtering.
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

def fix_index():
    """Fix location_id index type."""

    print("="*70)
    print("Fixing Location ID Index")
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
            sys.exit(1)

        print(f"✓ Collection '{collection_name}' found")
        print()

    except Exception as e:
        print(f"✗ Error checking collection: {e}")
        sys.exit(1)

    # Delete existing location_id index
    print("Deleting old location_id index (integer type)...")
    try:
        client.delete_payload_index(
            collection_name=collection_name,
            field_name="location_id"
        )
        print("✓ Old index deleted")
    except Exception as e:
        if "not found" in str(e).lower():
            print("⚠ No existing index to delete")
        else:
            print(f"⚠ Could not delete old index: {e}")
    print()

    # Create new index as keyword
    print("Creating location_id index as keyword type...")
    try:
        client.create_payload_index(
            collection_name=collection_name,
            field_name="location_id",
            field_schema=PayloadSchemaType.KEYWORD
        )
        print("✓ New keyword index created")
    except Exception as e:
        if "already exists" in str(e).lower():
            print("⚠ Index already exists (keyword type)")
        else:
            print(f"✗ Error creating index: {e}")
            sys.exit(1)

    print()
    print("="*70)
    print("✓ Location ID index fixed")
    print("="*70)
    print()

    # Verify
    print("Verifying collection info...")
    try:
        info = client.get_collection(collection_name)
        print(f"Total points: {info.points_count}")

        if info.payload_schema:
            print(f"\nPayload schema:")
            for field_name, field_info in info.payload_schema.items():
                marker = " ← UPDATED" if field_name == "location_id" else ""
                print(f"  - {field_name}: {field_info.data_type}{marker}")
    except Exception as e:
        print(f"Could not retrieve collection info: {e}")

    print()


if __name__ == "__main__":
    try:
        fix_index()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
