"""
Test Situational Context Awareness

Demonstrates how context adapts dynamically based on:
1. Current situation (food, combat, romance, etc.)
2. Model token limits (5 turns vs 10 turns)
3. Relevance detection (only include relevant character details)
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services.context_manager import (
    build_character_context,
    ModelContextLimits,
    _detect_context_relevance,
    _get_adaptive_memory_window
)


def create_detailed_character():
    """Create a character with many attributes."""
    return {
        "name": "Elara the Wanderer",
        "physical_appearance": "Tall woman with auburn hair and sharp green eyes",
        "current_clothing": "Travel-worn leather armor with a dark cloak",
        "personality_traits": ["cautious", "observant", "cunning", "loyal"],
        "current_emotional_state": "alert but weary",
        "current_stance": "standing near the door, hand near weapon",
        "motivations_short_term": ["Find lodging for the night", "Gather information about the road ahead"],
        "motivations_long_term": ["Reach the capital", "Clear her name"],

        # Preferences (conditionally relevant)
        "preferences": {
            "food": ["roasted meat", "dark bread", "ale"],
            "clothing_style": "practical, dark colors, easy to move in",
            "attraction_types": "values competence and honesty over appearance",
            "activities": ["training with weapons", "reading maps"],
            "locations": ["quiet taverns", "forest camps"]
        },

        # Knowledge (conditionally relevant)
        "education_level": "Self-taught, learned to read from stolen books",
        "skills": ["swordsmanship", "tracking", "herbalism", "lockpicking"],
        "hobbies": ["sketching maps", "whittling"],
        "superstitions": "Never speak a demon's name aloud, always leave coin for dead travelers",

        # Social (conditionally relevant)
        "social_class": "Former minor noble, now outcast",
        "reputation": "Known as a competent mercenary in the northern provinces",

        "backstory": "Once a minor noble's daughter, now falsely accused of murder..."
    }


def test_scenario(scenario_name, game_context, model):
    """Test context assembly for a specific scenario."""
    print(f"\n{'='*70}")
    print(f"SCENARIO: {scenario_name}")
    print(f"Model: {model} (Context limit: {ModelContextLimits.get_limit(model):,} tokens)")
    print(f"{'='*70}\n")

    character = create_detailed_character()

    # Build context
    final_context, metadata = build_character_context(
        character=character,
        game_context=game_context,
        model=model,
        max_response_tokens=2048
    )

    # Display adaptive strategy
    adaptive = metadata['adaptive_strategy']
    print(f"Adaptive Strategy:")
    print(f"  Memory window: {adaptive['memory_window']} turns")
    print(f"  Summary priority: {adaptive['summary_priority']}")
    print(f"  Context limit: {adaptive['context_limit']:,} tokens")
    print()

    print(f"Relevant character attributes included:")
    if adaptive['relevant_attributes']:
        for attr in adaptive['relevant_attributes']:
            print(f"  + {attr}")
    else:
        print(f"  (Only core attributes - no conditional attributes triggered)")
    print()

    # Context usage
    print(f"Context Usage:")
    print(f"  Total tokens: {metadata['total_tokens']:,}")
    print(f"  Available: {metadata['available_tokens']:,}")
    print(f"  Utilization: {metadata['total_tokens'] / metadata['available_tokens'] * 100:.1f}%")
    print(f"  Truncated: {metadata['was_truncated']}")
    print()

    print(f"Components included: ({len(metadata['components_included'])})")
    for component in metadata['components_included']:
        marker = "[+]"
        if "(trimmed)" in component:
            marker = "[!]"
        print(f"  {marker} {component}")

    if metadata['components_dropped']:
        print(f"\nComponents dropped: ({len(metadata['components_dropped'])})")
        for component in metadata['components_dropped']:
            print(f"  [-] {component}")

    print(f"\nFirst 600 chars of character identity:")
    print("-"*70)
    # Extract character identity from context
    identity_end = final_context.find("\nCurrent location:")
    if identity_end > 0:
        print(final_context[:identity_end][:600] + "...")
    print("-"*70)


def scenario_1_tavern_neutral():
    """Neutral scenario - no special context triggers."""
    return {
        "system_prompt": "You are a narrative AI for a dark fantasy RPG.",
        "location_name": "The Weary Traveler Inn",
        "location_description": (
            "A modest roadside inn with wooden tables and a crackling fireplace. "
            "The common room is dimly lit by oil lamps."
        ),
        "visible_characters": ["Innkeeper", "Traveling Merchant"],
        "working_memory": "Turn 1: You entered the inn.\nTurn 2: You surveyed the room.",
        "short_term_summary": "You just arrived at the inn seeking lodging."
    }


def scenario_2_tavern_food():
    """Food-related scenario - should trigger food preferences."""
    return {
        "system_prompt": "You are a narrative AI for a dark fantasy RPG.",
        "location_name": "The Weary Traveler Inn",
        "location_description": (
            "A modest roadside inn with wooden tables and a crackling fireplace. "
            "The smell of roasted meat and fresh bread fills the air. "
            "The innkeeper is serving meals to hungry travelers."
        ),
        "visible_characters": ["Innkeeper", "Traveling Merchant"],
        "working_memory": (
            "Turn 1: You entered the inn and approached the bar.\n"
            "Turn 2: The innkeeper asked what you'd like to eat.\n"
            "Turn 3: You glanced at the menu board."
        ),
        "short_term_summary": "You just arrived at the inn seeking food and lodging.",
        "action_type": "deciding what to eat"
    }


def scenario_3_romance():
    """Romantic scenario - should trigger attraction preferences."""
    return {
        "system_prompt": "You are a narrative AI for a dark fantasy RPG.",
        "location_name": "The Silver Moon Tavern",
        "location_description": (
            "An upscale tavern with private booths and soft candlelight. "
            "A bard plays gentle music in the corner."
        ),
        "visible_characters": ["Dashing Mercenary Captain", "Innkeeper"],
        "working_memory": (
            "Turn 1: The captain caught your eye across the room.\n"
            "Turn 2: He smiled and gestured to the empty seat at his table.\n"
            "Turn 3: You hesitated, considering your options.\n"
            "Turn 4: He stood and approached you with confidence."
        ),
        "short_term_summary": (
            "A charismatic mercenary captain has shown interest in you. "
            "You're uncertain of his intentions but find him intriguing."
        ),
        "action_type": "responding to romantic advance"
    }


def scenario_4_supernatural():
    """Supernatural scenario - should trigger superstitions."""
    return {
        "system_prompt": "You are a narrative AI for a dark fantasy RPG.",
        "location_name": "Abandoned Shrine",
        "location_description": (
            "An ancient stone shrine covered in strange symbols. "
            "The air feels heavy with an unnatural presence. "
            "Offerings left by travelers lie scattered at the base of a crumbling altar."
        ),
        "visible_characters": ["Hooded Cultist", "Terrified Villager"],
        "working_memory": (
            "Turn 1: You discovered this shrine while tracking your target.\n"
            "Turn 2: A cultist emerged from the shadows, chanting.\n"
            "Turn 3: The villager warned you that speaking certain names summons evil.\n"
            "Turn 4: The cultist began a ritual, drawing symbols in blood."
        ),
        "short_term_summary": (
            "You've stumbled upon a dangerous ritual in progress. "
            "A cultist is attempting to summon something terrible."
        ),
        "action_type": "responding to supernatural threat"
    }


def scenario_5_scholarly():
    """Scholarly scenario - should trigger education details."""
    return {
        "system_prompt": "You are a narrative AI for a dark fantasy RPG.",
        "location_name": "The Grand Library",
        "location_description": (
            "Towering shelves filled with ancient tomes and scrolls. "
            "Scholars huddle over manuscripts by candlelight. "
            "The smell of old parchment and ink fills the air."
        ),
        "visible_characters": ["Master Librarian", "Young Scholar"],
        "working_memory": (
            "Turn 1: You requested access to restricted texts.\n"
            "Turn 2: The librarian questioned your qualifications.\n"
            "Turn 3: You mentioned your knowledge of ancient languages.\n"
            "Turn 4: The scholar offered to vouch for your education."
        ),
        "short_term_summary": (
            "You're trying to gain access to restricted library materials. "
            "Your education level is being questioned."
        ),
        "action_type": "proving scholarly knowledge"
    }


def main():
    """Run all test scenarios."""
    print("="*70)
    print("SITUATIONAL CONTEXT AWARENESS TEST")
    print("="*70)
    print("\nDemonstrates how context adapts to:")
    print("  1. Current situation (triggers relevant character attributes)")
    print("  2. Model size (adjusts memory window: 5, 8, or 10 turns)")
    print("  3. Token limits (prioritizes summaries for small models)")
    print()

    scenarios = [
        ("1. Neutral Context (No Triggers)", scenario_1_tavern_neutral()),
        ("2. Food Context (Triggers Food Preferences)", scenario_2_tavern_food()),
        ("3. Romance Context (Triggers Attraction)", scenario_3_romance()),
        ("4. Supernatural Context (Triggers Superstitions)", scenario_4_supernatural()),
        ("5. Scholarly Context (Triggers Education)", scenario_5_scholarly()),
    ]

    models = [
        "meta-llama/Meta-Llama-3-70B-Instruct",  # 8K - small model
        "mistralai/Mixtral-8x7B-Instruct-v0.1",  # 32K - medium model
    ]

    # Test each scenario with different models
    for scenario_name, game_context in scenarios[:2]:  # Just test first 2 scenarios
        for model in models:
            test_scenario(scenario_name, game_context, model)

    # Show one detailed scenario with all models
    print("\n" + "="*70)
    print("DETAILED COMPARISON: Food Scenario Across All Models")
    print("="*70)

    food_context = scenario_2_tavern_food()
    for model in models + ["claude-3-5-sonnet-20241022"]:  # Add large model
        test_scenario("Food Scenario", food_context, model)

    print("\n" + "="*70)
    print("[SUCCESS] Situational awareness test complete!")
    print("="*70)
    print("\nKey Observations:")
    print("  - Small models (8K): Use 5-turn memory window + HIGH priority summaries")
    print("  - Medium models (32K): Use 8-turn memory window + MEDIUM priority summaries")
    print("  - Large models (200K): Use 10-turn memory window + MEDIUM priority summaries")
    print("  - Food context triggers 'food_preferences' attribute")
    print("  - Neutral context only includes core attributes (saves tokens)")
    print()


if __name__ == "__main__":
    main()
