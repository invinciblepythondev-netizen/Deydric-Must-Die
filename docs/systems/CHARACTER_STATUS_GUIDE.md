# Character Status System Guide

The character status system tracks temporary and ongoing conditions that affect character behavior and responses in the game. Statuses like intoxication, anger, fear, or exhaustion influence how LLMs generate character actions and dialogue.

## Overview

**Key Features:**
- **Multiple simultaneous statuses**: Characters can have many active statuses at once (e.g., intoxicated + angry + in pain)
- **Intensity levels**: Each status has a 0-100 intensity scale (mild → moderate → strong → severe)
- **Duration tracking**: Statuses can be temporary (expire after N turns) or indefinite (until manually removed)
- **Stackable vs Non-stackable**: Some statuses (anger) can have multiple instances, others (intoxicated) cannot
- **Categories**: Physical, emotional, mental, social - helps organize status effects
- **LLM integration**: Formatted summaries for easy inclusion in context prompts

## Database Structure

### Tables

**`character.status_type`** - Reference table defining available status types
- `status_type_code`: Unique identifier (e.g., 'intoxicated', 'angry')
- `display_name`: Human-readable name
- `description`: Effect description for LLM context
- `default_duration_turns`: How many turns it typically lasts (NULL = indefinite)
- `category`: 'physical', 'emotional', 'mental', 'social'
- `stackable`: Whether multiple instances can exist simultaneously

**`character.character_status`** - Active statuses affecting characters
- `character_status_id`: UUID primary key
- `character_id`: UUID of affected character
- `status_type_code`: Type of status
- `intensity`: Strength (0-100)
- `onset_turn`: Turn when status began
- `duration_turns`: How long it lasts (NULL = indefinite)
- `expiry_turn`: Calculated turn when it expires
- `source`: What caused the status (for narrative context)
- `notes`: Additional LLM context
- `is_active`: Whether status is currently active

## Pre-defined Status Types

The system comes with 16 common status types:

### Physical
- **intoxicated**: Impaired judgment, slurred speech, reduced coordination (8 turns, non-stackable)
- **exhausted**: Reduced physical/mental performance (indefinite, non-stackable)
- **poisoned**: Pain, weakness, impaired senses (12 turns, stackable)
- **in_pain**: Distracted, irritable from injuries (indefinite, stackable)
- **starving**: Weak, irritable, food-obsessed (indefinite, non-stackable)
- **bleeding**: Weakening over time, needs medical attention (indefinite, stackable)
- **feverish**: Delirious, weak, impaired thinking (indefinite, non-stackable)

### Emotional
- **angry**: Impulsive, harsh, confrontational (indefinite, stackable)
- **frightened**: May flee, freeze, or act defensively (5 turns, stackable)
- **grieving**: Withdrawn, sad, avoids social interaction (indefinite, non-stackable)
- **euphoric**: Overly optimistic, carefree (4 turns, non-stackable)
- **aroused**: Flirtatious, seeks intimacy (indefinite, stackable)

### Mental
- **suspicious**: Distrusting, cautious, paranoid (indefinite, stackable)
- **focused**: Enhanced clarity but tunnel vision (6 turns, non-stackable)
- **confident**: Self-assured, takes risks, leads (8 turns, non-stackable)

### Social
- **humiliated**: Shame, embarrassment, may lash out (10 turns, stackable)

## Python Usage

### Adding a Status

```python
from models.character_status import CharacterStatus
from uuid import UUID

# Character drinks ale and becomes intoxicated
status_id = CharacterStatus.add_status(
    db_session=session,
    character_id=UUID('a1111111-1111-1111-1111-111111111111'),
    status_type_code='intoxicated',
    intensity=60,  # Moderately drunk
    onset_turn=15,
    duration_turns=8,  # Will last 8 turns
    source='drank three mugs of ale',
    notes='Likely to make poor decisions and speak too freely'
)
session.commit()
```

### Getting Active Statuses

```python
# Get all active statuses for a character
statuses = CharacterStatus.get_active_statuses(
    db_session=session,
    character_id=UUID('a1111111-1111-1111-1111-111111111111'),
    current_turn=18
)

for status in statuses:
    print(f"{status['display_name']}: {status['intensity']}/100")
    print(f"  Source: {status['source']}")
    print(f"  Turns remaining: {status['turns_remaining']}")
```

### Getting Status Summary for LLM Context

```python
# Get formatted summary for inclusion in LLM prompt
summary = CharacterStatus.get_status_summary(
    db_session=session,
    character_id=character_id,
    current_turn=18
)

print(summary)
# Output:
# moderately intoxicated (drank three mugs of ale) [5 turns remaining] - Likely to make poor decisions
# strongly angry (was insulted publicly) - may seek confrontation
# mildly frightened (witnessed violence)
```

### Updating Status Intensity

