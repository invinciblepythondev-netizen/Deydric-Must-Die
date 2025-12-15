# LLM Integration Guide

## Overview

The **Deydric Must Die** LLM integration provides a resilient, multi-provider system for generating character actions, planning objectives, and summarizing game events. The system handles dark fantasy content through intelligent provider fallback and includes manual input as a final safety net.

### Key Features

- **Multi-Provider Support**: Claude (Anthropic), OpenAI, AIML API, Together.ai
- **Automatic Fallback**: Seamlessly switches providers on content policy violations
- **Provider-Optimized Prompts**: Different formats for different LLM families
- **Manual Fallback**: Blocking user input with JSON validation when all providers fail
- **Cost Optimization**: Quality-first for critical content, cheap models for routine tasks
- **Content Classification**: 4 intensity levels (MILD → MODERATE → MATURE → UNRESTRICTED)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Game Components                          │
│  (ObjectivePlanner, ActionGenerator, MemorySummarizer)      │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                 UnifiedLLMService                           │
│  • High-level API for all use cases                         │
│  • Automatic fallback to manual input                       │
│  • Provider-specific prompt formatting                      │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
┌───────────┐ ┌──────────┐ ┌────────────┐
│  Action   │ │ Planning │ │Summarize   │
│Generation │ │Provider  │ │Provider    │
└─────┬─────┘ └─────┬────┘ └──────┬─────┘
      │             │              │
      ▼             ▼              ▼
┌─────────────────────────────────────────────────────────────┐
│              ResilientActionGenerator                       │
│  • Tries providers in priority order                        │
│  • Handles content policy violations                        │
│  • Tracks failures and attempts                             │
└────────────────────┬────────────────────────────────────────┘
                     │
     ┌───────────────┼───────────────┬──────────────┐
     ▼               ▼               ▼              ▼
┌─────────┐  ┌──────────┐  ┌─────────────┐  ┌─────────────┐
│ Claude  │  │ OpenAI   │  │ AIML API    │  │ Together.ai │
│ Sonnet  │  │ GPT-4    │  │ Mixtral     │  │ Llama 3     │
│ Haiku   │  │ GPT-3.5  │  │ Mistral     │  │ Mixtral     │
└─────────┘  └──────────┘  └─────────────┘  └─────────────┘
                     │
                     │ (All providers fail)
                     ▼
┌─────────────────────────────────────────────────────────────┐
│           ManualFallbackHandler                             │
│  • Blocks execution waiting for user input                  │
│  • Validates JSON structure                                 │
│  • Provides clear instructions and examples                 │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Purpose |
|-----------|---------|
| **UnifiedLLMService** | High-level API, orchestrates fallback |
| **ResilientActionGenerator** | Provider fallback chain, error handling |
| **LLMProvider** (base) | Abstract interface for all providers |
| **ProviderPromptTemplate** | Format prompts for each provider type |
| **ManualFallbackHandler** | User input collection and validation |
| **LLMServiceFactory** | Provider initialization and caching |

## Use Cases

### 1. Action Generation

**Purpose**: Generate character action options during their turn

**Quality Requirements**: HIGH - needs understanding of character psychology, relationships, and narrative

**Provider Priority**:
1. Claude Sonnet 3.5 (primary - best quality)
2. GPT-4 (fallback - high quality)
3. AIML Mixtral 8x7B (fallback - mature content)
4. Together.ai Llama 3 70B (fallback - unrestricted)

**Usage**:

```python
from services.llm_service import get_unified_llm_service

service = get_unified_llm_service()

character = {
    "name": "Branndic Solt",
    "personality_traits": ["cautious", "analytical"],
    "current_emotional_state": "anxious",
    "motivations_short_term": ["Uncover Deydric's crimes"]
}

context = {
    "action_type": "speak",
    "location_name": "Tavern Common Room",
    "visible_characters": ["Lysa Darnog", "Mable Carptun"],
    "working_memory": "Branndic just discovered suspicious documents...",
    "situation_summary": "Branndic must decide who to trust"
}

# Returns list of action dictionaries
actions = service.generate_actions(
    character=character,
    game_context=context,
    num_options=4
)

# Output format:
# [
#     {
#         "thought": "I need to be careful who I trust...",
#         "speech": "Lysa, may I speak with you privately?",
#         "action": "Branndic gestures toward a quiet corner",
#         "action_type": "speak"
#     },
#     ...
# ]
```

