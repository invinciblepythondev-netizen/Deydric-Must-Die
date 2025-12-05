# Phase 1 Complete - Core Models

## ✅ All Model Wrappers Created

Phase 1 is complete! All core Python model wrappers have been created as thin layers over the existing stored procedures.

### Models Created

#### 1. Character Model (`models/character.py`)
**Methods:**
- `Character.get(db, character_id)` - Get character by ID
- `Character.list_by_location(db, location_id)` - Get all characters at location
- `Character.create_or_update(db, ...)` - Create/update character
- `Character.update_location(db, character_id, location_id)` - Move character
- `Character.delete(db, character_id)` - Delete character

**Usage Example:**
```python
from models.character import Character

# Get character
character = Character.get(db_session, character_id)
print(f"{character['name']} is at location {character['current_location_id']}")

# List characters at location
characters = Character.list_by_location(db_session, location_id=1)
for char in characters:
    print(f"- {char['name']} ({char['current_stance']})")

# Move character
Character.update_location(db_session, character_id, new_location_id=2)
```

#### 2. Location Model (`models/location.py`)
**Methods:**
- `Location.get(db, location_id)` - Get location by ID
- `Location.list_all(db)` - Get all locations
- `Location.create_or_update(db, ...)` - Create/update location
- `Location.get_connections(db, location_id)` - Get connected locations
- `Location.get_characters_at(db, location_id)` - Get characters at location
- `Location.delete(db, location_id)` - Delete location

**Usage Example:**
```python
from models.location import Location

# Get location
location = Location.get(db_session, location_id=1)
print(f"{location['name']}: {location['description']}")

# Get connections
connections = Location.get_connections(db_session, location_id=1)
for conn in connections:
    print(f"Go {conn['direction']} to {conn['location_name']}")

# Get characters here
characters = Location.get_characters_at(db_session, location_id=1)
```

#### 3. Turn Model (`models/turn.py`)
**Classes:**
- `Turn` - Turn history operations
- `MemorySummary` - Memory summary operations

**Turn Methods:**
- `Turn.create_action(db, ...)` - Record an action in turn history
- `Turn.get_working_memory(db, game_state_id, n_turns)` - Get last N turns
- `Turn.get_witnessed_memory(db, game_state_id, character_id, n_turns)` - Get what character knows
- `Turn.mark_as_embedded(db, turn_id, embedding_id)` - Mark as embedded
- `Turn.get_unembedded(db, min_significance, limit)` - Get actions needing embedding

**MemorySummary Methods:**
- `MemorySummary.create(db, game_state_id, start_turn, end_turn, summary_text)` - Create summary
- `MemorySummary.get_summaries(db, game_state_id, summary_type)` - Get summaries

**Usage Example:**
```python
from models.turn import Turn, MemorySummary

# Record an action
turn_id = Turn.create_action(
    db_session,
    game_state_id=game_id,
    turn_number=15,
    character_id=character_id,
    action_type='speak',
    action_description='Character A says "Hello!"',
    location_id=1,
    sequence_number=0,
    is_private=False,
    witnesses=[char_b_id, char_c_id]
)

# Get working memory (all characters see)
working_memory = Turn.get_working_memory(db_session, game_id, last_n_turns=10)

# Get witnessed memory (specific character's perspective)
witnessed = Turn.get_witnessed_memory(db_session, game_id, character_id, last_n_turns=10)

# Create summary
summary_id = MemorySummary.create(
    db_session, game_id,
    start_turn=1, end_turn=10,
    summary_text="The tavern was tense as Gareth became increasingly drunk..."
)
```

#### 4. Wound Model (`models/wound.py`)
**Methods:**
- `Wound.list_by_character(db, character_id)` - Get all wounds for character
- `Wound.get(db, wound_id)` - Get specific wound
- `Wound.create(db, character_id, body_part, wound_type, severity, ...)` - Create wound
- `Wound.update(db, wound_id, ...)` - Update wound status
- `Wound.add_treatment(db, wound_id, treater_id, treatment_type, ...)` - Record treatment
- `Wound.age_all_wounds(db)` - Increment turns_since_injury for all wounds
- `Wound.delete(db, wound_id)` - Delete wound (healed)
- `Wound.get_summary(db, character_id)` - Get natural language summary

**Usage Example:**
```python
from models.wound import Wound

# Create wound
wound_id = Wound.create(
    db_session,
    character_id=character_id,
    body_part='left_arm',
    wound_type='cut',
    severity='moderate',
    is_bleeding=True,
    description='Deep gash from sword',
    caused_by='Gareth',
    occurred_at_turn=15
)

# Get character's wounds
wounds = Wound.list_by_character(db_session, character_id)

# Get summary
summary = Wound.get_summary(db_session, character_id)
print(summary)  # "Wounded: moderate cut on left_arm"

# Add treatment
Wound.add_treatment(
    db_session, wound_id,
    treater_character_id=healer_id,
    treatment_type='bandage',
    was_successful=True,
    turn_number=16
)

# Age all wounds (call once per turn)
Wound.age_all_wounds(db_session)
```

#### 5. Relationship Model (`models/relationship.py`)
**Methods:**
- `Relationship.get(db, source_id, target_id)` - Get relationship
- `Relationship.list_for_character(db, character_id)` - Get all relationships
- `Relationship.create_or_update(db, source_id, target_id, trust, fear, respect, ...)` - Create/update
- `Relationship.adjust(db, source_id, target_id, trust_delta, fear_delta, ...)` - Adjust by deltas
- `Relationship.delete(db, source_id, target_id)` - Delete relationship
- `Relationship.get_summary(db, source_id, target_id)` - Get natural language summary
- `Relationship.get_relationships_for_location(db, character_id, location_id)` - Get all relationships at location

