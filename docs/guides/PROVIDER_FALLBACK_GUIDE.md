# Provider Fallback System for Dark Fantasy Content

## Overview

Dark fantasy games include themes that may trigger content moderation:
- Realistic violence and injury
- Character death and consequences
- Morally ambiguous motivations
- Psychological manipulation
- Dark/disturbing narrative elements

This system handles automatic provider fallback when content policy violations occur.

---

## How It Works

### 1. Content Classification

When generating content, the system first classifies intensity:

```python
# Context includes action type, wounds, severity, etc.
context = {
    "action_type": "attack",
    "has_wounds": True,
    "wound_severity": "severe",
    "tense_situation": True
}

# Automatically classified as ContentIntensity.MATURE
intensity = strategy.classify_content_intensity(context)
```

**Intensity Levels:**

| Level | Examples | Typical Providers |
|-------|----------|-------------------|
| **MILD** | Dialogue, observation, movement | Claude, GPT-4, GPT-3.5 |
| **MODERATE** | Basic combat, minor wounds, tension | Claude, GPT-4, GPT-3.5 |
| **MATURE** | Graphic violence, critical wounds, death | GPT-4, Open models via API |
| **UNRESTRICTED** | Extreme/disturbing content | Local models, unrestricted APIs |

### 2. Provider Chain

System builds a fallback chain of providers that can handle the content:

```python
# For MATURE content:
provider_chain = [
    {"provider": "openai", "model": "gpt-4"},           # Try first
    {"provider": "together_ai", "model": "mixtral"},    # Fallback 1
    {"provider": "together_ai", "model": "llama-70b"},  # Fallback 2
    {"provider": "local", "model": "llama-3-70b"}       # Last resort
]
```

### 3. Automatic Fallback

If a provider refuses:

1. **Detect refusal** - Analyze error (content policy vs. API error)
2. **Log it** - Record for monitoring and analysis
3. **Try next provider** - Automatically attempt next in chain
4. **Adjust prompt** - Optimize wording for each provider
5. **Return result** - Or fail if all providers refuse

---

## Setup

### 1. Environment Variables

```bash
# .env file

# Primary providers (some content restrictions)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Secondary providers (more permissive, open models)
TOGETHER_API_KEY=...  # together.ai for hosted open models

# Local models (no restrictions)
LOCAL_MODEL_ENABLED=false  # Set to true if running locally
LOCAL_MODEL_PATH=/path/to/model
```

### 2. Configuration

Edit `config_providers.py`:

```python
PROVIDER_CONFIG = {
    "primary": [
        {
            "provider": "anthropic",
            "model": "claude-3-5-sonnet",
            "enabled": True,
            "priority": 1,
            "use_for": ["mild", "moderate"]
        }
    ],
    # ... more providers
}
```

### 3. Cost Settings

```python
COST_SETTINGS = {
    "prefer_cheap_for_simple_actions": True,  # Use GPT-3.5/Haiku when possible
    "daily_budget": 10.0,  # USD per day
    "fallback_to_free_on_budget": True  # Use local models if budget hit
}
```

---

## Usage Examples

### Example 1: Generate Actions (with Auto-Fallback)

```python
from services.llm.resilient_generator import ResilientActionGenerator

generator = ResilientActionGenerator()

# Context includes combat and wounds (MATURE intensity)
context = {
    "action_type": "attack",
    "has_wounds": True,
    "wound_severity": "critical",
    "location_name": "Dark Alley",
    "visible_characters": ["Character B", "Character C"],
    "working_memory": "Recent combat has left both characters wounded..."
}

try:
    # Automatically tries providers in order until one succeeds
    actions = generator.generate_action_options(
        character=character_profile,
        context=context,
        num_options=4
    )

    # If Claude refuses, tries GPT-4
    # If GPT-4 refuses, tries open models via API
    # If all fail, raises AllProvidersFailedError

except AllProvidersFailedError as e:
    # All providers failed
    # Log the issue and provide fallback content
    logger.error(f"Could not generate actions: {e}")
    actions = get_safe_fallback_actions()
```

**What happens internally:**

```
1. Content classified as MATURE
2. Provider chain: [gpt-4, mixtral, llama-70b, local-llama]
3. Try gpt-4... ✗ Refused (content policy)
4. Log refusal
5. Try mixtral... ✓ Success!
6. Return actions
```

