"""
Objective Manager Service
Handles CRUD operations and state management for character objectives.
"""

import json
from typing import List, Dict, Optional, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy import text
from database import db


class ObjectiveManager:
    """Manages character objectives at the data layer."""

    @staticmethod
    def create_objective(
        character_id: UUID,
        game_id: UUID,
        description: str,
        objective_type: str = 'main',
        priority: str = 'medium',
        parent_objective_id: Optional[UUID] = None,
        success_criteria: Optional[str] = None,
        source: str = 'internal',
        delegated_from_character_id: Optional[UUID] = None,
        delegated_to_character_id: Optional[UUID] = None,
        confirmation_required: bool = False,
        deadline_soft: Optional[datetime] = None,
        deadline_hard: Optional[datetime] = None,
        current_turn: int = 0,
        decay_after_turns: Optional[int] = None,
        is_atomic: bool = False,
        metadata: Optional[Dict] = None,
        mood_impact_positive: int = 0,
        mood_impact_negative: int = 0
    ) -> UUID:
        """Create a new objective for a character."""

        result = db.session.execute(
            text("""
                SELECT objective.character_objective_upsert(
                    NULL, :character_id, :game_id, :parent_objective_id,
                    CAST(:objective_type AS objective.objective_type),
                    :description, :success_criteria,
                    CAST(:priority AS objective.priority_level),
                    'active'::objective.objective_status,
                    CAST(:source AS objective.objective_source),
                    :delegated_from_character_id, :delegated_to_character_id,
                    :confirmation_required,
                    :deadline_soft, :deadline_hard, :current_turn,
                    :decay_after_turns, :is_atomic, CAST(:metadata AS jsonb),
                    :mood_impact_positive, :mood_impact_negative
                ) as objective_id
            """),
            {
                "character_id": str(character_id),
                "game_id": str(game_id),
                "parent_objective_id": str(parent_objective_id) if parent_objective_id else None,
                "objective_type": objective_type,
                "description": description,
                "success_criteria": success_criteria,
                "priority": priority,
                "source": source,
                "delegated_from_character_id": str(delegated_from_character_id) if delegated_from_character_id else None,
                "delegated_to_character_id": str(delegated_to_character_id) if delegated_to_character_id else None,
                "confirmation_required": confirmation_required,
                "deadline_soft": deadline_soft,
                "deadline_hard": deadline_hard,
                "current_turn": current_turn,
                "decay_after_turns": decay_after_turns,
                "is_atomic": is_atomic,
                "metadata": json.dumps(metadata or {}),
                "mood_impact_positive": mood_impact_positive,
                "mood_impact_negative": mood_impact_negative
            }
        )

        objective_id = result.scalar()
        db.session.commit()

        # The stored procedure already returns a UUID
        if isinstance(objective_id, UUID):
            return objective_id
        return UUID(objective_id)

    @staticmethod
    def get_objective(objective_id: UUID) -> Optional[Dict[str, Any]]:
        """Retrieve an objective by ID."""

        result = db.session.execute(
            text("SELECT * FROM objective.character_objective_get(:objective_id)"),
            {"objective_id": str(objective_id)}
        ).fetchone()

        if not result:
            return None

        return dict(result._mapping)

    @staticmethod
    def list_objectives(
        character_id: UUID,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        parent_objective_id: Optional[UUID] = None,
        include_children: bool = True
    ) -> List[Dict[str, Any]]:
        """List objectives for a character with optional filtering."""

        results = db.session.execute(
            text("""
                SELECT * FROM objective.character_objectives_list(
                    :character_id,
                    CAST(:status AS objective.objective_status),
                    CAST(:priority AS objective.priority_level),
                    :parent_objective_id,
                    :include_children
                )
            """),
            {
                "character_id": str(character_id),
                "status": status,
                "priority": priority,
                "parent_objective_id": str(parent_objective_id) if parent_objective_id else None,
                "include_children": include_children
            }
        ).fetchall()

        return [dict(row._mapping) for row in results]

    @staticmethod
    def get_objective_tree(objective_id: UUID) -> List[Dict[str, Any]]:
        """Get full hierarchical tree for an objective."""

        results = db.session.execute(
            text("SELECT * FROM objective.character_objective_tree(:objective_id)"),
            {"objective_id": str(objective_id)}
        ).fetchall()

        return [dict(row._mapping) for row in results]

    @staticmethod
    def update_objective_status(
        objective_id: UUID,
        new_status: str,
        completed_turn: Optional[int] = None
    ) -> None:
        """Update an objective's status."""

        db.session.execute(
            text("""
                SELECT objective.character_objective_update_status(
                    :objective_id,
                    CAST(:new_status AS objective.objective_status),
                    :completed_turn
                )
            """),
            {
                "objective_id": str(objective_id),
                "new_status": new_status,
                "completed_turn": completed_turn
            }
        )
        db.session.commit()

    @staticmethod
    def update_objective_progress(
        objective_id: UUID,
        progress_delta: float,
        turn_number: int,
        action_taken: Optional[str] = None,
        notes: Optional[str] = None
    ) -> None:
        """Update progress toward objective completion."""

        db.session.execute(
            text("""
                SELECT objective.character_objective_update_progress(
                    :objective_id, :progress_delta, :turn_number,
                    :action_taken, :notes
                )
            """),
            {
                "objective_id": str(objective_id),
                "progress_delta": progress_delta,
                "turn_number": turn_number,
                "action_taken": action_taken,
                "notes": notes
            }
        )
        db.session.commit()

    @staticmethod
    def increment_inactivity(character_id: UUID, current_turn: int) -> None:
        """Increment inactivity counters for all character's objectives."""

        db.session.execute(
            text("""
                SELECT objective.character_objectives_increment_inactivity(
                    :character_id, :current_turn
                )
            """),
            {
                "character_id": str(character_id),
                "current_turn": current_turn
            }
        )
        db.session.commit()

    @staticmethod
    def delete_objective(objective_id: UUID) -> None:
        """Delete an objective and all its children."""

        db.session.execute(
            text("SELECT objective.character_objective_delete(:objective_id)"),
            {"objective_id": str(objective_id)}
        )
        db.session.commit()

    @staticmethod
    def get_awaiting_confirmation(character_id: UUID) -> List[Dict[str, Any]]:
        """Get objectives awaiting confirmation from delegated characters."""

        results = db.session.execute(
            text("""
                SELECT * FROM objective.character_objectives_awaiting_confirmation(
                    :character_id
                )
            """),
            {"character_id": str(character_id)}
        ).fetchall()

        return [dict(row._mapping) for row in results]

    @staticmethod
    def confirm_objective(objective_id: UUID, confirmation_turn: int) -> None:
        """Mark a delegated objective as confirmed."""

        db.session.execute(
            text("""
                SELECT objective.character_objective_confirm(
                    :objective_id, :confirmation_turn
                )
            """),
            {
                "objective_id": str(objective_id),
                "confirmation_turn": confirmation_turn
            }
        )
        db.session.commit()


