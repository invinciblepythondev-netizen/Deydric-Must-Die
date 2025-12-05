# Context Management Guide

## Overview

Different LLM models have vastly different context windows, and your game generates rich context (10,000+ tokens). The system automatically adapts context to each model's capacity through:

1. **Situational Awareness** - Includes only relevant character attributes
2. **Adaptive Memory Windows** - 5/8/10 turns based on model size
3. **Priority-Based Truncation** - Intelligently drops low-priority content
4. **Dynamic Summary Elevation** - Summaries become more important for small models

### Model Context Limits

| Model | Context Window | Game Context Needs |
|-------|----------------|-------------------|
| Llama 3 70B | 8K tokens | 10K+ tokens |
| GPT-4 | 8K-32K tokens | 10K+ tokens |
| Mixtral 8x7B | 32K tokens | 10K+ tokens |
| GPT-4 Turbo | 128K tokens | 10K+ tokens |
| Claude 3.5 Sonnet | 200K tokens | 10K+ tokens |

Without intelligent management:
- ❌ Request fails with "context too large"
- ❌ Provider truncates randomly, breaking meaning
- ❌ Model misinterprets incomplete information

---

## Situational Awareness

### Core Principle

**Always include:**
- Character objectives
- Appearance & clothing
- Items/inventory
- Stance
- Physical/emotional state
- Personality traits

**Conditionally include (only when relevant):**
- Food preferences → when eating, at tavern, cooking
- Clothing preferences → when shopping, discussing fashion
- Hobbies → during leisure time
- Superstitions → in supernatural contexts
- Attraction types → in romantic situations
- Education details → in scholarly contexts
- Social class details → in political/social contexts

### How Relevance Detection Works

The system scans game context for trigger words:

```python
# Example: Food preferences
food_triggers = ['eat', 'food', 'meal', 'cook', 'drink', 'tavern', 'kitchen', 'hungry']

# Scans these fields:
- action_type (e.g., "deciding what to eat")
- location_description (e.g., "smell of roasted meat")
- working_memory (e.g., "innkeeper asked what you'd like")
```

**Example Results:**

**Neutral Context (no triggers):**
- Character Identity: **197 tokens**
- Includes: name, appearance, clothing, stance, objectives, personality
- Excludes: food preferences, hobbies, etc.

**Food Context (triggers detected):**
- Character Identity: **246 tokens**
- Includes: everything above PLUS food preferences
- Token cost: +49 tokens

**Savings:** 30-43% token reduction in irrelevant contexts!

### Relevance Triggers Reference

| Attribute | Trigger Words | Use Cases |
|-----------|--------------|-----------|
| **Food Preferences** | eat, food, meal, cook, drink, tavern, kitchen, hungry | Ordering food, discussing meals, shopping for provisions |
| **Clothing Preferences** | shop, tailor, merchant, wear, dress, appearance, clothing | Shopping, fashion discussion, formal events |
| **Hobbies** | leisure, free time, hobby, pastime, entertainment | Free time activities, socializing |
| **Superstitions** | supernatural, curse, blessing, ritual, omen, magic | Supernatural events, rituals, omens |
| **Attraction Types** | romance, attraction, flirt, court, seduce, intimate | Romantic situations, courtship |
| **Education Details** | study, knowledge, library, scholar, academic, learn, teach | Scholarly discussions, learning |
| **Social Class** | noble, lord, peasant, social, hierarchy, status, class | Political contexts, social events |

---

## Adaptive Memory Windows

Memory window size adapts to model capacity:

| Model Context Limit | Memory Window | Summary Priority | Reasoning |
|---------------------|---------------|------------------|-----------|
| ≤16K (8K-16K) | **5 turns** | HIGH | Small models need concise context |
| 16K-64K | **8 turns** | MEDIUM | Medium models can handle more |
| >64K (128K-200K) | **10 turns** | MEDIUM | Large models use full window |

**Example:**

**Small Model (Llama 3 70B, 8K context):**
```python
memory_window = 5 turns
summary_priority = HIGH  # Summaries more important than full history
```

**Large Model (Claude Sonnet, 200K context):**
```python
memory_window = 10 turns
summary_priority = MEDIUM  # Full history preferred
```

**Key Insight:** Small models rely more on summaries; large models use full turn-by-turn history.

---

## Priority System

Context components are prioritized for intelligent truncation:

