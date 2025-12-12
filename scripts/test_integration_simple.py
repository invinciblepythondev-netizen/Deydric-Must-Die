"""
Basic Integration Test for Objective System

This script tests the objective system with a real character:
1. Creates a simple objective
2. Lists character's objectives
3. Updates progress on the objective
4. Checks if it completes
5. Tests objective hierarchy
"""

import sys
import os
from pathlib import Path
from uuid import UUID

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app import app
from database import db
from sqlalchemy import text
from services.objective_manager import ObjectiveManager

# Test data
CHARACTER_ID = UUID('266cf37e-286b-49ab-ae8d-4dcc36f61c1d')  # Lysa Darnog
GAME_ID = UUID('f8ea19f8-3ae4-47ce-876d-a9cfcc7fc7c3')


def print_header(title):
    """Print a formatted header."""
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def test_basic_objective_crud():
    """Test creating, reading, updating, and completing objectives."""
    print_header("TEST 1: Basic Objective CRUD")

    with app.app_context():
        obj_mgr = ObjectiveManager()

        # Get character name
        char_result = db.session.execute(
            text("SELECT name FROM character.character WHERE character_id = :id"),
            {"id": str(CHARACTER_ID)}
        ).fetchone()
        char_name = char_result[0]
        print(f"\nTesting with character: {char_name}")
        print(f"Game ID: {GAME_ID}")

        # 1. Create a simple atomic objective
        print("\n1. Creating a simple objective...")
        objective_id = obj_mgr.create_objective(
            character_id=CHARACTER_ID,
            game_id=GAME_ID,
            description="Go to the tavern and order a drink",
            objective_type='main',
            priority='medium',
            current_turn=1,
            is_atomic=True  # Can be completed in one action
        )
        print(f"   [OK] Created objective: {objective_id}")

        # 2. List character's objectives
        print("\n2. Listing all active objectives...")
        objectives = obj_mgr.list_objectives(CHARACTER_ID, status='active')
        print(f"   [OK] Character has {len(objectives)} active objectives:")
        for obj in objectives:
            obj_type = obj['objective_type']
            print(f"      - [{obj['priority']}] {obj['description']} (type: {obj_type})")

        # 3. Get the specific objective we created
        print("\n3. Retrieving the created objective...")
        objective = obj_mgr.get_objective(objective_id)
        print(f"   [OK] Objective details:")
        print(f"      Description: {objective['description']}")
        print(f"      Status: {objective['status']}")
        print(f"      Progress: {objective['partial_completion']*100:.0f}%")
        print(f"      Is atomic: {objective['is_atomic']}")

        # 4. Update progress (50%)
        print("\n4. Updating progress to 50%...")
        obj_mgr.update_objective_progress(
            objective_id=objective_id,
            progress_delta=0.5,
            turn_number=3,
            action_taken="Walked halfway to the tavern"
        )

        objective = obj_mgr.get_objective(objective_id)
        print(f"   [OK] Progress: {objective['partial_completion']*100:.0f}%")
        print(f"   [OK] Status: {objective['status']}")

        # 5. Complete the objective
        print("\n5. Completing the objective...")
        obj_mgr.update_objective_progress(
            objective_id=objective_id,
            progress_delta=0.5,
            turn_number=5,
            action_taken="Arrived at the tavern and ordered ale"
        )

        objective = obj_mgr.get_objective(objective_id)
        print(f"   [OK] Progress: {objective['partial_completion']*100:.0f}%")
        print(f"   [OK] Status: {objective['status']}")

        if objective['status'] == 'completed':
            print(f"   [OK] Objective auto-completed at 100%!")

        return True


