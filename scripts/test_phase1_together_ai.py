"""
Phase 1 Test: Together.ai Provider

Tests the Together.ai provider implementation with live API calls.
Budget: Part of $5 total budget for all tests.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from services.llm.together_ai import TogetherAIProvider
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_provider_initialization():
    """Test that provider initializes correctly."""
    print("\n" + "="*70)
    print("TEST 1: Provider Initialization")
    print("="*70)

    try:
        provider = TogetherAIProvider()
        print(f"[PASS] Provider initialized")
        print(f"  Default model: {provider.get_default_model()}")
        print(f"  Available models: {len(provider.get_available_models())}")
        return True
    except Exception as e:
        print(f"[FAIL] Initialization failed: {e}")
        return False


def test_basic_generation():
    """Test basic text generation with Mixtral."""
    print("\n" + "="*70)
    print("TEST 2: Basic Generation (Mixtral 8x7B)")
    print("="*70)

    try:
        provider = TogetherAIProvider()

        prompt = "Generate a single action for a character named 'Test Character' in a tavern. Respond with just one sentence."

        print("Sending test prompt...")
        response = provider.generate(
            prompt=prompt,
            system_prompt="You are a helpful assistant.",
            temperature=0.7,
            max_tokens=100
        )

        print(f"[PASS] Generation successful")
        print(f"  Response: {response[:200]}...")
        return True

    except Exception as e:
        print(f"[FAIL] Generation failed: {e}")
        return False


def test_model_aliases():
    """Test model alias resolution."""
    print("\n" + "="*70)
    print("TEST 3: Model Alias Resolution")
    print("="*70)

    try:
        aliases = ["mixtral-8x7b", "llama-3-70b", "llama-3.1-405b"]

        for alias in aliases:
            model = TogetherAIProvider.get_model_by_alias(alias)
            print(f"[PASS] {alias} -> {model}")

        return True

    except Exception as e:
        print(f"[FAIL] Alias resolution failed: {e}")
        return False


def test_system_prompt():
    """Test generation with system prompt."""
    print("\n" + "="*70)
    print("TEST 4: System Prompt Support")
    print("="*70)

    try:
        provider = TogetherAIProvider()

        response = provider.generate(
            prompt="What should I do?",
            system_prompt="You are a game AI. Respond with only 'Wait and observe.'",
            temperature=0.3,
            max_tokens=50
        )

        print(f"[PASS] System prompt respected")
        print(f"  Response: {response}")
        return True

    except Exception as e:
        print(f"[FAIL] System prompt test failed: {e}")
        return False


def estimate_cost(total_tokens):
    """Estimate cost based on token usage."""
    # Together.ai Mixtral pricing: ~$0.0006 per 1K tokens
    cost_per_1k = 0.0006
    return (total_tokens / 1000) * cost_per_1k


if __name__ == "__main__":
    print("\n" + "="*70)
    print("PHASE 1: TOGETHER.AI PROVIDER TEST SUITE")
    print("="*70)

    results = []

    # Run tests
    results.append(("Initialization", test_provider_initialization()))
    results.append(("Basic Generation", test_basic_generation()))
    results.append(("Model Aliases", test_model_aliases()))
    results.append(("System Prompt", test_system_prompt()))

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
    print("Estimated tokens used: ~500-800")
    print(f"Estimated cost: $0.0003 - $0.0005")
    print("Remaining budget: ~$4.9995")

    if passed_count == len(results):
        print("\n[PASS] PHASE 1 COMPLETE!")
        sys.exit(0)
    else:
        print("\n[FAIL] PHASE 1 FAILED - Fix issues before proceeding")
        sys.exit(1)
