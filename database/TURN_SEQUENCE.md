# Turn Sequence System

## Overview

Each character's turn can contain **multiple sequenced actions** that execute in order. This allows realistic narrative turns like: *think → speak → act*.

### Key Concepts

**Sequence Number:**
- Each action gets a `sequence_number` (0, 1, 2, ...)
- Actions execute and display in sequence order
- Allows realistic "flow" of character behavior

**Private Actions:**
- `is_private = true` → only known by the acting character
- Typically: thoughts, internal decisions, hidden actions
- `witnesses` array automatically empty
- Other characters never see these

**Public Actions:**
- `is_private = false` → can be witnessed
- `witnesses` array contains character_ids in same location
- Shown in working memory for all witnesses

---

## Example: Complex Turn

**Character A's Turn 15 (at Tavern):**

### Sequence 0: Private Thought
```sql
SELECT turn_history_create(
    p_game_state_id := 'game-uuid',
    p_turn_number := 15,
    p_character_id := 'character-a-uuid',
    p_sequence_number := 0,
    p_action_type := 'think',
    p_action_description := 'I can deceive Character B. They trust me, and I can use that.',
    p_location_id := 1, -- Tavern
    p_is_private := true, -- PRIVATE - only Character A knows
    p_significance_score := 0.8
);
```

**Witnesses:** `[]` (no one)
**Visible to:** Character A only

### Sequence 1: Public Speech
```sql
SELECT turn_history_create(
    p_game_state_id := 'game-uuid',
    p_turn_number := 15,
    p_character_id := 'character-a-uuid',
    p_sequence_number := 1,
    p_action_type := 'speak',
    p_action_description := 'Character A smiles warmly and says, "I''m glad you are here, I''d like to help you."',
    p_location_id := 1,
    p_is_private := false, -- PUBLIC
    p_action_target_character_id := 'character-b-uuid',
    p_witnesses := '["character-b-uuid", "character-c-uuid"]'::jsonb,
    p_significance_score := 0.6
);
```

**Witnesses:** `[Character B, Character C]`
**Visible to:** Character A, Character B, Character C

### Sequence 2: Physical Action
```sql
SELECT turn_history_create(
    p_game_state_id := 'game-uuid',
    p_turn_number := 15,
    p_character_id := 'character-a-uuid',
    p_sequence_number := 2,
    p_action_type := 'interact',
    p_action_description := 'Character A reaches out and gently touches Character B''s arm, a gesture of reassurance.',
    p_location_id := 1,
    p_is_private := false,
    p_action_target_character_id := 'character-b-uuid',
    p_witnesses := '["character-b-uuid", "character-c-uuid"]'::jsonb,
    p_significance_score := 0.5
);
```

**Witnesses:** `[Character B, Character C]`
**Visible to:** Character A, Character B, Character C

---

## What Each Character Sees

### Character A (actor)
**Full sequence:**
```
Turn 15, Seq 0: [PRIVATE THOUGHT] I can deceive Character B...
Turn 15, Seq 1: [SPEAK] "I'm glad you are here..."
Turn 15, Seq 2: [INTERACT] Reaches out to touch B's arm
```

### Character B (witness)
**Only public actions:**
```
Turn 15, Seq 1: Character A says "I'm glad you are here..."
Turn 15, Seq 2: Character A touches your arm
```

### Character C (witness)
**Only public actions:**
```
Turn 15, Seq 1: Character A says to B "I'm glad you are here..."
Turn 15, Seq 2: Character A touches B's arm
```

### Character D (not present)
**Nothing - was not in the location**

---

## Action Types

### Private (typically `is_private = true`)
- `think` - Internal thought/monologue
- `plan` - Mental planning
- `feel` - Internal emotional state
- `decide` - Internal decision making

### Public (typically `is_private = false`)
- `speak` - Verbal communication
- `move` - Change location
- `interact` - Physical interaction
- `attack` - Combat action
- `examine` - Look at something
- `use_item` - Use inventory item
- `wait` - Observable inaction

---

## Querying Turns

### Get Full Turn Sequence
```sql
-- All actions for Turn 15
SELECT * FROM memory.turn_history
WHERE game_state_id = 'game-uuid'
  AND turn_number = 15
  AND character_id = 'character-a-uuid'
ORDER BY sequence_number ASC;
```

### Get What a Character Witnessed
```sql
-- What did Character B see in last 10 turns?
SELECT * FROM turn_history_get_witnessed('game-uuid', 'character-b-uuid', 10);

-- Returns:
-- - Character B's own actions (including private thoughts)
-- - Public actions by others that Character B witnessed
```

### Get Working Memory (All Recent Actions)
```sql
-- Last 10 turns, all public actions
SELECT * FROM turn_history_get_working_memory('game-uuid', 10);

-- Returns all actions including private thoughts of all characters
-- Useful for omniscient narrator or debugging
```

---

## LLM Context Assembly

When generating actions for a character:

```python
def assemble_character_context(character_id, game_state_id):
    # Get what THIS character knows
    witnessed_actions = turn_history_get_witnessed(
        game_state_id,
        character_id,
        last_n_turns=10
    )

    # Filter: own actions (including private) OR public actions by others
    character_context = [
        action for action in witnessed_actions
        if action.character_id == character_id  # Own (including private)
        or not action.is_private  # Or public by others
    ]

    # Format for LLM
    context_string = ""
    for action in character_context:
        if action.is_private and action.character_id == character_id:
            context_string += f"[YOUR PRIVATE THOUGHT] {action.action_description}\n"
        else:
            context_string += f"{action.character_name}: {action.action_description}\n"

    return context_string
```

**Privacy Guarantee:**

The `turn_history_get_witnessed()` function ensures characters only see what they should know:

```sql
WHERE game_state_id = p_game_state_id
  AND (
      -- Character's own actions (including private)
      th.character_id = p_character_id
      -- OR public actions they witnessed
      OR (th.is_private = false AND th.witnesses @> to_jsonb(p_character_id::text))
  )
```

---

## Python Usage Example

```python
def execute_character_turn(character_id, turn_number):
    # 1. Assemble context (what character knows)
    context = turn_history_get_witnessed(game_id, character_id, 10)

    # 2. Generate action options via LLM
    options = llm.generate_actions(character, context)

    # 3. Character selects (player) or AI picks (NPC)
    selected = pick_action(options)

    # 4. Execute as sequence
    seq = 0

    # Private thought
    if selected.has_internal_thought:
        turn_history_create(
            game_id, turn_number, character_id,
            action_type='think',
            action_description=selected.thought,
            location_id=character.location,
            sequence_number=seq,
            is_private=True
        )
        seq += 1

    # Public speech
    if selected.has_speech:
        witnesses = get_characters_in_location(character.location)
        turn_history_create(
            game_id, turn_number, character_id,
            action_type='speak',
            action_description=selected.speech,
            location_id=character.location,
            sequence_number=seq,
            is_private=False,
            witnesses=witnesses
        )
        seq += 1

    # Physical action
    if selected.has_action:
        witnesses = get_characters_in_location(character.location)
        turn_history_create(
            game_id, turn_number, character_id,
            action_type=selected.action_type,
            action_description=selected.action,
            location_id=character.location,
            sequence_number=seq,
            is_private=False,
            witnesses=witnesses
        )
```

---

## Best Practices

### 1. Sequence Numbering
- Start at 0 for first action
- Increment by 1 for each subsequent action
- No gaps (0, 1, 2, 3... not 0, 2, 5...)

### 2. Private vs Public
- **Thoughts ALWAYS private**
- **Speech ALWAYS public**
- **Physical actions usually public**
- **Secret actions** (hiding something, pickpocketing) could be private

### 3. Witnesses Array
- Include ALL characters in same location
- For private actions, leave empty `[]`
- Don't include the acting character in their own witnesses

### 4. Significance Scores
- Private thoughts: 0.3-0.5 (less significant)
- Normal dialogue: 0.4-0.6
- Important decisions: 0.7-0.8
- Major plot events: 0.9-1.0

### 5. Action Descriptions

**Private thoughts (first-person):**
- ✅ Good: "I can deceive them..."
- ❌ Bad: "Character A thinks about deceiving..."

**Public actions (third-person):**
- ✅ Good: "Character A smiles warmly..."
- ❌ Bad: "I smile warmly..."

---

## Database Schema

### Schema Changes (Migration `001_add_turn_sequence.sql`)

Added to `memory.turn_history`:
- `sequence_number INTEGER DEFAULT 0`
- `is_private BOOLEAN DEFAULT false`
- Updated unique constraint to include sequence_number
- Added index for sequence queries

### Stored Procedures

**Updated functions:**

1. **`turn_history_create()`**
   - Accepts `sequence_number` (default 0)
   - Accepts `is_private` (default false)
   - Automatically empties witnesses for private actions

2. **`turn_history_get_working_memory()`**
   - Returns `sequence_number` and `is_private`
   - Orders by `turn_number DESC, sequence_number ASC`

3. **`turn_history_get_witnessed()`**
   - Filters: own actions OR public witnessed actions
   - Excludes private actions of other characters

---

## Migration & Application

### Apply Migration
```bash
python scripts/migrate_db.py
```

This adds:
- `sequence_number` column
- `is_private` column
- Updated constraints and indexes

### Update Procedures
```bash
python scripts/init_db.py
```

Updates stored procedures (CREATE OR REPLACE).

### Verify
```bash
python scripts/migrate_db.py --list
```

Should show `001_add_turn_sequence.sql` as applied.

---

## Benefits

1. **Chronological ordering** - All actions (including thoughts) in one table, properly sequenced
2. **Privacy control** - Built-in logic prevents characters from knowing others' private thoughts
3. **Realistic narrative** - Allows *think → speak → act* patterns
4. **Flexible** - 1-N actions per turn as needed
5. **Query efficiency** - Single query returns everything a character knows
6. **LLM-friendly** - Easy context assembly showing what character witnessed

---

## Notes

- `memory.character_thought` table is **deprecated** but remains for compatibility
- Future implementations should use `is_private=true` in turn_history
- Sequence numbers start at 0, increment by 1
- Private actions automatically have empty witnesses array
