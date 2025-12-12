"""
Test/Demo Script for Action Generation System

Demonstrates:
- Multi-action sequences
- Mood tracking and adjustment
- Escalation/de-escalation options
- AI random selection vs player choice
- Full turn execution

Run with: python scripts/test_action_generation.py
"""

import os
import sys
from uuid import uuid4

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.action_sequence import (
    ActionSequence, SingleAction, ActionType, ActionOption,
    GeneratedActionOptions, create_simple_action
)
from models.scene_mood import SceneMood
from services.action_generator import ActionSelector
import logging
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_action_sequence_creation():
    """Test creating multi-action sequences."""
    logger.info("\n=== Testing Action Sequence Creation ===")

    # Create a complex sequence: distract and steal
    sequence = ActionSequence(
        actions=[
            SingleAction(
                action_type=ActionType.THINK,
                description="I'm going to distract them and try to steal their ring",
                is_private=True
            ),
            SingleAction(
                action_type=ActionType.SPEAK,
                description="What's that over there? Is it an animal?",
                is_private=False
            ),
            SingleAction(
                action_type=ActionType.EMOTE,
                description="Points excitedly toward the window",
                is_private=False
            ),
            SingleAction(
                action_type=ActionType.THINK,
                description="Perfect, they're distracted. Now's my chance.",
                is_private=True
            ),
            SingleAction(
                action_type=ActionType.STEAL,
                description="Subtly reaches for the ring on their finger",
                is_private=False,
                target_object="ring"
            )
        ],
        summary="Distract and steal the ring",
        escalates_mood=True,
        deescalates_mood=False,
        emotional_tone="cunning",
        estimated_mood_impact={'tension': +15, 'hostility': +10}
    )

    logger.info(f"Created sequence: {sequence.summary}")
    logger.info(f"Emotional tone: {sequence.emotional_tone}")
    logger.info(f"Number of actions: {len(sequence.actions)}")
    logger.info(f"\nFull sequence:")
    logger.info(sequence.get_full_description())
    logger.info(f"\nPublic description (what witnesses see):")
    logger.info(sequence.get_public_description())

    # Test serialization
    sequence_dict = sequence.to_dict()
    logger.info(f"\nSerialized to dict: {json.dumps(sequence_dict, indent=2)[:300]}...")

    # Test deserialization
    restored = ActionSequence.from_dict(sequence_dict)
    assert len(restored.actions) == len(sequence.actions)
    logger.info("✓ Serialization/deserialization works")

    return sequence


def test_escalation_vs_deescalation():
    """Test creating both escalating and de-escalating options."""
    logger.info("\n=== Testing Escalation vs De-escalation ===")

    # Escalation option
    escalation = ActionSequence(
        actions=[
            SingleAction(ActionType.THINK, "I've had enough of their insults", True),
            SingleAction(ActionType.EMOTE, "Clenches fists, face reddening", False),
            SingleAction(ActionType.SPEAK, "Say that again, I dare you!", False),
            SingleAction(ActionType.EMOTE, "Steps forward menacingly", False)
        ],
        summary="Respond aggressively to provocation",
        escalates_mood=True,
        deescalates_mood=False,
        emotional_tone="aggressive",
        estimated_mood_impact={'tension': +20, 'hostility': +15}
    )

    # De-escalation option
    deescalation = ActionSequence(
        actions=[
            SingleAction(ActionType.THINK, "This is getting out of hand", True),
            SingleAction(ActionType.EMOTE, "Takes a deep breath, relaxes posture", False),
            SingleAction(ActionType.SPEAK, "Let's all take a moment to calm down", False),
            SingleAction(ActionType.EMOTE, "Offers a conciliatory smile", False)
        ],
        summary="Attempt to calm the situation",
        escalates_mood=False,
        deescalates_mood=True,
        emotional_tone="calming",
        estimated_mood_impact={'tension': -15, 'hostility': -10}
    )

    logger.info("Escalation option:")
    logger.info(f"  {escalation.summary} (tone: {escalation.emotional_tone})")
    logger.info(f"  Impact: {escalation.estimated_mood_impact}")

    logger.info("\nDe-escalation option:")
    logger.info(f"  {deescalation.summary} (tone: {deescalation.emotional_tone})")
    logger.info(f"  Impact: {deescalation.estimated_mood_impact}")

    return escalation, deescalation


