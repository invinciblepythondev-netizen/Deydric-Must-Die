"""
Phase 4 Test: LLM Service Integration

Tests the unified LLM service with all components integrated.
Minimal API calls to stay within budget.

Budget: Part of $5 total budget (~$0.001 for this phase).
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment
from dotenv import load_dotenv
load_dotenv()

from services.llm_service import get_unified_llm_service, get_llm_service_factory
import logging

logging.basicConfig(level=logging.INFO)


def test_service_initialization():
    """Test that unified service initializes correctly."""
    print("\n" + "="*70)
    print("TEST 1: Service Initialization")
    print("="*70)

    try:
        service = get_unified_llm_service()
        print("[PASS] Unified service initialized")

        # Check components
        if service.factory is None:
            print("[FAIL] Factory not initialized")
            return False
        print("[PASS] Factory initialized")

        if service.manual_fallback is None:
            print("[FAIL] Manual fallback not initialized")
            return False
        print("[PASS] Manual fallback initialized")

        if service.prompt_templates is None:
            print("[FAIL] Prompt templates not initialized")
            return False
        print("[PASS] Prompt templates initialized")

        return True

    except Exception as e:
        print(f"[FAIL] Initialization failed: {e}")
        return False


def test_factory_providers():
    """Test that factory has providers available."""
    print("\n" + "="*70)
    print("TEST 2: Factory Providers")
    print("="*70)

    try:
        factory = get_llm_service_factory()

        if not factory._cached_providers:
            print("[FAIL] No providers initialized")
            return False

        print(f"[PASS] {len(factory._cached_providers)} providers initialized:")
        for name in factory._cached_providers.keys():
            print(f"  - {name}")

        return True

    except Exception as e:
        print(f"[FAIL] Factory test failed: {e}")
        return False


def test_action_generator_available():
    """Test that action generator is available."""
    print("\n" + "="*70)
    print("TEST 3: Action Generator Available")
    print("="*70)

    try:
        service = get_unified_llm_service()
        generator = service.factory.get_action_generator()

        if generator is None:
            print("[FAIL] Action generator not available")
            return False

        print("[PASS] Action generator available")
        print(f"  Type: {generator.__class__.__name__}")

        return True

    except Exception as e:
        print(f"[FAIL] Action generator test failed: {e}")
        return False


def test_summarization_provider_available():
    """Test that summarization provider is available."""
    print("\n" + "="*70)
    print("TEST 4: Summarization Provider Available")
    print("="*70)

    try:
        service = get_unified_llm_service()
        provider = service.factory.get_summarization_provider()

        if provider is None:
            print("[FAIL] Summarization provider not available")
            return False

        print("[PASS] Summarization provider available")
        print(f"  Type: {provider.__class__.__name__}")

        return True

    except Exception as e:
        print(f"[FAIL] Summarization provider test failed: {e}")
        return False


def test_simple_summarization():
    """Test basic summarization (minimal API call)."""
    print("\n" + "="*70)
    print("TEST 5: Simple Summarization (Live API)")
    print("="*70)

    try:
        service = get_unified_llm_service()

        # Minimal test data
        turns = [
            {"turn_number": 1, "action_description": "Character entered tavern."},
            {"turn_number": 2, "action_description": "Character sat down."}
        ]

        summary = service.summarize_memory(turns, importance="routine")

        if not summary or len(summary) < 10:
            print(f"[FAIL] Summary too short or empty")
            return False

        print(f"[PASS] Summary generated ({len(summary)} chars)")
        print(f"  Preview: {summary[:100]}...")

        return True

    except Exception as e:
        print(f"[FAIL] Summarization test failed: {e}")
        return False


if __name__ == "__main__":
    print("\n" + "="*70)
    print("PHASE 4: LLM SERVICE INTEGRATION TEST SUITE")
    print("="*70)
    print("\nTests unified service with all components integrated.")

    results = []

    # Run tests
    results.append(("Service Initialization", test_service_initialization()))
    results.append(("Factory Providers", test_factory_providers()))
    results.append(("Action Generator", test_action_generator_available()))
    results.append(("Summarization Provider", test_summarization_provider_available()))
    results.append(("Simple Summarization", test_simple_summarization()))

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
    print("API calls: 1 (simple summarization)")
    print("Estimated tokens: ~200-300")
    print("Estimated cost: $0.0001 - $0.0002")
    print("Remaining budget: ~$4.999")

    if passed_count == len(results):
        print("\n[PASS] PHASE 4 COMPLETE!")
        print("\nUnified LLM Service is ready with all components integrated.")
        sys.exit(0)
    else:
        print("\n[FAIL] PHASE 4 FAILED - Fix issues before proceeding")
        sys.exit(1)
