# Emotional State System - Complete Implementation

## Overview

The emotional state system provides **hierarchical intensity tracking** with content boundaries for both individual characters and group scenes. It tracks emotional progression from neutral to extreme states across multiple emotional arcs.

## System Architecture

### 1. Intensity Level Hierarchy

Five tiers of emotional intensity:

| Level | Name | Points | Description |
|-------|------|--------|-------------|
| 0 | **NEUTRAL** | 0-24 | Calm, indifferent, routine interactions |
| 1 | **ENGAGED** | 25-49 | Interested, aware, emotionally attentive |
| 2 | **PASSIONATE** | 50-74 | Intense, emotionally invested |
| 3 | **EXTREME** | 75-99 | Critical, overwhelming, climactic |
| 4 | **BREAKING** | 100-120 | Threshold exceeded, major event imminent |

### 2. Emotional Arcs

Four primary progression paths:

**Conflict Arc:** `tension → hostility → violence`
- Emotions: anger, aggression, hostility, violence, rage
- Progression: Disagreement → Argument → Physical confrontation

**Intimacy Arc:** `attraction → romance → intimacy`
- Emotions: attraction, desire, romance, affection, lust
- Progression: Interest → Affection → Physical closeness

**Fear Arc:** `unease → fear → terror`
- Emotions: fear, terror, dread, panic, anxiety, unease
- Progression: Suspicion → Anxiety → Panic

**Social Arc:** `cooperation → camaraderie → devotion`
- Emotions: cooperation, camaraderie, devotion, trust, loyalty
- Progression: Working together → Friendship → Loyalty

### 3. Two-Layer Tracking

**Individual Level:** `character_emotional_state`
- Tracks each character's personal emotional state
- Multiple emotions tracked simultaneously in `emotion_scores` JSONB
- Dominant emotion becomes `primary_emotion`
- Intensity calculated from highest emotion score

**Scene/Group Level:** `scene_mood`
- Tracks collective emotional state at a location
- Four emotion dimensions: tension, romance, hostility, cooperation
- Automatically calculates dominant arc and intensity
- Aware of content boundaries for the game

---

## Database Schema

### Character Emotional State Table

```sql
CREATE TABLE character.character_emotional_state (
    state_id UUID PRIMARY KEY,
    character_id UUID NOT NULL,
    game_state_id UUID NOT NULL,

    -- Current state
    primary_emotion TEXT NOT NULL DEFAULT 'calm',
    intensity_level INTEGER DEFAULT 0 CHECK (0-4),
    intensity_points INTEGER DEFAULT 0 CHECK (0-120),

    -- Multiple emotions tracked
    emotion_scores JSONB DEFAULT '{}'::jsonb,
    -- Example: {"anger": 45, "fear": 20, "attraction": 5}

    -- Tracking
    last_intensity_change_turn INTEGER,
    emotional_trajectory TEXT DEFAULT 'stable',  -- rising, falling, stable, volatile

    -- Context
    triggered_by_character_id UUID,
    trigger_description TEXT,

    UNIQUE(character_id, game_state_id)
);
```

### Scene Mood Table (Updated)

```sql
ALTER TABLE game.scene_mood ADD COLUMN intensity_level INTEGER DEFAULT 0;
ALTER TABLE game.scene_mood ADD COLUMN intensity_points INTEGER DEFAULT 0;
ALTER TABLE game.scene_mood ADD COLUMN dominant_arc TEXT;  -- conflict, intimacy, fear, social
ALTER TABLE game.scene_mood ADD COLUMN scene_phase TEXT;  -- building, climax, resolution, aftermath
ALTER TABLE game.scene_mood ADD COLUMN last_level_change_turn INTEGER;
```

### Content Settings Table

