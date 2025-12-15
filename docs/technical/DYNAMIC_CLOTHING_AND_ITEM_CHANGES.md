# Dynamic Clothing and Item Changes System

## Overview

This document describes the implementation of dynamic clothing descriptions from Qdrant items and LLM-driven item property updates based on atmospheric descriptions.

## Changes Made

### 1. Context Manager Updates (`services/context_manager.py`)

**Location**: Line 627-633

**Change**: Updated `_build_dynamic_character_identity()` to prioritize clothing from Qdrant items over static database field.

```python
# Get current clothing from Qdrant (dynamically generated from worn items)
clothing_description = character.get('current_clothing_from_items')
if clothing_description:
    parts.append(f"Clothing: {clothing_description}")
elif character.get('current_clothing'):
    # Fallback to static database field if dynamic clothing not available
    parts.append(f"Clothing: {character.get('current_clothing')}")
```

**Impact**: Character identity in LLM prompts now reflects actual worn items from Qdrant instead of static database text.

---

### 2. Action Generator Updates (`services/action_generator.py`)

**Location**: Lines 163-196

**Change**: Updated `ActionGenerationContext.build()` to retrieve clothing descriptions from Qdrant for both the acting character and visible characters.

```python
# Get clothing from Qdrant items (dynamic)
if self.item_context_helper:
    try:
        character_id = self.character.get('character_id')
        clothing_from_items = self.item_context_helper.get_clothing_description_from_items(
            character_id, brief=True
        )
        context['character_clothing'] = clothing_from_items or self.character.get('current_clothing', 'unchanged')
    except Exception as e:
        logger.warning(f"Failed to get clothing from items: {e}")
        context['character_clothing'] = self.character.get('current_clothing', 'unchanged')
```

**Impact**:
- Action generation now uses real-time clothing from worn items
- Visible characters also show their worn items
- Graceful fallback to database field if Qdrant is unavailable

---

### 3. Item Context Helper Enhancements (`services/item_context_helper.py`)

#### A. New Method: `get_clothing_description_from_items()`

**Location**: Lines 293-337

**Purpose**: Generate dynamic clothing description from character's worn items in Qdrant.

**Features**:
- Brief mode: Returns comma-separated item names
- Detailed mode: Includes descriptions, worn slots, and current_state
- Example output (brief): `"linen shirt, leather boots, wool cloak"`
- Example output (detailed): `"linen shirt (on torso): Simple white shirt; leather boots (on feet): Worn travel boots; wool cloak (on back): Heavy gray cloak (slightly damp)"`

#### B. New Method: `apply_item_changes_from_atmospheric_description()`

**Location**: Lines 339-436

**Purpose**: Parse atmospheric description data and update item properties in Qdrant.

**Supported Changes**:
- `visibility_level`: Changes item visibility (obvious, visible, hidden, concealed)
- `current_state`: Updates item state description (e.g., "flickering dimly", "slightly torn")
- `position_type`: Changes spatial positioning (on, in, under, beside, behind, etc.)
- `positioned_at`: Updates which item this item is positioned relative to

**Expected Data Structure**:
```json
{
    "description": "narrative description...",
    "mood_deltas": {...},
    "item_changes": [
        {
            "item_name": "candle",
            "visibility_level": "obvious",
            "current_state": "flickering dimly",
            "position_type": "on",
            "positioned_at": "wooden table"
        }
    ]
}
```

**Item Lookup Priority**:
1. Character's inventory (if character_id provided)
2. Location items (via find_item_by_name)

---

### 4. Game Routes Updates (`routes/game.py`)

#### A. New Helper Functions

**Location**: Lines 54-82

**Functions Added**:
- `get_item_store()`: Lazy initialization of ItemStore
- `get_item_context_helper()`: Lazy initialization of ItemContextHelper

**Purpose**: Provide singleton instances for item operations in route handlers.

#### B. Player Turn Item Change Application

**Location**: Lines 941-954

**Change**: After generating atmospheric description for player actions, apply any item changes.

```python
# Apply item changes from atmospheric description (if any)
if isinstance(atmos_result, dict) and atmos_result.get('item_changes'):
    item_helper = get_item_context_helper()
    if item_helper:
        try:
            updated_count = item_helper.apply_item_changes_from_atmospheric_description(
                atmos_result,
                location_id=location_id,
                character_id=player_id
            )
            if updated_count > 0:
                logger.info(f"Applied {updated_count} item changes from atmospheric description")
        except Exception as e:
            logger.warning(f"Failed to apply item changes: {e}")
```

#### C. AI Character Turn Item Change Application

**Location**: Lines 1410-1423

**Change**: Same logic applied for AI character atmospheric descriptions.

---

## Usage

### For LLM Prompt Assembly

When building character context, the system now automatically:
1. Queries Qdrant for items with `carry_method='worn'` for the character
2. Generates a clothing description from those items
3. Includes it in the character identity section of prompts

### For Atmospheric Description Generation

To enable item changes, the LLM generating atmospheric descriptions should return:

```json
{
    "description": "The candle flickers as Sir Gelarthon sets it on the mahogany table. The light catches the golden embroidery on his cloak.",
    "mood_deltas": {
        "tension": 0,
        "romance": 1,
        "hostility": 0,
        "cooperation": 0
    },
    "item_changes": [
        {
            "item_name": "brass candle",
            "visibility_level": "obvious",
            "current_state": "flickering softly",
            "position_type": "on",
            "positioned_at": "mahogany table"
        }
    ]
}
```

### Item State Tracking

The system now tracks dynamic item states:
- **visibility_level**: Controls when items appear in descriptions
- **current_state**: Narrative description of current condition
- **position_type + positioned_at_item_id**: Spatial relationships between items
- **contained_by_item_id**: Containment relationships

---

## Benefits

1. **Consistency**: Character clothing always matches what they're actually wearing
2. **Dynamic World**: Items change state based on narrative actions
3. **Reduced Maintenance**: No need to manually update `current_clothing` database field
4. **Immersion**: Players see clothing items they acquire/equip immediately reflected
5. **Flexible State**: Items can be "slightly torn", "bloodstained", "flickering", etc.

---

## Backward Compatibility

The system gracefully falls back to database fields when:
- Qdrant is unavailable
- ItemStore initialization fails
- Character has no worn items
- Item lookup fails

This ensures the game continues to function even if the item system encounters errors.

---

## Future Enhancements

Potential improvements:
1. **LLM Prompt Updates**: Modify atmospheric description system prompt to encourage `item_changes` generation
2. **Visibility Logic**: Implement filtering based on `visibility_level` in context assembly
3. **State History**: Track item state changes over time for debugging
4. **Validation**: Add checks for valid position_type values
5. **Bulk Updates**: Support updating multiple items in a single atmospheric response

---

## Testing

To verify the system works:

1. **Test Clothing Display**:
   - Add worn items to a character in Qdrant
   - Generate action options
   - Verify the clothing description includes those items

2. **Test Item Changes**:
   - Return `item_changes` in atmospheric description JSON
   - Verify items are updated in Qdrant
   - Check logs for update confirmation

3. **Test Fallback**:
   - Temporarily disable Qdrant
   - Verify game still uses database `current_clothing` field

---

## Related Files

- `services/context_manager.py` - Context assembly with dynamic clothing
- `services/action_generator.py` - Action generation with Qdrant clothing
- `services/item_context_helper.py` - Item description and change application
- `services/item_store.py` - Qdrant item storage and retrieval
- `routes/game.py` - Item change application on player/AI turns
- `QDRANT_ITEM_INDEX_FIX.md` - Documentation of location_id index fix (prerequisite)
