"""
Objective Evaluator Service
Handles automatic objective evaluation, decay, deadline checking, and completion.
"""

from typing import List, Dict, Optional, Any, Tuple
from uuid import UUID
from datetime import datetime, timedelta
from services.objective_manager import ObjectiveManager, CognitiveTraitManager


class ObjectiveEvaluator:
    """
    Evaluates objective state and applies automatic rules:
    - Deadline checking and priority elevation
    - Decay and abandonment
    - Completion propagation
    - Mood impact calculation
    """

    def __init__(self):
        self.objective_manager = ObjectiveManager()
        self.trait_manager = CognitiveTraitManager()

    def evaluate_turn_completion(
        self,
        character_id: UUID,
        action_description: str,
        turn_number: int,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Check if the character's action this turn completed or advanced any objectives.
        Returns list of affected objectives with progress deltas.
        """

        active_objectives = self.objective_manager.list_objectives(
            character_id=character_id,
            status='active'
        )

        affected = []

        for objective in active_objectives:
            # Simple keyword matching (in production, use LLM or embeddings)
            progress_delta = self._calculate_progress_delta(
                objective,
                action_description,
                context
            )

            if progress_delta > 0:
                self.objective_manager.update_objective_progress(
                    objective_id=UUID(objective['objective_id']),
                    progress_delta=progress_delta,
                    turn_number=turn_number,
                    action_taken=action_description
                )

                affected.append({
                    'objective_id': objective['objective_id'],
                    'description': objective['description'],
                    'progress_delta': progress_delta,
                    'new_completion': min(1.0, objective['partial_completion'] + progress_delta)
                })

        # Also increment inactivity for objectives that weren't advanced
        self.objective_manager.increment_inactivity(character_id, turn_number)

        return affected

    def check_deadlines(
        self,
        character_id: UUID,
        current_time: datetime,
        current_turn: int
    ) -> List[Dict[str, Any]]:
        """
        Check all objectives for approaching or missed deadlines.
        Elevate priority or mark as failed accordingly.
        """

        active_objectives = self.objective_manager.list_objectives(
            character_id=character_id,
            status='active'
        )

        deadline_actions = []

        for objective in active_objectives:
            deadline_soft = objective.get('deadline_soft')
            deadline_hard = objective.get('deadline_hard')

            # Check hard deadline (failure)
            if deadline_hard and current_time >= deadline_hard:
                self.objective_manager.update_objective_status(
                    UUID(objective['objective_id']),
                    'abandoned'
                )
                deadline_actions.append({
                    'objective_id': objective['objective_id'],
                    'action': 'failed_hard_deadline',
                    'description': objective['description']
                })
                continue

            # Check soft deadline (priority elevation)
            if deadline_soft and current_time >= deadline_soft:
                # Elevate priority if not already at max
                if objective['priority'] not in ['critical', 'high']:
                    new_priority = 'high' if objective['priority'] == 'medium' else 'medium'
                    deadline_actions.append({
                        'objective_id': objective['objective_id'],
                        'action': 'elevated_priority',
                        'old_priority': objective['priority'],
                        'new_priority': new_priority,
                        'reason': 'soft_deadline_passed'
                    })

            # Check approaching deadlines (within 5 turns or 1 hour)
            elif deadline_soft:
                time_until_deadline = (deadline_soft - current_time).total_seconds()
                if time_until_deadline < 3600 and objective['priority'] == 'low':  # 1 hour
                    deadline_actions.append({
                        'objective_id': objective['objective_id'],
                        'action': 'elevated_priority',
                        'old_priority': 'low',
                        'new_priority': 'medium',
                        'reason': 'deadline_approaching'
                    })

        return deadline_actions

    def check_completion_cascade(
        self,
        objective_id: UUID,
        turn_number: int
    ) -> List[UUID]:
        """
        When an objective completes, check if parent objective should complete too.
        Returns list of parent objective IDs that were completed.
        """

        objective = self.objective_manager.get_objective(objective_id)

        if not objective or not objective['parent_objective_id']:
            return []

        completed_parents = []

        # Check parent
        parent_id = UUID(objective['parent_objective_id'])
        parent = self.objective_manager.get_objective(parent_id)

        if parent and parent['status'] == 'active':
            # Get all children of parent
            children = self.objective_manager.list_objectives(
                character_id=UUID(parent['character_id']),
                parent_objective_id=parent_id,
                include_children=False
            )

            # Check if all children are complete
            all_complete = all(
                child['status'] == 'completed'
                for child in children
            )

            if all_complete:
                self.objective_manager.update_objective_status(
                    parent_id,
                    'completed',
                    turn_number
                )
                completed_parents.append(parent_id)

                # Recursively check grandparent
                grandparents = self.check_completion_cascade(parent_id, turn_number)
                completed_parents.extend(grandparents)

        return completed_parents

    def calculate_mood_impact(
        self,
        character_id: UUID,
        completed_objective_ids: List[UUID],
        failed_objective_ids: List[UUID]
    ) -> int:
        """
        Calculate total mood impact from completed/failed objectives.
        Returns net mood change.
        """

        total_impact = 0

        for obj_id in completed_objective_ids:
            objective = self.objective_manager.get_objective(obj_id)
            if objective:
                total_impact += objective.get('mood_impact_positive', 0)

        for obj_id in failed_objective_ids:
            objective = self.objective_manager.get_objective(obj_id)
            if objective:
                total_impact += objective.get('mood_impact_negative', 0)

        return total_impact

    def check_blocked_objectives(
        self,
        character_id: UUID,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Check if any objectives are blocked by circumstances.
        Returns list of blocked objectives with reasons.
        """

        active_objectives = self.objective_manager.list_objectives(
            character_id=character_id,
            status='active'
        )

        blocked = []

        for objective in active_objectives:
            block_reason = self._check_if_blocked(objective, context)

            if block_reason:
                # Update status to blocked
                self.objective_manager.update_objective_status(
                    UUID(objective['objective_id']),
                    'blocked'
                )

                blocked.append({
                    'objective_id': objective['objective_id'],
                    'description': objective['description'],
                    'reason': block_reason
                })

        return blocked

    def apply_personality_focus_decay(
        self,
        character_id: UUID,
        current_turn: int
    ) -> List[UUID]:
        """
        Based on character's focus score, randomly abandon low-priority objectives
        if they have too many active. Returns abandoned objective IDs.
        """

        planning_state = self.trait_manager.get_planning_state(character_id)

        if not planning_state:
            return []

        focus_score = planning_state['focus_score']
        current_count = planning_state['current_total_objective_count']
        max_capacity = planning_state['max_active_high_priority'] * 2  # Allow some overflow

        # If under capacity, no need to abandon
        if current_count <= max_capacity:
            return []

        # Low focus = more likely to abandon
        abandon_threshold = 10 - focus_score  # 0-10 scale inverted

        # Get low-priority objectives sorted by inactivity
        low_priority_objectives = self.objective_manager.list_objectives(
            character_id=character_id,
            status='active',
            priority='low'
        )

        low_priority_objectives.sort(key=lambda x: x['turns_inactive'], reverse=True)

        abandoned = []
        objectives_to_abandon = current_count - max_capacity

        for objective in low_priority_objectives[:objectives_to_abandon]:
            # Probabilistic abandonment based on focus
            if objective['turns_inactive'] >= abandon_threshold:
                self.objective_manager.update_objective_status(
                    UUID(objective['objective_id']),
                    'abandoned'
                )
                abandoned.append(UUID(objective['objective_id']))

        return abandoned

    def get_next_atomic_objective(
        self,
        character_id: UUID,
        current_location_id: Optional[UUID] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Find the highest-priority atomic objective that can be completed this turn.
        Useful for AI character decision-making.
        """

        active_objectives = self.objective_manager.list_objectives(
            character_id=character_id,
            status='active'
        )

        # Filter to atomic objectives
        atomic_objectives = [obj for obj in active_objectives if obj['is_atomic']]

        if not atomic_objectives:
            return None

        # Sort by priority
        atomic_objectives.sort(
            key=lambda x: self._priority_score(x['priority']),
            reverse=True
        )

        # Return highest priority
        return atomic_objectives[0]

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _calculate_progress_delta(
        self,
        objective: Dict,
        action_description: str,
        context: Dict[str, Any]
    ) -> float:
        """
        Calculate how much progress an action made toward an objective.
        Simple keyword matching. In production, use embeddings or LLM.
        """

        # Atomic objectives complete in one action if keywords match
        if objective['is_atomic']:
            keywords = objective['description'].lower().split()
            action_lower = action_description.lower()

            if any(keyword in action_lower for keyword in keywords if len(keyword) > 3):
                return 1.0
            return 0.0

        # Non-atomic objectives use partial progress
        # This is a placeholder - should use LLM to judge progress
        return 0.0

    def _check_if_blocked(
        self,
        objective: Dict,
        context: Dict[str, Any]
    ) -> Optional[str]:
        """
        Check if an objective is blocked by current circumstances.
        Returns block reason if blocked, None otherwise.
        """

        # Example: Navigation objectives blocked if destination unreachable
        metadata = objective.get('metadata', {})

        if 'target_location_id' in metadata:
            target_location = metadata['target_location_id']
            current_location = context.get('current_location_id')

            # Check if path exists (placeholder logic)
            # In production, check actual location graph
            if not context.get('location_reachable', True):
                return f"Cannot reach location {target_location}"

        # Example: Interaction objectives blocked if character not present
        if 'target_character_id' in metadata:
            target_char = metadata['target_character_id']
            visible_characters = context.get('visible_character_ids', [])

            if target_char not in visible_characters:
                return f"Target character not present"

        return None

    @staticmethod
    def _priority_score(priority: str) -> int:
        """Convert priority to numeric score."""
        return {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}.get(priority, 0)
