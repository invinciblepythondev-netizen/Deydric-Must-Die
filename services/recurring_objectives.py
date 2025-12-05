"""
Recurring Objectives Service
Manages recurring character needs: sleep, hunger, hygiene, etc.
"""

from typing import List, Dict, Optional, Any
from uuid import UUID
from sqlalchemy import text
from database import db
from services.objective_manager import ObjectiveManager


class RecurringObjectiveManager:
    """
    Manages recurring objectives that represent basic character needs.
    Auto-generates and prioritizes based on character state.
    """

    def __init__(self):
        self.objective_manager = ObjectiveManager()

    # =========================================================================
    # Template Management
    # =========================================================================

    def create_template(
        self,
        name: str,
        description_template: str,
        default_priority: str = 'medium',
        recurs_every_turns: Optional[int] = None,
        recurs_daily: bool = False,
        success_criteria_template: Optional[str] = None,
        decay_after_turns: Optional[int] = None,
        metadata_template: Optional[Dict] = None,
        priority_increase_rules: Optional[Dict] = None
    ) -> UUID:
        """Create a recurring objective template."""

        result = db.session.execute(
            text("""
                INSERT INTO objective.recurring_objective_template (
                    name, description_template, success_criteria_template,
                    default_priority, recurs_every_turns, recurs_daily,
                    decay_after_turns, metadata_template, priority_increase_rules
                ) VALUES (
                    :name, :description_template, :success_criteria_template,
                    :default_priority::objective.priority_level,
                    :recurs_every_turns, :recurs_daily,
                    :decay_after_turns, :metadata_template::jsonb,
                    :priority_increase_rules::jsonb
                )
                RETURNING template_id
            """),
            {
                "name": name,
                "description_template": description_template,
                "success_criteria_template": success_criteria_template,
                "default_priority": default_priority,
                "recurs_every_turns": recurs_every_turns,
                "recurs_daily": recurs_daily,
                "decay_after_turns": decay_after_turns,
                "metadata_template": metadata_template or {},
                "priority_increase_rules": priority_increase_rules or {}
            }
        )

        template_id = result.scalar()
        db.session.commit()

        return UUID(template_id)

    def get_template_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get template by name."""

        result = db.session.execute(
            text("""
                SELECT * FROM objective.recurring_objective_template
                WHERE name = :name AND is_active = TRUE
            """),
            {"name": name}
        ).fetchone()

        if not result:
            return None

        return dict(result._mapping)

    def list_templates(self) -> List[Dict[str, Any]]:
        """List all active templates."""

        results = db.session.execute(
            text("""
                SELECT * FROM objective.recurring_objective_template
                WHERE is_active = TRUE
                ORDER BY name
            """)
        ).fetchall()

        return [dict(row._mapping) for row in results]

    # =========================================================================
    # Instance Creation
    # =========================================================================

    def create_from_template(
        self,
        template_id: UUID,
        character_id: UUID,
        game_id: UUID,
        current_turn: int
    ) -> UUID:
        """Create a recurring objective instance from a template."""

        result = db.session.execute(
            text("""
                SELECT objective.recurring_objective_create_from_template(
                    :template_id, :character_id, :game_id, :current_turn
                ) as objective_id
            """),
            {
                "template_id": str(template_id),
                "character_id": str(character_id),
                "game_id": str(game_id),
                "current_turn": current_turn
            }
        )

        objective_id = result.scalar()
        db.session.commit()

        return UUID(objective_id)

    def initialize_character_recurring_objectives(
        self,
        character_id: UUID,
        game_id: UUID,
        current_turn: int
    ) -> List[UUID]:
        """
        Initialize all standard recurring objectives for a new character.
        """

        standard_templates = ['Daily Sleep', 'Hunger', 'Hygiene', 'Social Interaction']
        created_ids = []

        for template_name in standard_templates:
            template = self.get_template_by_name(template_name)

            if template:
                obj_id = self.create_from_template(
                    template_id=UUID(template['template_id']),
                    character_id=character_id,
                    game_id=game_id,
                    current_turn=current_turn
                )
                created_ids.append(obj_id)

        return created_ids

    # =========================================================================
    # Evaluation & Auto-Prioritization
    # =========================================================================

    def evaluate_needs(
        self,
        character_id: UUID,
        character_state: Dict[str, Any],
        current_turn: int
    ) -> List[Dict[str, Any]]:
        """
        Evaluate character's current state and adjust recurring objective priorities.
        Returns list of priority changes.
        """

        recurring_objectives = self.objective_manager.list_objectives(
            character_id=character_id,
            status='active'
        )

        # Filter to recurring type
        recurring_objectives = [obj for obj in recurring_objectives if obj.get('objective_type') == 'recurring']

        priority_changes = []

        for objective in recurring_objectives:
            metadata = objective.get('metadata', {})
            template_name = metadata.get('template_name', '')

            # Check if priority should change based on character state
            new_priority = self._calculate_need_priority(
                template_name,
                character_state,
                objective,
                current_turn
            )

            if new_priority and new_priority != objective['priority']:
                priority_changes.append({
                    'objective_id': objective['objective_id'],
                    'description': objective['description'],
                    'old_priority': objective['priority'],
                    'new_priority': new_priority,
                    'reason': self._get_priority_reason(template_name, character_state)
                })

        return priority_changes

    def check_and_regenerate(
        self,
        character_id: UUID,
        game_id: UUID,
        current_turn: int
    ) -> List[UUID]:
        """
        Check if any recurring objectives should be regenerated.
        Returns list of newly created objective IDs.
        """

        # Get all recurring objective templates
        templates = self.list_templates()
        created_ids = []

        for template in templates:
            # Check if character has an active instance of this template
            existing = self._has_active_instance(
                character_id,
                template['name']
            )

            if not existing:
                # Check recurrence rules
                should_create = self._should_create_instance(
                    character_id,
                    template,
                    current_turn
                )

                if should_create:
                    obj_id = self.create_from_template(
                        template_id=UUID(template['template_id']),
                        character_id=character_id,
                        game_id=game_id,
                        current_turn=current_turn
                    )
                    created_ids.append(obj_id)

        return created_ids

    def update_sleep_progress(
        self,
        character_id: UUID,
        hours_slept: float,
        turn_number: int
    ) -> None:
        """Update progress on sleep objective."""

        # Find active sleep objective
        sleep_obj = self._find_active_recurring_objective(character_id, 'Daily Sleep')

        if not sleep_obj:
            return

        metadata = sleep_obj.get('metadata', {})
        hours_needed = metadata.get('hours_needed', 8)

        # Calculate progress
        progress_delta = hours_slept / hours_needed

        self.objective_manager.update_objective_progress(
            objective_id=UUID(sleep_obj['objective_id']),
            progress_delta=progress_delta,
            turn_number=turn_number,
            action_taken=f"Slept for {hours_slept:.1f} hours"
        )

    def update_hunger_progress(
        self,
        character_id: UUID,
        meal_quality: str,
        turn_number: int
    ) -> None:
        """Update progress on hunger objective."""

        hunger_obj = self._find_active_recurring_objective(character_id, 'Hunger')

        if not hunger_obj:
            return

        # Map meal quality to progress
        quality_map = {
            'snack': 0.2,
            'light_meal': 0.5,
            'full_meal': 1.0,
            'feast': 1.0
        }

        progress_delta = quality_map.get(meal_quality, 0.5)

        self.objective_manager.update_objective_progress(
            objective_id=UUID(hunger_obj['objective_id']),
            progress_delta=progress_delta,
            turn_number=turn_number,
            action_taken=f"Ate {meal_quality.replace('_', ' ')}"
        )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _has_active_instance(
        self,
        character_id: UUID,
        template_name: str
    ) -> bool:
        """Check if character has active instance of this template."""

        objectives = self.objective_manager.list_objectives(
            character_id=character_id,
            status='active'
        )

        for obj in objectives:
            metadata = obj.get('metadata', {})
            if metadata.get('template_name') == template_name:
                return True

        return False

    def _find_active_recurring_objective(
        self,
        character_id: UUID,
        template_name: str
    ) -> Optional[Dict[str, Any]]:
        """Find active recurring objective by template name."""

        objectives = self.objective_manager.list_objectives(
            character_id=character_id,
            status='active'
        )

        for obj in objectives:
            metadata = obj.get('metadata', {})
            if metadata.get('template_name') == template_name:
                return obj

        return None

    def _should_create_instance(
        self,
        character_id: UUID,
        template: Dict,
        current_turn: int
    ) -> bool:
        """Determine if a new instance should be created based on recurrence rules."""

        # Check if it's turn-based recurrence
        if template['recurs_every_turns']:
            # Check last instance
            # Simplified logic - in production, check last completion turn
            return True

        # Check if it's daily recurrence
        if template['recurs_daily']:
            # Check in-game time for new day
            # Placeholder logic
            return True

        return False

    def _calculate_need_priority(
        self,
        template_name: str,
        character_state: Dict[str, Any],
        objective: Dict[str, Any],
        current_turn: int
    ) -> Optional[str]:
        """
        Calculate what priority a need should have based on character state.
        Returns new priority or None if no change needed.
        """

        turns_inactive = objective.get('turns_inactive', 0)

        if template_name == 'Daily Sleep':
            fatigue = character_state.get('fatigue_level', 0)

            if fatigue >= 80:
                return 'critical'
            elif fatigue >= 60:
                return 'high'
            elif fatigue >= 40:
                return 'medium'
            else:
                return 'low'

        elif template_name == 'Hunger':
            hunger = character_state.get('hunger_level', 0)

            if hunger >= 90:
                return 'critical'
            elif hunger >= 70:
                return 'high'
            elif hunger >= 50:
                return 'medium'
            else:
                return 'low'

        elif template_name == 'Hygiene':
            # Lower priority, escalates slowly
            if turns_inactive >= 30:
                return 'medium'
            elif turns_inactive >= 50:
                return 'high'
            else:
                return 'low'

        elif template_name == 'Social Interaction':
            # Personality-dependent
            social_need = character_state.get('social_need', 50)

            if social_need >= 80:
                return 'high'
            elif social_need >= 60:
                return 'medium'
            else:
                return 'low'

        return None

    def _get_priority_reason(
        self,
        template_name: str,
        character_state: Dict[str, Any]
    ) -> str:
        """Get human-readable reason for priority change."""

        if template_name == 'Daily Sleep':
            fatigue = character_state.get('fatigue_level', 0)
            return f"Fatigue level at {fatigue}%"

        elif template_name == 'Hunger':
            hunger = character_state.get('hunger_level', 0)
            return f"Hunger level at {hunger}%"

        elif template_name == 'Hygiene':
            return "Too long since last hygiene maintenance"

        elif template_name == 'Social Interaction':
            social_need = character_state.get('social_need', 50)
            return f"Social need at {social_need}%"

        return "State evaluation"


# ============================================================================
# Template Initialization
# ============================================================================

def initialize_standard_templates() -> None:
    """
    Create standard recurring objective templates.
    Call this during database initialization.
    """

    manager = RecurringObjectiveManager()

    # Sleep template
    manager.create_template(
        name='Daily Sleep',
        description_template='Get at least 6-8 hours of sleep',
        success_criteria_template='Sleep for sufficient hours',
        default_priority='medium',
        recurs_daily=True,
        decay_after_turns=None,  # Never decays
        metadata_template={'hours_needed': 7, 'template_name': 'Daily Sleep'},
        priority_increase_rules={
            'thresholds': [
                {'fatigue_level': 60, 'new_priority': 'high'},
                {'fatigue_level': 80, 'new_priority': 'critical'}
            ]
        }
    )

    # Hunger template
    manager.create_template(
        name='Hunger',
        description_template='Find and consume food',
        success_criteria_template='Eat a meal',
        default_priority='medium',
        recurs_every_turns=15,  # Roughly every 15 turns
        decay_after_turns=None,
        metadata_template={'hunger_threshold': 70, 'template_name': 'Hunger'},
        priority_increase_rules={
            'thresholds': [
                {'hunger_level': 70, 'new_priority': 'high'},
                {'hunger_level': 90, 'new_priority': 'critical'}
            ]
        }
    )

    # Hygiene template
    manager.create_template(
        name='Hygiene',
        description_template='Maintain personal cleanliness',
        success_criteria_template='Bathe or clean oneself',
        default_priority='low',
        recurs_daily=True,
        decay_after_turns=50,  # Can forget if low priority
        metadata_template={'template_name': 'Hygiene'}
    )

    # Social interaction template
    manager.create_template(
        name='Social Interaction',
        description_template='Engage in meaningful social interaction',
        success_criteria_template='Have a conversation or social activity',
        default_priority='low',
        recurs_every_turns=10,
        decay_after_turns=30,
        metadata_template={'template_name': 'Social Interaction'}
    )

    print("Standard recurring objective templates initialized")