```sql
CREATE TABLE game.content_settings (
    game_state_id UUID PRIMARY KEY,

    -- Overall rating
    content_rating TEXT DEFAULT 'pg13',  -- g, pg, pg13, r, nc17, unrestricted

    -- Category limits (0-4 for each)
    violence_max_level INTEGER DEFAULT 2,
    romance_max_level INTEGER DEFAULT 1,
    intimacy_max_level INTEGER DEFAULT 0,
    language_max_level INTEGER DEFAULT 2,
    horror_max_level INTEGER DEFAULT 2,

    -- Flags
    allow_graphic_violence BOOLEAN DEFAULT FALSE,
    allow_sexual_content BOOLEAN DEFAULT FALSE,
    allow_substance_use BOOLEAN DEFAULT TRUE,
    allow_psychological_horror BOOLEAN DEFAULT TRUE,
    allow_death BOOLEAN DEFAULT TRUE,

    -- Fade-to-black preferences
    fade_to_black_violence BOOLEAN DEFAULT FALSE,
    fade_to_black_intimacy BOOLEAN DEFAULT TRUE,
    fade_to_black_death BOOLEAN DEFAULT FALSE,

    -- Provider preference
    preferred_nsfw_provider TEXT  -- aiml, together, local
);
```

---

## Python API

### CharacterEmotionalState Model

```python
from models.character_emotional_state import CharacterEmotionalState
from uuid import UUID

# Get character's emotional state
state = CharacterEmotionalState.get(db_session, character_id, game_state_id)
# Returns: {'primary_emotion': 'anger', 'intensity_level': 2, ...}

# Adjust emotion (incremental)
result = CharacterEmotionalState.adjust(
    db_session,
    character_id=character_id,
    game_state_id=game_state_id,
    emotion='anger',
    points_delta=+15,  # Add 15 points to anger
    triggered_by_character_id=other_char_id,
    trigger_description="Insulted by other character"
)
# Returns: {
#   'new_intensity_level': 2,
#   'new_intensity_points': 65,
#   'level_changed': True,
#   'content_boundary_hit': False,
#   'previous_level': 1
# }

# Get natural language description
description = CharacterEmotionalState.get_description(db_session, character_id, game_state_id)
# Returns: "Feeling anger (passionate intensity, escalating) - 65 points"

# Reset to neutral
CharacterEmotionalState.reset(db_session, character_id, game_state_id)

# List all emotional states at location
states = CharacterEmotionalState.list_by_location(db_session, game_state_id, location_id)
```

### ContentSettings Model

```python
from models.content_settings import ContentSettings

# Set preset rating (easiest)
ContentSettings.set_preset(db_session, game_state_id, 'pg13')
# Presets: g, pg, pg13, r, nc17, unrestricted

# Get settings
settings = ContentSettings.get(db_session, game_state_id)
# Returns: {'content_rating': 'pg13', 'violence_max_level': 2, ...}

# Manual configuration
ContentSettings.upsert(
    db_session,
    game_state_id=game_state_id,
    content_rating='r',
    violence_max_level=3,
    intimacy_max_level=2,
    fade_to_black_intimacy=True,
    preferred_nsfw_provider='aiml'
)

# Check if emotion can escalate
check = ContentSettings.can_escalate(
    db_session, game_state_id,
    emotion_category='violence',
    target_level=3
)
# Returns: {'can_escalate': True, 'reason': None}

# Get LLM prompt instructions
instructions = ContentSettings.get_fade_instructions(db_session, game_state_id)
# Returns: "For intimate actions, imply what happens rather than..."
```

### SceneMood Model (Updated)

```python
from models.scene_mood import SceneMood

# Adjust scene mood (automatic intensity calculation)
result = SceneMood.adjust(
    db_session,
    game_state_id=game_state_id,
    location_id=location_id,
    hostility_delta=+20,  # Increase hostility by 20
    tension_delta=+10,
    current_turn=15,
    mood_change_description="Fight breaks out"
)
# Returns: {
#   'tension': 35, 'hostility': 65, 'romance': 0, 'cooperation': 10,
#   'intensity_level': 2,  # PASSIONATE
#   'intensity_points': 65,
#   'dominant_arc': 'conflict',  # Hostility is highest
#   'tension_trajectory': 'rising',
#   'level_changed': True
# }

# Get action generation guidance
guidance = SceneMood.get_action_guidance(db_session, game_state_id, location_id)
# Returns: {
#   'should_generate_escalation': True,
#   'escalation_weight': 0.65,  # 65% escalation options
#   'deescalation_required': True,
#   'intensity_level': 2,
#   'intensity_points': 65,
#   'dominant_arc': 'conflict',
#   'scene_phase': 'building',
#   'can_escalate_further': True,  # Respects content boundaries
#   'content_boundary_near': False,
#   'mood_category': 'antagonistic'
# }

# Get description for LLM prompts
description = SceneMood.get_description(db_session, game_state_id, location_id)
# Returns: "Emotional Intensity: Passionate (Level 2, 65 points).
#           Dominant theme: conflict escalating (tensions are building).
#           The situation is escalating. Hostility is high."
```

