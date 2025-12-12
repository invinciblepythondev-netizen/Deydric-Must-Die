"""
Phase 3 Test: Provider-Specific Prompt Templates

Tests the prompt template system for all providers and use cases.
No API calls - just template generation.

Budget: Part of $5 total budget (no API calls = $0.00).
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.llm.prompt_templates import ProviderPromptTemplate, PromptFormat


def test_provider_format_mapping():
    """Test that all providers have format mappings."""
    print("\n" + "="*70)
    print("TEST 1: Provider Format Mapping")
    print("="*70)

    providers = ["anthropic", "openai", "aimlapi", "together_ai", "local"]

    for provider in providers:
        format_style = ProviderPromptTemplate.get_format_for_provider(provider)
        print(f"[PASS] {provider} -> {format_style.value}")

    return True


def test_action_generation_templates():
    """Test action generation templates for all providers."""
    print("\n" + "="*70)
    print("TEST 2: Action Generation Templates")
    print("="*70)

    providers = ["anthropic", "openai", "aimlapi"]
    character_context = "Character: Test Character\nLocation: Tavern"
    num_options = 3

    for provider in providers:
        prompt = ProviderPromptTemplate.format_action_generation_prompt(
            provider=provider,
            character_context=character_context,
            num_options=num_options
        )

        # Verify prompt is generated
        if not prompt or len(prompt) < 50:
            print(f"[FAIL] {provider}: Prompt too short or empty")
            return False

        # Verify it contains context
        if character_context not in prompt:
            print(f"[FAIL] {provider}: Context not included")
            return False

        # Verify it mentions number of options
        if str(num_options) not in prompt:
            print(f"[FAIL] {provider}: Number of options not specified")
            return False

        print(f"[PASS] {provider}: {len(prompt)} chars")

    return True


def test_objective_planning_templates():
    """Test objective planning templates for all providers."""
    print("\n" + "="*70)
    print("TEST 3: Objective Planning Templates")
    print("="*70)

    providers = ["anthropic", "openai", "aimlapi"]
    character_profile = {
        "name": "Test Character",
        "role_responsibilities": "Guard",
        "personality_traits": ["brave", "loyal"],
        "motivations_short_term": ["Protect the castle"],
        "motivations_long_term": ["Become captain of the guard"],
        "backstory": "A young guard with aspirations."
    }
    planning_context = "New threat detected at the gates."

    for provider in providers:
        prompt = ProviderPromptTemplate.format_objective_planning_prompt(
            provider=provider,
            character_profile=character_profile,
            planning_context=planning_context
        )

        # Verify prompt is generated
        if not prompt or len(prompt) < 50:
            print(f"[FAIL] {provider}: Prompt too short or empty")
            return False

        # Verify it contains character name
        if character_profile["name"] not in prompt:
            print(f"[FAIL] {provider}: Character name not included")
            return False

        # Verify it contains context
        if planning_context not in prompt:
            print(f"[FAIL] {provider}: Context not included")
            return False

        print(f"[PASS] {provider}: {len(prompt)} chars")

    return True


def test_memory_summary_templates():
    """Test memory summarization templates for all providers."""
    print("\n" + "="*70)
    print("TEST 4: Memory Summary Templates")
    print("="*70)

    providers = ["anthropic", "openai", "aimlapi"]
    turns = [
        {"turn_number": 1, "action_description": "Character entered the tavern."},
        {"turn_number": 2, "action_description": "Character ordered ale."},
        {"turn_number": 3, "action_description": "Character sat down."}
    ]
    importance = "routine"

    for provider in providers:
        prompt = ProviderPromptTemplate.format_memory_summary_prompt(
            provider=provider,
            turns=turns,
            importance=importance
        )

        # Verify prompt is generated
        if not prompt or len(prompt) < 50:
            print(f"[FAIL] {provider}: Prompt too short or empty")
            return False

        # Verify it contains turn data
        if "tavern" not in prompt:
            print(f"[FAIL] {provider}: Turn data not included")
            return False

        print(f"[PASS] {provider}: {len(prompt)} chars")

    return True


def test_claude_xml_format():
    """Test that Claude prompts use XML structure."""
    print("\n" + "="*70)
    print("TEST 5: Claude XML Format")
    print("="*70)

    character_context = "Test context"
    num_options = 3

    prompt = ProviderPromptTemplate.format_action_generation_prompt(
        provider="anthropic",
        character_context=character_context,
        num_options=num_options
    )

    # Check for XML tags
    xml_tags = ["<context>", "</context>", "<task>", "</task>", "<format>", "</format>"]

    for tag in xml_tags:
        if tag not in prompt:
            print(f"[FAIL] Missing XML tag: {tag}")
            return False

    print("[PASS] All XML tags present")
    return True


def test_openai_markdown_format():
    """Test that OpenAI prompts use Markdown structure."""
    print("\n" + "="*70)
    print("TEST 6: OpenAI Markdown Format")
    print("="*70)

    character_context = "Test context"
    num_options = 3

    prompt = ProviderPromptTemplate.format_action_generation_prompt(
        provider="openai",
        character_context=character_context,
        num_options=num_options
    )

    # Check for Markdown headers
    markdown_headers = ["# ", "## ", "```json"]

    for header in markdown_headers:
        if header not in prompt:
            print(f"[FAIL] Missing Markdown header: {header}")
            return False

    print("[PASS] All Markdown headers present")
    return True


def test_template_length_reasonable():
    """Test that templates are reasonable length (not too long/short)."""
    print("\n" + "="*70)
    print("TEST 7: Template Length")
    print("="*70)

    character_context = "A" * 1000  # 1000 chars
    num_options = 4

    providers = ["anthropic", "openai", "aimlapi"]

    for provider in providers:
        prompt = ProviderPromptTemplate.format_action_generation_prompt(
            provider=provider,
            character_context=character_context,
            num_options=num_options
        )

        # Should be longer than just context (has instructions)
        if len(prompt) <= len(character_context):
            print(f"[FAIL] {provider}: Template not adding instructions")
            return False

        # Should not be excessively long
        if len(prompt) > len(character_context) + 2000:
            print(f"[FAIL] {provider}: Template too verbose ({len(prompt)} chars)")
            return False

        print(f"[PASS] {provider}: {len(prompt)} chars (reasonable)")

    return True


if __name__ == "__main__":
    print("\n" + "="*70)
    print("PHASE 3: PROMPT TEMPLATES TEST SUITE")
    print("="*70)
    print("\nTests template generation for all providers and use cases.")

    results = []

    # Run tests
    results.append(("Provider Format Mapping", test_provider_format_mapping()))
    results.append(("Action Templates", test_action_generation_templates()))
    results.append(("Planning Templates", test_objective_planning_templates()))
    results.append(("Summary Templates", test_memory_summary_templates()))
    results.append(("Claude XML Format", test_claude_xml_format()))
    results.append(("OpenAI Markdown Format", test_openai_markdown_format()))
    results.append(("Template Length", test_template_length_reasonable()))

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
    print("API calls: 0 (template generation only)")
    print("Cost: $0.00")
    print("Remaining budget: ~$4.9995")

    if passed_count == len(results):
        print("\n[PASS] PHASE 3 COMPLETE!")
        print("\nPrompt templates are ready for all providers and use cases.")
        sys.exit(0)
    else:
        print("\n[FAIL] PHASE 3 FAILED - Fix issues before proceeding")
        sys.exit(1)
