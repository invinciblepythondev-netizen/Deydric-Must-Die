"""
Test Provider Chain

Shows which providers would be used for different content intensities.
Useful for verifying configuration before running the game.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services.llm.provider_strategy import (
    ContentIntensity,
    ProviderCapability,
    get_provider_strategy
)


def test_provider_chain():
    """Test provider chain for each intensity level."""

    print("="*70)
    print("Provider Chain Test")
    print("="*70)
    print()

    strategy = get_provider_strategy(prefer_cheap=False)

    # Test each intensity level
    intensities = [
        ContentIntensity.MILD,
        ContentIntensity.MODERATE,
        ContentIntensity.MATURE,
        ContentIntensity.UNRESTRICTED
    ]

    for intensity in intensities:
        print(f"\n{intensity.value.upper()} CONTENT")
        print("-" * 70)

        chain = strategy.get_provider_chain(intensity)

        if not chain:
            print("  ⚠ No providers available for this intensity!")
            continue

        for i, provider_config in enumerate(chain, 1):
            provider = provider_config["provider"]
            model = provider_config["model"]
            cost = provider_config["cost"]
            max_intensity = provider_config["max_intensity"].value

            print(f"  {i}. {provider}/{model}")
            print(f"     Max Intensity: {max_intensity}")
            print(f"     Cost: ${cost:.6f} per 1k tokens")
            print(f"     Notes: {provider_config['notes']}")
            print()

    print()
    print("="*70)


def test_cost_optimization():
    """Test cost-optimized provider chain."""

    print("\n\nCOST-OPTIMIZED PROVIDER CHAIN")
    print("="*70)
    print()

    strategy = get_provider_strategy(prefer_cheap=True)

    intensity = ContentIntensity.MODERATE

    print(f"Providers for {intensity.value.upper()} content (cheapest first):")
    print("-" * 70)

    chain = strategy.get_provider_chain(intensity)

    for i, provider_config in enumerate(chain, 1):
        provider = provider_config["provider"]
        model = provider_config["model"]
        cost = provider_config["cost"]

        print(f"  {i}. {provider}/{model} - ${cost:.6f}/1k tokens")

    print()


def test_content_classification():
    """Test content intensity classification."""

    print("\n\nCONTENT CLASSIFICATION TEST")
    print("="*70)
    print()

    strategy = get_provider_strategy()

    # Test scenarios
    scenarios = [
        {
            "name": "Basic Dialogue",
            "context": {
                "action_type": "speak",
                "has_wounds": False
            }
        },
        {
            "name": "Combat with Wounds",
            "context": {
                "action_type": "attack",
                "has_wounds": True,
                "wound_severity": "moderate"
            }
        },
        {
            "name": "Critical Injury",
            "context": {
                "action_type": "examine",
                "has_wounds": True,
                "wound_severity": "critical"
            }
        },
        {
            "name": "Character Death",
            "context": {
                "action_type": "attack",
                "has_wounds": True,
                "has_death": True,
                "wound_severity": "mortal"
            }
        }
    ]

    for scenario in scenarios:
        intensity = strategy.classify_content_intensity(scenario["context"])
        print(f"{scenario['name']:<25} → {intensity.value.upper()}")

    print()


def test_provider_capabilities():
    """Show provider capability matrix."""

    print("\n\nPROVIDER CAPABILITY MATRIX")
    print("="*70)
    print()

    print(f"{'Provider/Model':<40} {'Mild':<8} {'Moderate':<10} {'Mature':<8} {'Unrestricted':<12} {'Cost/1k'}")
    print("-" * 90)

    # Test each provider against each intensity
    for provider, models in ProviderCapability.CAPABILITIES.items():
        for model, info in models.items():
            full_name = f"{provider}/{model}"

            # Test each intensity
            can_mild = ProviderCapability.can_handle(
                provider, model, ContentIntensity.MILD
            )
            can_moderate = ProviderCapability.can_handle(
                provider, model, ContentIntensity.MODERATE
            )
            can_mature = ProviderCapability.can_handle(
                provider, model, ContentIntensity.MATURE
            )
            can_unrestricted = ProviderCapability.can_handle(
                provider, model, ContentIntensity.UNRESTRICTED
            )

            # Format output
            mild_str = "✅" if can_mild else "❌"
            mod_str = "✅" if can_moderate else "❌"
            mature_str = "✅" if can_mature else "❌"
            unrest_str = "✅" if can_unrestricted else "❌"
            cost_str = f"${info['cost_per_1k_tokens']:.6f}"

            # Truncate long names
            if len(full_name) > 38:
                full_name = full_name[:35] + "..."

            print(f"{full_name:<40} {mild_str:<8} {mod_str:<10} {mature_str:<8} {unrest_str:<12} {cost_str}")

    print()


if __name__ == "__main__":
    try:
        test_provider_chain()
        test_cost_optimization()
        test_content_classification()
        test_provider_capabilities()

        print("="*70)
        print("✓ Provider chain test complete!")
        print("="*70)
        print()

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
