# Objective System Integration Guide

This document explains how to integrate the hierarchical objective system with the existing game architecture.

## Overview

The objective system adds goal-driven decision-making to characters through:
- **Hierarchical objectives** (main → child → atomic)
- **Personality-driven planning** (cognitive traits affect capacity and behavior)
- **Recurring needs** (sleep, hunger, hygiene)
- **Delegation** (characters can give each other tasks)
- **LLM-driven planning** (objectives generated and evaluated by AI)

## Architecture Components

```
┌─────────────────────────────────────────────────────────┐
│                     Game Engine                          │
│  ┌───────────────────────────────────────────────────┐  │
│  │              Turn Loop (Modified)                  │  │
│  │  1. Determine turn order                          │  │
│  │  2. For each character:                           │  │
│  │     a. Check if planning turn → ObjectivePlanner  │  │
│  │     b. Evaluate objectives → ObjectiveEvaluator   │  │
│  │     c. Assemble context (with objectives)         │  │
│  │     d. Generate actions (objective-aware)         │  │
│  │     e. Execute action                             │  │
│  │     f. Update objective progress                  │  │
│  │  3. Post-turn: Check recurring needs              │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                  Objective Services                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Objective    │  │ Objective    │  │ Recurring    │  │
│  │ Manager      │  │ Planner      │  │ Objectives   │  │
│  │ (CRUD)       │  │ (LLM-driven) │  │ (Needs)      │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Objective    │  │ Cognitive    │  │ Context      │  │
│  │ Evaluator    │  │ Trait Mgr    │  │ Assembler    │  │
│  │ (Auto-eval)  │  │ (Capacity)   │  │ (Modified)   │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                   Database Layer                         │
│  objective.character_objective                           │
│  objective.cognitive_trait                               │
│  objective.recurring_objective_template                  │
└─────────────────────────────────────────────────────────┘
```

## Integration Points

### 1. Character Creation

When a character is created, initialize their objective system:

```python
# In services/character_service.py or similar

from services.objective_planner import ObjectivePlanner
from services.recurring_objectives import RecurringObjectiveManager
from services.objective_manager import CognitiveTraitManager

def create_character(character_data, game_id):
    # ... existing character creation code ...

    character_id = character.id

    # 1. Set cognitive traits based on personality
    trait_manager = CognitiveTraitManager()
    _assign_cognitive_traits(character_id, character_data['personality_traits'])

    # 2. Recalculate planning capacity
    trait_manager.recalculate_planning_capacity(character_id)

    # 3. Generate initial main objectives
    planner = ObjectivePlanner(llm_provider)
    planner.create_initial_objectives(
        character_id=character_id,
        game_id=game_id,
        character_profile=character_data,
        current_turn=0
    )

    # 4. Initialize recurring needs
    recurring_mgr = RecurringObjectiveManager()
    recurring_mgr.initialize_character_recurring_objectives(
        character_id=character_id,
        game_id=game_id,
        current_turn=0
    )

    return character_id

def _assign_cognitive_traits(character_id, personality_traits):
    """Map personality traits to cognitive traits."""
    trait_manager = CognitiveTraitManager()

    # Example mappings
    trait_mappings = {
        'methodical': ('Methodical Planner', 7),
        'impulsive': ('Impulsive', 8),
        'detail-oriented': ('Detail-Oriented', 7),
        'anxious': ('Anxious', 6),
        'laid-back': ('Laid-Back', 7),
        'strategic': ('Strategic Thinker', 8)
    }

    for personality_trait, (cognitive_trait_name, score) in trait_mappings.items():
        if personality_trait in personality_traits:
            # Get trait ID by name (would need a lookup function)
            # trait_id = get_cognitive_trait_id_by_name(cognitive_trait_name)
            # trait_manager.set_character_trait(character_id, trait_id, score)
            pass  # Implement actual lookup
```

### 2. Turn Loop Modification

Integrate objective evaluation and planning into the turn loop:

