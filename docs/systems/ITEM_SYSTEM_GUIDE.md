# Item System Guide

## Overview

The item system uses Qdrant vector database to store and retrieve game items with semantic search capabilities. Items can be located in rooms, contained within other items (like a chest), or carried by characters.

## Embedding Providers

The item system requires embedding vectors for semantic search. Embeddings are generated using external APIs with automatic fallback:

**Priority Order:**
1. **Voyage AI** (voyage-large-2) - Preferred for cost and quality
2. **OpenAI** (text-embedding-3-small) - Fallback option

**Setup:**
To use Voyage AI (recommended), add to your `.env` file:
```bash
VOYAGE_API_KEY=your-voyage-api-key
```

Get a Voyage API key at: https://www.voyageai.com/

If Voyage AI is not available, the system will automatically fall back to OpenAI embeddings (if `OPENAI_API_KEY` is set).

## Item Storage

Items are stored in Qdrant with the following schema:

- **item_id**: UUID - Unique identifier
- **location_id**: Integer - SQL database location.location_id (null if contained/carried)
- **item_type**: String - Category (furniture, clothing, weapon, tool, decoration, container, consumable, other)
- **item_name**: String - Display name
- **item_description**: Text - Detailed description (embedded for semantic search)
- **item_description_short**: Text - Brief one-sentence description
- **size**: Integer (1-10000) - Physical size scale
- **weight**: Integer (1-10000) - Weight scale
- **capacity**: Integer (0-100000) - Storage capacity (0 = cannot contain items)
- **contained_by_item_id**: UUID - Item ID of container (null if not contained)
- **carried_by_character_id**: UUID - Character ID if carried (null if not carried)
- **current_state**: Text - Description of state changes from base description
- **created_turn**: Integer - Turn number when created (negative for pre-game items)
- **created_at**: Timestamp - Creation timestamp
- **updated_at**: Timestamp - Last update timestamp

## Scale Guidelines

### Size Scale (1-10000)

Represents the physical volume/dimensions of an item.

#### Tiny (1-10)
- Pin, needle, coin, button
- Earring, bead, pebble
- Examples: `1-5 = pin`, `5-10 = coin`

#### Small (11-50)
- Ring, key, scroll, letter
- Small knife, vial, thimble
- Examples: `15 = ring`, `20 = scroll`, `40 = key`

#### Medium (51-150)
- Book, dagger, shirt, bottle
- Candlestick, goblet, plate
- Examples: `60 = dagger`, `80 = shirt`, `100 = book`

#### Large (151-500)
- Sword, chair, cloak, bag
- Boots, helmet, shield
- Examples: `200 = sword`, `300 = chair`, `450 = large cloak`

#### Very Large (501-2000)
- Chest, table, wardrobe, door
- Barrel, rug, tapestry
- Examples: `600 = chest`, `1000 = table`, `1500 = wardrobe`

#### Massive (2001-10000)
- Four-poster bed, carriage
- Large furniture, heavy doors
- Examples: `3000 = bed`, `5000 = large wardrobe`, `8000 = carriage`

### Weight Scale (1-10000)

Represents how heavy the item is.

#### Feather-light (1-10)
- Paper, cloth, feather, cobweb
- Empty scroll, silk handkerchief
- Examples: `1 = feather`, `5 = paper`, `10 = silk scarf`

#### Light (11-50)
- Book, empty bottle, dagger
- Letter, small jewelry
- Examples: `20 = letter`, `35 = dagger`, `50 = book`

#### Medium (51-200)
- Sword, full bottle, small bag of coins
- Shirt, boots, candlestick
- Examples: `80 = full bottle`, `150 = sword`, `180 = boots`

#### Heavy (201-800)
- Chair, armor, full backpack
- Large weapon, shield
- Examples: `300 = chair`, `500 = armor`, `700 = full backpack`

#### Very Heavy (801-3000)
- Chest of items, table, wardrobe
- Person, barrel of liquid
- Examples: `1000 = table`, `2000 = chest full of items`, `2500 = wardrobe`

#### Extremely Heavy (3001-10000)
- Wardrobe full of clothes, bed
- Stone statue, heavy furniture
- Examples: `4000 = bed`, `6000 = full wardrobe`, `9000 = stone statue`

### Capacity Scale (0 to 80% of size)

**CRITICAL RULE**: Capacity represents interior volume and MUST be less than the item's size!