class CognitiveTraitManager:
    """Manages cognitive traits and character planning capacity."""

    @staticmethod
    def get_character_traits(character_id: UUID) -> List[Dict[str, Any]]:
        """Get all cognitive traits for a character with scores."""

        results = db.session.execute(
            text("""
                SELECT * FROM objective.character_cognitive_traits_get(:character_id)
            """),
            {"character_id": str(character_id)}
        ).fetchall()

        return [dict(row._mapping) for row in results]

    @staticmethod
    def set_character_trait(
        character_id: UUID,
        trait_id: UUID,
        score: int
    ) -> None:
        """Set a character's score for a cognitive trait."""

        db.session.execute(
            text("""
                SELECT objective.character_cognitive_trait_set(
                    :character_id, :trait_id, :score
                )
            """),
            {
                "character_id": str(character_id),
                "trait_id": str(trait_id),
                "score": score
            }
        )
        db.session.commit()

    @staticmethod
    def recalculate_planning_capacity(
        character_id: UUID,
        capacity_multiplier: float = 1.0,
        focus_multiplier: float = 1.0
    ) -> None:
        """Recalculate character's planning capacity from traits and state."""

        db.session.execute(
            text("""
                SELECT objective.character_planning_state_recalculate(
                    :character_id, :capacity_multiplier, :focus_multiplier
                )
            """),
            {
                "character_id": str(character_id),
                "capacity_multiplier": capacity_multiplier,
                "focus_multiplier": focus_multiplier
            }
        )
        db.session.commit()

    @staticmethod
    def get_planning_state(character_id: UUID) -> Optional[Dict[str, Any]]:
        """Get character's current planning state and capacity."""

        result = db.session.execute(
            text("""
                SELECT * FROM objective.character_planning_state_get(:character_id)
            """),
            {"character_id": str(character_id)}
        ).fetchone()

        if not result:
            return None

        return dict(result._mapping)

    @staticmethod
    def update_planning_counters(character_id: UUID) -> None:
        """Update objective counters in planning state."""

        db.session.execute(
            text("""
                SELECT objective.character_planning_state_update_counts(:character_id)
            """),
            {"character_id": str(character_id)}
        )
        db.session.commit()
