# Item System Design - Comprehensive Analysis

## Current Approach (populate_west_guest_room_items.py)

### How It Works
```python
# 1. Generate ALL items at once using LLM
items = item_generator.generate_items_for_location(
    location_name="West Guest Room",
    location_description="...",
    location_id=7,
    created_turn=-1
)

# 2. Store all items in Qdrant with embeddings
for item in items:
    item_store.add_item(...)
```

### Current Schema
```
item_id: UUID
location_id: Integer (SQL location)
contained_by_item_id: UUID (if inside another item)
carried_by_character_id: UUID (if carried)
item_type, item_name, item_description, item_description_short
size, weight, capacity
current_state: TEXT (deviations from base description)
created_turn: Integer
```

### Strengths
✓ Simple and straightforward
✓ Embeddings enable semantic search
✓ Containment tracking (contained_by_item_id)
✓ Character inventory (carried_by_character_id)
✓ State tracking (current_state field)

### Limitations
✗ **Eager generation**: All items generated upfront (token expensive)
✗ **No spatial positioning**: Can't distinguish "on table" vs "in table drawer"
✗ **No visibility levels**: All items equally prominent
✗ **No lazy loading**: Container contents generated even if never opened
✗ **No relevance filtering**: All items in room loaded into context
✗ **No importance tagging**: Can't prioritize crucial items

---

## Your Requirements

### 1. Lazy Container Generation
- **Goal**: Only generate container contents when opened/examined
- **Exception**: Crucial items (quest items, plot devices) pre-generated

### 2. Spatial Positioning
- **Goal**: Track WHERE in room (on table, under bed, in corner)
- **Example**: Box "contained by" table but "positioned on" table top

### 3. Narrative Depth
- **Goal**: Visible items add context to LLM prompts
- **Use**: "You see a dusty book on the mahogany table..."

### 4. Context-Aware Retrieval
- **Goal**: Only load relevant items (not all 50 items in room)
- **Method**: Semantic search based on action/context

### 5. Action-Based State Updates
- **Goal**: Track changes from actions (moved, damaged, opened, combined)
- **Fields**: location, container, carrier, state

---

## Proposed Approaches

## **Approach A: Layered Generation with Importance**

### Schema Extensions
```sql
-- Add to Qdrant payload
importance_level: "crucial" | "notable" | "mundane" | "trivial"
visibility_level: "obvious" | "visible" | "hidden" | "concealed"
position_type: "in" | "on" | "under" | "beside" | "behind" | "hanging_from" | "leaning_against"
positioned_at_item_id: UUID (what item it's positioned relative to)
has_contents: Boolean (container has ungenerated items)
contents_generated: Boolean (contents have been generated)
```

### Generation Strategy
```python
# Phase 1: Game Initialization
def initialize_room_items(location_id, location_description):
    """Generate obvious and crucial items only."""

    # LLM prompt: "Generate 3-7 OBVIOUS items in this room.
    # Mark crucial items (plot-relevant, unique, valuable).
    # Mark containers that would have contents."

    items = llm.generate_obvious_items(
        location_description=location_description,
        importance_filter=["crucial", "notable"],
        visibility_filter=["obvious", "visible"]
    )

    # Store with metadata
    for item in items:
        item_store.add_item(
            ...,
            importance_level=item.importance,
            visibility_level="obvious",
            has_contents=item.is_container and item.capacity > 0,
            contents_generated=False
        )

    return items


# Phase 2: Container Examination
def examine_container(container_id, character_id):
    """Lazily generate contents when opened."""

    container = item_store.get_item(container_id)

    if not container['contents_generated'] and container['has_contents']:
        # Generate contents now
        contents = llm.generate_container_contents(
            container_name=container['item_name'],
            container_description=container['item_description'],
            container_capacity=container['capacity'],
            room_context=location_description
        )

        # Store contents
        for item in contents:
            item_store.add_item(
                ...,
                contained_by_item_id=container_id,
                importance_level="mundane",  # Most contents are mundane
                visibility_level="hidden"  # Not visible until container opened
            )

        # Mark as generated
        item_store.update_item(container_id, contents_generated=True)

    # Return visible contents
    return item_store.get_items_in_container(container_id)
```

