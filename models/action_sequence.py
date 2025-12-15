"""
Action Sequence Models

Represents multi-action sequences where a single turn option can contain:
- Multiple actions (think → speak → act → think → steal)
- Each action has a type, description, and privacy level
- Actions execute in order
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
import json


class ActionType(Enum):
    """Types of actions a character can take"""
    THINK = "think"              # Private thought
    SPEAK = "speak"              # Public dialogue
    MOVE = "move"                # Change location
    INTERACT = "interact"        # Interact with object/character
    ATTACK = "attack"            # Combat action
    USE_ITEM = "use_item"        # Use inventory item
    EXAMINE = "examine"          # Look at something
    WAIT = "wait"                # Do nothing/observe
    EMOTE = "emote"              # Body language/gesture
    HIDE = "hide"                # Attempt stealth
    STEAL = "steal"              # Take something covertly


# DEPRECATED: MoodCategory enum removed in favor of dynamic LLM-generated mood strings
# Keeping this for reference of common mood types, but mood_category is now a free-form string
# Examples: "neutral", "tense", "romantic", "hostile", "conflicted", "playful", "melancholic", etc.
#
# class MoodCategory(Enum):
#     """Mood categories for action generation"""
#     NEUTRAL = "neutral"
#     TENSE = "tense"
#     RELAXED = "relaxed"
#     ANTAGONISTIC = "antagonistic"
#     VIOLENT = "violent"
#     ROMANTIC = "romantic"
#     FLIRTATIOUS = "flirtatious"
#     COOPERATIVE = "cooperative"


@dataclass
class SingleAction:
    """
    A single action within a sequence.

    Example: "Character A thinks 'I am going to distract them'"
    """
    action_type: ActionType
    description: str
    is_private: bool  # If True, only the character knows
    target_character_id: Optional[str] = None  # Who/what is targeted
    target_object: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'action_type': self.action_type.value,
            'description': self.description,
            'is_private': self.is_private,
            'target_character_id': self.target_character_id,
            'target_object': self.target_object,
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SingleAction':
        """Create from dictionary."""
        return cls(
            action_type=ActionType(data['action_type']),
            description=data['description'],
            is_private=data['is_private'],
            target_character_id=data.get('target_character_id'),
            target_object=data.get('target_object'),
            metadata=data.get('metadata', {})
        )


@dataclass
class ActionSequence:
    """
    A complete action sequence (one turn option).

    Example sequence:
    1. think: "I am going to distract them and try to steal their ring"
    2. speak: "What's that over there, is it an animal?"
    3. emote: "Character A looks for the ring on Character B's finger"
    4. think: "They are distracted, I can steal the ring"
    5. steal: "Attempts to steal the ring"
    """
    actions: List[SingleAction]
    summary: str  # Short description of overall sequence
    escalates_mood: bool  # Does this escalate tension?
    deescalates_mood: bool  # Does this de-escalate tension?
    emotional_tone: str  # e.g., "cunning", "aggressive", "friendly"
    estimated_mood_impact: Dict[str, int] = field(default_factory=dict)  # {tension: +10, hostility: +5}
    turn_duration: int = 1  # Number of turns this action takes (1 turn = ~30 seconds)
    current_stance: str = "standing"  # Character's physical position after action
    current_clothing: str = "unchanged"  # Description of clothing changes or "unchanged"
    current_emotional_state: str = "neutral"  # Character's internal emotional state after action

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'actions': [action.to_dict() for action in self.actions],
            'summary': self.summary,
            'escalates_mood': self.escalates_mood,
            'deescalates_mood': self.deescalates_mood,
            'emotional_tone': self.emotional_tone,
            'estimated_mood_impact': self.estimated_mood_impact,
            'turn_duration': self.turn_duration,
            'current_stance': self.current_stance,
            'current_clothing': self.current_clothing,
            'current_emotional_state': self.current_emotional_state
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ActionSequence':
        """Create from dictionary."""
        return cls(
            actions=[SingleAction.from_dict(a) for a in data['actions']],
            summary=data['summary'],
            escalates_mood=data['escalates_mood'],
            deescalates_mood=data['deescalates_mood'],
            emotional_tone=data['emotional_tone'],
            estimated_mood_impact=data.get('estimated_mood_impact', {}),
            turn_duration=data.get('turn_duration', 1),
            current_stance=data.get('current_stance', 'standing'),
            current_clothing=data.get('current_clothing', 'unchanged'),
            current_emotional_state=data.get('current_emotional_state', 'neutral')
        )

    def get_public_description(self) -> str:
        """Get description of public actions only (what witnesses see)."""
        public_actions = [a for a in self.actions if not a.is_private]
        if not public_actions:
            return "No visible actions"

        descriptions = [a.description for a in public_actions]
        return " → ".join(descriptions)

    def get_full_description(self) -> str:
        """Get description of all actions including private thoughts."""
        descriptions = []
        for action in self.actions:
            prefix = f"[{action.action_type.value}]"
            if action.is_private:
                prefix += " (private)"
            descriptions.append(f"{prefix} {action.description}")

        return "\n".join(descriptions)


@dataclass
class ActionOption:
    """
    A single option presented to the player/AI for selection.

    Contains the action sequence and metadata for selection.
    """
    option_id: int  # 1-based index for display
    sequence: ActionSequence
    selection_weight: float = 1.0  # For AI random selection (higher = more likely)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'option_id': self.option_id,
            'sequence': self.sequence.to_dict(),
            'selection_weight': self.selection_weight
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ActionOption':
        """Create from dictionary."""
        return cls(
            option_id=data['option_id'],
            sequence=ActionSequence.from_dict(data['sequence']),
            selection_weight=data.get('selection_weight', 1.0)
        )


@dataclass
class GeneratedActionOptions:
    """
    Complete set of action options generated for a character's turn.
    """
    character_id: str
    turn_number: int
    options: List[ActionOption]
    mood_category: str  # Dynamic LLM-generated mood (e.g., "tense", "romantic", "playful", "hostile")
    generation_context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'character_id': self.character_id,
            'turn_number': self.turn_number,
            'options': [opt.to_dict() for opt in self.options],
            'mood_category': self.mood_category,  # Already a string
            'generation_context': self.generation_context
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GeneratedActionOptions':
        """Create from dictionary."""
        return cls(
            character_id=data['character_id'],
            turn_number=data['turn_number'],
            options=[ActionOption.from_dict(opt) for opt in data['options']],
            mood_category=data.get('mood_category', 'neutral'),  # Direct string, default to 'neutral'
            generation_context=data.get('generation_context', {})
        )

    def get_option_by_id(self, option_id: int) -> Optional[ActionOption]:
        """Get option by its ID."""
        for option in self.options:
            if option.option_id == option_id:
                return option
        return None

    def get_escalation_options(self) -> List[ActionOption]:
        """Get all options that escalate mood."""
        return [opt for opt in self.options if opt.sequence.escalates_mood]

    def get_deescalation_options(self) -> List[ActionOption]:
        """Get all options that de-escalate mood."""
        return [opt for opt in self.options if opt.sequence.deescalates_mood]

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'GeneratedActionOptions':
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))


def create_simple_action(
    action_type: ActionType,
    description: str,
    is_private: bool = False
) -> SingleAction:
    """Helper to create a simple single action."""
    return SingleAction(
        action_type=action_type,
        description=description,
        is_private=is_private
    )


def create_simple_sequence(
    summary: str,
    actions: List[SingleAction],
    escalates: bool = False,
    deescalates: bool = False,
    emotional_tone: str = "neutral",
    turn_duration: int = 1,
    current_stance: str = "standing",
    current_clothing: str = "unchanged"
) -> ActionSequence:
    """Helper to create a simple action sequence."""
    return ActionSequence(
        actions=actions,
        summary=summary,
        escalates_mood=escalates,
        deescalates_mood=deescalates,
        emotional_tone=emotional_tone,
        turn_duration=turn_duration,
        current_stance=current_stance,
        current_clothing=current_clothing
    )