**Cost per call**: $0.001 - $0.003 (depending on context size)

### 2. Objective Planning

**Purpose**: Generate character objectives based on personality and motivations

**Quality Requirements**: HIGH - needs strategic thinking and consistency

**Provider Priority**: Same as action generation

**Usage**:

```python
service = get_unified_llm_service()

character_profile = {
    "name": "Sir Gelarthon Findraell",
    "role_responsibilities": "Knight investigating corruption",
    "personality_traits": ["honorable", "determined"],
    "motivations_short_term": ["Gather evidence"],
    "motivations_long_term": ["Bring Deydric to justice"],
    "backstory": "Once served Deydric loyally..."
}

planning_context = "Character is being initialized. Create 2-4 main objectives."

# Returns objectives data
objectives = service.plan_objectives(
    character_profile=character_profile,
    planning_context=planning_context
)

# Output format:
# {
#     "objectives": [
#         {
#             "description": "Infiltrate Deydric's inner circle",
#             "priority": "high",
#             "success_criteria": "Gain access to private documents",
#             "mood_impact_positive": 10,
#             "mood_impact_negative": -8
#         },
#         ...
#     ]
# }
```

**Cost per call**: $0.001 - $0.002

### 3. Memory Summarization

**Purpose**: Compress turn history into readable summaries

**Quality Requirements**: MEDIUM - needs accuracy but not creativity

**Provider Priority**:
1. Claude Haiku (primary - cheap, good quality)
2. AIML Mistral 7B (fallback - cheapest)
3. GPT-3.5 Turbo (fallback - cheap)

**Usage**:

```python
service = get_unified_llm_service()

turns = [
    {"turn_number": 1, "action_description": "Branndic entered the tavern."},
    {"turn_number": 2, "action_description": "Branndic greeted Mable warmly."},
    {"turn_number": 3, "action_description": "Mable served Branndic ale."},
    {"turn_number": 4, "action_description": "Branndic sat near the fire."}
]

# Returns summary text
summary = service.summarize_memory(
    turns=turns,
    importance="routine"  # or "critical"
)

# Output example:
# "Branndic arrived at the tavern and exchanged pleasantries with
#  Mable the innkeeper, who served him ale. He settled near the
#  fireplace to warm himself."
```

**Cost per call**: $0.0001 - $0.0005 (10x cheaper than action generation)

## Provider Selection Matrix

| Use Case | Primary | Fallback 1 | Fallback 2 | Fallback 3 | Cost Range |
|----------|---------|------------|------------|------------|------------|
| **Action Generation (MILD)** | Claude Sonnet | GPT-4 | AIML Mixtral | Together Llama | $0.001-0.003 |
| **Action Generation (MODERATE)** | Claude Sonnet | GPT-4 | AIML Mixtral | Together Llama | $0.002-0.004 |
| **Action Generation (MATURE)** | AIML Mixtral | Together Llama | Manual Input | - | $0.0005-0.002 |
| **Objective Planning** | Claude Sonnet | GPT-4 | AIML Mixtral | Manual Input | $0.001-0.002 |
| **Memory Summary (Routine)** | Claude Haiku | AIML Mistral | GPT-3.5 | Manual Input | $0.0001-0.0005 |
| **Memory Summary (Critical)** | Claude Sonnet | GPT-4 | AIML Mixtral | Manual Input | $0.001-0.002 |

### Content Intensity Routing

