# Objective System - Quick Reference

## Setup Commands (One-Time)

```bash
# 1. Apply database schema
python scripts/migrate_objectives.py

# 2. Seed cognitive traits
python scripts/seed_cognitive_traits.py

# 3. Initialize recurring templates
python scripts/init_recurring_templates.py

# 4. Test everything works
python scripts/test_objective_system.py
```

## Common Code Patterns

### Import Services

```python
from services.objective_manager import ObjectiveManager, CognitiveTraitManager
from services.objective_planner import ObjectivePlanner
from services.objective_evaluator import ObjectiveEvaluator
from services.recurring_objectives import RecurringObjectiveManager
from uuid import UUID
```

### Create an Objective

```python
obj_mgr = ObjectiveManager()

objective_id = obj_mgr.create_objective(
    character_id=character_id,  # UUID
    game_id=game_id,            # UUID
    description="Get to the tavern",
    objective_type='main',      # 'main', 'child', 'recurring', 'delegated'
    priority='medium',          # 'critical', 'high', 'medium', 'low'
    current_turn=current_turn,
    is_atomic=True              # Can be completed in one turn?
)
```

### Create Child Objective

```python
child_id = obj_mgr.create_objective(
    character_id=character_id,
    game_id=game_id,
    description="Leave current room",
    objective_type='child',
    priority='medium',
    parent_objective_id=parent_objective_id,  # UUID of parent
    current_turn=current_turn,
    is_atomic=True
)
```

### List Character's Objectives

```python
# Get all active objectives
active_objectives = obj_mgr.list_objectives(
    character_id=character_id,
    status='active'
)

# Get only high-priority objectives
high_priority = obj_mgr.list_objectives(
    character_id=character_id,
    status='active',
    priority='high'
)

# Get children of a specific objective
children = obj_mgr.list_objectives(
    character_id=character_id,
    parent_objective_id=parent_id,
    include_children=False
)
```

### Update Progress

```python
# Add progress (0.0 to 1.0)
obj_mgr.update_objective_progress(
    objective_id=objective_id,
    progress_delta=0.25,        # +25% progress
    turn_number=current_turn,
    action_taken="Walked halfway to tavern"
)

# Complete objective immediately
obj_mgr.update_objective_progress(
    objective_id=objective_id,
    progress_delta=1.0,         # 100% progress
    turn_number=current_turn,
    action_taken="Arrived at tavern"
)
# Auto-completes when progress reaches 1.0
```

### Update Status

```python
# Mark as completed
obj_mgr.update_objective_status(
    objective_id,
    'completed',
    current_turn
)

# Mark as blocked
obj_mgr.update_objective_status(
    objective_id,
    'blocked'
)

# Mark as abandoned
obj_mgr.update_objective_status(
    objective_id,
    'abandoned'
)
```

### Check Completion Cascade

```python
evaluator = ObjectiveEvaluator()

# When a child completes, check if parent should auto-complete
completed_parents = evaluator.check_completion_cascade(
    objective_id=child_objective_id,
    turn_number=current_turn
)

# Returns list of parent objective IDs that were completed
```

### Assign Cognitive Traits

```python
trait_mgr = CognitiveTraitManager()

# Assign trait to character
trait_mgr.set_character_trait(
    character_id=character_id,
    trait_id=trait_id,  # Get from database
    score=7             # 0-10 scale
)

# Recalculate planning capacity
trait_mgr.recalculate_planning_capacity(character_id)

# Get planning state
planning_state = trait_mgr.get_planning_state(character_id)
# Returns: max_active_high_priority, max_objective_depth,
#          planning_frequency_turns, focus_score, etc.
```

### Initialize Recurring Objectives

```python
recurring_mgr = RecurringObjectiveManager()

# Initialize all recurring objectives for character
created_ids = recurring_mgr.initialize_character_recurring_objectives(
    character_id=character_id,
    game_id=game_id,
    current_turn=0
)
# Creates: Daily Sleep, Hunger, Hygiene, Social Interaction
```

