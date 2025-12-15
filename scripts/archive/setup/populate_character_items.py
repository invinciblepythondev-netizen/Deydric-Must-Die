"""
Populate Character Items

Generate and store items for characters based on their clothing, appearance, and role.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from uuid import UUID

# Load environment variables
load_dotenv()

# Character IDs to populate
CHARACTER_IDS = [
    'e6212f28-1081-4e8e-89e3-49e26a4a4372',  # Fizrae Yinai
    'f3807eaf-6d3a-425c-8916-32fd226d899f'   # Sir Gelarthon Findraell
]


def generate_character_items(character_data):
    """
    Generate items for a character using LLM based on their clothing and role.

    Args:
        character_data: Dictionary with character info

    Returns:
        List of generated item dictionaries
    """
    from services.llm_service import get_unified_llm_service
    import json
    import re
    from uuid import uuid4

    print(f"\n{'='*70}")
    print(f"Generating items for: {character_data['name']}")
    print(f"Role: {character_data['role']}")
    print(f"{'='*70}\n")

    # Initialize LLM service
    llm_service = get_unified_llm_service()
    resilient_generator = llm_service.factory.get_action_generator()

    # Build prompt for character items
    system_prompt = """You are generating worn clothing and carried items for a character in a dark fantasy game.

Based on the character's CURRENT_CLOTHING description, create individual item entries for each piece they're wearing or carrying.

ITEM CATEGORIES:
- Clothing items (shirts, pants, dresses, stockings, undergarments, etc.)
- Jewelry (rings, necklaces, bracelets, etc.)
- Accessories (spectacles, belts, scarves, etc.)
- Role-appropriate items (tools, documents, small carried items)

SIZE & WEIGHT SCALES:
- Clothing: size 100-500, weight 50-200
- Jewelry: size 5-20, weight 5-30
- Accessories: size 20-100, weight 10-100
- Small carried items: size 10-150, weight 10-200

IMPORTANT:
- Each piece of clothing/jewelry mentioned should be a separate item
- Mark worn items with: "worn_slot": "head|torso|legs|feet|hands|neck|finger|waist|back"
- All items have: "carry_method": "worn" (for clothing/jewelry) or "carried" (for tools/items)
- Set importance_level: "notable" for significant items (jewelry, unique clothing), "mundane" for basic clothing
- Set visibility_level: "obvious" (worn items are "obvious", unless beneath other clothing then "hidden")
- Capacity should be 0 for most items unless it's a bag/pouch

Return a JSON array:
[
  {
    "item_type": "clothing|weapon|tool|decoration|container|consumable|other",
    "item_name": "Display name",
    "item_description": "Detailed description (2-3 sentences)",
    "item_description_short": "Brief one-sentence description",
    "size": <number 1-10000>,
    "weight": <number 1-10000>,
    "capacity": <number 0 for non-containers>,
    "worn_slot": "head|torso|legs|feet|hands|neck|finger|waist|back|null",
    "carry_method": "worn|carried",
    "importance_level": "notable|mundane",
    "visibility_level": "obvious"
  }
]

CRITICAL: Return ONLY valid JSON, no markdown, no extra text."""

    user_prompt = f"""CHARACTER: {character_data['name']}
ROLE: {character_data['role']}
APPEARANCE: {character_data['appearance']}
CURRENT_CLOTHING: {character_data['clothing']}

Generate individual item entries for each piece of clothing, jewelry, and accessory mentioned in CURRENT_CLOTHING, plus 2-3 small carried items appropriate for their role.

For example, if CURRENT_CLOTHING mentions "black night shirt, grey breeches, ruby ring, spectacles", you should create 4 separate items:
1. Black night shirt (worn on torso)
2. Grey breeches (worn on legs)
3. Ruby ring (worn on finger)
4. Spectacles (worn on head/face)