```python
# In services/game_engine.py

from services.objective_planner import ObjectivePlanner
from services.objective_evaluator import ObjectiveEvaluator
from services.recurring_objectives import RecurringObjectiveManager

class GameEngine:
    def __init__(self):
        self.objective_planner = ObjectivePlanner(llm_provider)
        self.objective_evaluator = ObjectiveEvaluator()
        self.recurring_mgr = RecurringObjectiveManager()

    def process_turn(self, game_id, current_turn):
        """Modified turn processing with objectives."""

        # 1. Determine turn order (unchanged)
        characters_in_order = self._get_turn_order(game_id)

        # 2. For each character
        for character in characters_in_order:
            character_id = character['character_id']

            # === NEW: Objective Planning Phase ===
            self._objective_planning_phase(character_id, game_id, current_turn)

            # 3. Assemble context (now includes objectives)
            context = self._assemble_context_with_objectives(character_id, game_id)

            # 4. Generate action options (objective-aware)
            actions = self._generate_objective_aware_actions(character, context)

            # 5. Select action (AI or player)
            if character['is_player']:
                selected_action = self._wait_for_player_selection(actions)
            else:
                selected_action = self._ai_select_action(actions, context)

            # 6. Execute action
            action_result = self._execute_action(selected_action, character, game_id, current_turn)

            # === NEW: Update Objective Progress ===
            self._update_objective_progress(
                character_id,
                action_result['description'],
                current_turn,
                context
            )

        # === NEW: Post-Turn Objective Maintenance ===
        self._post_turn_objective_maintenance(game_id, current_turn)

    def _objective_planning_phase(self, character_id, game_id, current_turn):
        """Handle character's planning activities."""

        # Check if character should plan this turn
        should_plan = self.objective_planner.should_plan_this_turn(
            character_id, current_turn
        )

        if should_plan:
            character_profile = self._get_character_profile(character_id)
            context = self._get_current_context(character_id, game_id)

            # Re-evaluate existing objectives
            changes = self.objective_planner.re_evaluate_objectives(
                character_id=character_id,
                game_id=game_id,
                character_profile=character_profile,
                context=context,
                current_turn=current_turn
            )

            # Break down high-priority objectives if needed
            if changes.get('breakdown_suggestions'):
                for suggestion in changes['breakdown_suggestions']:
                    self.objective_planner.break_down_objective(
                        objective_id=UUID(suggestion['objective_id']),
                        character_id=character_id,
                        game_id=game_id,
                        character_profile=character_profile,
                        context=context,
                        current_turn=current_turn
                    )

    def _update_objective_progress(self, character_id, action_description, turn_number, context):
        """Update progress based on action taken."""

        affected = self.objective_evaluator.evaluate_turn_completion(
            character_id=character_id,
            action_description=action_description,
            turn_number=turn_number,
            context=context
        )

        # Check for completion cascades
        for obj_data in affected:
            if obj_data['new_completion'] >= 1.0:
                completed_parents = self.objective_evaluator.check_completion_cascade(
                    objective_id=UUID(obj_data['objective_id']),
                    turn_number=turn_number
                )

                # Apply mood impact
                if completed_parents:
                    mood_impact = self.objective_evaluator.calculate_mood_impact(
                        character_id=character_id,
                        completed_objective_ids=[UUID(obj_data['objective_id'])] + completed_parents,
                        failed_objective_ids=[]
                    )
                    self._apply_mood_change(character_id, mood_impact)

    def _post_turn_objective_maintenance(self, game_id, current_turn):
        """Maintenance tasks after all characters have acted."""

        characters = self._get_all_characters(game_id)

        for character in characters:
            character_id = character['character_id']

            # Check deadlines
            deadline_actions = self.objective_evaluator.check_deadlines(
                character_id=character_id,
                current_time=self._get_game_time(),
                current_turn=current_turn
            )

            # Regenerate recurring objectives if needed
            self.recurring_mgr.check_and_regenerate(
                character_id=character_id,
                game_id=game_id,
                current_turn=current_turn
            )

            # Evaluate and adjust recurring objective priorities
            character_state = self._get_character_state(character_id)
            priority_changes = self.recurring_mgr.evaluate_needs(
                character_id=character_id,
                character_state=character_state,
                current_turn=current_turn
            )

            # Apply personality-based focus decay
            abandoned = self.objective_evaluator.apply_personality_focus_decay(
                character_id=character_id,
                current_turn=current_turn
            )
```