```python
# services/llm/provider_strategy.py defines the routing

def get_provider_for_intensity(intensity: ContentIntensity) -> list:
    """Returns ordered list of providers to try."""

    if intensity == ContentIntensity.MILD:
        return ["anthropic", "openai", "aimlapi", "together_ai"]

    elif intensity == ContentIntensity.MODERATE:
        return ["anthropic", "openai", "aimlapi", "together_ai"]

    elif intensity == ContentIntensity.MATURE:
        # Skip more restrictive providers
        return ["aimlapi", "together_ai"]

    elif intensity == ContentIntensity.UNRESTRICTED:
        # Only most permissive providers
        return ["together_ai", "local_llama"]
```

## Provider-Specific Prompts

Different LLM families perform better with different prompt structures. The system automatically adapts prompts based on the provider.

### Claude (XML Format)

**Best for**: Detailed instructions, hierarchical context

```xml
<context>
<character>
Name: Branndic Solt
Traits: cautious, analytical
State: anxious
</character>

<location>
The Sleeping Lion Tavern - A dim common room
Visible: Lysa Darnog, Mable Carptun
</location>

<situation>
Branndic just discovered suspicious documents implicating Lord Deydric.
</situation>
</context>

<task>
Generate 4 action options for Branndic.
Consider: personality, emotional state, relationships, objectives.
</task>

<format>
Return valid JSON array:
[
  {
    "thought": "Character's private thinking",
    "speech": "What the character says (or null)",
    "action": "Physical action description",
    "action_type": "speak|move|interact|think"
  }
]
</format>
```

### OpenAI (Markdown + JSON)

**Best for**: Clear sections, JSON examples

```markdown
# Character Context

**Name**: Branndic Solt
**Personality**: cautious, analytical
**Emotional State**: anxious

# Current Situation

**Location**: The Sleeping Lion Tavern
**Visible Characters**: Lysa Darnog, Mable Carptun
**Context**: Branndic just discovered suspicious documents implicating Lord Deydric

# Task

Generate 4 action options for Branndic that reflect his cautious personality.

# Expected Format

```json
[
  {
    "thought": "Character's private thinking",
    "speech": "What the character says (or null)",
    "action": "Physical action description",
    "action_type": "speak|move|interact|think"
  }
]
```
```

### Open Models (Simplified)

**Best for**: Direct, minimal formatting

```
Character: Branndic Solt (cautious, analytical, anxious)
Location: The Sleeping Lion Tavern
Present: Lysa Darnog, Mable Carptun
Situation: Branndic just discovered documents implicating Lord Deydric.

Generate 4 actions as JSON array with: thought, speech, action, action_type
```

## Manual Fallback System

When all LLM providers fail (API errors, content policy, etc.), the system falls back to **blocking user input**.

### How It Works

1. **Detection**: `AllProvidersFailedError` is caught by `UnifiedLLMService`
2. **User Prompt**: Clear instructions displayed in console
3. **Input Collection**: Multi-line JSON input (end with `END` on new line)
4. **Validation**: JSON schema validation ensures correct structure
5. **Retry Loop**: If invalid, user is prompted again
6. **Return**: Validated data returned to game engine

### Example Session

```
======================================================================
ALL LLM PROVIDERS FAILED
======================================================================
Could not generate actions via API.
Attempted providers: anthropic, openai, aimlapi, together_ai

Please provide actions manually.

Character: Branndic Solt
Context: Branndic is in the tavern and must decide who to trust
Number of options needed: 2

Required format (JSON array):
[
  {
    "thought": "Character's private thinking",
    "speech": "What they say (or null)",
    "action": "Physical action description",
    "action_type": "speak|move|interact|attack|observe|wait|think"
  }
]

Enter JSON (type END on new line when done):
> [
>   {
>     "thought": "I need to be careful who I trust with this information",
>     "speech": "Lysa, may I speak with you privately?",
>     "action": "Branndic gestures toward a quiet corner",
>     "action_type": "speak"
>   },
>   {
>     "thought": "Perhaps I should observe the room first",
>     "speech": null,
>     "action": "Branndic scans the tavern patrons carefully",
>     "action_type": "observe"
>   }
> ]
> END

[SUCCESS] Manual input validated.
```

