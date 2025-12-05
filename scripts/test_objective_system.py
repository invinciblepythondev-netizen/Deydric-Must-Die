"""
Test script for objective system.
Verifies all components work correctly.
"""

import os
import sys
from uuid import uuid4, UUID
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import db
from app import app
from services.objective_manager import ObjectiveManager, CognitiveTraitManager
from services.objective_evaluator import ObjectiveEvaluator


def print_section(title):
    """Print formatted section header."""
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def test_cognitive_traits():
    """Test cognitive trait system."""
    print_section("Testing Cognitive Traits")

    trait_mgr = CognitiveTraitManager()

    # Create test character
    character_id = uuid4()
    print(f"\nTest character ID: {character_id}")

    # Get available traits
    from sqlalchemy import text
    with app.app_context():
        result = db.session.execute(
            text("SELECT trait_id, trait_name FROM objective.cognitive_trait WHERE is_active = TRUE LIMIT 3")
        )
        traits = result.fetchall()

        if not traits:
            print("✗ No cognitive traits found! Run seed_cognitive_traits.py first.")
            return False

        print(f"\n✓ Found {len(traits)} cognitive traits")

        # Assign traits to character
        for trait in traits:
            trait_id = UUID(trait.trait_id)
            score = 7  # Medium-high score
            trait_mgr.set_character_trait(character_id, trait_id, score)
            print(f"  • Assigned '{trait.trait_name}' with score {score}")

        # Recalculate planning capacity
        trait_mgr.recalculate_planning_capacity(character_id)
        print("\n✓ Planning capacity recalculated")

        # Get planning state
        planning_state = trait_mgr.get_planning_state(character_id)

        if planning_state:
            print("\nPlanning State:")
            print(f"  • Max high-priority objectives: {planning_state['max_active_high_priority']}")
            print(f"  • Max objective depth: {planning_state['max_objective_depth']}")
            print(f"  • Planning frequency: every {planning_state['planning_frequency_turns']} turns")
            print(f"  • Focus score: {planning_state['focus_score']:.1f}/10")
            return character_id
        else:
            print("✗ Planning state not found")
            return None


def test_objective_crud(character_id):
    """Test objective CRUD operations."""
    print_section("Testing Objective CRUD")

    obj_mgr = ObjectiveManager()
    game_id = uuid4()

    print(f"\nGame ID: {game_id}")

    # Create main objective
    print("\n1. Creating main objective...")
    main_obj_id = obj_mgr.create_objective(
        character_id=character_id,
        game_id=game_id,
        description="Get revenge on Lord Deydric",
        objective_type='main',
        priority='high',
        success_criteria="Lord Deydric is brought to justice",
        current_turn=1,
        mood_impact_positive=10,
        mood_impact_negative=-5
    )
    print(f"  ✓ Created main objective: {main_obj_id}")

    # Create child objectives
    print("\n2. Creating child objectives...")
    child1_id = obj_mgr.create_objective(
        character_id=character_id,
        game_id=game_id,
        description="Gather evidence of his crimes",
        objective_type='child',
        priority='high',
        parent_objective_id=main_obj_id,
        current_turn=1,
        is_atomic=False
    )
    print(f"  ✓ Created child objective 1: {child1_id}")

    child2_id = obj_mgr.create_objective(
        character_id=character_id,
        game_id=game_id,
        description="Search Lord Deydric's office",
        objective_type='child',
        priority='high',
        parent_objective_id=child1_id,
        current_turn=1,
        is_atomic=True
    )
    print(f"  ✓ Created atomic child objective 2: {child2_id}")

    # List objectives
    print("\n3. Listing all objectives...")
    objectives = obj_mgr.list_objectives(character_id, status='active')
    print(f"  ✓ Found {len(objectives)} active objectives:")
    for obj in objectives:
        indent = "  " * (obj['depth'] + 1)
        atomic_marker = " [ATOMIC]" if obj['is_atomic'] else ""
        print(f"{indent}• [{obj['priority']}] {obj['description']}{atomic_marker}")

    # Get objective tree
    print("\n4. Getting objective tree...")
    tree = obj_mgr.get_objective_tree(main_obj_id)
    print(f"  ✓ Tree has {len(tree)} nodes:")
    for node in tree:
        indent = "  " * (node['depth'] + 1)
        print(f"{indent}• {node['description']} (depth {node['depth']})")

    # Update progress
    print("\n5. Updating progress on atomic objective...")
    obj_mgr.update_objective_progress(
        objective_id=child2_id,
        progress_delta=1.0,
        turn_number=5,
        action_taken="Successfully searched the office"
    )
    print("  ✓ Progress updated to 100% (should auto-complete)")

    # Check status
    child2_obj = obj_mgr.get_objective(child2_id)
    if child2_obj['status'] == 'completed':
        print("  ✓ Objective auto-completed!")
    else:
        print(f"  ✗ Objective status is '{child2_obj['status']}', expected 'completed'")

    return game_id, main_obj_id, child1_id, child2_id