Then add 2-3 role-appropriate carried items."""

    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                print(f"   Retrying (attempt {attempt + 1}/{max_retries + 1})...")

            response = resilient_generator.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=3000
            )

            # Parse JSON
            json_str = response.strip()
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()

            json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
            items_data = json.loads(json_str)

            if not isinstance(items_data, list):
                raise ValueError("Response is not a JSON array")

            # Validate and enrich items
            items = []
            for idx, item_data in enumerate(items_data):
                required = ['item_type', 'item_name', 'item_description', 'item_description_short', 'size', 'weight']
                missing = [f for f in required if f not in item_data]
                if missing:
                    print(f"   ⚠ Item {idx} missing fields: {missing}, skipping")
                    continue

                # Validate ranges
                if not (1 <= item_data['size'] <= 10000):
                    item_data['size'] = max(1, min(10000, item_data.get('size', 100)))

                if not (1 <= item_data['weight'] <= 10000):
                    item_data['weight'] = max(1, min(10000, item_data.get('weight', 50)))

                # Set defaults
                item_data['capacity'] = item_data.get('capacity', 0)
                if item_data['capacity'] > int(item_data['size'] * 0.8):
                    item_data['capacity'] = int(item_data['size'] * 0.8)

                # Add metadata
                item_data['item_id'] = uuid4()
                item_data['location_id'] = None  # Carried by character
                item_data['created_turn'] = -1  # Pre-game item
                item_data['contained_by_item_id'] = None
                item_data['carried_by_character_id'] = UUID(character_data['character_id'])
                item_data['current_state'] = None

                # Set hybrid fields
                item_data['importance_level'] = item_data.get('importance_level', 'mundane')
                item_data['visibility_level'] = item_data.get('visibility_level', 'obvious')
                item_data['position_type'] = None
                item_data['positioned_at_item_id'] = None
                item_data['has_contents'] = item_data.get('capacity', 0) > 0
                item_data['contents_generated'] = False

                # Ensure worn_slot and carry_method are set
                item_data['worn_slot'] = item_data.get('worn_slot')
                item_data['carry_method'] = item_data.get('carry_method', 'carried')

                items.append(item_data)

            if not items:
                raise ValueError("No valid items generated")

            print(f"✓ Generated {len(items)} items")
            return items

        except json.JSONDecodeError as e:
            print(f"   ✗ JSON parse error (attempt {attempt + 1}): {e}")
            if attempt >= max_retries:
                print("   ✗ Max retries reached")
                return []

        except Exception as e:
            print(f"   ✗ Error (attempt {attempt + 1}): {e}")
            if attempt >= max_retries:
                print("   ✗ Max retries reached")
                return []

    return []


def populate_character_items():
    """Main function to populate items for characters."""

    print("="*70)
    print("Populating Character Items")
    print("="*70)
    print()

    # Get database connection
    database_url = os.getenv('NEON_DATABASE_URL')
    if not database_url:
        print("ERROR: NEON_DATABASE_URL not found in environment variables")
        sys.exit(1)

    if 'postgresql://' in database_url:
        database_url = database_url.replace('postgresql://', 'postgresql+psycopg://')

    engine = create_engine(database_url)

    # Get character details
    print("Fetching character details...")
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT character_id, name, role_responsibilities, physical_appearance,
                       current_clothing, backstory
                FROM character.character
                WHERE character_id = ANY(:ids)
            """), {"ids": CHARACTER_IDS})

            characters = []
            for row in result:
                characters.append({
                    'character_id': str(row.character_id),
                    'name': row.name,
                    'role': row.role_responsibilities,
                    'appearance': row.physical_appearance,
                    'clothing': row.current_clothing,
                    'backstory': row.backstory
                })

            if not characters:
                print("ERROR: No characters found!")
                sys.exit(1)

            print(f"✓ Found {len(characters)} characters")
            for char in characters:
                print(f"  - {char['name']} ({char['role']})")
            print()

    except Exception as e:
        print(f"✗ Error fetching characters: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Initialize item store
    print("Initializing Qdrant item store...")
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

    # Generate and store items for each character
    all_success = 0
    all_failed = 0

    for character_data in characters:
        # Generate items
        items = generate_character_items(character_data)

        if not items:
            print(f"✗ No items generated for {character_data['name']}")
            continue

        # Display generated items
        print(f"\nGenerated Items for {character_data['name']}:")
        print("-" * 70)
        for i, item in enumerate(items, 1):
            worn_info = f" [worn on {item['worn_slot']}]" if item.get('worn_slot') else ""
            carried_info = f" [{item.get('carry_method', 'carried')}]"
            print(f"{i}. {item['item_name']} ({item['item_type']}){worn_info}{carried_info}")
            print(f"   Size: {item['size']:,} | Weight: {item['weight']:,}")
            print(f"   {item['item_description_short']}")
            print()

        # Store items
        print(f"Storing items for {character_data['name']}...")
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
                    carried_by_character_id=item['carried_by_character_id'],
                    current_state=item.get('current_state'),
                    created_turn=item['created_turn'],
                    importance_level=item['importance_level'],
                    visibility_level=item['visibility_level'],
                    position_type=item.get('position_type'),
                    positioned_at_item_id=item.get('positioned_at_item_id'),
                    has_contents=item['has_contents'],
                    contents_generated=item['contents_generated'],
                    worn_slot=item.get('worn_slot'),
                    carry_method=item['carry_method']
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

        print(f"✓ {character_data['name']}: {success_count} items stored, {failed_count} failed")
        all_success += success_count
        all_failed += failed_count
        print()

    # Verify items
    print("="*70)
    print("Verifying stored items...")
    print("-"*70)
    for character_data in characters:
        try:
            items = item_store.get_items_carried_by(UUID(character_data['character_id']))
            print(f"{character_data['name']}: {len(items)} items")

            # Show worn vs carried
            worn = [i for i in items if i.get('carry_method') == 'worn']
            carried = [i for i in items if i.get('carry_method') != 'worn']
            print(f"  - {len(worn)} worn items")
            print(f"  - {len(carried)} carried items")

            total_weight = item_store.get_total_carried_weight(UUID(character_data['character_id']))
            print(f"  - Total weight: {total_weight:,}")
        except Exception as e:
            print(f"{character_data['name']}: Error verifying - {e}")

    print()
    print("="*70)
    print(f"✓ Completed: {all_success} items stored, {all_failed} failed")
    print("="*70)


if __name__ == "__main__":
    try:
        populate_character_items()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