### Validation Rules

**Actions**:
- Must be JSON array
- Each item must have: `thought`, `action`, `action_type`
- `speech` is optional (can be null)
- `action_type` must be one of: speak, move, interact, attack, observe, wait, think

**Objectives**:
- Must be JSON object with `objectives` array
- Each objective must have: `description`, `priority`, `success_criteria`
- `priority` must be: high, medium, or low

**Summaries**:
- Must be plain text string
- Minimum 50 characters
- Should be narrative prose, not bullet points

## Configuration

### Environment Variables

Required in `.env`:

```bash
# Anthropic (Claude)
ANTHROPIC_API_KEY=sk-ant-api03-...

# OpenAI
OPENAI_API_KEY=sk-proj-...

# AIML API (Mixtral, Mistral, Llama)
AIMLAPI_API_KEY=...

# Together.ai (open-source models)
TOGETHER_API_KEY=...
```

### Provider Initialization

Providers are auto-initialized in `services/llm_service.py`:

```python
# LLMServiceFactory.__init__() attempts to initialize all providers
# If API key is missing, that provider is skipped (not an error)

factory = get_llm_service_factory()
print(factory._cached_providers.keys())
# Output: dict_keys(['anthropic', 'openai', 'aimlapi', 'together_ai'])
```

**Minimum Requirements**:
- At least 1 provider must initialize successfully
- Recommended: 2+ providers for fallback redundancy
- For mature content: AIML or Together.ai required

### Customizing Provider Strategy

Edit `services/llm/provider_strategy.py`:

```python
class ProviderStrategy:
    """Customize provider selection logic."""

    # Change priority order
    DEFAULT_PRIORITY = [
        "anthropic",     # Your preferred primary
        "openai",        # Fallback 1
        "aimlapi",       # Fallback 2
        "together_ai"    # Fallback 3
    ]

    # Adjust content intensity thresholds
    @staticmethod
    def classify_content_intensity(context: dict) -> ContentIntensity:
        # Your custom logic here
        if context.get("has_wounds") and context.get("wound_severity") == "critical":
            return ContentIntensity.MATURE
        # ...
```

## Testing

### Unit Tests (No API Calls)

Test individual components without hitting APIs:

```bash
# Test provider interfaces
pytest tests/test_providers.py

# Test prompt templates
pytest tests/test_prompt_templates.py

# Test manual fallback validation
pytest tests/test_manual_fallback.py
```

### Integration Tests (Live API Calls)

Test with real LLM providers:

```bash
# Phase 1: Together.ai provider
python scripts/test_phase1_together_ai.py

# Phase 2: Manual fallback
python scripts/test_phase2_manual_fallback.py

# Phase 3: Prompt templates
python scripts/test_phase3_prompt_templates.py

# Phase 4: LLM service
python scripts/test_phase4_llm_service.py

# Phase 5: ObjectivePlanner integration
python scripts/test_phase5_objective_planner.py

# Phase 6: Comprehensive integration
python scripts/test_phase6_comprehensive.py
```

**Budget-Conscious Testing**:
- Phase 6 comprehensive test costs ~$0.003
- Run full suite: ~$0.005 total
- Well within development budget

### Testing Manual Fallback

To force manual fallback for testing:

```python
# Temporarily disable all providers
import os
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["OPENAI_API_KEY"] = ""
os.environ["AIMLAPI_API_KEY"] = ""
os.environ["TOGETHER_API_KEY"] = ""

# Or use factory method
from services.llm_service import get_unified_llm_service
service = get_unified_llm_service()
service.factory._cached_providers.clear()  # Remove all providers

# Now any call will trigger manual fallback
actions = service.generate_actions(character, context)
# >> Prompts for manual input
```

## Troubleshooting

### Problem: "No LLM providers could be initialized"

**Cause**: No valid API keys in `.env`

**Solution**:
1. Check `.env` file exists in project root
2. Verify at least one API key is set correctly
3. Restart application to reload environment