### 3. Context Assembly Modification

Add objectives to the context provided to the LLM:

```python
# In services/context_assembler.py

class ContextAssembler:
    def assemble_action_context(self, character_id, game_id):
        """Assemble context including objectives."""

        # ... existing context assembly ...

        # Add objectives
        objectives_context = self._assemble_objectives_context(character_id)

        context.update({
            'objectives': objectives_context
        })

        return context

    def _assemble_objectives_context(self, character_id):
        """Build objectives section for LLM context."""

        from services.objective_manager import ObjectiveManager

        obj_mgr = ObjectiveManager()

        # Get active objectives sorted by priority
        active_objectives = obj_mgr.list_objectives(
            character_id=character_id,
            status='active'
        )

        # Organize by type
        main_objectives = [obj for obj in active_objectives if obj['objective_type'] == 'main']
        recurring_objectives = [obj for obj in active_objectives if obj['objective_type'] == 'recurring']
        delegated_objectives = [obj for obj in active_objectives if obj['objective_type'] == 'delegated']

        # Get highest-priority atomic objective (immediate actionable)
        atomic_objectives = [obj for obj in active_objectives if obj['is_atomic']]
        atomic_objectives.sort(key=lambda x: self._priority_score(x['priority']), reverse=True)
        next_atomic = atomic_objectives[0] if atomic_objectives else None

        return {
            'main_objectives': self._format_objectives(main_objectives),
            'recurring_needs': self._format_objectives(recurring_objectives),
            'delegated_tasks': self._format_objectives(delegated_objectives),
            'immediate_action': self._format_objective(next_atomic) if next_atomic else None,
            'total_active_count': len(active_objectives),
            'high_priority_count': len([obj for obj in active_objectives if obj['priority'] in ['critical', 'high']])
        }

    def _format_objectives(self, objectives):
        """Format objectives for LLM consumption."""
        return [
            {
                'description': obj['description'],
                'priority': obj['priority'],
                'progress': f"{obj['partial_completion']*100:.0f}%",
                'success_criteria': obj.get('success_criteria')
            }
            for obj in objectives
        ]

    def _format_objective(self, objective):
        """Format single objective."""
        if not objective:
            return None

        return {
            'description': objective['description'],
            'priority': objective['priority'],
            'success_criteria': objective.get('success_criteria'),
            'can_complete_now': objective['is_atomic']
        }

    @staticmethod
    def _priority_score(priority):
        return {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}.get(priority, 0)
```

### 4. Action Generation Modification

Modify action generation to be objective-aware:

```python
# In services/action_generator.py

class ActionGenerator:
    def generate_actions(self, character, context):
        """Generate action options considering objectives."""

        # Build objective-aware prompt
        prompt = self._build_objective_aware_prompt(character, context)

        # Generate actions via LLM
        response = self.llm.generate(
            system_prompt=self._get_system_prompt(),
            user_prompt=prompt
        )

        actions = self._parse_actions(response)

        # Annotate actions with objective relevance
        actions = self._annotate_objective_relevance(actions, context['objectives'])

        return actions

    def _build_objective_aware_prompt(self, character, context):
        """Build prompt that includes objectives."""

        objectives = context.get('objectives', {})

        prompt = f"""
Generate 4-6 action options for {character['name']}.

Current Situation:
{context['situation_summary']}

Current Objectives:
"""

        # Main objectives
        if objectives.get('main_objectives'):
            prompt += "\n**Main Objectives:**\n"
            for obj in objectives['main_objectives']:
                prompt += f"- [{obj['priority']}] {obj['description']} ({obj['progress']} complete)\n"

        # Immediate action
        if objectives.get('immediate_action'):
            immediate = objectives['immediate_action']
            prompt += f"\n**Immediate Action Available:**\n"
            prompt += f"- {immediate['description']} (can be completed this turn)\n"

        # Recurring needs
        if objectives.get('recurring_needs'):
            prompt += "\n**Current Needs:**\n"
            for need in objectives['recurring_needs']:
                prompt += f"- [{need['priority']}] {need['description']}\n"

        # Delegated tasks
        if objectives.get('delegated_tasks'):
            prompt += "\n**Tasks from Others:**\n"
            for task in objectives['delegated_tasks']:
                prompt += f"- {task['description']}\n"

        prompt += f"""

Generate actions that:
1. Advance high-priority objectives when possible
2. Address critical needs (hunger, sleep) if priority is high
3. Consider character's personality and current emotional state
4. Are realistic given current location and circumstances

Return 4-6 diverse action options, including at least one that advances an objective.
"""

        return prompt

    def _annotate_objective_relevance(self, actions, objectives_context):
        """Add metadata about which objectives each action advances."""

        # In production, use embeddings or LLM to match actions to objectives
        # Placeholder: simple keyword matching

        for action in actions:
            action['advances_objectives'] = []

            # Check if action description matches objective descriptions
            # (Simplified - use better matching in production)

        return actions
```

### 5. Delegation Handling

When a character delegates a task to another:

```python
# In action execution logic

def handle_delegation_action(delegating_character_id, target_character_id, task_description, game_id, current_turn):
    """Create a delegated objective."""

    from services.objective_manager import ObjectiveManager

    obj_mgr = ObjectiveManager()

    # Create objective for delegating character (waiting for confirmation)
    delegator_obj_id = obj_mgr.create_objective(
        character_id=delegating_character_id,
        game_id=game_id,
        description=f"Ensure {target_character_id} completes: {task_description}",
        objective_type='main',
        priority='medium',
        source='internal',
        confirmation_required=True,
        current_turn=current_turn,
        delegated_to_character_id=target_character_id
    )

    # Create objective for target character (delegated task)
    delegated_obj_id = obj_mgr.create_objective(
        character_id=target_character_id,
        game_id=game_id,
        description=task_description,
        objective_type='delegated',
        priority='medium',
        source='delegated',
        delegated_from_character_id=delegating_character_id,
        current_turn=current_turn
    )

    return delegator_obj_id, delegated_obj_id

def handle_task_completion_confirmation(delegated_obj_id, confirmation_turn):
    """When delegated task completes, notify delegator."""

    from services.objective_manager import ObjectiveManager

    obj_mgr = ObjectiveManager()

    # Mark delegated objective as waiting for confirmation
    obj_mgr.update_objective_status(delegated_obj_id, 'waiting_confirmation', confirmation_turn)

    # Get awaiting confirmation objectives for delegator
    delegated_obj = obj_mgr.get_objective(delegated_obj_id)
    delegator_id = delegated_obj['delegated_from_character_id']

    # In next turn, delegator can confirm (this could be automatic or require action)
    obj_mgr.confirm_objective(delegated_obj_id, confirmation_turn)

    # Complete delegator's tracking objective
    # (Find the objective where delegated_to_character_id matches)
```

### 6. Recurring Needs Integration

Update recurring objectives when character performs relevant actions:

```python
# In action execution logic

def handle_sleep_action(character_id, hours_slept, turn_number):
    """Update sleep objective when character sleeps."""

    from services.recurring_objectives import RecurringObjectiveManager

    recurring_mgr = RecurringObjectiveManager()
    recurring_mgr.update_sleep_progress(character_id, hours_slept, turn_number)

def handle_eat_action(character_id, meal_quality, turn_number):
    """Update hunger objective when character eats."""

    from services.recurring_objectives import RecurringObjectiveManager

    recurring_mgr = RecurringObjectiveManager()
    recurring_mgr.update_hunger_progress(character_id, meal_quality, turn_number)
```