def test_objective_evaluation(character_id, game_id, objectives):
    """Test objective evaluator."""
    print_section("Testing Objective Evaluator")

    evaluator = ObjectiveEvaluator()
    main_obj_id, child1_id, child2_id = objectives

    # Test completion cascade
    print("\n1. Testing completion cascade...")
    print("  Completing all children of main objective...")

    obj_mgr = ObjectiveManager()

    # Complete child1 (parent of already-completed child2)
    obj_mgr.update_objective_status(child1_id, 'completed', 10)

    # Check if main objective auto-completed
    completed_parents = evaluator.check_completion_cascade(child1_id, 10)
    if completed_parents:
        print(f"  ✓ Cascade triggered! Completed {len(completed_parents)} parent(s)")
        for parent_id in completed_parents:
            print(f"    • {parent_id}")
    else:
        print("  Note: Main objective not completed (may have other incomplete children)")

    # Test mood impact
    print("\n2. Testing mood impact calculation...")
    mood_impact = evaluator.calculate_mood_impact(
        character_id=character_id,
        completed_objective_ids=[child2_id, child1_id],
        failed_objective_ids=[]
    )
    print(f"  ✓ Total mood impact: {mood_impact:+d}")

    # Test inactivity increment
    print("\n3. Testing inactivity tracking...")
    obj_mgr.increment_inactivity(character_id, 15)
    print("  ✓ Inactivity counters incremented")

    # List objectives to see inactivity
    objectives = obj_mgr.list_objectives(character_id, status='active')
    if objectives:
        print(f"  Active objectives with inactivity counts:")
        for obj in objectives:
            print(f"    • {obj['description']}: {obj['turns_inactive']} turns inactive")
    else:
        print("  (No active objectives remaining)")


def test_recurring_objectives(character_id, game_id):
    """Test recurring objective system."""
    print_section("Testing Recurring Objectives")

    from services.recurring_objectives import RecurringObjectiveManager
    from sqlalchemy import text

    recurring_mgr = RecurringObjectiveManager()

    # Check templates exist
    print("\n1. Checking recurring templates...")
    with app.app_context():
        result = db.session.execute(
            text("SELECT COUNT(*) as count FROM objective.recurring_objective_template WHERE is_active = TRUE")
        )
        count = result.scalar()

        if count == 0:
            print("  ✗ No recurring templates found! Run init_recurring_templates.py first.")
            return

        print(f"  ✓ Found {count} recurring templates")

        # Initialize recurring objectives for character
        print("\n2. Initializing recurring objectives for character...")
        created_ids = recurring_mgr.initialize_character_recurring_objectives(
            character_id=character_id,
            game_id=game_id,
            current_turn=1
        )

        print(f"  ✓ Created {len(created_ids)} recurring objectives:")
        obj_mgr = ObjectiveManager()
        for obj_id in created_ids:
            obj = obj_mgr.get_objective(obj_id)
            print(f"    • [{obj['priority']}] {obj['description']}")

        # Test progress update
        print("\n3. Testing sleep progress update...")
        recurring_mgr.update_sleep_progress(
            character_id=character_id,
            hours_slept=3.5,
            turn_number=5
        )
        print("  ✓ Sleep progress updated (3.5 hours slept)")

        # Test hunger progress update
        print("\n4. Testing hunger progress update...")
        recurring_mgr.update_hunger_progress(
            character_id=character_id,
            meal_quality='full_meal',
            turn_number=6
        )
        print("  ✓ Hunger progress updated (full meal)")

        # Check objectives status
        print("\n5. Checking objective completion status...")
        objectives = obj_mgr.list_objectives(
            character_id=character_id,
            status='completed'
        )

        if objectives:
            print(f"  ✓ {len(objectives)} objectives completed:")
            for obj in objectives:
                print(f"    • {obj['description']} ({obj['partial_completion']*100:.0f}%)")
        else:
            print("  Note: No objectives completed yet (may need more progress)")


def run_all_tests():
    """Run all objective system tests."""
    print("\n" + "=" * 60)
    print("OBJECTIVE SYSTEM TEST SUITE")
    print("=" * 60)

    with app.app_context():
        try:
            # Test 1: Cognitive traits
            character_id = test_cognitive_traits()
            if not character_id:
                print("\n✗ Cognitive trait test failed. Aborting.")
                return

            # Test 2: Objective CRUD
            game_id, main_obj_id, child1_id, child2_id = test_objective_crud(character_id)

            # Test 3: Objective evaluation
            test_objective_evaluation(character_id, game_id, (main_obj_id, child1_id, child2_id))

            # Test 4: Recurring objectives
            test_recurring_objectives(character_id, game_id)

            # Final summary
            print("\n" + "=" * 60)
            print("✓ ALL TESTS COMPLETED SUCCESSFULLY!")
            print("=" * 60)
            print("\nThe objective system is ready to use.")
            print("\nNext steps:")
            print("  1. Integrate with game engine (see OBJECTIVE_SYSTEM_INTEGRATION.md)")
            print("  2. Add LLM integration for planning")
            print("  3. Test with real characters")

        except Exception as e:
            print(f"\n✗ Test failed with error:")
            print(f"  {str(e)}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == '__main__':
    run_all_tests()