### Problem: "AllProvidersFailedError" on MILD content

**Cause**: API keys invalid or rate limits hit

**Solution**:
1. Check API key validity (test with curl)
2. Check account billing status
3. Wait 60 seconds and retry (rate limit reset)
4. Check provider status pages

### Problem: Manual fallback prompt appears for safe content

**Cause**: Network issues or all providers down

**Solution**:
1. Check internet connection
2. Verify provider API status:
   - https://status.anthropic.com
   - https://status.openai.com
   - Check AIML/Together.ai dashboards
3. Use manual input as temporary workaround
4. File bug report with error logs

### Problem: JSON validation fails in manual input

**Cause**: Incorrect JSON syntax

**Common Errors**:

```python
# Missing quotes around strings
{thought: "text"}  # ❌ Wrong
{"thought": "text"}  # ✓ Correct

# Using single quotes
{'thought': 'text'}  # ❌ Wrong
{"thought": "text"}  # ✓ Correct

# Trailing commas
{"thought": "text",}  # ❌ Wrong
{"thought": "text"}   # ✓ Correct

# Unescaped quotes in strings
{"speech": "He said "hello""}  # ❌ Wrong
{"speech": "He said \"hello\""}  # ✓ Correct
```

**Solution**: Use JSON validator before submitting (e.g., jsonlint.com)

### Problem: Inconsistent action quality between providers

**Cause**: Different models have different capabilities

**Solution**:
1. Use `ProviderPromptTemplate` for provider-optimized prompts
2. For critical content, prefer Claude Sonnet or GPT-4
3. For routine content, cheaper models are fine
4. Monitor output quality and adjust strategy

### Problem: High API costs

**Cause**: Using expensive models for routine tasks

**Solution**:
1. Ensure summarization uses Haiku/Mistral (check `get_summarization_provider`)
2. Reduce context size (trim old memories)
3. Cache action options for similar contexts
4. Use Together.ai for mature content (cheaper than Claude/GPT-4)

### Problem: Content policy violations on legitimate dark fantasy

**Cause**: Provider's content policy too restrictive

**Solution**:
1. Verify content intensity classification is correct
2. Ensure fallback chain includes permissive providers (AIML, Together.ai)
3. Rephrase prompts to be less explicit (focus on narrative consequences, not graphic details)
4. For truly unrestricted content, use local models or Together.ai

## Performance Tips

### 1. Provider Caching

Providers are initialized once and cached:

```python
# Good - reuses cached instance
service = get_unified_llm_service()  # Singleton

# Bad - creates new instances (not actually possible, but for illustration)
# Don't call LLMServiceFactory() directly multiple times
```

### 2. Prompt Optimization

Minimize token usage:

```python
# Bad - includes unnecessary detail
context = {
    "working_memory": [last_50_turns],  # Too much
    "full_backstory": character.backstory  # 5000 tokens
}

# Good - trim to essentials
context = {
    "working_memory": [last_10_turns],  # Just enough
    "backstory_summary": character.backstory[:500]  # Key points only
}
```

### 3. Use Case Routing

Use appropriate models:

```python
# Bad - using expensive model for simple task
expensive_provider = factory.get_action_generator()
summary = expensive_provider.generate(summary_prompt)  # $0.003

# Good - using cheap model for summarization
cheap_provider = factory.get_summarization_provider()
summary = cheap_provider.generate(summary_prompt)  # $0.0003
```

### 4. Batch Operations

When possible, batch multiple requests:

```python
# Bad - 4 separate API calls
for character in characters:
    actions = service.generate_actions(character, context)

# Better - combine into single prompt (if provider supports it)
all_actions = service.generate_actions_batch(characters, context)
```

### 5. Content Classification

Classify content early to skip expensive providers:

```python
# Early classification saves API calls
intensity = classify_content_intensity(context)

if intensity == ContentIntensity.MATURE:
    # Skip Claude/OpenAI, go straight to permissive providers
    providers = ["aimlapi", "together_ai"]
else:
    providers = ["anthropic", "openai", "aimlapi", "together_ai"]
```

