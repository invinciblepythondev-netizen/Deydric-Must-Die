"""
Verify location-based search works after migration
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import os
from dotenv import load_dotenv
from services.item_store import ItemStore
from collections import Counter

# Load environment variables
load_dotenv()

def verify_search():
    """Verify search functionality with real data."""

    print("="*70)
    print("Verifying Location-Based Search")
    print("="*70)
    print()

    try:
        item_store = ItemStore()

        # Get all items to see what locations we have
        print("Fetching all items...")
        all_results = item_store.client.scroll(
            collection_name="game_items",
            limit=200,
            with_payload=True,
            with_vectors=False
        )

        all_items = [hit.payload for hit in all_results[0]]
        print(f"Total items in collection: {len(all_items)}")
        print()

        # Count items by location
        location_counts = Counter()
        for item in all_items:
            loc_id = item.get('location_id')
            if loc_id:
                location_counts[loc_id] += 1

        if location_counts:
            print("Items per location:")
            for loc_id, count in sorted(location_counts.items(), key=lambda x: x[1], reverse=True):
                print(f"  Location {loc_id}: {count} items")
            print()

            # Test search for the location with most items
            test_location = max(location_counts, key=location_counts.get)
            print(f"Testing search for location '{test_location}'...")

            # Try get_items_at_location
            items = item_store.get_items_at_location(location_id=int(test_location), limit=10)
            print(f"get_items_at_location found {len(items)} items")

            if items:
                print("\nSample items:")
                for item in items[:3]:
                    print(f"  - {item.get('item_name')}")
                    print(f"    Type: {item.get('item_type')}")
                    print(f"    Location: {item.get('location_id')}")
                    print()

            # Try search_items
            print(f"Testing search_items for location '{test_location}'...")
            search_results = item_store.search_items(location_id=int(test_location), limit=10)
            print(f"search_items found {len(search_results)} items")
            print()

        else:
            print("No items with location_id found in the database")
            print()

        print("="*70)
        print("Verification complete!")
        print("="*70)

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    try:
        verify_search()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