| Priority | Description | Examples | Can Drop? |
|----------|-------------|----------|-----------|
| **CRITICAL** | Must always include | Character identity, current situation | ❌ Never |
| **HIGH** | Very important | Working memory, relationships, wounds | ⚠️ Only if required |
| **MEDIUM** | Useful context | Session summaries, inventory | ✅ Yes |
| **LOW** | Nice to have | Long-term memories | ✅ Yes |
| **OPTIONAL** | Flavor text | Extended backstory | ✅ First to drop |

### Priority Hierarchy by Model Size

**Small Model (8K):**
```
1. CRITICAL: Character identity, current situation (always)
2. HIGH: Working memory (5 turns), relationships, wounds, summaries
3. MEDIUM: Long-term memories
4. OPTIONAL: Extended backstory (dropped)
```

**Large Model (200K):**
```
1. CRITICAL: Character identity, current situation (always)
2. HIGH: Working memory (10 turns), relationships, wounds
3. MEDIUM: Summaries, long-term memories
4. OPTIONAL: Extended backstory (included)
```

---

## Model-Specific Behavior

### Small Window Models (8K tokens)

**Example: Llama 3 70B**

Available context: ~6,000 tokens (8K - 2K response buffer)

**Typical fit:**
- ✅ Character identity (200 tokens) - relevant attributes only
- ✅ Current situation (300 tokens)
- ✅ Working memory - 5 turns (1,750 tokens)
- ✅ Relationships (800 tokens)
- ✅ Character wounds/inventory (400 tokens)
- ✅ Session summary - FULL (2,000 tokens) - elevated priority
- ❌ Long-term memories - DROPPED
- ❌ Extended backstory - DROPPED

**Result:** ~5,450 tokens of critical context

### Medium Window Models (32K tokens)

**Example: Mixtral 8x7B**

Available context: ~27,000 tokens (32K - 5K buffer)

**Typical fit:**
- ✅ Character identity (250 tokens) - some conditional attributes
- ✅ Current situation (300 tokens)
- ✅ Working memory - 8 turns (2,800 tokens)
- ✅ Relationships - full (1,500 tokens)
- ✅ Character wounds/inventory (400 tokens)
- ✅ Session summary - full (2,000 tokens)
- ✅ Long-term memories - full (5,000 tokens)
- ✅ Extended backstory - partial (2,000 tokens)

**Result:** ~14,250 tokens - all important context fits!

### Large Window Models (128K+ tokens)

**Example: Claude 3.5 Sonnet, GPT-4 Turbo**

Available context: 100,000+ tokens

**Result:** Everything fits with room to spare! Even entire session history can be included.

---

## Usage Examples

### Automatic Usage (Recommended)

```python
from services.llm.resilient_generator import ResilientActionGenerator

generator = ResilientActionGenerator()

# Context automatically adapts based on situation and model
actions = generator.generate_action_options(
    character=character_profile,
    context=game_context,
    num_options=4
)
```

### Manual Usage

```python
from services.context_manager import build_character_context

final_context, metadata = build_character_context(
    character=character_profile,
    game_context=game_context,
    model="meta-llama/Meta-Llama-3-70B-Instruct"
)

# Inspect what was included/dropped
print(f"Memory window: {metadata['adaptive_strategy']['memory_window']}")
# Output: 5

print(f"Relevant attributes: {metadata['adaptive_strategy']['relevant_attributes']}")
# Output: ['food_preferences'] (if food context detected)

print(f"Summary priority: {metadata['adaptive_strategy']['summary_priority']}")
# Output: 'HIGH'

print(f"Total tokens: {metadata['total_tokens']}")
# Output: 5450

print(f"Was truncated: {metadata['was_truncated']}")
# Output: True

print(f"Components dropped: {metadata['components_dropped']}")
# Output: ['long_term_memories', 'extended_backstory']
```

---

## Token Optimization Results

### Neutral Context (No Triggers)
- **Before:** 350 tokens (all attributes)
- **After:** 197 tokens (core only)
- **Savings:** 153 tokens (43% reduction)

### Food Context (Food Triggers Detected)
- **Before:** 350 tokens
- **After:** 246 tokens (core + food_preferences)
- **Savings:** 104 tokens (30% reduction)

### Small Model (8K) Budget Comparison

**Traditional Approach:**
- 10-turn memory: 3,500 tokens
- All attributes: 350 tokens
- Total: ~5,450 tokens (tight fit)

**Situational Approach:**
- 5-turn memory: 1,750 tokens
- Relevant attributes: 200 tokens
- Total: ~4,550 tokens
- **Savings:** 900 tokens (16% reduction)