## Examples

### Complete Workflow: Character Takes Turn

```python
from services.llm_service import get_unified_llm_service
from services.game_engine import GameEngine

# Initialize
service = get_unified_llm_service()
game = GameEngine(game_id="uuid-here")

# Get character whose turn it is
character = game.get_current_character()

# Assemble context
context = game.assemble_context(character)

# Generate action options via LLM
try:
    actions = service.generate_actions(
        character=character,
        game_context=context,
        num_options=4
    )
except Exception as e:
    logger.error(f"Action generation failed: {e}")
    # Manual fallback happens automatically inside service
    actions = service.generate_actions(character, context, num_options=4)

# Present to player (or AI picks)
if character.is_player:
    selected = game.prompt_player_choice(actions)
else:
    selected = game.ai_pick_action(actions)

# Execute
game.execute_action(character, selected)
```

### Custom Provider Strategy

```python
from services.llm.provider_strategy import ProviderStrategy, ContentIntensity

class MyCustomStrategy(ProviderStrategy):
    """Custom strategy that prefers OpenAI."""

    DEFAULT_PRIORITY = [
        "openai",        # My preferred primary
        "anthropic",     # Fallback
        "aimlapi",
        "together_ai"
    ]

    @staticmethod
    def classify_content_intensity(context: dict) -> ContentIntensity:
        """More lenient classification."""
        if context.get("combat") and context.get("fatal_wound"):
            return ContentIntensity.MODERATE  # Not MATURE
        return ContentIntensity.MILD

# Use in factory
from services.llm_service import LLMServiceFactory
factory = LLMServiceFactory()
factory.strategy = MyCustomStrategy()
```

### Monitoring Costs

```python
import logging

# Enable cost tracking
logging.basicConfig(level=logging.INFO)

# Calls will log token usage
service = get_unified_llm_service()
actions = service.generate_actions(character, context)

# Output:
# INFO:services.llm.claude:Prompt tokens: 2500, Completion tokens: 450
# INFO:services.llm.claude:Estimated cost: $0.0023
```

## Best Practices

### 1. Always Use UnifiedLLMService

```python
# Good
from services.llm_service import get_unified_llm_service
service = get_unified_llm_service()
actions = service.generate_actions(character, context)

# Bad - no fallback protection
from services.llm.claude import ClaudeProvider
provider = ClaudeProvider()
response = provider.generate(prompt)  # May fail with no fallback
```

### 2. Classify Content Accurately

```python
# Good - accurate classification
context["content_intensity"] = classify_content_intensity({
    "combat": True,
    "wound_severity": "critical",
    "graphic_description": False
})
# Result: MODERATE (appropriate)

# Bad - over-classification wastes money on expensive providers
context["content_intensity"] = ContentIntensity.UNRESTRICTED
# Forces use of expensive Together.ai when Claude could handle it
```

### 3. Handle Manual Fallback Gracefully

```python
# Good - provide context to user
print(f"\n{character.name} is taking their turn...")
print(f"Location: {context['location_name']}")
print(f"Situation: {context['situation_summary']}")
actions = service.generate_actions(character, context)
# If manual fallback triggers, user has context

# Bad - no context
actions = service.generate_actions(character, context)
# User sees manual prompt with no game state context
```

### 4. Test with Budget Limits

```python
# Good - run tests with cost tracking
python scripts/test_phase6_comprehensive.py
# Output shows: "Estimated cost: $0.0034"

# Set budget alerts
if total_cost > 5.00:
    raise BudgetExceededError("API costs exceeded $5 limit")
```

### 5. Log Provider Failures

```python
# Good - helps debug provider issues
import logging
logging.basicConfig(level=logging.WARNING)

# Now provider failures are logged:
# WARNING:services.llm.resilient_generator:Provider 'anthropic' failed: ContentPolicyError
# INFO:services.llm.resilient_generator:Trying next provider: openai
```

## API Reference

### UnifiedLLMService