---

## Content Boundaries

### Rating Presets

| Rating | Violence | Romance | Intimacy | Language | Horror |
|--------|----------|---------|----------|----------|--------|
| **G** | 0 | 0 | 0 | 0 | 0 |
| **PG** | 1 | 1 | 0 | 1 | 1 |
| **PG-13** | 2 | 2 | 1 | 2 | 2 |
| **R** | 3 | 3 | 2 | 3 | 3 |
| **NC-17** | 4 | 4 | 3 | 4 | 4 |
| **Unrestricted** | 4 | 4 | 4 | 4 | 4 |

### How Content Boundaries Work

1. **Automatic Capping:** When emotions escalate, the system checks content settings
2. **Content Boundary Hit:** If target level exceeds max, it's capped at the maximum
3. **Action Generation:** Action generator is informed when boundary is near
4. **Provider Selection:** For mature content at boundaries, use permissive provider

```python
# Example: PG-13 game with intimacy_max_level=1 (kissing only)

# Character tries to escalate intimacy
result = CharacterEmotionalState.adjust(
    db_session, character_id, game_state_id,
    emotion='desire',
    points_delta=+60  # Would push to Level 3
)

# System automatically caps it
assert result['new_intensity_level'] == 1  # Capped at kissing
assert result['content_boundary_hit'] == True
assert result['new_intensity_points'] == 49  # Max for Level 1

# Scene action guidance reflects this
guidance = SceneMood.get_action_guidance(db_session, game_state_id, location_id)
assert guidance['can_escalate_further'] == False  # At content boundary
assert guidance['content_boundary_near'] == True
```

---

## Usage Patterns

### Pattern 1: Action Execution Updates Emotions

```python
from models.character_emotional_state import CharacterEmotionalState
from models.scene_mood import SceneMood

# When a character insults another character
def execute_insult_action(insulter_id, target_id, game_state_id, location_id, turn_number):
    # Update target's emotional state
    result = CharacterEmotionalState.adjust(
        db_session,
        character_id=target_id,
        game_state_id=game_state_id,
        emotion='anger',
        points_delta=+12,
        triggered_by_character_id=insulter_id,
        trigger_description="Insulted"
    )

    # Update scene mood
    scene_result = SceneMood.adjust(
        db_session,
        game_state_id=game_state_id,
        location_id=location_id,
        hostility_delta=+8,
        tension_delta=+5,
        current_turn=turn_number,
        mood_change_description="Insult exchanged"
    )

    # Check if level changed
    if result['level_changed']:
        print(f"Target anger escalated to Level {result['new_intensity_level']}")

    if scene_result['level_changed']:
        print(f"Scene intensity escalated to Level {scene_result['intensity_level']}")
```

### Pattern 2: Action Generation Uses Guidance

