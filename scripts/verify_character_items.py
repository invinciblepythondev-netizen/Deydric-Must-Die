"""
Verify Character Items

Check that character items were stored correctly in Qdrant.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import os
from dotenv import load_dotenv
from services.item_store import ItemStore
from uuid import UUID

load_dotenv()

# Character IDs
CHARACTER_DATA = [
    {
        'id': UUID('f3807eaf-6d3a-425c-8916-32fd226d899f'),
        'name': 'Sir Gelarthon Findraell'
    },
    {
        'id': UUID('e6212f28-1081-4e8e-89e3-49e26a4a4372'),
        'name': 'Fizrae Yinai'
    }
]

def verify_items():
    """Verify character items."""

    print('='*70)
    print('Character Items Verification')
    print('='*70)
    print()

    # Initialize item store
    item_store = ItemStore()

    for char_data in CHARACTER_DATA:
        char_id = char_data['id']
        char_name = char_data['name']

        print(f'{char_name}:')
        print('-'*70)

        try:
            # Get all items
            items = item_store.get_items_carried_by(char_id)
            worn = item_store.get_worn_items(char_id)
            carried = item_store.get_carried_items_not_worn(char_id)
            total_weight = item_store.get_total_carried_weight(char_id)

            print(f'Total items: {len(items)}')
            print()

            print(f'Worn items ({len(worn)}):')
            if worn:
                for item in worn:
                    slot = item.get('worn_slot', 'unknown')
                    weight = item.get('weight', 0)
                    print(f'  - {item["item_name"]} (on {slot}, weight: {weight})')
            else:
                print('  (none)')
            print()

            print(f'Carried items ({len(carried)}):')
            if carried:
                for item in carried:
                    weight = item.get('weight', 0)
                    print(f'  - {item["item_name"]} (weight: {weight})')
            else:
                print('  (none)')
            print()

            print(f'Total weight carried: {total_weight:,}')
            print()

        except Exception as e:
            print(f'Error: {e}')
            import traceback
            traceback.print_exc()
            print()

    print('='*70)
    print('✓ Verification complete')
    print('='*70)


if __name__ == "__main__":
    try:
        verify_items()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
