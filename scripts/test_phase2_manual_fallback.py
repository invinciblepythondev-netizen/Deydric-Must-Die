"""
Phase 2 Test: Manual Fallback System

Tests the manual fallback validation logic (schema validation).
Does NOT test interactive input (that would require manual interaction).

Budget: Part of $5 total budget (no API calls in this phase).
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.llm.manual_fallback import ManualFallbackHandler
from jsonschema import ValidationError
import json


def test_action_schema_validation():
    """Test action schema validation with valid and invalid data."""
    print("\n" + "="*70)
    print("TEST 1: Action Schema Validation")
    print("="*70)

    handler = ManualFallbackHandler()

    # Valid actions
    valid_actions = [
        {
            "thought": "I should greet them",
            "speech": "Hello, friend!",
            "action": "Character waves at the other person",
            "action_type": "speak"
        },
        {
            "thought": "Time to move",
            "speech": None,
            "action": "Character walks to the door",
            "action_type": "move"
        }
    ]

    # Test valid data
    try:
        from jsonschema import validate
        validate(instance=valid_actions, schema=handler.ACTION_SCHEMA)
        print("[PASS] Valid action data accepted")
    except ValidationError as e:
        print(f"[FAIL] Valid data rejected: {e.message}")
        return False

    # Invalid actions (missing required field)
    invalid_actions_1 = [
        {
            "thought": "I should greet them",
            # Missing action_type
            "action": "Character waves"
        }
    ]

    try:
        validate(instance=invalid_actions_1, schema=handler.ACTION_SCHEMA)
        print("[FAIL] Invalid data (missing field) was accepted")
        return False
    except ValidationError:
        print("[PASS] Invalid data (missing field) correctly rejected")

    # Invalid actions (wrong enum value)
    invalid_actions_2 = [
        {
            "thought": "Test",
            "speech": None,
            "action": "Test action",
            "action_type": "invalid_type"  # Not in enum
        }
    ]

    try:
        validate(instance=invalid_actions_2, schema=handler.ACTION_SCHEMA)
        print("[FAIL] Invalid data (bad enum) was accepted")
        return False
    except ValidationError:
        print("[PASS] Invalid data (bad enum) correctly rejected")

    # Empty array (should fail - minItems: 1)
    try:
        validate(instance=[], schema=handler.ACTION_SCHEMA)
        print("[FAIL] Empty array was accepted")
        return False
    except ValidationError:
        print("[PASS] Empty array correctly rejected")

    return True


def test_objective_schema_validation():
    """Test objective schema validation."""
    print("\n" + "="*70)
    print("TEST 2: Objective Schema Validation")
    print("="*70)

    handler = ManualFallbackHandler()

    # Valid objectives
    valid_objectives = {
        "objectives": [
            {
                "description": "Find evidence against Lord Deydric",
                "priority": "high",
                "success_criteria": "Obtain documents from his office",
                "mood_impact_positive": 10,
                "mood_impact_negative": -5
            },
            {
                "description": "Gather allies",
                "priority": "medium"
                # Optional fields omitted
            }
        ]
    }

    try:
        from jsonschema import validate
        validate(instance=valid_objectives, schema=handler.OBJECTIVE_SCHEMA)
        print("[PASS] Valid objective data accepted")
    except ValidationError as e:
        print(f"[FAIL] Valid data rejected: {e.message}")
        return False

    # Invalid objectives (missing required field)
    invalid_objectives = {
        "objectives": [
            {
                "description": "Test objective"
                # Missing priority
            }
        ]
    }

    try:
        validate(instance=invalid_objectives, schema=handler.OBJECTIVE_SCHEMA)
        print("[FAIL] Invalid data (missing priority) was accepted")
        return False
    except ValidationError:
        print("[PASS] Invalid data (missing priority) correctly rejected")

    # Invalid priority value
    invalid_objectives_2 = {
        "objectives": [
            {
                "description": "Test",
                "priority": "super_high"  # Not in enum
            }
        ]
    }

    try:
        validate(instance=invalid_objectives_2, schema=handler.OBJECTIVE_SCHEMA)
        print("[FAIL] Invalid data (bad priority) was accepted")
        return False
    except ValidationError:
        print("[PASS] Invalid data (bad priority) correctly rejected")

    return True


def test_action_type_enum():
    """Test that all valid action types are accepted."""
    print("\n" + "="*70)
    print("TEST 3: Action Type Enum Coverage")
    print("="*70)

    handler = ManualFallbackHandler()
    from jsonschema import validate

    valid_action_types = ["speak", "move", "interact", "attack", "observe", "wait", "think"]

    for action_type in valid_action_types:
        test_action = [{
            "thought": "Test",
            "speech": None,
            "action": "Test action",
            "action_type": action_type
        }]

        try:
            validate(instance=test_action, schema=handler.ACTION_SCHEMA)
            print(f"[PASS] Action type '{action_type}' accepted")
        except ValidationError as e:
            print(f"[FAIL] Action type '{action_type}' rejected: {e.message}")
            return False

    return True


def test_validation_error_reporting():
    """Test that validation errors are reported clearly."""
    print("\n" + "="*70)
    print("TEST 4: Validation Error Reporting")
    print("="*70)

    handler = ManualFallbackHandler()

    invalid_data = [
        {
            "thought": "Test",
            # Missing both action and action_type
        }
    ]

    errors = handler.get_validation_errors(invalid_data, handler.ACTION_SCHEMA)

    if len(errors) > 0:
        print(f"[PASS] Found {len(errors)} validation errors:")
        for error in errors:
            print(f"  - {error}")
        return True
    else:
        print("[FAIL] No validation errors reported for invalid data")
        return False


def test_json_parsing():
    """Test that valid JSON strings can be parsed."""
    print("\n" + "="*70)
    print("TEST 5: JSON Parsing")
    print("="*70)

    # Test multi-line JSON
    json_string = """[
        {
            "thought": "Test thought",
            "speech": "Test speech",
            "action": "Test action",
            "action_type": "speak"
        },
        {
            "thought": "Another thought",
            "speech": null,
            "action": "Another action",
            "action_type": "move"
        }
    ]"""

    try:
        data = json.loads(json_string)
        print(f"[PASS] Multi-line JSON parsed successfully")
        print(f"  Parsed {len(data)} actions")

        # Validate it
        from jsonschema import validate
        validate(instance=data, schema=ManualFallbackHandler.ACTION_SCHEMA)
        print(f"[PASS] Parsed data is valid")
        return True

    except Exception as e:
        print(f"[FAIL] JSON parsing failed: {e}")
        return False


if __name__ == "__main__":
    print("\n" + "="*70)
    print("PHASE 2: MANUAL FALLBACK VALIDATION TEST SUITE")
    print("="*70)
    print("\nNOTE: This tests schema validation logic only.")
    print("Interactive manual input testing requires user interaction.")

    results = []

    # Run tests
    results.append(("Action Schema Validation", test_action_schema_validation()))
    results.append(("Objective Schema Validation", test_objective_schema_validation()))
    results.append(("Action Type Enum", test_action_type_enum()))
    results.append(("Error Reporting", test_validation_error_reporting()))
    results.append(("JSON Parsing", test_json_parsing()))

    # Summary
    print("\n" + "="*70)
    print("TEST RESULTS")
    print("="*70)

    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status}: {name}")

    passed_count = sum(1 for _, p in results if p)
    print(f"\n{passed_count}/{len(results)} tests passed")

    # Cost estimate
    print("\n" + "="*70)
    print("COST ESTIMATE")
    print("="*70)
    print("API calls: 0 (schema validation only)")
    print("Cost: $0.00")
    print("Remaining budget: ~$4.9995")

    if passed_count == len(results):
        print("\n[PASS] PHASE 2 COMPLETE!")
        print("\nManual fallback system is ready.")
        print("To test interactive input, try integrating with the game engine.")
        sys.exit(0)
    else:
        print("\n[FAIL] PHASE 2 FAILED - Fix issues before proceeding")
        sys.exit(1)