**Usage Example:**
```python
from models.relationship import Relationship

# Get relationship
rel = Relationship.get(db_session, aldric_id, gareth_id)
print(f"Trust: {rel['trust']}, Fear: {rel['fear']}")

# Adjust relationship (incremental change)
Relationship.adjust(
    db_session,
    source_character_id=aldric_id,
    target_character_id=gareth_id,
    trust_delta=-0.1,  # Decrease trust by 10%
    fear_delta=+0.15,  # Increase fear by 15%
    interaction_turn=15
)

# Get summary
summary = Relationship.get_summary(db_session, aldric_id, gareth_id)
print(summary)  # "Distrustful (30%), Wary (40%), Neutral (50%)"

# Get all relationships at location (for context assembly)
relationships = Relationship.get_relationships_for_location(
    db_session,
    character_id=aldric_id,
    location_id=1
)
```

---

## Usage Patterns

### Database Session Management

All models expect a SQLAlchemy session:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

# Create engine
DATABASE_URL = os.getenv('NEON_DATABASE_URL')
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

# Use session
db_session = Session()
try:
    # Use models
    character = Character.get(db_session, character_id)

    # Models handle commit internally for write operations
    # No need to manually commit
finally:
    db_session.close()
```

### Error Handling

Models return:
- `None` for get operations when not found
- `[]` (empty list) for list operations when no results
- `bool` for success/failure operations
- `UUID` or `int` for create/update operations

```python
character = Character.get(db_session, character_id)
if character is None:
    print("Character not found")
else:
    print(f"Found: {character['name']}")
```

### Logging

All models use Python's logging module:

```python
import logging

# Enable logging to see model operations
logging.basicConfig(level=logging.INFO)

# Models will log:
# - INFO: Successful operations
# - DEBUG: Detailed operation info
# - WARNING: Issues
# - ERROR: Failures
```

---

## What's Next: Phase 2

With Phase 1 complete, you can now build:

**Phase 2: Action Execution (3-4 hours)**
1. `services/action_executor.py` - Execute ActionSequence, apply effects
2. `services/turn_order.py` - Manage turn order
3. `services/witness_tracker.py` - Determine who sees actions

**Phase 3: Game Engine (2-3 hours)**
1. `services/game_engine.py` - Main orchestrator

**Phase 4: Flask App (3 hours)**
1. `app.py` - Entry point
2. `routes/game.py` - Routes

**Phase 5: UI (3-4 hours)**
1. Templates (base.html, game.html)

**Phase 6: Seed Data (1 hour)**
1. `scripts/seed_data.py` - Test content

---

## Testing Models

You can test models directly:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.character import Character
from models.location import Location
from uuid import uuid4
import os

# Setup
engine = create_engine(os.getenv('NEON_DATABASE_URL'))
Session = sessionmaker(bind=engine)
db = Session()

# Create location
location_id = Location.create_or_update(
    db, 1, "Test Tavern", "A test location",
    connections={"north": 2}
)

# Create character
character_id = Character.create_or_update(
    db, uuid4(), "Test Character",
    physical_appearance="Tall man",
    current_location_id=location_id
)

# Query
chars = Character.list_by_location(db, location_id)
print(f"Found {len(chars)} characters at location")

db.close()
```

---

## Files Created

```
models/
├── action_sequence.py  ✅ (already existed)
├── character_status.py ✅ (already existed)
├── game_time.py        ✅ (already existed)
├── scene_mood.py       ✅ (already existed)
├── character.py        ✅ NEW - Phase 1
├── location.py         ✅ NEW - Phase 1
├── turn.py             ✅ NEW - Phase 1
├── wound.py            ✅ NEW - Phase 1
└── relationship.py     ✅ NEW - Phase 1
```

---

## Integration with Existing Systems

### With Action Generation

```python
from models.character import Character
from models.location import Location
from models.relationship import Relationship
from models.scene_mood import SceneMood
from models.game_time import GameTime
from services.action_generator import ActionGenerator

# Gather context
character = Character.get(db, character_id)
location = Location.get(db, location_id)
visible_chars = Location.get_characters_at(db, location_id)
relationships = Relationship.get_relationships_for_location(db, character_id, location_id)
mood = SceneMood.get_description(db, game_state_id, location_id)
time = GameTime.get_time_context(db, game_state_id)

# Generate actions
generator = ActionGenerator(llm_provider)
options = generator.generate_options(
    db, character, game_state_id, location,
    visible_chars, current_turn
)
```

### With Turn History

```python
from models.turn import Turn
from models.action_sequence import ActionType

# Execute action sequence
for seq_num, action in enumerate(selected_option.sequence.actions):
    Turn.create_action(
        db,
        game_state_id=game_id,
        turn_number=current_turn,
        character_id=character_id,
        action_type=action.action_type.value,
        action_description=action.description,
        location_id=location_id,
        sequence_number=seq_num,
        is_private=action.is_private,
        witnesses=witnesses if not action.is_private else []
    )
```

---

## Summary

✅ **5 core model wrappers created**
✅ **All stored procedures wrapped**
✅ **Consistent API patterns**
✅ **Logging integrated**
✅ **Ready for Phase 2**

The database foundation is now fully accessible from Python. You can proceed with building the Action Executor and Game Engine!