Items have walls, structure, and material thickness. A chest cannot hold more than fits inside it.

#### Capacity Calculation
- **Non-containers**: Capacity = 0 (most items)
- **Thin-walled containers**: Capacity ≈ 70-80% of size (bags, satchels, cloth pouches)
- **Thick-walled containers**: Capacity ≈ 50-60% of size (chests, wardrobes, barrels)

#### Examples

**Small Items (size 11-150)**
- Ring box (size=20) → capacity ~15 (can hold tiny items)
- Pouch (size=100) → capacity ~70 (thin cloth)
- Bottle (size=120) → capacity ~60 (thick glass)

**Medium/Large Items (size 151-500)**
- Backpack (size=300) → capacity ~220 (thin canvas)
- Small chest (size=400) → capacity ~250 (thick wood)
- Large bag (size=450) → capacity ~350 (reinforced fabric)

**Very Large Items (size 501-2000)**
- Medium chest (size=600) → capacity ~400 (can hold ~4 shirts OR ~6 books)
- Large chest (size=800) → capacity ~500 (thick wood + metal)
- Wardrobe (size=1500) → capacity ~1000 (can hold clothing, NOT furniture)
- Barrel (size=1000) → capacity ~650 (thick staves)

**Massive Items (size 2001+)**
- Large wardrobe (size=2500) → capacity ~1600 (can hold many clothes, small items)
- Four-poster bed (size=5000) → capacity 0 (NOT a container)

#### Containment Rules

1. **Item size ≤ Container capacity**: A chest (capacity=400) CANNOT hold a bed (size=5000)
2. **Total size ≤ Capacity**: Container holding items totaling size=300 can fit one more item of size=100 if capacity=400
3. **No nested oversizing**: Each level of containment must respect capacity limits

#### Real-World Examples

- Small chest (size=600, capacity=400) can hold:
  - ✓ 5 shirts (80 each = 400 total)
  - ✓ 2 swords (200 each = 400 total)
  - ✗ 1 chair (size=500) - too large!
  - ✗ 1 bed (size=5000) - way too large!

- Wardrobe (size=1500, capacity=1000) can hold:
  - ✓ Many clothing items
  - ✓ Small/medium items
  - ✗ Furniture (chairs, tables)
  - ✗ Other wardrobes

## Usage Examples

### Creating Items

```python
from services.item_generator import ItemGenerator
from services.llm_service import get_unified_llm_service

# Initialize
llm_service = get_unified_llm_service()
resilient_generator = llm_service.factory.get_action_generator()
item_generator = ItemGenerator(resilient_generator)

# Generate items for a location
items = item_generator.generate_items_for_location(
    location_name="West Guest Room",
    location_description="A lavishly appointed guest chamber...",
    location_id=7,
    created_turn=-1
)
```

### Storing Items

```python
from services.item_store import ItemStore
from uuid import uuid4

item_store = ItemStore(collection_name="game_items")

# Add an item
item_store.add_item(
    item_id=uuid4(),
    location_id=7,
    item_type="furniture",
    item_name="Four-poster Bed",
    item_description="A massive four-poster bed with crimson velvet curtains...",
    item_description_short="A large four-poster bed with velvet curtains",
    size=5000,  # Very large
    weight=4000,  # Extremely heavy
    capacity=0,  # Cannot contain items
    created_turn=-1
)
```

### Retrieving Items

```python
# Get all items at a location
items = item_store.get_items_at_location(location_id=7)

# Get items carried by a character
items = item_store.get_items_carried_by(character_id="...")

# Get items in a container
items = item_store.get_items_in_container(container_id="...")
```

## Design Principles

1. **Realistic Scales**: Size and weight should feel realistic (a pin is nearly weightless, a bed is massive)
2. **Containers**: Only items with capacity > 0 can contain other items
3. **Containment Rules**: An item cannot be both at a location AND contained/carried
4. **State Tracking**: `current_state` tracks deviations from base description (damage, modifications, etc.)
5. **Semantic Search**: Item descriptions are embedded for finding similar items
6. **Turn-based Age**: `created_turn` allows calculating item age for perishables

## Testing

Run the test script to populate West Guest Room:

```bash
python scripts/populate_west_guest_room_items.py
```

This will:
1. Fetch location details from database
2. Generate 5-15 items using LLM
3. Store them in Qdrant with embeddings
4. Verify storage and display results