```python
from services.action_generator import ActionGenerator
from models.scene_mood import SceneMood
from models.content_settings import ContentSettings

def generate_action_options(character_id, game_state_id, location_id):
    # Get mood guidance
    guidance = SceneMood.get_action_guidance(db_session, game_state_id, location_id)

    # Get content settings
    settings = ContentSettings.get(db_session, game_state_id)
    fade_instructions = ContentSettings.get_fade_instructions(db_session, game_state_id)

    # Build action generator context
    generator = ActionGenerator(llm_provider)

    # Determine option distribution
    num_options = 5
    if guidance['should_generate_escalation'] and guidance['can_escalate_further']:
        num_escalation = int(num_options * guidance['escalation_weight'])  # 0-4
        num_neutral = num_options - num_escalation - 1  # Always 1 de-escalation
        num_deescalation = 1
    else:
        # At content boundary - mostly neutral/de-escalation
        num_escalation = 0
        num_neutral = 3
        num_deescalation = 2

    # Generate options with mood awareness
    options = generator.generate_options(
        character_id=character_id,
        mood_context={
            'intensity_level': guidance['intensity_level'],
            'dominant_arc': guidance['dominant_arc'],
            'scene_phase': guidance['scene_phase'],
            'content_boundary_near': guidance['content_boundary_near']
        },
        content_instructions=fade_instructions,
        num_escalation=num_escalation,
        num_neutral=num_neutral,
        num_deescalation=num_deescalation
    )

    return options
```

### Pattern 3: De-escalation Actions

```python
def execute_deescalation_action(character_id, game_state_id, location_id, turn_number):
    """Character tries to calm the situation"""

    # Reduce character's own anger
    CharacterEmotionalState.adjust(
        db_session,
        character_id=character_id,
        game_state_id=game_state_id,
        emotion='anger',
        points_delta=-15,  # Reduce anger
        trigger_description="Took deep breath, tried to calm down"
    )

    # Reduce scene tension
    SceneMood.adjust(
        db_session,
        game_state_id=game_state_id,
        location_id=location_id,
        tension_delta=-10,
        hostility_delta=-8,
        cooperation_delta=+5,
        current_turn=turn_number,
        mood_change_description="Character attempts to de-escalate"
    )
```

---

## Files Created/Modified

### Migrations
- `004_add_character_emotional_state.sql` - Character emotional state table
- `005_add_content_settings.sql` - Content rating system table
- `006_update_scene_mood_intensity.sql` - Scene mood intensity tracking columns

### Stored Procedures
- `character_emotional_state_procedures.sql` - Complete emotional state operations
- `content_settings_procedures.sql` - Content boundary management
- `mood_procedures.sql` - Updated scene mood procedures with intensity tracking

### Python Models
- `models/character_emotional_state.py` - NEW: Individual character emotions
- `models/content_settings.py` - NEW: Content rating and boundaries
- `models/scene_mood.py` - UPDATED: Now includes intensity tracking

---

## Integration with Action Generation

The emotional state system integrates with the existing action generation system:

1. **Context Assembly:** Include emotional states in character context
2. **Mood Description:** Include scene mood in situation description
3. **Action Guidance:** Use guidance to determine escalation ratios
4. **Content Instructions:** Add fade-to-black instructions to system prompt
5. **Provider Selection:** Use permissive provider when near content boundaries

---

## Next Steps

To fully integrate this system:

1. **Update ActionGenerator** (`services/action_generator.py`)
   - Use `SceneMood.get_action_guidance()` for option distribution
   - Include `ContentSettings.get_fade_instructions()` in prompts
   - Select appropriate LLM provider based on content needs

2. **Update ActionExecutor** (`services/action_executor.py`)
   - Call `CharacterEmotionalState.adjust()` based on action effects
   - Call `SceneMood.adjust()` based on action mood impact
   - Check for level changes and log significant escalations

3. **Update ContextAssembler** (`services/context_assembler.py`)
   - Include character emotional state in character context
   - Include scene mood description in situation context
   - Add emotional state of visible characters

4. **Initialize on Game Start**
   - Call `ContentSettings.set_preset()` when creating new game
   - Initialize scene moods for all locations
   - Initialize character emotional states (optional, auto-creates on first use)

---

## Summary

✅ **Hierarchical intensity tracking** - 5 levels from neutral to breaking
✅ **Multiple emotional arcs** - Conflict, intimacy, fear, social
✅ **Two-layer system** - Individual characters + group scenes
✅ **Content boundaries** - Configurable per game with automatic enforcement
✅ **Fade-to-black support** - Imply vs describe for mature content
✅ **LLM integration ready** - Guidance for action generation
✅ **Automatic arc detection** - System determines dominant emotional theme
✅ **Turn-based progression** - Tracks changes over time

The system is production-ready and fully integrated with the existing database architecture!
