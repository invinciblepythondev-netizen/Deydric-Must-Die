"""
Phase 5 Test: ObjectivePlanner Integration

Tests that ObjectivePlanner works with UnifiedLLMService.
No API calls - just integration verification.

Budget: Part of $5 total budget (no API calls = $0.00).
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.objective_planner import ObjectivePlanner


def test_planner_initialization():
    """Test that planner initializes with unified service."""
    print("\n" + "="*70)
    print("TEST 1: Planner Initialization")
    print("="*70)

    try:
        planner = ObjectivePlanner()

        if planner.llm_service is None:
            print("[FAIL] LLM service not initialized")
            return False
        print("[PASS] LLM service initialized")

        if planner.objective_manager is None:
            print("[FAIL] Objective manager not initialized")
            return False
        print("[PASS] Objective manager initialized")

        if planner.trait_manager is None:
            print("[FAIL] Trait manager not initialized")
            return False
        print("[PASS] Trait manager initialized")

        return True

    except Exception as e:
        print(f"[FAIL] Initialization failed: {e}")
        return False


def test_context_building():
    """Test that context building method exists and works."""
    print("\n" + "="*70)
    print("TEST 2: Context Building")
    print("="*70)

    try:
        planner = ObjectivePlanner()

        character_profile = {
            "name": "Test Character",
            "role_responsibilities": "Guard",
            "personality_traits": ["brave"],
            "motivations_short_term": ["Protect castle"],
            "motivations_long_term": ["Become captain"],
            "backstory": "Young guard"
        }

        context = planner._build_initial_objectives_context(character_profile)

        if not context or len(context) < 10:
            print("[FAIL] Context too short or empty")
            return False

        print(f"[PASS] Context generated ({len(context)} chars)")

        return True

    except Exception as e:
        print(f"[FAIL] Context building failed: {e}")
        return False


def test_service_integration():
    """Test that planner has access to unified service methods."""
    print("\n" + "="*70)
    print("TEST 3: Service Integration")
    print("="*70)

    try:
        planner = ObjectivePlanner()

        # Check that planner has access to service
        if not hasattr(planner.llm_service, 'plan_objectives'):
            print("[FAIL] Service missing plan_objectives method")
            return False
        print("[PASS] Service has plan_objectives method")

        if not hasattr(planner.llm_service, 'manual_fallback'):
            print("[FAIL] Service missing manual_fallback")
            return False
        print("[PASS] Service has manual_fallback")

        if not hasattr(planner.llm_service, 'prompt_templates'):
            print("[FAIL] Service missing prompt_templates")
            return False
        print("[PASS] Service has prompt_templates")

        return True

    except Exception as e:
        print(f"[FAIL] Service integration test failed: {e}")
        return False


if __name__ == "__main__":
    print("\n" + "="*70)
    print("PHASE 5: OBJECTIVE PLANNER INTEGRATION TEST SUITE")
    print("="*70)
    print("\nTests ObjectivePlanner integration with UnifiedLLMService.")

    results = []

    # Run tests
    results.append(("Planner Initialization", test_planner_initialization()))
    results.append(("Context Building", test_context_building()))
    results.append(("Service Integration", test_service_integration()))

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
    print("API calls: 0 (integration test only)")
    print("Cost: $0.00")
    print("Remaining budget: ~$4.999")

    if passed_count == len(results):
        print("\n[PASS] PHASE 5 COMPLETE!")
        print("\nObjectivePlanner integrated with resilient LLM service.")
        sys.exit(0)
    else:
        print("\n[FAIL] PHASE 5 FAILED - Fix issues before proceeding")
        sys.exit(1)
