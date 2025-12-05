## Action Generation System Guide

## Overview

The action generation system creates distinctive action options for each character's turn using LLMs with:

### Key Features

1. **Multi-Action Sequences**: Each option can contain multiple actions in order
   - Example: think → speak → emote → think → steal

2. **Mood-Aware Generation**: Actions respond to the current emotional atmosphere
   - Escalation options when tension is rising
   - Always includes at least one de-escalation option
   - Mood tracking across locations

3. **Public/Private Actions**: Proper separation of what others can witness
   - **Private**: Thoughts, hidden actions (only the character knows)
   - **Public**: Speech, gestures, movements (others can see)

4. **Diverse Options**: Each option covers different emotional approaches
   - Cunning, aggressive, friendly, cautious, romantic, etc.

5. **Smart Selection**:
   - **AI characters**: Weighted random selection
   - **Player characters**: User chooses from options

## Architecture

### Components

```
models/action_sequence.py     # Data structures for actions/sequences
models/scene_mood.py           # Mood tracking (wraps stored procedures)
services/action_generator.py  # LLM-powered action generation
database/migrations/003_add_mood_tracking.sql  # Mood database schema
database/procedures/mood_procedures.sql        # Mood operations
```

### Flow

```
1. Character's turn starts
   ↓
2. ActionGenerationContext builds context:
   - Character identity (relevant attributes only)
   - Other characters (basic attributes)
   - Relationships
   - Current situation
   - General mood
   - Character state (mood, wounds, inventory)
   - Location description
   - Time of day
   - Working memory
   - Session summary
   - Long-term memories (optional)
   ↓
3. ActionGenerator generates 4-6 options via LLM
   - Considers mood (escalation/de-escalation mix)
   - Each option is a multi-action sequence
   - Properly marked as public/private
   ↓
4. Selection:
   - AI: ActionSelector.random_select_for_ai()
   - Player: ActionSelector.player_select(choice)
   ↓
5. Execution:
   - Execute actions in sequence order
   - Record in turn_history with sequence_number
   - Update mood based on mood_impact
   - Update relationships if needed
```

## Data Structures

### SingleAction

A single atomic action within a sequence:

```python
from models.action_sequence import SingleAction, ActionType

action = SingleAction(
    action_type=ActionType.THINK,
    description="I'm going to distract them and steal the ring",
    is_private=True,  # Only the character knows
    target_character_id="uuid-of-target",
    target_object="ring"
)
```

**Available Action Types:**
- `THINK` - Private thought
- `SPEAK` - Public dialogue
- `EMOTE` - Body language/gesture
- `INTERACT` - Interact with object/character
- `EXAMINE` - Look at something
- `MOVE` - Change location
- `ATTACK` - Combat action
- `STEAL` - Take something covertly
- `USE_ITEM` - Use inventory item
- `WAIT` - Do nothing/observe
- `HIDE` - Attempt stealth

### ActionSequence

A complete sequence of actions (one turn option):

```python
from models.action_sequence import ActionSequence, SingleAction, ActionType

sequence = ActionSequence(
    actions=[
        SingleAction(ActionType.THINK, "I'm going to steal their ring", is_private=True),
        SingleAction(ActionType.SPEAK, "What's that over there?", is_private=False),
        SingleAction(ActionType.EMOTE, "Points in distance, distracting them", is_private=False),
        SingleAction(ActionType.THINK, "They're distracted, now's my chance", is_private=True),
        SingleAction(ActionType.STEAL, "Attempts to steal the ring", is_private=False, target_object="ring")
    ],
    summary="Distract and steal the ring",
    escalates_mood=True,  # This will increase tension
    deescalates_mood=False,
    emotional_tone="cunning",
    estimated_mood_impact={'tension': +15, 'hostility': +10}
)
```

### ActionOption

A selectable option presented to player/AI:

```python
from models.action_sequence import ActionOption

option = ActionOption(
    option_id=1,  # Display number
    sequence=sequence,  # ActionSequence from above
    selection_weight=1.0  # For AI selection (higher = more likely)
)
```

### GeneratedActionOptions

Complete set of options for a turn:

```python
from models.action_sequence import GeneratedActionOptions, MoodCategory

generated = GeneratedActionOptions(
    character_id="character-uuid",
    turn_number=15,
    options=[option1, option2, option3, option4, option5],
    mood_category=MoodCategory.TENSE,
    generation_context={...}  # Full context used for generation
)
```

## Mood Tracking

### Mood Dimensions

Scene moods track four dimensions (all range -100 to +100):

1. **Tension**: General stress/pressure level
   - -100 = Very relaxed
   - 0 = Neutral
   - +100 = Extreme tension

2. **Romance**: Romantic/intimate atmosphere
   - -100 = Hostile/cold
   - 0 = Neutral
   - +100 = Very romantic

3. **Hostility**: Antagonism between characters
   - -100 = Friendly/warm
   - 0 = Neutral
   - +100 = Violent conflict

4. **Cooperation**: Willingness to work together
   - -100 = Competitive/distrustful
   - 0 = Neutral
   - +100 = Highly cooperative

### Mood Trajectory

Indicates direction mood is heading:
- `rising` - Situation is escalating
- `falling` - Situation is calming down
- `stable` - No significant change

### Using Mood System

```python
from models.scene_mood import SceneMood

# Get current mood
mood = SceneMood.get(db_session, game_state_id, location_id)

# Create/update mood
SceneMood.create_or_update(
    db_session,
    game_state_id,
    location_id,
    tension_level=30,
    hostility_level=20,
    romance_level=0,
    cooperation_level=-10,
    tension_trajectory='rising',
    last_mood_change_turn=15,
    last_mood_change_description="Character A insulted Character B"
)

# Adjust mood (add deltas)
SceneMood.adjust(
    db_session,
    game_state_id,
    location_id,
    tension_delta=+10,  # Increase tension by 10
    hostility_delta=+5,  # Increase hostility by 5
    current_turn=16,
    mood_change_description="Character B responded angrily"
)

# Get natural language description for LLM prompts
mood_desc = SceneMood.get_description(db_session, game_state_id, location_id)
# Returns: "General mood: moderately tense. The situation is escalating. There is underlying antagonism."

# Get guidance for action generation
guidance = SceneMood.get_action_guidance(db_session, game_state_id, location_id)
# Returns:
# {
#     'should_generate_escalation': True,
#     'escalation_weight': 0.67,  # 67% escalation options, 33% neutral/de-escalation
#     'deescalation_required': True,  # Always at least one
#     'mood_category': 'antagonistic'
# }
```

## Action Generation

### Basic Usage

```python
from services.action_generator import ActionGenerator, ActionSelector

# Initialize with LLM provider
generator = ActionGenerator(llm_provider=claude_provider)

# Generate options
generated_options = generator.generate_options(
    db_session=db_session,
    character=character_profile,
    game_state_id=game_state_id,
    location=location_dict,
    visible_characters=[char1, char2, char3],
    current_turn=15,
    num_options=5
)

# For AI character - random selection
if character.is_ai:
    selected_option = ActionSelector.random_select_for_ai(generated_options)

# For player character - user chooses
else:
    # Display options to user
    for option in generated_options.options:
        print(f"{option.option_id}. {option.sequence.summary}")
        print(f"   Tone: {option.sequence.emotional_tone}")
        print(f"   {option.sequence.get_full_description()}")
        print()

    # Get user input
    choice = int(input("Choose an option (1-5): "))
    selected_option = ActionSelector.player_select(generated_options, choice)
```

### Context Structure for Generation

The `ActionGenerationContext` builds context specifically for action generation:

#### Always Included (CRITICAL Priority):
1. **Character identity** (relevant attributes only via situational awareness)
   - Name
   - Emotional state
   - Current objectives/motivations
   - Relevant conditional attributes (food prefs if eating, etc.)

