"""
Objective Planner Service
Uses LLM to create, break down, and re-evaluate character objectives.
"""

from typing import List, Dict, Optional, Any
from uuid import UUID
import json
from services.llm_service import get_unified_llm_service
from services.objective_manager import ObjectiveManager, CognitiveTraitManager


class ObjectivePlanner:
    """
    LLM-driven objective planning and breakdown with resilient fallback.
    Generates child objectives, re-evaluates priorities, and adapts plans.

    Now uses UnifiedLLMService for automatic fallback to manual input.
    """

    def __init__(self):
        """Initialize planner with unified LLM service."""
        self.llm_service = get_unified_llm_service()
        self.objective_manager = ObjectiveManager()
        self.trait_manager = CognitiveTraitManager()

    def should_plan_this_turn(
        self,
        character_id: UUID,
        current_turn: int
    ) -> bool:
        """Determine if character should do planning this turn."""

        planning_state = self.trait_manager.get_planning_state(character_id)

        if not planning_state:
            return True  # No state yet, initialize

        # Check if it's time for periodic planning
        if planning_state['next_planning_turn'] and current_turn >= planning_state['next_planning_turn']:
            return True

        # Check if cognitive load is too high (needs to reassess)
        if planning_state['current_critical_priority_count'] > planning_state['max_active_high_priority']:
            return True

        return False

    def create_initial_objectives(
        self,
        character_id: UUID,
        game_id: UUID,
        character_profile: Dict[str, Any],
        current_turn: int
    ) -> List[UUID]:
        """
        Generate initial main objectives for a character based on their profile.
        Called during character creation.

        Uses UnifiedLLMService with automatic fallback to manual input.
        """

        planning_context = self._build_initial_objectives_context(character_profile)

        # Use unified service (with automatic fallback)
        objectives_data = self.llm_service.plan_objectives(
            character_profile=character_profile,
            planning_context=planning_context
        )
        created_ids = []

        for obj_data in objectives_data.get('objectives', []):
            objective_id = self.objective_manager.create_objective(
                character_id=character_id,
                game_id=game_id,
                description=obj_data['description'],
                objective_type='main',
                priority=obj_data.get('priority', 'medium'),
                success_criteria=obj_data.get('success_criteria'),
                source='initial',
                current_turn=current_turn,
                is_atomic=False,
                mood_impact_positive=obj_data.get('mood_impact_positive', 5),
                mood_impact_negative=obj_data.get('mood_impact_negative', -5)
            )
            created_ids.append(objective_id)

        return created_ids

    def break_down_objective(
        self,
        objective_id: UUID,
        character_id: UUID,
        game_id: UUID,
        character_profile: Dict[str, Any],
        context: Dict[str, Any],
        current_turn: int,
        max_depth: Optional[int] = None
    ) -> List[UUID]:
        """
        Break down a high-level objective into child objectives.
        """

        objective = self.objective_manager.get_objective(objective_id)

        if not objective:
            raise ValueError(f"Objective {objective_id} not found")

        # Check depth limit
        planning_state = self.trait_manager.get_planning_state(character_id)
        max_allowed_depth = max_depth or planning_state['max_objective_depth']

        if objective['depth'] >= max_allowed_depth:
            return []  # Already at max depth

        prompt = self._build_breakdown_prompt(objective, character_profile, context)

        response = self.llm.generate(
            prompt=prompt,
            system_prompt="You are a game AI that breaks down objectives into actionable steps. Always respond with valid JSON.",
            temperature=0.7
        )

        breakdown_data = json.loads(response)
        created_ids = []

        for child_data in breakdown_data.get('child_objectives', []):
            child_id = self.objective_manager.create_objective(
                character_id=character_id,
                game_id=game_id,
                description=child_data['description'],
                objective_type='child',
                priority=child_data.get('priority', objective['priority']),
                parent_objective_id=objective_id,
                success_criteria=child_data.get('success_criteria'),
                source='internal',
                current_turn=current_turn,
                is_atomic=child_data.get('is_atomic', False),
                decay_after_turns=child_data.get('decay_after_turns'),
                metadata=child_data.get('metadata', {})
            )
            created_ids.append(child_id)

        return created_ids

    def re_evaluate_objectives(
        self,
        character_id: UUID,
        game_id: UUID,
        character_profile: Dict[str, Any],
        context: Dict[str, Any],
        current_turn: int
    ) -> Dict[str, Any]:
        """
        Re-evaluate all active objectives:
        - Check completion
        - Update priorities based on mood/context
        - Identify blocked objectives
        - Suggest new objectives or breakdown
        """

        # Get current objectives
        active_objectives = self.objective_manager.list_objectives(
            character_id=character_id,
            status='active'
        )

        if not active_objectives:
            return {"changes_made": False}

        # Get planning state
        planning_state = self.trait_manager.get_planning_state(character_id)

        # Limit number of objectives to re-evaluate (based on personality)
        max_to_evaluate = min(len(active_objectives), 5)  # Cap at 5 per turn
        objectives_to_evaluate = sorted(
            active_objectives,
            key=lambda x: (self._priority_score(x['priority']), -x['created_turn'])
        )[:max_to_evaluate]

        prompt = self._build_reevaluation_prompt(
            objectives_to_evaluate,
            character_profile,
            context,
            planning_state
        )

        response = self.llm.generate(
            prompt=prompt,
            system_prompt="You are a game AI that evaluates and adjusts character objectives. Always respond with valid JSON.",
            temperature=0.7
        )

        evaluation_data = json.loads(response)
        changes = {
            "changes_made": False,
            "priority_changes": [],
            "status_changes": [],
            "new_objectives": [],
            "breakdown_suggestions": []
        }

        # Apply priority changes
        for change in evaluation_data.get('priority_changes', []):
            obj_id = UUID(change['objective_id'])
            # Update via direct SQL (procedure doesn't have priority-only update)
            # In production, add a dedicated procedure for this
            changes["priority_changes"].append(change)
            changes["changes_made"] = True

        # Apply status changes
        for change in evaluation_data.get('status_changes', []):
            obj_id = UUID(change['objective_id'])
            self.objective_manager.update_objective_status(
                obj_id,
                change['new_status'],
                current_turn if change['new_status'] == 'completed' else None
            )
            changes["status_changes"].append(change)
            changes["changes_made"] = True

        # Create new objectives suggested by evaluation
        for new_obj in evaluation_data.get('new_objectives', []):
            new_id = self.objective_manager.create_objective(
                character_id=character_id,
                game_id=game_id,
                description=new_obj['description'],
                objective_type=new_obj.get('objective_type', 'main'),
                priority=new_obj.get('priority', 'medium'),
                parent_objective_id=UUID(new_obj['parent_objective_id']) if new_obj.get('parent_objective_id') else None,
                source='internal',
                current_turn=current_turn,
                is_atomic=new_obj.get('is_atomic', False)
            )
            changes["new_objectives"].append(str(new_id))
            changes["changes_made"] = True

        # Note breakdown suggestions for later processing
        changes["breakdown_suggestions"] = evaluation_data.get('breakdown_suggestions', [])

        return changes

    def generate_objective_from_interaction(
        self,
        character_id: UUID,
        game_id: UUID,
        interaction_context: Dict[str, Any],
        current_turn: int
    ) -> Optional[UUID]:
        """
        Generate a new objective based on an interaction or event.
        E.g., "Character A asked me to fetch herbs" → new delegated objective
        """

        prompt = self._build_interaction_objective_prompt(interaction_context)

        response = self.llm.generate(
            prompt=prompt,
            system_prompt="You are a game AI that creates objectives from character interactions. Always respond with valid JSON.",
            temperature=0.7
        )

        obj_data = json.loads(response)

        if not obj_data.get('create_objective'):
            return None

        objective_id = self.objective_manager.create_objective(
            character_id=character_id,
            game_id=game_id,
            description=obj_data['description'],
            objective_type=obj_data.get('objective_type', 'delegated' if obj_data.get('delegated_from') else 'main'),
            priority=obj_data.get('priority', 'medium'),
            source='delegated' if obj_data.get('delegated_from') else 'internal',
            delegated_from_character_id=UUID(obj_data['delegated_from']) if obj_data.get('delegated_from') else None,
            current_turn=current_turn,
            is_atomic=obj_data.get('is_atomic', False),
            deadline_soft=obj_data.get('deadline_soft'),
            deadline_hard=obj_data.get('deadline_hard')
        )

        return objective_id

    # =========================================================================
    # Context Building (for UnifiedLLMService)
    # =========================================================================

    def _build_initial_objectives_context(self, character_profile: Dict) -> str:
        """Build context string for initial objectives planning."""
        return f"""Character is being initialized. Create 2-4 main objectives based on their profile and motivations."""

    # =========================================================================
    # Prompt Building (Legacy - kept for backwards compatibility)
    # =========================================================================

    def _build_initial_objectives_prompt(self, character_profile: Dict) -> str:
        """Build prompt for generating initial character objectives."""

        return f"""
Create 2-4 main objectives for this character based on their profile.

Character Profile:
- Name: {character_profile.get('name')}
- Role: {character_profile.get('role_responsibilities')}
- Personality: {character_profile.get('personality_traits')}
- Motivations (Short-term): {character_profile.get('motivations_short_term')}
- Motivations (Long-term): {character_profile.get('motivations_long_term')}
- Backstory: {character_profile.get('backstory')}

Return JSON with this structure:
{{
    "objectives": [
        {{
            "description": "Objective description",
            "priority": "high|medium|low",
            "success_criteria": "What defines completion",
            "mood_impact_positive": 5,
            "mood_impact_negative": -5
        }}
    ]
}}
"""

    def _build_breakdown_prompt(
        self,
        objective: Dict,
        character_profile: Dict,
        context: Dict
    ) -> str:
        """Build prompt for breaking down an objective."""

        return f"""
Break down this objective into 2-5 actionable child objectives.

Parent Objective: {objective['description']}
Success Criteria: {objective.get('success_criteria', 'Not specified')}

Character: {character_profile.get('name')}
Current Location: {context.get('current_location', {}).get('name')}
Current Situation: {context.get('situation_summary', 'Standard circumstances')}

Consider:
- What are the logical steps to achieve this objective?
- What obstacles might need to be overcome?
- Can any steps be completed in a single turn (atomic)?
- Should any steps have decay timers (if forgotten)?

Return JSON:
{{
    "child_objectives": [
        {{
            "description": "Child objective description",
            "priority": "high|medium|low",
            "success_criteria": "Completion criteria",
            "is_atomic": true|false,
            "decay_after_turns": null or integer,
            "metadata": {{}}
        }}
    ]
}}
"""

    def _build_reevaluation_prompt(
        self,
        objectives: List[Dict],
        character_profile: Dict,
        context: Dict,
        planning_state: Dict
    ) -> str:
        """Build prompt for re-evaluating objectives."""

        objectives_str = "\n".join([
            f"- [{obj['priority']}] {obj['description']} (ID: {obj['objective_id']}, Progress: {obj['partial_completion']*100:.0f}%)"
            for obj in objectives
        ])

        return f"""
Re-evaluate these objectives for {character_profile.get('name')}:

Current Objectives:
{objectives_str}

Character State:
- Emotional State: {character_profile.get('current_emotional_state')}
- Location: {context.get('current_location', {}).get('name')}
- Recent Events: {context.get('recent_events_summary', 'None')}

Planning Capacity:
- Max High Priority: {planning_state['max_active_high_priority']}
- Current High Priority: {planning_state['current_high_priority_count']}
- Focus Score: {planning_state['focus_score']}/10

For each objective, consider:
1. Is it still relevant given current context?
2. Should priority change based on mood/deadlines/events?
3. Is it blocked? If so, should it be marked blocked or abandoned?
4. Has it been completed?

Return JSON:
{{
    "priority_changes": [
        {{"objective_id": "uuid", "new_priority": "high|medium|low", "reason": "..."}}
    ],
    "status_changes": [
        {{"objective_id": "uuid", "new_status": "completed|blocked|abandoned", "reason": "..."}}
    ],
    "new_objectives": [
        {{"description": "...", "priority": "...", "objective_type": "main|child", "parent_objective_id": "uuid or null"}}
    ],
    "breakdown_suggestions": [
        {{"objective_id": "uuid", "reason": "Why this should be broken down"}}
    ]
}}
"""

    def _build_interaction_objective_prompt(self, interaction: Dict) -> str:
        """Build prompt for generating objective from interaction."""

        return f"""
Analyze this interaction and determine if a new objective should be created:

Interaction Type: {interaction.get('type')}
From Character: {interaction.get('from_character_name')}
Content: {interaction.get('content')}
Context: {interaction.get('context')}

Should this create a new objective? If yes, define it.

Return JSON:
{{
    "create_objective": true|false,
    "description": "Objective description" or null,
    "priority": "high|medium|low",
    "objective_type": "main|delegated",
    "delegated_from": "character_uuid" or null,
    "is_atomic": true|false,
    "deadline_soft": "ISO timestamp" or null,
    "deadline_hard": "ISO timestamp" or null
}}
"""

    @staticmethod
    def _priority_score(priority: str) -> int:
        """Convert priority to numeric score for sorting."""
        return {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}.get(priority, 0)