### Example 2: Execute Specific Action

```python
# Character executes a lethal attack
result = generator.generate_single_action(
    action_type="attack",
    character=character_a,
    context={
        "action_type": "attack",
        "has_death": True,  # Classified as UNRESTRICTED
        "target": "Character B",
        "weapon": "dagger",
        "wound_severity": "mortal"
    },
    target="Character B"
)

# Automatically uses appropriate provider for UNRESTRICTED content
# Likely skips mainstream providers and goes straight to open/local models
```

### Example 3: Manual Provider Selection

```python
from services.llm.provider_strategy import ContentIntensity

# Force a specific intensity classification
strategy = get_provider_strategy()

# Get providers for mature content
providers = strategy.get_provider_chain(ContentIntensity.MATURE)

print("Will try these providers:")
for p in providers:
    print(f"  - {p['provider']}/{p['model']} (${p['cost']}/1k tokens)")
```

---

## Prompt Adaptation

Prompts are automatically adjusted per provider:

### For Mainstream Providers (Claude, GPT-4)

```python
# Original prompt
"Character A attacks Character B with a dagger."

# Adjusted prompt
"""
You are helping create narrative content for a dark fantasy role-playing game.
This is fictional content for an adult audience.

Focus on the narrative consequences and character psychology rather than graphic details.

Character A attacks Character B with a dagger.
"""
```

### For Local Models

```python
# No adjustment needed - use original prompt directly
"Character A attacks Character B with a dagger."
```

---

## Monitoring & Logging

### Refusal Log

Automatically logs all provider refusals:

```json
{
  "provider": "anthropic",
  "model": "claude-3-5-sonnet",
  "reason": "content_policy",
  "intensity": "mature",
  "error_message": "Content policy violation: violence",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

Location: `logs/provider_refusals.json`

### Analysis

```bash
# View refusal statistics
python scripts/analyze_refusals.py

# Output:
# Provider Refusal Statistics:
#   Anthropic: 45 refusals (30% of mature content)
#   OpenAI: 12 refusals (8% of mature content)
#   Together.ai: 0 refusals
```

---

## Provider Comparison

### Content Policy Comparison (as of 2024)

| Provider | Mild | Moderate | Mature | Unrestricted | Cost (per 1M tokens) |
|----------|------|----------|--------|--------------|----------------------|
| **Claude 3.5 Sonnet** | ✅ | ✅ | ⚠️ | ❌ | $3,000 |
| **GPT-4** | ✅ | ✅ | ⚠️ | ❌ | $30,000 |
| **GPT-3.5 Turbo** | ✅ | ✅ | ✅ | ❌ | $1,500 |
| **AIML API - Mistral 7B** | ✅ | ✅ | ⚠️ | ❌ | $200 |
| **AIML API - Mixtral 8x7B** | ✅ | ✅ | ✅ | ⚠️ | $500 |
| **Together.ai - Mixtral** | ✅ | ✅ | ✅ | ⚠️ | $600 |
| **AIML API - Llama 3 70B** | ✅ | ✅ | ✅ | ✅ | $800 |
| **Together.ai - Llama 70B** | ✅ | ✅ | ✅ | ✅ | $900 |
| **AIML API - Llama 3.1 405B** | ✅ | ✅ | ✅ | ✅ | $2,700 |
| **Local Llama 3** | ✅ | ✅ | ✅ | ✅ | Free (after setup) |

**Legend:**
- ✅ Generally allows
- ⚠️ Sometimes refuses
- ❌ Usually refuses

### Recommendations

**For Most Game Content (MILD/MODERATE):**
- Primary: Claude 3.5 Sonnet (best quality)
- Fallback: GPT-3.5 Turbo (cheap, permissive)

**For Combat/Injury (MODERATE/MATURE):**
- Primary: GPT-4 (higher quality)
- Fallback: Mixtral via Together.ai (cheaper, more permissive)

**For Extreme Content (UNRESTRICTED):**
- Primary: Llama 3 70B via Together.ai
- Fallback: Local Llama 3 70B (requires GPU)

---

## Local Model Setup (Optional)

For truly unrestricted content, run models locally:

### Hardware Requirements

**Llama 3 70B (recommended):**
- GPU: 2x NVIDIA A100 (80GB) or 4x RTX 3090 (24GB)
- RAM: 128GB+
- Storage: 200GB

**Mistral 7B (lighter alternative):**
- GPU: 1x RTX 3090 (24GB) or similar
- RAM: 32GB
- Storage: 50GB

### Setup with Ollama (Easiest)

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull model
ollama pull llama3:70b

# Verify
ollama run llama3:70b "Hello, world!"
```