2. **Current situation**
   - Time of day (formatted: "Day 1, 7:00 AM (morning, sun is up)")
   - Lighting description
   - Location name and description
   - General mood description

3. **Other characters** (basic attributes only)
   - Name
   - Appearance
   - Current stance
   - Clothing

#### High Priority:
4. **Relationships** (with characters in room)
   - Trust/fear/respect levels
   - Recent interaction history

5. **Character state**
   - Current mood/status effects (intoxicated, angry, etc.)
   - Wounds and their severity
   - Inventory items

6. **Working memory** (adaptive: 5/8/10 turns based on model)
   - Recent events the character witnessed

#### Medium Priority:
7. **Session summary**
   - Compressed narrative of recent history
   - Elevated to HIGH for small models (8K)

#### Optional (if tokens available):
8. **Long-term memories**
   - Semantic search results for relevant past events

9. **Extended backstory**
   - Full character history
   - First to drop if context too large

### Escalation/De-escalation Rules

**Always Required:**
- At least ONE de-escalation option must be generated

**When Mood is Escalating:**
- Generate MORE escalation options
- Calculate ratio based on tension level:
  - Tension 25-50: ~50% escalation, ~30% neutral, ~20% de-escalation
  - Tension 50-75: ~67% escalation, ~17% neutral, ~16% de-escalation
  - Tension 75+: ~75% escalation, ~12% neutral, ~13% de-escalation

**Example Escalation Option:**
```python
ActionSequence(
    actions=[
        SingleAction(THINK, "I've had enough of their insults", is_private=True),
        SingleAction(EMOTE, "Clenches fists, face reddening", is_private=False),
        SingleAction(SPEAK, "Say that again, I dare you!", is_private=False),
    ],
    summary="Respond aggressively to provocation",
    escalates_mood=True,
    deescalates_mood=False,
    emotional_tone="aggressive",
    estimated_mood_impact={'tension': +20, 'hostility': +15}
)
```

**Example De-escalation Option:**
```python
ActionSequence(
    actions=[
        SingleAction(THINK, "This is getting out of hand, I should calm things", is_private=True),
        SingleAction(EMOTE, "Takes a deep breath and relaxes posture", is_private=False),
        SingleAction(SPEAK, "Let's all take a moment to calm down", is_private=False),
        SingleAction(EMOTE, "Offers a conciliatory smile", is_private=False),
    ],
    summary="Attempt to calm the situation",
    escalates_mood=False,
    deescalates_mood=True,
    emotional_tone="calming",
    estimated_mood_impact={'tension': -15, 'hostility': -10}
)
```

## Execution and Storage

### Recording Actions in Database

Each action in the sequence is recorded separately in `turn_history` with `sequence_number`:

```python
# For a sequence with 5 actions
for seq_num, action in enumerate(selected_option.sequence.actions):
    turn_history_create(
        game_state_id=game_state_id,
        turn_number=current_turn,
        character_id=character_id,
        sequence_number=seq_num,
        action_type=action.action_type.value,
        action_description=action.description,
        is_private=action.is_private,
        witnesses=get_witnesses_if_public(action, location),
        metadata=action.metadata
    )
```

**Result in database:**
```sql
-- Turn 15, Character A's turn
turn_number | character_id | sequence_number | action_type | description              | is_private | witnesses
------------|--------------|-----------------|-------------|--------------------------|------------|----------
15          | char_a_uuid  | 0               | think       | I'm going to steal...    | true       | []
15          | char_a_uuid  | 1               | speak       | What's that over there?  | false      | [B, C]
15          | char_a_uuid  | 2               | emote       | Points in distance       | false      | [B, C]
15          | char_a_uuid  | 3               | think       | They're distracted       | true       | []
15          | char_a_uuid  | 4               | steal       | Attempts to steal ring   | false      | [B, C]
```