### Spatial Positioning
```python
# Example: Book on table
item_store.add_item(
    item_id=book_uuid,
    location_id=7,
    positioned_at_item_id=table_uuid,  # Positioned relative to table
    position_type="on",  # On top of
    contained_by_item_id=None  # Not contained (book is outside)
)

# Example: Scroll in table drawer
item_store.add_item(
    item_id=scroll_uuid,
    location_id=7,
    positioned_at_item_id=None,  # No spatial positioning
    position_type=None,
    contained_by_item_id=drawer_uuid  # Actually contained
)

# Narrative generation
def get_item_position_description(item):
    if item['position_type'] and item['positioned_at_item_id']:
        positioned_at = item_store.get_item(item['positioned_at_item_id'])
        return f"{item['position_type']} the {positioned_at['item_name']}"
    elif item['contained_by_item_id']:
        container = item_store.get_item(item['contained_by_item_id'])
        return f"in the {container['item_name']}"
    else:
        return "in the room"

# "A dusty book on the mahogany table"
# "A scroll in the drawer"
```

### Context-Aware Retrieval
```python
def get_relevant_items_for_context(
    location_id,
    action_description,
    character_id,
    max_items=10
):
    """Retrieve only relevant items for LLM context."""

    # 1. Get obvious items (always visible)
    obvious_items = item_store.search_items(
        location_id=location_id,
        visibility_level=["obvious", "visible"],
        limit=5
    )

    # 2. Semantic search for action-relevant items
    # Example: "examine the bookshelf" → returns books, scrolls
    action_relevant = item_store.semantic_search(
        query_text=action_description,
        location_id=location_id,
        limit=5,
        score_threshold=0.7
    )

    # 3. Get character's inventory
    inventory = item_store.get_items_carried_by(character_id)

    # 4. Combine and deduplicate
    all_items = deduplicate([
        *obvious_items,
        *action_relevant,
        *inventory[:5]  # Limit inventory items
    ])

    return all_items[:max_items]
```

### Action-Based State Updates
```python
# After LLM generates action outcome
def apply_action_to_items(action_outcome, character_id, location_id):
    """Parse action and update item states."""

    # Example outcome: "Character A picks up the rusty dagger from the table."

    # 1. Detect item manipulation (using LLM or regex)
    item_changes = parse_item_manipulations(action_outcome)

    # item_changes = [{
    #     'item_name': 'rusty dagger',
    #     'action_type': 'pick_up',
    #     'from_position': 'on table'
    # }]

    for change in item_changes:
        # Find item by name in location
        item = item_store.find_item_by_name(
            item_name=change['item_name'],
            location_id=location_id
        )

        if item:
            if change['action_type'] == 'pick_up':
                # Move to character inventory
                item_store.update_item(
                    item_id=item['item_id'],
                    carried_by_character_id=character_id,
                    location_id=None,  # No longer at location
                    positioned_at_item_id=None,
                    position_type=None
                )

            elif change['action_type'] == 'place':
                # Place on another item
                target_item = item_store.find_item_by_name(
                    item_name=change['target_item'],
                    location_id=location_id
                )
                item_store.update_item(
                    item_id=item['item_id'],
                    positioned_at_item_id=target_item['item_id'],
                    position_type=change['position_type'],  # "on", "under", etc.
                    carried_by_character_id=None,
                    location_id=location_id
                )

            elif change['action_type'] == 'damage':
                # Update state
                current_state = item.get('current_state', '')
                new_state = f"{current_state}; {change['damage_description']}"
                item_store.update_item(
                    item_id=item['item_id'],
                    current_state=new_state.strip('; ')
                )

    return item_changes
```

---

## **Approach B: Room Manifests with Tiers**

### Concept
Instead of generating all items, create a **manifest** of what SHOULD be in a room, then generate on-demand.

```python
# Room manifest (stored in SQL or Qdrant)
room_manifest = {
    "location_id": 7,
    "item_tiers": [
        {
            "tier": "obvious",  # Always generated
            "item_types": ["furniture", "decoration"],
            "count_range": [3, 7],
            "generated": True
        },
        {
            "tier": "searchable",  # Generated on search
            "item_types": ["container", "tool", "weapon"],
            "count_range": [2, 5],
            "generated": False
        },
        {
            "tier": "hidden",  # Generated on thorough search
            "item_types": ["consumable", "other"],
            "count_range": [1, 3],
            "generated": False
        }
    ],
    "containers": [
        {
            "container_id": "wardrobe_uuid",
            "contents_tier": "clothing",
            "contents_generated": False
        }
    ]
}

# Generate on-demand
def perform_search_action(location_id, search_depth):
    manifest = get_room_manifest(location_id)

    if search_depth == "quick":
        # Only obvious items
        tier = "obvious"
    elif search_depth == "thorough":
        # Obvious + searchable
        tier = "searchable"
    elif search_depth == "exhaustive":
        # All tiers
        tier = "hidden"

    # Generate items for requested tier if not yet generated
    for tier_config in manifest['item_tiers']:
        if tier_config['tier'] == tier and not tier_config['generated']:
            items = llm.generate_items_for_tier(
                location=location,
                tier=tier_config['tier'],
                item_types=tier_config['item_types'],
                count=random.randint(*tier_config['count_range'])
            )

            # Store items
            for item in items:
                item_store.add_item(...)

            # Mark as generated
            tier_config['generated'] = True
            save_manifest(manifest)
```