### Update Recurring Progress

```python
# Update sleep
recurring_mgr.update_sleep_progress(
    character_id=character_id,
    hours_slept=4.5,
    turn_number=current_turn
)

# Update hunger
recurring_mgr.update_hunger_progress(
    character_id=character_id,
    meal_quality='full_meal',  # 'snack', 'light_meal', 'full_meal', 'feast'
    turn_number=current_turn
)
```

### Delegation

```python
# Character A delegates task to Character B

# Create objective for A (tracking)
delegator_obj_id = obj_mgr.create_objective(
    character_id=character_A_id,
    game_id=game_id,
    description=f"Ensure B completes: {task_description}",
    objective_type='main',
    priority='medium',
    source='internal',
    confirmation_required=True,
    delegated_to_character_id=character_B_id,
    current_turn=current_turn
)

# Create objective for B (task)
delegated_obj_id = obj_mgr.create_objective(
    character_id=character_B_id,
    game_id=game_id,
    description=task_description,
    objective_type='delegated',
    priority='medium',
    source='delegated',
    delegated_from_character_id=character_A_id,
    current_turn=current_turn
)

# When B completes task, mark as waiting confirmation
obj_mgr.update_objective_status(
    delegated_obj_id,
    'waiting_confirmation',
    current_turn
)

# A confirms completion
obj_mgr.confirm_objective(
    delegated_obj_id,
    confirmation_turn=current_turn
)
```

## Turn Loop Integration Pattern

```python
class GameEngine:
    def __init__(self):
        self.obj_mgr = ObjectiveManager()
        self.obj_evaluator = ObjectiveEvaluator()
        self.recurring_mgr = RecurringObjectiveManager()

    def process_character_turn(self, character_id, game_id, current_turn):
        # 1. Pre-turn: Check recurring needs
        self.recurring_mgr.check_and_regenerate(
            character_id, game_id, current_turn
        )

        # 2. Get active objectives for context
        objectives = self.obj_mgr.list_objectives(
            character_id, status='active'
        )

        # 3. Generate actions (pass objectives to LLM context)
        context = self._assemble_context(character_id, objectives)
        actions = self._generate_actions(character_id, context)

        # 4. Execute selected action
        selected_action = self._select_action(actions)
        result = self._execute_action(selected_action)

        # 5. Update objective progress
        affected = self.obj_evaluator.evaluate_turn_completion(
            character_id=character_id,
            action_description=result['description'],
            turn_number=current_turn,
            context=context
        )

        # 6. Check for completion cascades
        for affected_obj in affected:
            if affected_obj['new_completion'] >= 1.0:
                self.obj_evaluator.check_completion_cascade(
                    UUID(affected_obj['objective_id']),
                    current_turn
                )

        return result
```

## Database Queries (Direct SQL if Needed)

```sql
-- Get all active objectives for a character
SELECT * FROM objective.character_objectives_list(
    'character-uuid'::uuid,
    'active'::objective.objective_status,
    NULL,
    NULL,
    TRUE
);

-- Get objective tree
SELECT * FROM objective.character_objective_tree('objective-uuid'::uuid);

-- Get planning state
SELECT * FROM objective.character_planning_state_get('character-uuid'::uuid);

-- Get character's cognitive traits
SELECT * FROM objective.character_cognitive_traits_get('character-uuid'::uuid);
```

## Cognitive Trait Reference

| Trait | Planning Capacity | Focus | Max Depth | Frequency |
|-------|------------------|-------|-----------|-----------|
| Methodical Planner | +0.5 | +1.0 | +0.3 | -0.5 (more often) |
| Impulsive | -0.3 | -1.0 | -0.2 | +1.0 (less often) |
| Detail-Oriented | 0 | +0.5 | +0.5 | -0.3 |
| Scattered | +0.2 | -1.5 | 0 | +0.5 |
| Single-Minded | -0.5 | +2.0 | +0.1 | 0 |
| Anxious | 0 | +0.2 | +0.1 | -0.8 |
| Laid-Back | 0 | -0.5 | -0.1 | +1.5 |
| Strategic Thinker | +0.8 | +0.5 | +0.4 | -1.0 |