---

## Testing

### Test Script

Run the test suite to see situational awareness in action:

```bash
python scripts/test_situational_context.py
```

**Expected output:**
- Demonstrates neutral vs triggered contexts
- Shows different memory windows per model size
- Displays token optimization results
- Confirms relevance detection works

### Manual Testing

```python
from services.context_manager import build_character_context

# Test with neutral context
game_context_neutral = {
    "action_type": "observe",
    "location_description": "A dimly lit room."
}

context, meta = build_character_context(
    character=character,
    game_context=game_context_neutral,
    model="meta-llama/Meta-Llama-3-70B-Instruct"
)

print(f"Neutral - Relevant: {meta['adaptive_strategy']['relevant_attributes']}")
# Output: []

# Test with food context
game_context_food = {
    "action_type": "deciding what to eat",
    "location_description": "The tavern smells of roasted meat."
}

context, meta = build_character_context(
    character=character,
    game_context=game_context_food,
    model="meta-llama/Meta-Llama-3-70B-Instruct"
)

print(f"Food - Relevant: {meta['adaptive_strategy']['relevant_attributes']}")
# Output: ['food_preferences']
```

---

## Implementation Details

### Adding New Conditional Attributes

To add a new conditional attribute:

**1. Update relevance detection** in `services/context_manager.py`:
```python
def _detect_context_relevance(character, game_context):
    relevance = {
        # ...existing...
        "new_attribute": False
    }

    new_triggers = ['trigger1', 'trigger2']
    if any(trigger in action_type or trigger in location_desc
           for trigger in new_triggers):
        relevance["new_attribute"] = True

    return relevance
```

**2. Update character identity builder:**
```python
def _build_dynamic_character_identity(character, relevance):
    parts = [...]

    if relevance.get("new_attribute") and character.get('new_field'):
        parts.append(f"New attribute: {character.get('new_field')}")

    return "\n".join(parts)
```

### Adjusting Memory Windows

To change memory window thresholds:

```python
def _get_adaptive_memory_window(model: str) -> int:
    context_limit = ModelContextLimits.get_limit(model)

    # Adjust thresholds as needed
    if context_limit <= 8192:     # Very small
        return 3
    elif context_limit <= 16384:  # Small
        return 5
    elif context_limit <= 65536:  # Medium
        return 8
    else:                          # Large
        return 10
```

### Debugging Relevance Detection

Add logging to see what's being detected:

```python
relevance = _detect_context_relevance(character, game_context)
logger.debug(f"Relevance: {relevance}")
logger.debug(f"Action: {game_context.get('action_type')}")
logger.debug(f"Location: {game_context.get('location_description')[:100]}")
```

---

## Best Practices

1. **Trust the automation** - The system automatically adapts to situation and model
2. **Monitor metadata** - Check `adaptive_strategy` to understand what was included/dropped
3. **Add relevant triggers** - Extend trigger lists for new game mechanics
4. **Test with small models** - If it works on Llama 70B (8K), it works everywhere
5. **Use summaries** - For small models, summaries are more valuable than full history
6. **Profile token usage** - Monitor `total_tokens` to optimize further

---

## Backwards Compatibility

Fully backwards compatible:
- All existing code continues to work
- `build_character_context()` signature unchanged
- New metadata fields are additive
- Automatic activation - no configuration required

---

## Performance Impact

Minimal overhead:
- Relevance detection: O(n) where n ≈ 50-100 trigger words
- String matching: Simple substring checks, very fast
- Memory window calculation: O(1) dictionary lookup
- **Total latency:** <1ms per context assembly

---

## Integration with Provider Fallback

Context management integrates seamlessly with the provider fallback system:

1. **Content classified** (mild/moderate/mature)
2. **Provider chain built** based on intensity
3. **Context adapted** to first provider's model
4. **If refused**, adapts context to next provider
5. **Continues** until success or all providers fail

See `PROVIDER_FALLBACK_GUIDE.md` for details.

---

## Summary

The context management system achieves:

✅ **30-43% token reduction** in irrelevant details
✅ **Adaptive memory windows** (5/8/10 turns)
✅ **Elevated summaries** for restrictive models
✅ **Situational awareness** - only relevant attributes
✅ **Model-specific optimization** - works from 8K to 200K windows
✅ **Backwards compatible** - no code changes required
✅ **Automatic** - no manual configuration

The system is production-ready and optimizes context for all gameplay scenarios automatically.