def test_action_options():
    """Test creating a full set of action options."""
    logger.info("\n=== Testing Action Options ===")

    # Create 5 diverse options
    options = []

    # Option 1: Cunning theft
    options.append(ActionOption(
        option_id=1,
        sequence=ActionSequence(
            actions=[
                SingleAction(ActionType.THINK, "I need that coin purse", True),
                SingleAction(ActionType.SPEAK, "Mind if I sit here?", False),
                SingleAction(ActionType.EMOTE, "Sits down casually", False),
                SingleAction(ActionType.STEAL, "Pickpockets the purse", False)
            ],
            summary="Sit and pickpocket",
            escalates_mood=True,
            deescalates_mood=False,
            emotional_tone="cunning",
            estimated_mood_impact={'tension': +10}
        ),
        selection_weight=1.0
    ))

    # Option 2: Friendly approach
    options.append(ActionOption(
        option_id=2,
        sequence=ActionSequence(
            actions=[
                SingleAction(ActionType.THINK, "Maybe I can befriend them", True),
                SingleAction(ActionType.SPEAK, "You look like you could use a drink", False),
                SingleAction(ActionType.EMOTE, "Smiles warmly", False)
            ],
            summary="Friendly conversation",
            escalates_mood=False,
            deescalates_mood=True,
            emotional_tone="friendly",
            estimated_mood_impact={'tension': -5, 'cooperation': +10}
        ),
        selection_weight=1.2  # Higher weight = more likely for AI
    ))

    # Option 3: Aggressive intimidation
    options.append(ActionOption(
        option_id=3,
        sequence=ActionSequence(
            actions=[
                SingleAction(ActionType.THINK, "Time to show them who's boss", True),
                SingleAction(ActionType.EMOTE, "Stands up abruptly", False),
                SingleAction(ActionType.SPEAK, "I suggest you leave. Now.", False),
                SingleAction(ActionType.EMOTE, "Hand moves toward sword hilt", False)
            ],
            summary="Intimidate them into leaving",
            escalates_mood=True,
            deescalates_mood=False,
            emotional_tone="aggressive",
            estimated_mood_impact={'tension': +25, 'hostility': +20}
        ),
        selection_weight=0.8  # Lower weight = less likely for AI
    ))

    # Option 4: Observant waiting
    options.append(ActionOption(
        option_id=4,
        sequence=ActionSequence(
            actions=[
                SingleAction(ActionType.THINK, "I should wait and see what happens", True),
                SingleAction(ActionType.WAIT, "Watches carefully", False),
                SingleAction(ActionType.EXAMINE, "Studies their body language", False)
            ],
            summary="Wait and observe",
            escalates_mood=False,
            deescalates_mood=False,
            emotional_tone="cautious",
            estimated_mood_impact={}
        ),
        selection_weight=1.0
    ))

    # Option 5: Calming intervention
    options.append(ActionOption(
        option_id=5,
        sequence=ActionSequence(
            actions=[
                SingleAction(ActionType.THINK, "Someone needs to calm this down", True),
                SingleAction(ActionType.EMOTE, "Steps between the arguing parties", False),
                SingleAction(ActionType.SPEAK, "Friends, there's no need for conflict", False),
                SingleAction(ActionType.EMOTE, "Holds up hands peacefully", False)
            ],
            summary="Mediate the conflict",
            escalates_mood=False,
            deescalates_mood=True,
            emotional_tone="diplomatic",
            estimated_mood_impact={'tension': -20, 'hostility': -15, 'cooperation': +10}
        ),
        selection_weight=1.0
    ))

    # Create GeneratedActionOptions
    generated = GeneratedActionOptions(
        character_id=str(uuid4()),
        turn_number=15,
        options=options,
        mood_category='tense'
    )

    logger.info(f"Generated {len(options)} action options:")
    for opt in options:
        logger.info(f"\n{opt.option_id}. {opt.sequence.summary}")
        logger.info(f"   Tone: {opt.sequence.emotional_tone}")
        logger.info(f"   Actions: {len(opt.sequence.actions)}")
        logger.info(f"   Escalates: {opt.sequence.escalates_mood}, De-escalates: {opt.sequence.deescalates_mood}")
        logger.info(f"   Weight: {opt.selection_weight}")

    # Check for required de-escalation
    deesc_options = generated.get_deescalation_options()
    logger.info(f"\n✓ De-escalation options: {len(deesc_options)} (required: at least 1)")
    assert len(deesc_options) >= 1, "Must have at least one de-escalation option"

    # Check for escalation options
    esc_options = generated.get_escalation_options()
    logger.info(f"✓ Escalation options: {len(esc_options)}")

    return generated