**Modifiers are per trait score point (0-10 scale)**

Example: Character with "Methodical Planner" score 8:
- Planning capacity: +4 objectives (0.5 × 8)
- Focus: +8.0 (1.0 × 8)
- Max depth: +2.4 levels (0.3 × 8)
- Planning frequency: -4 turns (plans more frequently)

## Priority Levels

| Priority | Usage |
|----------|-------|
| **critical** | Survival, immediate danger, hard deadline passed |
| **high** | Important goals, near deadlines, high needs (90% hunger) |
| **medium** | Normal objectives, moderate needs (60% hunger) |
| **low** | Nice-to-have, background goals, low needs (30% hunger) |

## Objective Types

| Type | Description |
|------|-------------|
| **main** | Top-level character goals |
| **child** | Sub-objectives that contribute to parent |
| **recurring** | Daily/periodic needs (auto-generated) |
| **delegated** | Assigned by another character |

## Status Values

| Status | Meaning |
|--------|---------|
| **active** | Currently being pursued |
| **completed** | Successfully achieved |
| **blocked** | Cannot be completed due to obstacle |
| **abandoned** | Character gave up |
| **waiting_confirmation** | Delegated task awaiting confirmation |

## Recurring Objective Templates

| Template | Default Priority | Recurrence |
|----------|-----------------|------------|
| Daily Sleep | medium | Daily (in-game) |
| Hunger | medium | Every 15 turns |
| Hygiene | low | Daily |
| Social Interaction | low | Every 10 turns |

**Priority auto-escalates based on character state (fatigue, hunger, etc.)**

## Performance Tips

1. **Limit LLM calls**: Use planning every 5-10 turns, not every turn
2. **Batch evaluations**: Evaluate 5-10 objectives at once
3. **Use Haiku**: For all objective operations (10x cheaper)
4. **Cap active objectives**: 5-10 per character maximum
5. **Prune old data**: Delete completed objectives older than 30 days

## Troubleshooting

**"Planning capacity exceeded"**
- Character has too many objectives for their cognitive capacity
- Solution: Lower planning_capacity_modifier or abandon low-priority objectives

**"Objective depth exceeds maximum"**
- Trying to create child objective beyond max_objective_depth
- Solution: Create objective at higher level or increase max_depth trait

**"Parent objective not found"**
- Specified parent_objective_id doesn't exist
- Solution: Verify parent_objective_id is valid UUID

**"Cannot create objective in completed objective tree"**
- Trying to add child to completed parent
- Solution: Don't add children to completed objectives

## Useful Constants

```python
# Priority scores for sorting
PRIORITY_SCORES = {
    'critical': 4,
    'high': 3,
    'medium': 2,
    'low': 1
}

# Meal quality to progress mapping
MEAL_QUALITY = {
    'snack': 0.2,
    'light_meal': 0.5,
    'full_meal': 1.0,
    'feast': 1.0
}

# Default planning values
DEFAULT_PLANNING_CAPACITY = 3
DEFAULT_MAX_DEPTH = 3
DEFAULT_PLANNING_FREQUENCY = 5  # turns
DEFAULT_FOCUS_SCORE = 5.0       # 0-10 scale
```

## File Locations

- **Schema**: `database/schemas/004_objective_schema.sql`
- **Procedures**: `database/procedures/objective_procedures.sql`
- **Services**: `services/objective_*.py`
- **Scripts**: `scripts/*_objective*.py`
- **Docs**: `OBJECTIVE_SYSTEM_*.md`