### Setup with llama.cpp (More control)

```bash
# Clone llama.cpp
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp

# Build with GPU support
make LLAMA_CUBLAS=1

# Download model (GGUF format)
# From HuggingFace: TheBloke/Llama-3-70B-GGUF

# Run server
./server -m models/llama-3-70b.Q4_K_M.gguf -c 8192 -ngl 80
```

### Configure in .env

```bash
LOCAL_MODEL_ENABLED=true
LOCAL_MODEL_ENDPOINT=http://localhost:11434  # Ollama default
# or
LOCAL_MODEL_ENDPOINT=http://localhost:8080   # llama.cpp default
```

---

## Fallback Strategies

### Strategy 1: Quality First (Default)

Try most capable models first, fallback to less capable:

```
Claude 3.5 Sonnet → GPT-4 → Mixtral → Llama 70B → Local Model
```

Good for: Important narrative moments, player-visible content

### Strategy 2: Cost Optimized

Try cheapest models first:

```
GPT-3.5 → Claude Haiku → Mixtral → Claude 3.5 → GPT-4
```

Good for: Background NPC actions, routine content

### Strategy 3: Permissive First

Try most permissive models first:

```
Local Model → Llama 70B (API) → Mixtral → GPT-4 → Claude
```

Good for: Content known to be mature/unrestricted

### Configuration

```python
# config_providers.py

# Choose strategy
FALLBACK_STRATEGY = "quality_first"  # or "cost_optimized" or "permissive_first"
```

---

## Testing

### Test Provider Chain

```bash
# Test what providers would be used for each intensity
python scripts/test_provider_chain.py

# Output:
# MILD intensity:
#   1. anthropic/claude-3-5-sonnet ($0.003/1k)
#   2. openai/gpt-3.5-turbo ($0.0015/1k)
#
# MATURE intensity:
#   1. openai/gpt-4 ($0.03/1k)
#   2. together_ai/mixtral-8x7b ($0.0006/1k)
#   3. together_ai/llama-70b ($0.0009/1k)
```

### Test Actual Generation

```bash
# Test with sample content
python scripts/test_generation.py --intensity mature --action attack

# Will attempt generation and show which provider succeeded
```

---

## Troubleshooting

### All Providers Fail

**Problem:** `AllProvidersFailedError` raised

**Solutions:**
1. Check API keys are valid
2. Check daily budget not exceeded
3. Enable local model as fallback
4. Adjust content classification (may be too intense)

### Too Many Refusals

**Problem:** Content frequently refused by mainstream providers

**Solutions:**
1. Adjust prompt wording (less graphic description)
2. Add more context about game/fiction
3. Use more permissive providers for that content type
4. Set up local model

### High Costs

**Problem:** API costs too high

**Solutions:**
1. Enable `prefer_cheap_for_simple_actions`
2. Use GPT-3.5/Claude Haiku for MILD content
3. Set daily budget limit
4. Set up local model for frequent high-intensity content

---

## Best Practices

1. **Classify Accurately**: Proper intensity classification prevents unnecessary fallbacks
2. **Monitor Refusals**: Review refusal logs to understand patterns
3. **Optimize Prompts**: Better prompts = fewer refusals = lower costs
4. **Use Local for Heavy Use**: If generating lots of mature content, local models are cost-effective
5. **Budget Limits**: Set daily budgets to prevent surprise bills
6. **Test Before Deploy**: Test provider chain with sample content before going live

---

## Summary

The provider fallback system:

✅ **Automatically handles** content policy refusals
✅ **Tries multiple providers** until one succeeds
✅ **Adjusts prompts** for each provider
✅ **Logs refusals** for monitoring
✅ **Optimizes costs** by using cheaper providers when possible
✅ **Supports local models** for truly unrestricted content

Your game can include dark fantasy themes without worrying about unexpected refusals breaking the experience.