def test_ai_selection():
    """Test AI random selection with weights."""
    logger.info("\n=== Testing AI Selection ===")

    # Create options with different weights
    options = [
        ActionOption(1, create_test_sequence("Aggressive"), 0.5),
        ActionOption(2, create_test_sequence("Friendly"), 1.5),  # More likely
        ActionOption(3, create_test_sequence("Cunning"), 1.0),
        ActionOption(4, create_test_sequence("Cautious"), 0.8),
    ]

    generated = GeneratedActionOptions(
        character_id=str(uuid4()),
        turn_number=1,
        options=options,
        mood_category='neutral'
    )

    # Run selection 100 times to test distribution
    selection_counts = {1: 0, 2: 0, 3: 0, 4: 0}

    for _ in range(100):
        selected = ActionSelector.random_select_for_ai(generated)
        selection_counts[selected.option_id] += 1

    logger.info("Selection distribution over 100 trials:")
    for option_id, count in sorted(selection_counts.items()):
        weight = options[option_id-1].selection_weight
        percentage = (count / 100) * 100
        logger.info(f"  Option {option_id} (weight={weight}): {count}/100 ({percentage:.1f}%)")

    # Option 2 should be selected most often (highest weight)
    assert selection_counts[2] > selection_counts[1], "Highest weight should be selected more often"
    logger.info("✓ Weighted selection works correctly")


def test_player_selection():
    """Test player selection."""
    logger.info("\n=== Testing Player Selection ===")

    options = [
        ActionOption(1, create_test_sequence("Aggressive"), 1.0),
        ActionOption(2, create_test_sequence("Friendly"), 1.0),
        ActionOption(3, create_test_sequence("Cautious"), 1.0),
    ]

    generated = GeneratedActionOptions(
        character_id=str(uuid4()),
        turn_number=1,
        options=options,
        mood_category='neutral'
    )

    # Test valid selection
    selected = ActionSelector.player_select(generated, 2)
    assert selected is not None, "Valid choice should return option"
    assert selected.option_id == 2, "Should return correct option"
    logger.info(f"✓ Valid selection (choice=2): {selected.sequence.summary}")

    # Test invalid selection
    selected = ActionSelector.player_select(generated, 99)
    assert selected is None, "Invalid choice should return None"
    logger.info("✓ Invalid selection (choice=99): returns None")


def test_mood_simulation():
    """Simulate mood changes through a sequence of actions."""
    logger.info("\n=== Simulating Mood Through Action Sequence ===")

    # Initial mood
    mood = {
        'tension': 0,
        'hostility': 0,
        'romance': 0,
        'cooperation': 10
    }

    logger.info(f"Starting mood: {mood}")

    # Sequence of actions with mood impacts
    actions_sequence = [
        ("Character A makes friendly conversation", {'tension': -5, 'cooperation': +5}),
        ("Character B responds warmly", {'tension': -5, 'cooperation': +10}),
        ("Character A accidentally insults B", {'tension': +15, 'hostility': +10, 'cooperation': -10}),
        ("Character B gets angry", {'tension': +20, 'hostility': +15}),
        ("Character A apologizes sincerely", {'tension': -10, 'hostility': -5}),
        ("Character B reluctantly accepts", {'tension': -15, 'hostility': -10, 'cooperation': +5}),
    ]

    for turn, (description, impact) in enumerate(actions_sequence, start=1):
        logger.info(f"\nTurn {turn}: {description}")
        logger.info(f"  Impact: {impact}")

        # Apply impact
        for dimension, delta in impact.items():
            mood[dimension] = max(-100, min(100, mood.get(dimension, 0) + delta))

        logger.info(f"  New mood: tension={mood['tension']}, hostility={mood['hostility']}, cooperation={mood['cooperation']}")

        # Determine trajectory
        if mood['tension'] > 30:
            trajectory = "ESCALATING"
        elif mood['tension'] < -10:
            trajectory = "CALMING"
        else:
            trajectory = "stable"

        logger.info(f"  Trajectory: {trajectory}")

    logger.info(f"\nFinal mood: {mood}")


def create_test_sequence(tone: str) -> ActionSequence:
    """Helper to create a simple test sequence."""
    return ActionSequence(
        actions=[
            SingleAction(ActionType.THINK, f"I'll be {tone.lower()}", True),
            SingleAction(ActionType.SPEAK, f"{tone} words", False)
        ],
        summary=f"{tone} approach",
        escalates_mood=False,
        deescalates_mood=False,
        emotional_tone=tone.lower()
    )