```python
class UnifiedLLMService:
    """High-level LLM service with automatic fallback."""

    def generate_actions(
        self,
        character: Dict,
        game_context: Dict,
        num_options: int = 4
    ) -> list:
        """Generate character actions.

        Args:
            character: Character profile dict
            game_context: Game state and context
            num_options: Number of actions to generate

        Returns:
            List of action dictionaries

        Raises:
            Never - falls back to manual input on failure
        """

    def plan_objectives(
        self,
        character_profile: Dict,
        planning_context: str
    ) -> Dict:
        """Plan character objectives.

        Args:
            character_profile: Character profile dict
            planning_context: Planning context string

        Returns:
            Objectives data dictionary

        Raises:
            Never - falls back to manual input on failure
        """

    def summarize_memory(
        self,
        turns: list,
        importance: str = "routine"
    ) -> str:
        """Summarize turn history.

        Args:
            turns: List of turn dictionaries
            importance: "routine" or "critical"

        Returns:
            Summary text string

        Raises:
            Never - falls back to manual input on failure
        """
```

### ManualFallbackHandler

```python
class ManualFallbackHandler:
    """Handles manual input when LLM providers fail."""

    @staticmethod
    def prompt_for_actions(
        character_name: str,
        context_summary: str,
        num_options: int,
        attempted_providers: list
    ) -> list:
        """Prompt user for character actions. BLOCKS until valid input.

        Args:
            character_name: Character taking action
            context_summary: Current game situation
            num_options: Number of actions needed
            attempted_providers: List of providers that failed

        Returns:
            List of validated action dictionaries
        """

    @staticmethod
    def prompt_for_objectives(
        character_name: str,
        character_profile: Dict,
        attempted_providers: list
    ) -> Dict:
        """Prompt user for character objectives. BLOCKS until valid input."""

    @staticmethod
    def prompt_for_summary(
        turns: list,
        attempted_providers: list
    ) -> str:
        """Prompt user for memory summary. BLOCKS until valid input."""
```

### ProviderPromptTemplate

```python
class ProviderPromptTemplate:
    """Format prompts for different providers."""

    @classmethod
    def format_action_generation_prompt(
        cls,
        provider: str,
        character_context: str,
        num_options: int
    ) -> str:
        """Format action generation prompt for provider."""

    @classmethod
    def format_objective_planning_prompt(
        cls,
        provider: str,
        character_profile: Dict,
        planning_context: str
    ) -> str:
        """Format objective planning prompt for provider."""

    @classmethod
    def format_memory_summary_prompt(
        cls,
        provider: str,
        turns: list,
        importance: str
    ) -> str:
        """Format memory summary prompt for provider."""
```

## Changelog

### Phase 6 (2024) - Comprehensive Integration
- ✅ All integration tests passing
- ✅ Tested with live API calls across all providers
- ✅ Budget tracking confirmed under $5 limit

### Phase 5 (2024) - ObjectivePlanner Integration
- ✅ Migrated ObjectivePlanner to UnifiedLLMService
- ✅ Maintained backward compatibility

### Phase 4 (2024) - Unified Service
- ✅ Created UnifiedLLMService
- ✅ Integrated manual fallback into service layer
- ✅ Added cost-optimized summarization routing

### Phase 3 (2024) - Prompt Templates
- ✅ Implemented provider-specific formatting
- ✅ Claude XML format
- ✅ OpenAI Markdown format
- ✅ Open model simplified format

### Phase 2 (2024) - Manual Fallback
- ✅ Blocking user input system
- ✅ JSON schema validation
- ✅ Support for all use cases

### Phase 1 (2024) - Together.ai Provider
- ✅ Added Together.ai provider
- ✅ Support for Llama 3 70B/405B and Mixtral
- ✅ Integrated into fallback chain

### Phase 0 (2024) - Initial Infrastructure
- ✅ Provider abstraction layer
- ✅ ResilientActionGenerator
- ✅ Claude, OpenAI, AIML providers
- ✅ Content intensity classification
