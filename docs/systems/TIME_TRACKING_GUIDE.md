# Time Tracking System Guide

## Overview

The game now includes a comprehensive in-game time tracking system where:
- **10 turns = 1 hour** (6 minutes per turn)
- Days are **24 hours** (1,440 minutes)
- **Sun up** at **7:00 AM** (420 minutes since midnight)
- **Sun down** at **7:00 PM** (1,140 minutes since midnight)

Time of day is automatically included in LLM context for action generation.

## Database Schema

### New Columns in `game.game_state`

```sql
game_day INTEGER DEFAULT 1                      -- Current day (starts at 1)
minutes_since_midnight INTEGER DEFAULT 420      -- Time as minutes (0-1439)
minutes_per_turn INTEGER DEFAULT 6              -- Configurable time per turn
```

**Default start time:** Day 1, 7:00 AM

## Migration

The migration file `002_add_time_tracking.sql` has been created. Apply it with:

```bash
python scripts/migrate_db.py
```

This will:
1. Add time tracking columns to `game.game_state`
2. Set default values (Day 1, 7:00 AM, 6 min/turn)
3. Create indexes for time queries

## Stored Procedures

All time operations use stored procedures in `database/procedures/game_state_procedures.sql`:

### Get Time Context
```sql
SELECT * FROM game_state_get_time_context(p_game_state_id);
```

Returns:
- `game_day` - Current day number
- `formatted_time` - Human-readable time (e.g., "7:06 AM")
- `time_of_day` - Category: dawn, morning, afternoon, evening, dusk, night
- `is_daytime` - Boolean (true if between 7am-7pm)
- `minutes_since_midnight` - Raw minutes value

### Advance Time
```sql
SELECT * FROM game_state_advance_time(p_game_state_id);
```

Adds `minutes_per_turn` (default 6) to current time. Handles day rollover automatically.

### Advance Turn (Recommended)
```sql
SELECT * FROM game_state_advance_turn(p_game_state_id);
```

**Use this at the end of each turn.** It:
1. Increments `current_turn`
2. Advances time by `minutes_per_turn`
3. Returns comprehensive turn and time info

### Format Time
```sql
SELECT game_state_format_time(minutes);
```

Converts minutes (0-1439) to formatted time string (e.g., "7:06 AM").

### Get Time Category
```sql
SELECT game_state_time_of_day(minutes);
```

Returns time category:
- `night` - 10pm-5am (1320-1439, 0-299)
- `dawn` - 5am-7am (300-419)
- `morning` - 7am-12pm (420-719)
- `afternoon` - 12pm-5pm (720-1019)
- `evening` - 5pm-7pm (1020-1139)
- `dusk` - 7pm-10pm (1140-1319)

### Check Daytime
```sql
SELECT game_state_is_daytime(minutes);
```

Returns `true` if time is between 7am and 7pm.

## Python API

Use `models/game_time.py` for all time operations:

### Get Time Context
```python
from models.game_time import GameTime

# Get full time context for game_state
time_context = GameTime.get_time_context(db_session, game_state_id)

# Returns:
{
    'game_day': 1,
    'formatted_time': '7:00 AM',
    'time_of_day': 'morning',
    'is_daytime': True,
    'minutes_since_midnight': 420
}
```

### Advance Time
```python
# Advance time by configured minutes_per_turn (default 6)
result = GameTime.advance_time(db_session, game_state_id)

# Returns updated time info
print(f"Now: Day {result['game_day']}, {result['time_of_day']}")
```

### Advance Turn (Recommended)
```python
# Increment turn number AND advance time (use at end of turn)
result = GameTime.advance_turn(db_session, game_state_id)

# Returns:
{
    'current_turn': 2,
    'game_day': 1,
    'formatted_time': '7:06 AM',
    'time_of_day': 'morning'
}
```

### Format for LLM Prompt
```python
# Get natural language time description
time_context = GameTime.get_time_context(db_session, game_state_id)
time_string = GameTime.format_time_for_prompt(time_context)

# Returns: "Day 1, 7:00 AM (morning, sun is up)"
```

### Get Lighting Description
```python
# Get lighting conditions for location descriptions
time_context = GameTime.get_time_context(db_session, game_state_id)
lighting = GameTime.get_lighting_description(time_context)

# Returns: "The area is well-lit by bright morning sunlight."
```