## Database Initialization

To set up the objective system in your database:

```bash
# 1. Run the schema
python scripts/init_db.py

# 2. Run the procedures
python scripts/init_db.py  # Procedures are included in init_db

# 3. Initialize standard templates (one-time setup)
python -c "from services.recurring_objectives import initialize_standard_templates; initialize_standard_templates()"
```

## Testing the System

Test the objective system integration:

```python
# tests/test_objective_integration.py

import pytest
from services.objective_planner import ObjectivePlanner
from services.objective_manager import ObjectiveManager

def test_character_objective_workflow(test_game_id, test_character_id):
    """Test full objective workflow."""

    obj_mgr = ObjectiveManager()
    planner = ObjectivePlanner(llm_provider)

    # 1. Create main objective
    main_obj_id = obj_mgr.create_objective(
        character_id=test_character_id,
        game_id=test_game_id,
        description="Get revenge on Lord Deydric",
        objective_type='main',
        priority='high',
        current_turn=0
    )

    # 2. Break it down
    child_ids = planner.break_down_objective(
        objective_id=main_obj_id,
        character_id=test_character_id,
        game_id=test_game_id,
        character_profile=get_test_profile(),
        context=get_test_context(),
        current_turn=1
    )

    assert len(child_ids) > 0

    # 3. Complete child objective
    obj_mgr.update_objective_progress(
        objective_id=child_ids[0],
        progress_delta=1.0,
        turn_number=5,
        action_taken="Completed child task"
    )

    # 4. Verify child is completed
    child_obj = obj_mgr.get_objective(child_ids[0])
    assert child_obj['status'] == 'completed'
```

## Performance Considerations

1. **Limit planning frequency**: Don't re-evaluate all objectives every turn
   - Use `planning_frequency_turns` from cognitive state
   - Only plan when needed (cognitive overload, approaching deadline, etc.)

2. **Limit LLM calls**:
   - Batch objective evaluations (5-10 objectives per LLM call)
   - Use caching for similar contexts
   - Use cheaper models (Haiku) for simple evaluations

3. **Index queries**:
   - Database indexes already created in schema
   - Query active objectives efficiently with composite indexes

4. **Prune old objectives**:
   - Regularly delete very old completed/abandoned objectives
   - Keep only last N turns of objective history

## Configuration Options

Add to `config.py`:

```python
# Objective System Configuration
OBJECTIVE_SYSTEM_ENABLED = True
OBJECTIVE_MAX_DEPTH = 5  # Maximum objective hierarchy depth
OBJECTIVE_PLANNING_FREQUENCY = 5  # Re-evaluate every N turns by default
OBJECTIVE_AUTO_PRUNE_DAYS = 30  # Delete objectives older than N days
OBJECTIVE_LLM_MODEL = 'haiku'  # Model for objective planning (haiku/sonnet)
```

## Next Steps

1. **Initialize database**: Run schema and procedures
2. **Create seed data**: Initialize cognitive traits and recurring templates
3. **Modify game engine**: Integrate turn loop changes
4. **Update context assembly**: Add objectives to prompts
5. **Test**: Run integration tests
6. **Monitor**: Track LLM costs and performance

## Troubleshooting

**Issue**: Character has too many objectives, planning is slow
- **Solution**: Adjust cognitive traits to lower planning capacity
- **Solution**: Increase decay rates on low-priority objectives

**Issue**: Objectives never complete
- **Solution**: Check `is_atomic` flag and completion criteria
- **Solution**: Verify progress tracking logic is being called

**Issue**: LLM generates unrealistic objectives
- **Solution**: Improve prompts with more context and constraints
- **Solution**: Add validation rules in objective creation

**Issue**: Delegation not working
- **Solution**: Verify both delegator and delegated objectives are created
- **Solution**: Check confirmation flow is implemented

---

For detailed schema documentation, see `database/schemas/004_objective_schema.sql`
For stored procedure reference, see `database/procedures/objective_procedures.sql`
