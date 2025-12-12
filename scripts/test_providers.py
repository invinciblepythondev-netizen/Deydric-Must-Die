"""
Test LLM providers to diagnose initialization and API issues.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_aimlapi():
    """Test AIML API provider."""
    print("\n" + "="*60)
    print("Testing AIML API Provider")
    print("="*60)

    try:
        from services.llm.aimlapi import AIMLAPIProvider

        api_key = os.getenv("AIMLAPI_API_KEY")
        if not api_key:
            print("[X] AIMLAPI_API_KEY not found in environment")
            return False

        print(f"API Key: {api_key[:10]}...")

        provider = AIMLAPIProvider()
        print("[OK] Provider initialized")

        # List available models
        print("\nFetching available models...")
        models = provider.get_available_models()

        if models:
            print(f"✓ Found {len(models)} models")
            print("\nAvailable models:")
            for model in models[:10]:  # Show first 10
                print(f"  - {model}")
            if len(models) > 10:
                print(f"  ... and {len(models) - 10} more")
        else:
            print("✗ No models found or error fetching models")

        # Test simple generation
        print("\nTesting simple generation...")
        try:
            response = provider.generate(
                prompt="Say hello",
                system_prompt="You are a helpful assistant.",
                model="meta-llama/Llama-3-70b-chat-hf",  # Try different model name
                temperature=0.7,
                max_tokens=50
            )
            print(f"✓ Generation successful: {response[:100]}")
            return True
        except Exception as e:
            print(f"✗ Generation failed: {e}")
            # Try alternative model name
            print("\nTrying alternative model name...")
            try:
                response = provider.generate(
                    prompt="Say hello",
                    system_prompt="You are a helpful assistant.",
                    model="mistralai/Mistral-7B-Instruct-v0.2",
                    temperature=0.7,
                    max_tokens=50
                )
                print(f"✓ Generation successful with Mistral: {response[:100]}")
                return True
            except Exception as e2:
                print(f"✗ Also failed with Mistral: {e2}")
                return False

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_together_ai():
    """Test Together.ai provider."""
    print("\n" + "="*60)
    print("Testing Together.ai Provider")
    print("="*60)

    try:
        api_key = os.getenv("TOGETHER_API_KEY")
        if not api_key:
            print("✗ TOGETHER_API_KEY not found in environment")
            return False

        print(f"API Key: {api_key[:10]}...")

        from services.llm.together_ai import TogetherAIProvider

        provider = TogetherAIProvider()
        print("✓ Provider initialized")

        # Test simple generation
        print("\nTesting simple generation...")
        response = provider.generate(
            prompt="Say hello",
            system_prompt="You are a helpful assistant.",
            temperature=0.7,
            max_tokens=50
        )
        print(f"✓ Generation successful: {response[:100]}")
        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_claude():
    """Test Claude provider."""
    print("\n" + "="*60)
    print("Testing Claude Provider")
    print("="*60)

    try:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print("✗ ANTHROPIC_API_KEY not found in environment")
            return False

        print(f"API Key: {api_key[:10]}...")

        from services.llm.claude import ClaudeProvider

        provider = ClaudeProvider()
        print("✓ Provider initialized")

        # Test simple generation
        print("\nTesting simple generation...")
        response = provider.generate(
            prompt="Say hello",
            system_prompt="You are a helpful assistant.",
            temperature=0.7,
            max_tokens=50
        )
        print(f"✓ Generation successful: {response[:100]}")
        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_openai():
    """Test OpenAI provider."""
    print("\n" + "="*60)
    print("Testing OpenAI Provider")
    print("="*60)

    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("✗ OPENAI_API_KEY not found in environment")
            return False

        print(f"API Key: {api_key[:10]}...")

        from services.llm.openai import OpenAIProvider

        provider = OpenAIProvider()
        print("✓ Provider initialized")

        # Test simple generation
        print("\nTesting simple generation...")
        response = provider.generate(
            prompt="Say hello",
            system_prompt="You are a helpful assistant.",
            temperature=0.7,
            max_tokens=50
        )
        print(f"✓ Generation successful: {response[:100]}")
        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n" + "="*60)
    print("LLM Provider Diagnostic Test")
    print("="*60)

    results = {
        "Claude": test_claude(),
        "OpenAI": test_openai(),
        "AIML API": test_aimlapi(),
        "Together.ai": test_together_ai()
    }

    print("\n" + "="*60)
    print("Summary")
    print("="*60)

    for provider, success in results.items():
        status = "✓ Working" if success else "✗ Failed"
        print(f"{provider}: {status}")

    working_count = sum(1 for success in results.values() if success)
    print(f"\n{working_count}/{len(results)} providers working")

    if working_count == 0:
        print("\n⚠️  No providers are working! Check your API keys in .env file")
        sys.exit(1)
    elif working_count < len(results):
        print("\n⚠️  Some providers failed. The game will use fallback providers.")
        sys.exit(0)
    else:
        print("\n✓ All providers working!")
        sys.exit(0)