## Game Engine Integration

### Step 1: Initialize Game State with Time

When creating a new game:

```python
from models.game_time import GameState
from uuid import uuid4

game_state_id = GameState.create(
    db_session,
    game_state_id=uuid4(),
    current_turn=1,
    game_day=1,                    # Start on Day 1
    minutes_since_midnight=420,    # Start at 7:00 AM
    minutes_per_turn=6             # 10 turns = 1 hour
)
```

### Step 2: Get Time Context for LLM Prompts

When assembling context for action generation:

```python
from models.game_time import GameTime
from services.context_manager import build_character_context

# Get time context
time_context = GameTime.get_time_context(db_session, game_state_id)

# Format for prompt
time_string = GameTime.format_time_for_prompt(time_context)
lighting = GameTime.get_lighting_description(time_context)

# Add to game_context dict
game_context = {
    'location_name': location.name,
    'location_description': location.description,
    'visible_characters': [...],
    'working_memory': [...],

    # Add time information
    'time_of_day': time_string,
    'lighting_description': lighting,

    # ... rest of context
}

# Build character context (automatically includes time)
final_context, metadata = build_character_context(
    character=character_profile,
    game_context=game_context,
    model='claude-3-5-sonnet-20241022'
)
```

The `context_manager.py` has been updated to automatically include time information in the "current_situation" component (CRITICAL priority, always included).

### Step 3: Advance Time at End of Turn

At the end of each game turn (after all characters have acted):

```python
from models.game_time import GameTime

# Advance turn number and time simultaneously
result = GameTime.advance_turn(db_session, game_state_id)

logger.info(
    f"Turn {result['current_turn']}: "
    f"Day {result['game_day']}, {result['formatted_time']} ({result['time_of_day']})"
)

# Time automatically advances by 6 minutes (configurable)
# Day rolls over automatically at midnight
```

### Step 4: Use Time in Game Logic

Time can affect gameplay:

```python
time_context = GameTime.get_time_context(db_session, game_state_id)

# Check if it's nighttime (affects visibility)
if not time_context['is_daytime']:
    # Apply night penalties, require light sources, etc.
    visibility_modifier = -2
    logger.info("It's nighttime - visibility reduced")

# Check specific time categories
if time_context['time_of_day'] == 'night':
    # Most NPCs are sleeping
    available_npcs = get_awake_npcs(location)
elif time_context['time_of_day'] in ['dawn', 'dusk']:
    # Twilight - special atmosphere
    ambient_description += " The sky is painted with twilight colors."
```

## Example: Complete Turn Loop

```python
from models.game_time import GameTime, GameState
from services.context_manager import build_character_context
import logging

logger = logging.getLogger(__name__)

def process_game_turn(db_session, game_state_id, characters):
    """Process one complete game turn with time tracking."""

    # Get current game state and time
    game_state = GameState.get(db_session, game_state_id)
    time_context = GameTime.get_time_context(db_session, game_state_id)

    logger.info(
        f"=== Turn {game_state['current_turn']} === "
        f"{GameTime.format_time_for_prompt(time_context)}"
    )

    # Process each character's turn
    for character in characters:
        # Build context with time info
        game_context = {
            'location_name': character.current_location.name,
            'location_description': character.current_location.description,
            'visible_characters': get_visible_characters(character),
            'working_memory': get_working_memory(game_state_id, character.id),

            # Time context
            'time_of_day': GameTime.format_time_for_prompt(time_context),
            'lighting_description': GameTime.get_lighting_description(time_context),
        }

        # Generate action options (context_manager automatically includes time)
        context, metadata = build_character_context(
            character=character.to_dict(),
            game_context=game_context,
            model='claude-3-5-sonnet-20241022'
        )

        # Generate and execute action
        action = generate_action(context)
        execute_action(db_session, character, action)

    # Advance turn and time
    result = GameTime.advance_turn(db_session, game_state_id)

    logger.info(
        f"Turn complete. Advanced to Turn {result['current_turn']}, "
        f"{result['formatted_time']} ({result['time_of_day']})"
    )

    # Check for time-based events
    if result['time_of_day'] == 'night' and time_context['time_of_day'] != 'night':
        logger.info("Night has fallen. NPCs retiring to bed.")
        handle_nightfall_event(db_session, game_state_id)

    return result
```

