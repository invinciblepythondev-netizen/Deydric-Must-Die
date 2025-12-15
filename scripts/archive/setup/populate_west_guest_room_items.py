"""
Populate West Guest Room with Items

Test script to generate and store items for the West Guest Room location using LLM.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables
load_dotenv()

def populate_items():
    """Generate and populate items for West Guest Room."""

    print("="*70)
    print("Populating West Guest Room Items")
    print("="*70)
    print()

    # Get database connection
    database_url = os.getenv('NEON_DATABASE_URL')
    if not database_url:
        print("ERROR: NEON_DATABASE_URL not found in environment variables")
        sys.exit(1)

    # Ensure psycopg driver
    if 'postgresql://' in database_url:
        database_url = database_url.replace('postgresql://', 'postgresql+psycopg://')

    engine = create_engine(database_url)

    # Get location details
    print("Fetching West Guest Room details...")
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT location_id, name, description_detailed
                FROM world.location
                WHERE location_id = 7
            """))
            location = result.fetchone()

            if not location:
                print("ERROR: West Guest Room (location_id=7) not found!")
                sys.exit(1)

            location_id, location_name, location_description = location
            print(f"✓ Found location: {location_name}")
            print(f"  ID: {location_id}")
            print(f"  Description: {location_description[:100]}...")
            print()

    except Exception as e:
        print(f"✗ Error fetching location: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Initialize LLM service
    print("Initializing LLM service...")
    try:
        from services.llm_service import get_unified_llm_service

        llm_service = get_unified_llm_service()
        resilient_generator = llm_service.factory.get_action_generator()
        print("✓ LLM service initialized")
        print()

    except Exception as e:
        print(f"✗ Error initializing LLM service: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Initialize item generator
    print("Initializing item generator...")
    try:
        from services.item_generator import ItemGenerator

        item_generator = ItemGenerator(resilient_generator)
        print("✓ Item generator initialized")
        print()

    except Exception as e:
        print(f"✗ Error initializing item generator: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Generate items (Hybrid Approach: only obvious + crucial items initially)
    print("Generating obvious/crucial items using LLM (Hybrid Approach)...")
    print("-" * 70)
    try:
        items = item_generator.generate_obvious_items(
            location_name=location_name,
            location_description=location_description,
            location_id=location_id,
            max_items=7,  # Limit to obvious items only
            created_turn=-1  # Pre-game item
        )

        if not items:
            print("✗ No items generated!")
            sys.exit(1)

        print(f"✓ Generated {len(items)} obvious/crucial items (Hybrid Approach)")
        print("   Hidden items will be generated when searched")
        print("   Container contents will be generated when opened")
        print()

        # Display generated items
        print("Generated Items:")
        print("-" * 70)
        for i, item in enumerate(items, 1):
            print(f"{i}. {item['item_name']} ({item['item_type']})")
            print(f"   Size: {item['size']:,} | Weight: {item['weight']:,} | Capacity: {item['capacity']:,}")
            print(f"   Importance: {item.get('importance_level', 'mundane')} | Visibility: {item.get('visibility_level', 'visible')}")
            print(f"   {item['item_description_short']}")
            if item.get('has_contents'):
                print(f"   [Container - contents will be generated when opened]")
            print()

    except Exception as e:
        print(f"✗ Error generating items: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Initialize item store
    print("Initializing Qdrant item store...")
    print("-" * 70)
    try:
        from services.item_store import ItemStore

        item_store = ItemStore(collection_name="game_items")
        print("✓ Item store initialized")
        print()

    except Exception as e:
        print(f"✗ Error initializing item store: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Store items in Qdrant
    print("Storing items in Qdrant...")
    print("-" * 70)
    success_count = 0
    failed_count = 0

    for item in items:
        try:
            result = item_store.add_item(
                item_id=item['item_id'],
                location_id=item['location_id'],
                item_type=item['item_type'],
                item_name=item['item_name'],
                item_description=item['item_description'],
                item_description_short=item['item_description_short'],
                size=item['size'],
                weight=item['weight'],
                capacity=item['capacity'],
                contained_by_item_id=item.get('contained_by_item_id'),
                carried_by_character_id=item.get('carried_by_character_id'),
                current_state=item.get('current_state'),
                created_turn=item['created_turn'],
                # Hybrid approach fields
                importance_level=item.get('importance_level', 'mundane'),
                visibility_level=item.get('visibility_level', 'visible'),
                position_type=item.get('position_type'),
                positioned_at_item_id=item.get('positioned_at_item_id'),
                has_contents=item.get('has_contents', False),
                contents_generated=item.get('contents_generated', False),
                worn_slot=item.get('worn_slot'),
                carry_method=item.get('carry_method')
            )

            if result:
                print(f"  ✓ {item['item_name']}")
                success_count += 1
            else:
                print(f"  ✗ {item['item_name']} - failed to store")
                failed_count += 1

        except Exception as e:
            print(f"  ✗ {item['item_name']} - error: {e}")
            failed_count += 1

    print()
    print("=" * 70)
    print(f"✓ Completed: {success_count} items stored, {failed_count} failed")
    print("=" * 70)
    print()

    # Verify items in Qdrant
    print("Verifying items in Qdrant...")
    try:
        retrieved_items = item_store.get_items_at_location(location_id)
        print(f"✓ Verified: {len(retrieved_items)} items found at location {location_id}")

        if retrieved_items:
            print()
            print("Sample items from Qdrant:")
            for item in retrieved_items[:3]:
                print(f"  - {item['item_name']}: {item['item_description_short']}")

    except Exception as e:
        print(f"✗ Error verifying items: {e}")

    print()
    print("=" * 70)
    print("✓ West Guest Room item population complete!")
    print("=" * 70)


if __name__ == "__main__":
    try:
        populate_items()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