### Updating Mood After Execution

```python
from models.scene_mood import SceneMood

# Get mood impact from selected option
mood_impact = selected_option.sequence.estimated_mood_impact

# Apply to scene mood
SceneMood.apply_action_impact(
    db_session,
    game_state_id,
    location_id,
    mood_impact=mood_impact,
    current_turn=current_turn,
    action_description=selected_option.sequence.summary
)
```

## Complete Turn Example

```python
from services.action_generator import ActionGenerator, ActionSelector
from models.scene_mood import SceneMood

def process_character_turn(
    db_session,
    character,
    game_state_id,
    location,
    visible_characters,
    current_turn
):
    """Process one character's turn with action generation."""

    # 1. Generate action options
    generator = ActionGenerator(llm_provider)
    generated_options = generator.generate_options(
        db_session,
        character,
        game_state_id,
        location,
        visible_characters,
        current_turn
    )

    # 2. Select option
    if character['is_ai']:
        selected = ActionSelector.random_select_for_ai(generated_options)
    else:
        # Display to player and get choice
        display_options_to_player(generated_options)
        choice = get_player_choice()
        selected = ActionSelector.player_select(generated_options, choice)

    # 3. Execute action sequence
    for seq_num, action in enumerate(selected.sequence.actions):
        # Record in database
        turn_history_create(
            game_state_id=game_state_id,
            turn_number=current_turn,
            character_id=character['character_id'],
            sequence_number=seq_num,
            action_type=action.action_type.value,
            action_description=action.description,
            is_private=action.is_private,
            witnesses=get_witnesses(action, location) if not action.is_private else []
        )

        # Apply game effects (movement, combat, etc.)
        apply_action_effects(action, character, location)

    # 4. Update mood
    SceneMood.apply_action_impact(
        db_session,
        game_state_id,
        location['location_id'],
        mood_impact=selected.sequence.estimated_mood_impact,
        current_turn=current_turn,
        action_description=selected.sequence.summary
    )

    # 5. Update relationships if needed
    if not selected.sequence.deescalates_mood:
        update_relationships_from_action(selected, character, visible_characters)

    logger.info(
        f"{character['name']} executed: {selected.sequence.summary} "
        f"(tone: {selected.sequence.emotional_tone})"
    )

    return selected
```

## Prompt Structure

### System Prompt

The system prompt defines the task and output format:

```
You are an expert at generating character action options for a dark fantasy text adventure game.

Your task is to generate distinctive action options for a character's turn. Each option should be a SEQUENCE of actions that execute in order.

Action types available:
- think: Private thought (only the character knows)
- speak: Public dialogue (others hear)
- emote: Body language/gesture (others see)
... [full list] ...

IMPORTANT RULES:
1. Generate 4-6 distinctive options covering different emotional approaches
2. Each option can contain MULTIPLE actions in sequence
3. Always include at least ONE option that de-escalates the mood/tension
4. If the mood is escalating, include more options that escalate further
5. Show internal thoughts to reveal character psychology
6. Mix public and private actions appropriately

[JSON format specification]
```

### User Prompt

The user prompt provides the full context:

```
CHARACTER: Aldric the Barkeep
Emotional state: Wary and suspicious
Current objectives: Protect his establishment, avoid trouble

TIME: Day 1, 9:30 PM (dusk, sun is setting)
The area is dimly lit as the sun sets; shadows are lengthening.

LOCATION: The Rusty Flagon Tavern
A dimly lit tavern with rough wooden tables. The air smells of ale and smoke.

MOOD: General mood: moderately tense. The situation is escalating. There is underlying antagonism.

PRESENT CHARACTERS:
- Gareth the Mercenary: Tall, scarred man in leather armor. Currently sitting aggressively at bar. Wearing travel-worn gear.
- Mira the Bard: Young woman with bright eyes. Currently watching nervously from corner. Wearing colorful performer's clothes.

RELATIONSHIPS:
- Gareth: Trust 20%, Fear 40%, Respect 30% - "Gareth has been drinking heavily and making threats"
- Mira: Trust 70%, Fear 10%, Respect 60% - "Mira is a regular, always pays on time"

CHARACTER STATE:
- Slightly anxious (worried about fight breaking out)
- No wounds
- Inventory: bar rag, keys to tavern, concealed cudgel

WORKING MEMORY (last 8 turns):
- Turn 12: Gareth ordered his fifth ale, slammed coins on bar
- Turn 13: Mira tried to play calming music, Gareth told her to shut up
- Turn 14: Gareth started insulting other patrons
- Turn 15: Aldric warned Gareth to calm down
- Turn 16: Gareth laughed and continued drinking
- Turn 17: Another patron left, looking frightened
- Turn 18: Gareth made threatening gesture toward Mira
- Turn 19: [Current turn]

--- GENERATE 5 DISTINCTIVE ACTION OPTIONS ---

The situation is ESCALATING. Generate 3 options that escalate the mood further, 1 neutral option, and 1 option that de-escalates.

Make each option DISTINCTIVE - cover different emotional approaches, objectives, and interaction styles. Remember to include internal thoughts to show character psychology.

Return a JSON array of options as specified in the system prompt.
```

## Testing

See `scripts/test_action_generation.py` for comprehensive tests and examples.

## Database Migration

Apply the mood tracking migration:

```bash
python scripts/migrate_db.py
```

Then load procedures:

```bash
python scripts/init_db.py
```

## Best Practices

1. **Always generate de-escalation options** - Players/AI need ways to calm situations

2. **Use internal thoughts liberally** - They reveal character psychology and make actions more interesting

3. **Mix action types** - Don't just have "speak" actions, combine think → emote → speak → interact

4. **Consider mood trajectory** - Escalating mood should generate more escalation options

5. **Apply mood changes** - After executing actions, update the scene mood

6. **Track witnesses properly** - Private actions should have empty witness arrays

7. **Use sequence_number** - Critical for maintaining action order in database

8. **Validate selections** - Check that player choices are valid option IDs

9. **Handle generation failures** - Always have fallback options ready

10. **Log everything** - Action generation and selection should be well-logged for debugging

## Integration with Game Loop

The action generation system integrates into the main game loop:

```python
def game_turn_loop(game_state_id, db_session):
    """Main game loop with action generation."""

    while game_is_active:
        # Get turn order
        turn_order = get_turn_order(game_state_id)
        current_turn = get_current_turn(game_state_id)

        for character in turn_order:
            location = get_character_location(character)
            visible_characters = get_characters_at_location(location)

            # GENERATE ACTION OPTIONS
            generated_options = action_generator.generate_options(
                db_session,
                character,
                game_state_id,
                location,
                visible_characters,
                current_turn
            )

            # SELECT AND EXECUTE
            selected = select_and_execute_action(
                character,
                generated_options,
                location,
                current_turn
            )

            # UPDATE WORLD STATE
            update_mood(selected)
            update_relationships(selected)
            check_wounds(character)

        # End of turn
        advance_turn_and_time(game_state_id)
```

## Future Enhancements

1. **Skill Checks**: Validate if character can perform action (e.g., stealth skill for STEAL)

2. **Item Requirements**: Check if character has required items (e.g., lockpicks for opening locks)

3. **Mood History**: Track mood changes over time for pattern analysis

4. **Character Mood Preferences**: Some characters prefer escalation, others de-escalation

5. **Location-Specific Actions**: Certain actions only available in specific locations

6. **Multi-Character Coordination**: Options that involve coordinating with allies

7. **Conditional Actions**: Actions that depend on previous actions succeeding

8. **AI Selection Strategy**: More sophisticated than pure random (consider personality, motivations)

9. **Player Feedback**: Allow players to rate generated options for LLM fine-tuning

10. **Batch Generation**: Generate options for multiple characters in parallel for performance