## UI Integration

### Display Current Time

When rendering the game UI, show the current time:

```python
from models.game_time import GameTime

@app.route('/game/<game_state_id>')
def game_view(game_state_id):
    time_context = GameTime.get_time_context(db_session, game_state_id)

    return render_template(
        'game.html',
        game_state=game_state,
        current_time=time_context['formatted_time'],
        game_day=time_context['game_day'],
        time_of_day=time_context['time_of_day'],
        is_daytime=time_context['is_daytime']
    )
```

### Example HTML Template

```html
<div class="game-header">
    <div class="time-display">
        <span class="day">Day {{ game_day }}</span>
        <span class="time">{{ current_time }}</span>
        <span class="tod-badge badge-{{ time_of_day }}">{{ time_of_day }}</span>
        {% if is_daytime %}
            <i class="icon-sun"></i>
        {% else %}
            <i class="icon-moon"></i>
        {% endif %}
    </div>
    <div class="turn-display">
        Turn {{ current_turn }}
    </div>
</div>
```

### Example CSS

```css
.time-display {
    display: flex;
    align-items: center;
    gap: 10px;
    font-family: 'Georgia', serif;
    padding: 10px;
    background: #2a2a2a;
    border-radius: 5px;
}

.day {
    font-weight: bold;
    color: #d4a574;
}

.time {
    font-size: 1.2em;
    color: #e0e0e0;
}

.tod-badge {
    padding: 3px 8px;
    border-radius: 3px;
    font-size: 0.85em;
}

.badge-dawn { background: #ff9a56; }
.badge-morning { background: #ffd700; }
.badge-afternoon { background: #87ceeb; }
.badge-evening { background: #ff7f50; }
.badge-dusk { background: #9370db; }
.badge-night { background: #2c3e50; }

.icon-sun, .icon-moon {
    color: #ffd700;
}

.icon-moon {
    color: #c0c0c0;
}
```

## Testing

See `scripts/test_time_tracking.py` for comprehensive tests of the time system.

## Configuration

To change the rate of time passage, modify `minutes_per_turn` in game state:

```python
# Faster time (20 turns = 1 hour)
GameState.create(db_session, minutes_per_turn=3)

# Slower time (5 turns = 1 hour)
GameState.create(db_session, minutes_per_turn=12)

# Default (10 turns = 1 hour)
GameState.create(db_session, minutes_per_turn=6)
```

## Time Categories

| Category   | Time Range    | Minutes Range | Description |
|------------|---------------|---------------|-------------|
| Night      | 10pm - 5am    | 1320-299      | Dark, most NPCs sleeping |
| Dawn       | 5am - 7am     | 300-419       | Sun rising, low light |
| Morning    | 7am - 12pm    | 420-719       | Sun up, full daylight |
| Afternoon  | 12pm - 5pm    | 720-1019      | Midday, brightest |
| Evening    | 5pm - 7pm     | 1020-1139     | Sun still up, golden hour |
| Dusk       | 7pm - 10pm    | 1140-1319     | Sun setting, dimming light |

## LLM Context Example

When generating actions, the LLM receives context like:

```
Time: Day 1, 7:06 AM (morning, sun is up)
The area is well-lit by bright morning sunlight.

Current location: The Rusty Flagon Tavern
Location description: A dimly lit tavern with rough wooden tables...
Present characters: Aldric the Barkeep, Mira the Bard

[... rest of context ...]
```

This allows the LLM to generate time-appropriate actions:
- Characters won't suggest going to bed at noon
- NPCs can reference "good morning" appropriately
- Actions consider lighting (easier to read documents in daylight)
- Characters can plan around time ("I'll meet you at dusk")

## Troubleshooting

**Migration fails:** Ensure you're running the latest `init_db.py` first, then run `migrate_db.py`.

**Time not appearing in context:** Check that `game_context` includes `time_of_day` when calling `build_character_context()`.

**Time advancing incorrectly:** Use `GameTime.advance_turn()` instead of manually incrementing the turn counter.

**SQL errors:** Ensure stored procedures are loaded with `python scripts/init_db.py`.
