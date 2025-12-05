"""
Test Context Management

Demonstrates how context is adapted for different model sizes.
Shows which components fit in each model's context window.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services.context_manager import (
    ContextAssembler,
    ContextPriority,
    ModelContextLimits,
    build_character_context
)


def create_sample_context():
    """Create a realistic game context for testing."""
    return {
        "system_prompt": "You are a narrative AI for a dark fantasy RPG...",
        "location_name": "The Dark Tavern",
        "location_description": (
            "A dimly lit establishment with rough wooden tables and shadowy corners. "
            "The air is thick with smoke and the smell of cheap ale. Suspicious patrons "
            "watch newcomers with wary eyes. This is a place where secrets are traded "
            "and dangerous deals are made."
        ),
        "visible_characters": ["Assassin in Hood", "Wary Guard", "Drunken Patron"],
        "working_memory": """
Turn 1: You entered the tavern, scanning for your target.
Turn 2: You spotted the hooded assassin in the corner, observing the same target.
Turn 3: The guard noticed you and began watching suspiciously.
Turn 4: You ordered ale to blend in while maintaining surveillance.
Turn 5: The target met with a cloaked figure and exchanged a package.
Turn 6: The assassin moved closer to the target, hand on weapon.
Turn 7: You positioned yourself to intercept if the assassin strikes.
Turn 8: The guard approached, asking about your business here.
Turn 9: You deflected with a cover story about meeting someone.
Turn 10: The target finished his meeting and prepared to leave.
""" * 3,  # Multiply to make it larger
        "short_term_summary": (
            "This session began when you tracked your target to this dangerous tavern. "
            "You've observed a potential rival assassin also watching the target. A guard "
            "has become suspicious of you. The target just completed a suspicious exchange "
            "with a cloaked figure. Tension is building as multiple parties circle the same prey. "
            "You must decide whether to act now, continue observing, or withdraw to avoid conflict "
            "with the other assassin and the guard." * 2
        ),
        "long_term_memories": (
            "Three months ago, you accepted this contract to eliminate Lord Blackwood for betraying "
            "your guild. Two months ago, you infiltrated his household staff to learn his patterns. "
            "Last month, you discovered he has ties to the Crimson Brotherhood. Two weeks ago, you "
            "learned he frequents this tavern for secret meetings. Last week, you spotted another "
            "assassin trailing him - likely from a rival guild. You've been wounded before in encounters "
            "with the Brotherhood. You know the guard captain in this district is corrupt and watches "
            "this tavern closely." * 3
        ),
        "relationships": """
Assassin in Hood: Unknown, potential rival - Fear: 0.6, Trust: 0.1, Respect: 0.7
Wary Guard: Suspicious of you - Fear: 0.3, Trust: 0.0, Respect: 0.4
Your Target (Lord Blackwood): Must eliminate - Fear: 0.0, Trust: 0.0, Respect: 0.0
""",
        "character_wounds": """
- Torso: Moderate stab wound from previous encounter (3 days ago)
- Left arm: Minor cut (healing well)
- Right leg: Bruised from recent escape
""",
        "character_inventory": """