```python
# Character drinks more ale - increase intoxication
new_intensity = CharacterStatus.update_intensity(
    db_session=session,
    character_status_id=status_id,
    intensity_change=+20  # +20 points more drunk
)
print(f"New intensity: {new_intensity}/100")

# Character calms down over time - reduce anger
CharacterStatus.update_intensity(
    db_session=session,
    character_status_id=anger_status_id,
    intensity_change=-15  # Calming down
)
```

### Removing Statuses

```python
# Remove a specific status instance
CharacterStatus.remove_status(
    db_session=session,
    character_status_id=status_id
)

# Remove all statuses of a type (e.g., all anger instances)
removed_count = CharacterStatus.remove_status_by_type(
    db_session=session,
    character_id=character_id,
    status_type_code='angry'
)
print(f"Removed {removed_count} anger statuses")
```

### Expiring Old Statuses (Called Each Turn)

```python
# At end of each game turn, expire statuses that have reached their duration
expired = CharacterStatus.expire_old_statuses(
    db_session=session,
    current_turn=23
)

for status in expired:
    print(f"{status['display_name']} expired for character {status['character_id']}")
    # Could generate narration: "Character A sobers up", "The fear subsides", etc.
```

### Get Statuses by Category

```python
# Get only emotional statuses
emotional_statuses = CharacterStatus.get_statuses_by_category(
    db_session=session,
    character_id=character_id,
    category='emotional',
    current_turn=20
)

for status in emotional_statuses:
    print(f"{status['display_name']}: {status['intensity']}")
```

## Integration with Game Loop

### During Action Generation

When assembling LLM context for character action generation:

```python
def assemble_character_context(character_id, current_turn):
    """Assemble context for LLM prompt"""

    context = {
        "character_profile": get_character_profile(character_id),
        "current_location": get_current_location(character_id),
        "visible_characters": get_visible_characters(character_id),
        "working_memory": get_working_memory(character_id),

        # ADD STATUS SUMMARY HERE
        "active_statuses": CharacterStatus.get_status_summary(
            db_session=session,
            character_id=character_id,
            current_turn=current_turn
        ),

        "relationships": get_relationships(character_id),
        "wounds": get_character_wounds(character_id)
    }

    return context
```

### In LLM Prompt

```
You are generating actions for Character A.

CURRENT EMOTIONAL & PHYSICAL STATE:
{active_statuses}
- moderately intoxicated (drank ale) [3 turns remaining] - impaired judgment
- strongly angry (was insulted) - may act impulsively
- mildly in pain (shoulder wound) - distracted by discomfort

Consider how these statuses affect the character's judgment, speech patterns,
and physical capabilities when generating action options.
```

### At End of Turn

```python
def end_turn(current_turn):
    """Called after all characters have acted"""

    # 1. Expire old statuses
    expired = CharacterStatus.expire_old_statuses(
        db_session=session,
        current_turn=current_turn
    )

    # 2. Generate narration for expired statuses
    for status in expired:
        if status['status_type_code'] == 'intoxicated':
            narrate(f"{get_character_name(status['character_id'])} sobers up slightly.")
        elif status['status_type_code'] == 'frightened':
            narrate(f"{get_character_name(status['character_id'])} feels less afraid.")

    # 3. Update wound-related statuses (bleeding, in_pain)
    update_wound_statuses(current_turn)

    # 4. Increment turn counter
    increment_turn()
```

## Common Patterns

### Stackable Statuses (Multiple Sources of Anger)

```python
# Character A is insulted by Character B
CharacterStatus.add_status(
    db_session=session,
    character_id=char_a_id,
    status_type_code='angry',
    intensity=40,
    onset_turn=10,
    source='insulted by Character B',
    notes='wants to defend honor'
)

# Later, Character A witnesses someone steal from them
CharacterStatus.add_status(
    db_session=session,
    character_id=char_a_id,
    status_type_code='angry',
    intensity=60,
    onset_turn=15,
    source='possessions stolen',
    notes='feels violated and wants justice'
)

# Character A now has TWO anger statuses from different sources
# Both will show in the status summary, providing rich context
```

### Non-Stackable Statuses (Only One Instance)

```python
# Character drinks ale
CharacterStatus.add_status(
    db_session=session,
    character_id=char_id,
    status_type_code='intoxicated',  # Non-stackable
    intensity=50,
    onset_turn=5,
    duration_turns=8
)

# Character drinks MORE ale
# This UPDATES the existing intoxicated status instead of creating a new one
CharacterStatus.add_status(
    db_session=session,
    character_id=char_id,
    status_type_code='intoxicated',
    intensity=70,  # Updated to more drunk
    onset_turn=7,  # Reset onset
    duration_turns=8,  # Duration resets
    source='drank additional ale'
)
```

### Linking Statuses to Wounds