def demonstrate_full_turn():
    """Demonstrate a complete turn with action generation and execution."""
    logger.info("\n=== Demonstrating Full Turn ===")

    character_name = "Aldric the Barkeep"
    location_name = "The Rusty Flagon"
    turn_number = 19

    logger.info(f"\n--- Turn {turn_number}: {character_name} at {location_name} ---")

    # Simulate generated options (in real game, would come from LLM)
    options = []

    # Option 1: Escalate - confront the troublemaker
    options.append(ActionOption(
        option_id=1,
        sequence=ActionSequence(
            actions=[
                SingleAction(ActionType.THINK, "Gareth is going to cause a fight. I need to act.", True),
                SingleAction(ActionType.EMOTE, "Reaches under bar for cudgel", False),
                SingleAction(ActionType.SPEAK, "Gareth, I'm asking you once more. Leave. Now.", False),
                SingleAction(ActionType.EMOTE, "Steps around bar, cudgel visible", False)
            ],
            summary="Confront Gareth with force",
            escalates_mood=True,
            deescalates_mood=False,
            emotional_tone="confrontational",
            estimated_mood_impact={'tension': +30, 'hostility': +25}
        ),
        selection_weight=0.8
    ))

    # Option 2: De-escalate - offer free drink
    options.append(ActionOption(
        option_id=2,
        sequence=ActionSequence(
            actions=[
                SingleAction(ActionType.THINK, "Maybe I can calm him with generosity", True),
                SingleAction(ActionType.SPEAK, "Gareth, friend, how about a drink on the house?", False),
                SingleAction(ActionType.EMOTE, "Pours a fresh ale and slides it over", False),
                SingleAction(ActionType.SPEAK, "Let's all enjoy the evening in peace", False)
            ],
            summary="Offer free drink to calm situation",
            escalates_mood=False,
            deescalates_mood=True,
            emotional_tone="conciliatory",
            estimated_mood_impact={'tension': -15, 'hostility': -10}
        ),
        selection_weight=1.2
    ))

    # Option 3: Neutral - call for help
    options.append(ActionOption(
        option_id=3,
        sequence=ActionSequence(
            actions=[
                SingleAction(ActionType.THINK, "I need backup for this", True),
                SingleAction(ActionType.EMOTE, "Catches eye of bouncer near door", False),
                SingleAction(ActionType.EMOTE, "Subtly gestures toward Gareth", False),
                SingleAction(ActionType.WAIT, "Waits for bouncer to approach", False)
            ],
            summary="Signal bouncer for help",
            escalates_mood=False,
            deescalates_mood=False,
            emotional_tone="tactical",
            estimated_mood_impact={'tension': +5}
        ),
        selection_weight=1.0
    ))

    generated = GeneratedActionOptions(
        character_id=str(uuid4()),
        turn_number=turn_number,
        options=options,
        mood_category='antagonistic'
    )

    # Display options
    logger.info("\nGenerated Action Options:")
    for opt in generated.options:
        logger.info(f"\n{opt.option_id}. {opt.sequence.summary}")
        logger.info(f"   Tone: {opt.sequence.emotional_tone}")
        logger.info(f"   Actions:")
        for action in opt.sequence.actions:
            privacy = "(private)" if action.is_private else ""
            logger.info(f"     - [{action.action_type.value}] {privacy} {action.description}")
        logger.info(f"   Mood impact: {opt.sequence.estimated_mood_impact}")

    # AI selects option
    selected = ActionSelector.random_select_for_ai(generated)

    logger.info(f"\n{character_name} chose: {selected.sequence.summary}")
    logger.info(f"Emotional tone: {selected.sequence.emotional_tone}")

    # "Execute" actions
    logger.info("\nExecuting action sequence:")
    for seq_num, action in enumerate(selected.sequence.actions):
        visibility = "🔒 PRIVATE" if action.is_private else "👁 PUBLIC"
        logger.info(f"  {seq_num}. {visibility} [{action.action_type.value}] {action.description}")

    # Update mood
    logger.info(f"\nMood impact: {selected.sequence.estimated_mood_impact}")
    logger.info("✓ Turn complete")


def main():
    """Run all tests and demonstrations."""
    logger.info("=" * 70)
    logger.info("ACTION GENERATION SYSTEM TEST SUITE")
    logger.info("=" * 70)

    try:
        # Basic tests
        test_action_sequence_creation()
        test_escalation_vs_deescalation()
        test_action_options()

        # Selection tests
        test_ai_selection()
        test_player_selection()

        # Simulation
        test_mood_simulation()

        # Full demonstration
        demonstrate_full_turn()

        logger.info("\n" + "=" * 70)
        logger.info("✓ ALL TESTS PASSED")
        logger.info("=" * 70)

    except AssertionError as e:
        logger.error(f"\n✗ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n✗ ERROR: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