- Poisoned dagger (concealed)
- Throwing knives (3)
- Smoke bomb (1)
- Healing herbs
- Lock picks
- Gold coins (47)
"""
    }


def create_sample_character():
    """Create a sample character profile."""
    return {
        "name": "Alaric the Shadow",
        "personality_traits": ["calculating", "ruthless", "patient", "paranoid"],
        "current_emotional_state": "tense and hyper-alert",
        "motivations_short_term": ["complete the contract", "avoid the rival assassin", "escape undetected"],
        "backstory": (
            "Born in the slums of Ravengard, you learned early that survival meant embracing the shadows. "
            "The Assassins' Guild found you at age twelve, recognizing your natural talent for stealth and "
            "patience. For twenty years, you've served as one of their most reliable operatives. You never fail "
            "a contract. Your reputation is built on perfect execution and leaving no witnesses. But this contract "
            "is different - Lord Blackwood was once your mentor before he betrayed the guild. This is personal. "
            "You've been tracking him for months, learning his patterns, waiting for the perfect moment. But now "
            "complications have emerged: a rival assassin, suspicious guards, and your old wounds that haven't "
            "fully healed. Failure is not an option, but neither is recklessness." * 2
        )
    }


def test_model_context_limits():
    """Show context limits for various models."""
    print("="*70)
    print("MODEL CONTEXT LIMITS")
    print("="*70)
    print()

    models = [
        "meta-llama/Meta-Llama-3-70B-Instruct",
        "mistralai/Mixtral-8x7B-Instruct-v0.1",
        "gpt-4",
        "gpt-4-turbo",
        "claude-3-5-sonnet-20241022"
    ]

    print(f"{'Model':<45} {'Total Limit':<12} {'Safe Input':<12} {'Response Buffer'}")
    print("-"*70)

    for model in models:
        total = ModelContextLimits.get_limit(model)
        safe = ModelContextLimits.get_safe_limit(model)
        buffer = total - safe

        # Truncate model name if too long
        model_display = model if len(model) <= 43 else model[:40] + "..."

        print(f"{model_display:<45} {total:<12,} {safe:<12,} {buffer:,}")

    print()


def test_context_assembly_for_models():
    """Test context assembly for different model sizes."""
    print("\n" + "="*70)
    print("CONTEXT ASSEMBLY TEST")
    print("="*70)
    print()

    character = create_sample_character()
    context = create_sample_context()

    models = [
        ("meta-llama/Meta-Llama-3-70B-Instruct", "Small (8K)"),
        ("mistralai/Mixtral-8x7B-Instruct-v0.1", "Medium (32K)"),
        ("claude-3-5-sonnet-20241022", "Large (200K)")
    ]

    for model, size_label in models:
        print(f"\n{'─'*70}")
        print(f"Model: {model}")
        print(f"Size: {size_label}")
        print(f"{'─'*70}")

        # Build context for this model
        final_context, metadata = build_character_context(
            character=character,
            game_context=context,
            model=model,
            max_response_tokens=2048
        )

        # Display results
        print(f"\nContext Summary:")
        print(f"  Total tokens: {metadata['total_tokens']:,}")
        print(f"  Available: {metadata['available_tokens']:,}")
        print(f"  Utilization: {metadata['total_tokens'] / metadata['available_tokens'] * 100:.1f}%")
        print(f"  Truncated: {metadata['was_truncated']}")

        if metadata['was_truncated']:
            print(f"  Tokens saved: {metadata.get('tokens_saved', 0):,}")

        print(f"\nComponents included: ({len(metadata['components_included'])})")
        for component in metadata['components_included']:
            marker = "✓"
            if "(trimmed)" in component:
                marker = "⚠"
            print(f"  {marker} {component}")

        if metadata['components_dropped']:
            print(f"\nComponents dropped: ({len(metadata['components_dropped'])})")
            for component in metadata['components_dropped']:
                print(f"  ✗ {component}")

        print(f"\nFirst 500 chars of context:")
        print("-"*70)
        print(final_context[:500] + "...")
        print("-"*70)

    print()


def test_manual_assembly():
    """Test manual context assembly with priority system."""
    print("\n" + "="*70)
    print("MANUAL CONTEXT ASSEMBLY (8K Model)")
    print("="*70)
    print()

    # Create assembler for small model
    assembler = ContextAssembler(
        model="meta-llama/Meta-Llama-3-70B-Instruct",
        max_response_tokens=2048
    )

    # Add components with different priorities
    print("Adding context components...")
    print()

    assembler.add_component(
        name="critical_identity",
        content="You are Alaric, a master assassin tracking Lord Blackwood.",
        priority=ContextPriority.CRITICAL,
        is_required=True
    )
    print("  ✓ Added CRITICAL: identity (required)")

    assembler.add_component(
        name="critical_situation",
        content="You are in a dark tavern. Your target is here, but so is a rival assassin and a suspicious guard.",
        priority=ContextPriority.CRITICAL,
        is_required=True
    )
    print("  ✓ Added CRITICAL: situation (required)")

    # Add large working memory
    large_memory = "Turn by turn events...\n" * 500  # ~3000 tokens
    assembler.add_component(
        name="working_memory",
        content=large_memory,
        priority=ContextPriority.HIGH
    )
    print("  ✓ Added HIGH: working memory (~3000 tokens)")

    # Add even larger backstory
    huge_backstory = "Your past history...\n" * 1000  # ~6000 tokens
    assembler.add_component(
        name="backstory",
        content=huge_backstory,
        priority=ContextPriority.OPTIONAL
    )
    print("  ✓ Added OPTIONAL: backstory (~6000 tokens)")

    # Assemble
    print()
    print("Assembling context...")
    print()

    final_context, metadata = assembler.assemble(preserve_order=True)

    # Results
    print(f"Results:")
    print(f"  Initial total: {sum(c.token_count for c in assembler.components):,} tokens")
    print(f"  Final total: {metadata['total_tokens']:,} tokens")
    print(f"  Available: {metadata['available_tokens']:,} tokens")
    print(f"  Truncated: {metadata['was_truncated']}")
    print(f"  Tokens saved: {metadata.get('tokens_saved', 0):,}")
    print()

    print(f"Components in final context:")
    for component in metadata['components_included']:
        print(f"  ✓ {component}")
    print()

    if metadata['components_dropped']:
        print(f"Components dropped:")
        for component in metadata['components_dropped']:
            print(f"  ✗ {component}")
        print()


def main():
    """Run all tests."""
    try:
        test_model_context_limits()
        test_context_assembly_for_models()
        test_manual_assembly()

        print("="*70)
        print("✓ All context management tests complete!")
        print("="*70)
        print()

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