```python
# Character receives a severe wound
wound_id = create_wound(
    character_id=char_id,
    body_part='torso',
    wound_type='stab',
    severity='severe',
    is_bleeding=True
)

# Automatically add related statuses
if wound_severity in ['severe', 'critical', 'mortal']:
    CharacterStatus.add_status(
        db_session=session,
        character_id=char_id,
        status_type_code='in_pain',
        intensity=80,
        onset_turn=current_turn,
        duration_turns=None,  # Lasts until wound treated
        source=f'severe stab wound to {body_part}'
    )

if wound.is_bleeding:
    CharacterStatus.add_status(
        db_session=session,
        character_id=char_id,
        status_type_code='bleeding',
        intensity=60,
        onset_turn=current_turn,
        duration_turns=None,
        source=f'bleeding from {body_part} wound'
    )
```

### Intensity Decay Over Time

```python
def decay_statuses_each_turn(current_turn):
    """Some statuses naturally decrease in intensity over time"""

    # Get all active emotional statuses
    for character in all_characters:
        statuses = CharacterStatus.get_statuses_by_category(
            db_session=session,
            character_id=character.id,
            category='emotional',
            current_turn=current_turn
        )

        for status in statuses:
            # Anger, fear, etc. decay by 5 points per turn if no new triggers
            if status['status_type_code'] in ['angry', 'frightened', 'suspicious']:
                CharacterStatus.update_intensity(
                    db_session=session,
                    character_status_id=status['character_status_id'],
                    intensity_change=-5
                )
                # Will auto-deactivate at intensity 0
```

## Direct SQL Usage (If Needed)

While the Python wrapper is recommended, you can call procedures directly:

```sql
-- Add a status
SELECT character_status_upsert(
    p_character_id := 'a1111111-1111-1111-1111-111111111111'::uuid,
    p_status_type_code := 'intoxicated',
    p_intensity := 60,
    p_onset_turn := 15,
    p_duration_turns := 8,
    p_source := 'drank three mugs of ale',
    p_notes := 'Likely to make poor decisions'
);

-- Get active statuses
SELECT * FROM character_status_list_active(
    p_character_id := 'a1111111-1111-1111-1111-111111111111'::uuid,
    p_current_turn := 18
);

-- Get formatted summary
SELECT character_status_get_summary(
    p_character_id := 'a1111111-1111-1111-1111-111111111111'::uuid,
    p_current_turn := 18
);

-- Expire old statuses
SELECT * FROM character_status_expire_old(p_current_turn := 25);
```

## Best Practices

1. **Update statuses based on events**: When significant events occur (drinking, witnessing violence, receiving compliments), add/update relevant statuses

2. **Include status summary in LLM context**: Always include `character_status_get_summary()` in action generation prompts

3. **Expire statuses each turn**: Call `expire_old_statuses()` at the end of every turn

4. **Use appropriate intensities**:
   - 0-25: Mild effect, barely noticeable
   - 26-50: Moderate effect, clearly affecting behavior
   - 51-75: Strong effect, major influence on decisions
   - 76-100: Severe effect, dominates character's state

5. **Provide descriptive sources**: Help the LLM understand context (e.g., "insulted in front of crowd" vs just "angry")

6. **Use notes for LLM guidance**: Add notes like "may lash out verbally" or "prone to poor decisions" to guide action generation

7. **Link to other systems**: Connect statuses to wounds, relationships, and events for rich narrative context

8. **Decay appropriately**: Not all statuses should last indefinitely - use duration or manual decay

## Testing the System

```python
# scripts/test_character_status.py
from models.character_status import CharacterStatus, StatusType
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from uuid import uuid4

DATABASE_URL = os.getenv('NEON_DATABASE_URL')
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

# List available status types
print("=== Available Status Types ===")
types = StatusType.list_all(session)
for t in types:
    print(f"{t['status_type_code']}: {t['display_name']} ({t['category']})")
    print(f"  {t['description']}")
    print(f"  Duration: {t['default_duration_turns']} turns, Stackable: {t['stackable']}")
    print()

# Create test character ID
test_char_id = uuid4()

# Add multiple statuses
print("=== Adding Statuses ===")
CharacterStatus.add_status(session, test_char_id, 'intoxicated', 70, 10, 8, 'drank ale')
CharacterStatus.add_status(session, test_char_id, 'angry', 50, 12, None, 'was insulted')
CharacterStatus.add_status(session, test_char_id, 'in_pain', 40, 8, None, 'shoulder wound')

# Get summary
print("\n=== Status Summary (Turn 15) ===")
summary = CharacterStatus.get_status_summary(session, test_char_id, 15)
print(summary)

# Get detailed list
print("\n=== Detailed Status List ===")
statuses = CharacterStatus.get_active_statuses(session, test_char_id, 15)
for s in statuses:
    print(f"{s['display_name']}: {s['intensity']}/100")
    print(f"  Category: {s['category']}")
    print(f"  Source: {s['source']}")
    if s['turns_remaining']:
        print(f"  Expires in: {s['turns_remaining']} turns")
    print()

session.close()
```

## Migration Instructions

To add this system to your database:

```bash
# 1. Apply the migration
python scripts/migrate_db.py

# 2. Verify tables created
psql $NEON_DATABASE_URL -c "\dt character.*status*"

# 3. Test procedures
psql $NEON_DATABASE_URL -c "SELECT * FROM status_type_list();"
```
