"""
Check if game_items collection exists in Qdrant
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient

# Load environment variables
load_dotenv()

def check_collection():
    """Check if game_items collection exists in Qdrant."""

    print("=" * 70)
    print("Checking Qdrant for game_items collection")
    print("=" * 70)
    print()

    # Get Qdrant configuration
    qdrant_host = os.getenv('QDRANT_HOST')
    qdrant_api_key = os.getenv('QDRANT_API_KEY')

    if not qdrant_host:
        print("[ERROR] QDRANT_HOST not found in environment variables")
        sys.exit(1)

    print(f"Connecting to Qdrant at: {qdrant_host}")

    try:
        # Initialize client
        client = QdrantClient(
            url=qdrant_host,
            api_key=qdrant_api_key,
            timeout=30
        )

        print("[OK] Connected to Qdrant")
        print()

        # Get all collections
        collections = client.get_collections().collections
        collection_names = [c.name for c in collections]

        print(f"Found {len(collections)} collections:")
        for name in collection_names:
            print(f"  - {name}")
        print()

        # Check for game_items
        if "game_items" in collection_names:
            print("[OK] 'game_items' collection EXISTS")

            # Get collection info
            collection_info = client.get_collection("game_items")
            print()
            print("Collection details:")
            print(f"  Vector size: {collection_info.config.params.vectors.size}")
            print(f"  Distance metric: {collection_info.config.params.vectors.distance}")
            print(f"  Points count: {collection_info.points_count}")

        else:
            print("[WARN] 'game_items' collection DOES NOT EXIST")
            print()
            print("The collection will be created automatically when you first add an item.")
            print("You can create it now by running:")
            print("  python scripts/populate_west_guest_room_items.py")

        print()
        print("=" * 70)

    except Exception as e:
        print(f"[ERROR] Failed to connect to Qdrant: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    try:
        check_collection()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