**Advantages:**
- Predictable item counts (manifests define expectations)
- Encourages thorough exploration
- Can seed specific items in specific tiers

**Disadvantages:**
- More complex manifest management
- Still requires LLM calls (just deferred)

---

## **Approach C: Hybrid Deterministic + Generative**

### Concept
Combine hand-authored crucial items with LLM-generated mundane items.

```python
# Manually defined crucial items (in SQL or JSON config)
crucial_items_config = {
    "location_7_west_guest_room": [
        {
            "item_name": "Letter to Lady Morgana",
            "item_type": "document",
            "importance": "crucial",
            "position": "in the desk drawer",
            "description": "A sealed letter with a blood-red wax seal..."
        }
    ]
}

# Generation combines both
def initialize_room(location_id):
    # 1. Add crucial items (deterministic)
    crucial = get_crucial_items_for_location(location_id)
    for item_config in crucial:
        item_store.add_item(**item_config)

    # 2. Generate mundane items (LLM)
    mundane = llm.generate_mundane_items(
        location=location,
        exclude_items=[item['item_name'] for item in crucial]
    )
    for item in mundane:
        item_store.add_item(**item)
```

**Advantages:**
- Guarantees important items exist
- LLM fills in atmospheric detail
- Mix of control + variety

**Disadvantages:**
- Requires manual item authoring for crucial items
- Less emergent/surprising

---

## **Approach D: Semantic Layers + LOD (Level of Detail)**

### Concept
Items have multiple levels of detail, generated progressively.

```python
# Item generation with LOD
class ItemLOD:
    """Level of Detail for items."""

    LOD_0 = "category"    # "furniture"
    LOD_1 = "brief"       # "a bed"
    LOD_2 = "detailed"    # "a four-poster bed with crimson curtains"
    LOD_3 = "examined"    # Full description + state + contents

# Progressive generation
def describe_room(location_id, detail_level):
    """Generate room description with appropriate item detail."""

    if detail_level == "glance":
        # LOD_1: Brief items only
        return "You see a bed, a wardrobe, and a table."

    elif detail_level == "look":
        # LOD_2: Detailed descriptions
        items = get_items_at_location(location_id, lod=ItemLOD.LOD_2)
        return "You see a four-poster bed with crimson curtains, " \
               "a dark oak wardrobe, and a small writing table."

    elif detail_level == "examine":
        # LOD_3: Full detail + generate contents
        items = get_items_at_location(location_id, lod=ItemLOD.LOD_3)
        # Generate container contents if not yet generated
        for item in items:
            if item.is_container and not item.contents_generated:
                generate_container_contents(item)
        return detailed_description_with_all_items(items)
```

**Advantages:**
- Token-efficient (only load detail when needed)
- Smooth progression from vague to specific
- Natural game feel (glance → look → examine)

**Disadvantages:**
- Requires tracking LOD state
- More complex retrieval logic

---

## Recommended Hybrid Approach

Combine the best elements:

### **Phase 1: Initialization (Eager)**
```python
# Generate obvious + crucial items only
items = generate_initial_items(
    location_id=7,
    importance_levels=["crucial", "notable"],
    visibility_levels=["obvious"],
    max_items=7
)

# Mark containers for lazy generation
for item in items:
    if item.capacity > 0:
        item.has_contents = True
        item.contents_generated = False
```

### **Phase 2: Interaction (Lazy)**
```python
# Generate container contents on examine/open
if action == "examine" and target.is_container:
    if not target.contents_generated:
        contents = generate_container_contents(target)
        target.contents_generated = True

# Generate searchable items on search action
if action == "search":
    if location.searchable_items_generated == False:
        items = generate_searchable_items(location)
        location.searchable_items_generated = True
```