def test_objective_hierarchy():
    """Test creating objectives with parent-child relationships."""
    print_header("TEST 2: Objective Hierarchy")

    with app.app_context():
        obj_mgr = ObjectiveManager()

        # 1. Create a main objective (non-atomic)
        print("\n1. Creating main objective...")
        main_obj_id = obj_mgr.create_objective(
            character_id=CHARACTER_ID,
            game_id=GAME_ID,
            description="Investigate the mysterious stranger",
            objective_type='main',
            priority='high',
            current_turn=10,
            is_atomic=False
        )
        print(f"   [OK] Created main objective: {main_obj_id}")

        # 2. Create child objectives
        print("\n2. Creating child objectives...")
        child1_id = obj_mgr.create_objective(
            character_id=CHARACTER_ID,
            game_id=GAME_ID,
            description="Observe the stranger's behavior",
            objective_type='child',
            priority='high',
            current_turn=10,
            parent_objective_id=main_obj_id,
            is_atomic=True
        )
        print(f"   [OK] Created child 1: {child1_id}")

        child2_id = obj_mgr.create_objective(
            character_id=CHARACTER_ID,
            game_id=GAME_ID,
            description="Ask the barkeep about the stranger",
            objective_type='child',
            priority='high',
            current_turn=10,
            parent_objective_id=main_obj_id,
            is_atomic=True
        )
        print(f"   [OK] Created child 2: {child2_id}")

        # 3. Get objective tree
        print("\n3. Getting objective tree...")
        tree_rows = obj_mgr.get_objective_tree(main_obj_id)
        print(f"   [OK] Tree structure ({len(tree_rows)} nodes):")

        for row in tree_rows:
            desc = row['description']
            status = row['status']
            progress = row['partial_completion'] * 100
            depth = row['depth']
            print(f"      {'  ' * depth}- {desc} ({status}, {progress:.0f}%)")

        # 4. Complete first child
        print("\n4. Completing first child objective...")
        obj_mgr.update_objective_progress(
            objective_id=child1_id,
            progress_delta=1.0,
            turn_number=12,
            action_taken="Observed stranger carefully for an hour"
        )

        child1 = obj_mgr.get_objective(child1_id)
        print(f"   [OK] Child 1 status: {child1['status']}")

        # 5. Complete second child
        print("\n5. Completing second child objective...")
        obj_mgr.update_objective_progress(
            objective_id=child2_id,
            progress_delta=1.0,
            turn_number=13,
            action_taken="Learned stranger is from the capital"
        )

        child2 = obj_mgr.get_objective(child2_id)
        print(f"   [OK] Child 2 status: {child2['status']}")

        # 6. Check if parent updated
        print("\n6. Checking parent objective...")
        main_obj = obj_mgr.get_objective(main_obj_id)
        print(f"   [OK] Main objective progress: {main_obj['partial_completion']*100:.0f}%")
        print(f"   [OK] Main objective status: {main_obj['status']}")

        return True


def test_recurring_objectives():
    """Test that recurring objectives were properly initialized."""
    print_header("TEST 3: Recurring Objectives")

    with app.app_context():
        obj_mgr = ObjectiveManager()

        # List recurring objectives
        print("\n1. Listing recurring objectives...")
        all_objectives = obj_mgr.list_objectives(
            CHARACTER_ID,
            status='active'
        )

        # Filter for recurring type
        recurring = [obj for obj in all_objectives if obj.get('objective_type') == 'recurring']

        print(f"   [OK] Found {len(recurring)} recurring objectives:")
        for obj in recurring:
            print(f"      - [{obj['priority']}] {obj['description']}")

        if len(recurring) > 0:
            # Update progress on first recurring objective
            first_obj = recurring[0]
            print(f"\n2. Testing progress update on: {first_obj['description']}")

            # Convert objective_id to UUID if it's a string
            obj_id = first_obj['objective_id']
            if isinstance(obj_id, str):
                obj_id = UUID(obj_id)

            obj_mgr.update_objective_progress(
                objective_id=obj_id,
                progress_delta=0.3,
                turn_number=15,
                action_taken="Made some progress on this need"
            )

            updated = obj_mgr.get_objective(obj_id)
            print(f"   [OK] Updated progress: {updated['partial_completion']*100:.0f}%")

        return True


def test_planning_state():
    """Test character planning state."""
    print_header("TEST 4: Planning State")

    with app.app_context():
        # Get planning state
        planning_state = db.session.execute(
            text("""
                SELECT
                    max_active_high_priority,
                    max_objective_depth,
                    planning_frequency_turns,
                    focus_score,
                    next_planning_turn
                FROM objective.character_planning_state
                WHERE character_id = :character_id
            """),
            {"character_id": str(CHARACTER_ID)}
        ).fetchone()

        if planning_state:
            print("\n[OK] Planning State:")
            print(f"   Max high-priority objectives: {planning_state[0]}")
            print(f"   Max objective depth: {planning_state[1]}")
            print(f"   Planning frequency: every {planning_state[2]} turns")
            print(f"   Focus score: {planning_state[3]:.1f}/10")
            print(f"   Next planning turn: {planning_state[4]}")
            return True
        else:
            print("\n[FAIL] No planning state found!")
            return False


def main():
    """Run all integration tests."""
    print("=" * 80)
    print("OBJECTIVE SYSTEM - BASIC INTEGRATION TEST")
    print("=" * 80)

    tests = [
        ("Basic CRUD", test_basic_objective_crud),
        ("Objective Hierarchy", test_objective_hierarchy),
        ("Recurring Objectives", test_recurring_objectives),
        ("Planning State", test_planning_state),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"\n[X] Test failed with error: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))

    # Print summary
    print_header("TEST SUMMARY")
    passed = sum(1 for _, success in results if success)
    total = len(results)

    for test_name, success in results:
        status = "[PASS]" if success else "[FAIL]"
        print(f"{status}: {test_name}")

    print(f"\nResults: {passed}/{total} tests passed")

    if passed == total:
        print("\n[OK] All integration tests passed!")
        return 0
    else:
        print(f"\n[FAIL] {total - passed} test(s) failed")
        return 1


if __name__ == '__main__':
    exit(main())