### **Phase 3: Context Assembly (Filtered)**
```python
# Only load relevant items into context
relevant_items = get_relevant_items(
    location_id=location_id,
    action_text=action_description,
    character_inventory=character_id,
    max_items=10  # Token budget
)

# Priority:
# 1. Character's inventory (5 items max)
# 2. Obvious items in room (3 items max)
# 3. Semantically relevant items (vector search, 2 items max)
```

### **Phase 4: State Updates (Reactive)**
```python
# After action executes, parse outcome for item changes
def update_items_from_action(action_outcome):
    # Use lightweight LLM to extract item manipulations
    changes = llm.extract_item_changes(action_outcome)

    # Apply changes
    for change in changes:
        item = find_item(change.item_name)
        item_store.update_item(
            item_id=item.id,
            location_id=change.new_location_id,
            contained_by_item_id=change.new_container_id,
            carried_by_character_id=change.new_carrier_id,
            positioned_at_item_id=change.positioned_at_id,
            position_type=change.position_type,
            current_state=change.state_change
        )
```

---

## Implementation Changes Required

### 1. **Schema Extensions (Qdrant Payload)**
```python
# Add to item_store.py payload
"importance_level": str,  # crucial, notable, mundane, trivial
"visibility_level": str,  # obvious, visible, hidden, concealed
"position_type": str,  # on, in, under, beside, behind, etc.
"positioned_at_item_id": str,  # UUID of item it's positioned relative to
"has_contents": bool,  # Container has ungenerated contents
"contents_generated": bool,  # Contents have been generated
```

### 2. **ItemStore Methods (services/item_store.py)**
```python
# New methods needed
def search_items(location_id, visibility_level, importance_level, limit):
    """Filter items by metadata."""

def semantic_search(query_text, location_id, limit, score_threshold):
    """Vector search for action-relevant items."""

def find_item_by_name(item_name, location_id):
    """Fuzzy match item by name in location."""

def update_item(item_id, **kwargs):
    """Update specific fields of an item."""

def mark_container_contents_generated(container_id):
    """Mark container contents as generated."""
```

### 3. **Item Generator Extensions (services/item_generator.py)**
```python
# New generation methods
def generate_obvious_items(location, max_items=7):
    """Generate only obvious/crucial items."""

def generate_container_contents(container, max_items=10):
    """Generate items inside a specific container."""

def generate_searchable_items(location, max_items=5):
    """Generate hidden items found via search."""
```

### 4. **Action Parser (new: services/item_action_parser.py)**
```python
class ItemActionParser:
    """Parse action outcomes for item state changes."""

    def extract_item_manipulations(self, action_outcome):
        """Use LLM to detect item changes in action text."""
        # Returns: [{item_name, action_type, new_state, ...}]

    def apply_item_changes(self, changes, location_id):
        """Update item store based on detected changes."""
```

### 5. **Context Assembly (services/context_manager.py)**
```python
# Modify get_game_context to use filtered items
def get_visible_items_for_context(location_id, action_text, character_id):
    """Get only relevant items (not all 50 items in room)."""

    # Combine:
    # - Character inventory
    # - Obvious items
    # - Action-relevant items (semantic search)

    return filtered_items  # Max 10 items
```

---

## Summary Comparison

| Approach | Pros | Cons | Best For |
|----------|------|------|----------|
| **A: Layered Generation** | Token-efficient, flexible, supports lazy loading | Complex metadata management | Large, item-rich games |
| **B: Room Manifests** | Predictable, encourages exploration | Requires manifest authoring | Structured, designed experiences |
| **C: Hybrid Deterministic** | Control over crucial items, variety for mundane | Manual item authoring | Story-driven games |
| **D: Semantic LOD** | Highly token-efficient, smooth detail progression | Complex LOD tracking | Performance-critical games |
| **Hybrid (Recommended)** | Balances control, efficiency, emergence | Moderate complexity | Most games, including yours |

---

## Next Steps

1. **Decide on approach** (recommend Hybrid)
2. **Extend Qdrant schema** with new fields
3. **Implement lazy container generation**
4. **Add spatial positioning** (position_type, positioned_at_item_id)
5. **Create filtered retrieval** (semantic search + visibility filtering)
6. **Build action parser** to update item states
7. **Update context assembly** to use filtered items

Would you like me to implement the **Hybrid Approach** with spatial positioning and lazy generation?
