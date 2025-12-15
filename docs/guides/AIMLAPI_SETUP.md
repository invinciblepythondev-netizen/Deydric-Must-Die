# AIML API Setup Guide

AIML API (api.aimlapi.com) provides access to various open-source models with competitive pricing and more permissive content policies than mainstream providers.

## Why Use AIML API?

✅ **Cheaper** than mainstream providers ($0.20-$2.70 per 1M tokens)
✅ **More permissive** - handles mature/dark fantasy content
✅ **Multiple models** - Mistral 7B, Mixtral 8x7B, Llama 3 70B, Llama 3.1 405B
✅ **OpenAI-compatible API** - easy to integrate
✅ **Fast** - hosted models with good latency

## Getting Started

### 1. Sign Up

Visit: https://aimlapi.com/

- Create account (email or OAuth)
- Get your API key from dashboard
- Free trial credits available

### 2. Add API Key to .env

```bash
# .env file
AIMLAPI_API_KEY=your-api-key-here
```

### 3. Verify It Works

```bash
# Test AIML API provider
python -c "
import os
os.environ['AIMLAPI_API_KEY'] = 'your-key-here'
from services.llm.aimlapi import AIMLAPIProvider

provider = AIMLAPIProvider()
response = provider.generate(
    prompt='Generate a dark fantasy character description.',
    system_prompt='You are creating content for an RPG game.',
    model='mistralai/Mistral-7B-Instruct-v0.2'
)
print(response)
"
```

## Available Models

### Mistral 7B Instruct
- **Model ID**: `mistralai/Mistral-7B-Instruct-v0.2`
- **Cost**: $0.20 per 1M tokens
- **Best for**: Moderate content, fast responses
- **Context**: 32K tokens

### Mixtral 8x7B Instruct
- **Model ID**: `mistralai/Mixtral-8x7B-Instruct-v0.1`
- **Cost**: $0.50 per 1M tokens
- **Best for**: Mature content, good quality
- **Context**: 32K tokens

### Llama 3 70B Instruct
- **Model ID**: `meta-llama/Meta-Llama-3-70B-Instruct`
- **Cost**: $0.80 per 1M tokens
- **Best for**: Unrestricted content, high quality
- **Context**: 8K tokens

### Llama 3.1 405B Instruct
- **Model ID**: `meta-llama/Meta-Llama-3.1-405B-Instruct`
- **Cost**: $2.70 per 1M tokens
- **Best for**: Highest quality, unrestricted content
- **Context**: 128K tokens

## Configuration

AIML API is already configured in `config_providers.py` with priority ordering:

```python
# Priority 3 - Fast and cheap for moderate content
"mistralai/Mistral-7B-Instruct-v0.2"

# Priority 4 - Good for mature content
"mistralai/Mixtral-8x7B-Instruct-v0.1"

# Priority 6 - Large model for unrestricted content
"meta-llama/Meta-Llama-3-70B-Instruct"

# Priority 8 - Highest quality for extreme content
"meta-llama/Meta-Llama-3.1-405B-Instruct"
```

## Usage in Your Game

The fallback system will automatically use AIML API when:

1. Mainstream providers (Claude, GPT-4) refuse content
2. Content is classified as MODERATE or MATURE
3. You want to minimize costs

### Example: Generate Character Action

```python
from services.llm.resilient_generator import ResilientActionGenerator

generator = ResilientActionGenerator()

# Context includes combat (MATURE intensity)
context = {
    "action_type": "attack",
    "has_wounds": True,
    "wound_severity": "severe",
    "location_name": "Dark Alley"
}

# Automatically tries providers in order:
# 1. GPT-4 (may refuse)
# 2. AIML API Mixtral 8x7B (likely succeeds)
actions = generator.generate_action_options(
    character=character_profile,
    context=context,
    num_options=4
)
```

## Cost Estimation

For a typical gaming session (100 character actions, ~500 tokens each):

| Scenario | Tokens | AIML API Cost | Claude Cost | Savings |
|----------|--------|---------------|-------------|---------|
| **All Moderate** (Mistral 7B) | 50K | $0.01 | $0.15 | 93% |
| **Mixed Moderate/Mature** (Mixtral) | 50K | $0.025 | $0.15 | 83% |
| **Mostly Mature** (Llama 70B) | 50K | $0.04 | $0.15 | 73% |

**Estimated monthly cost:**
- Light use (10 sessions/month): $0.50 - $2
- Regular use (30 sessions/month): $2 - $5
- Heavy use (60 sessions/month): $5 - $12

Compare to Claude-only: $20-60/month

## Pricing Details

AIML API uses pay-as-you-go pricing:

| Model | Input (per 1M tokens) | Output (per 1M tokens) | Average |
|-------|----------------------|------------------------|---------|
| Mistral 7B | $0.15 | $0.25 | $0.20 |
| Mixtral 8x7B | $0.40 | $0.60 | $0.50 |
| Llama 3 70B | $0.70 | $0.90 | $0.80 |
| Llama 3.1 405B | $2.50 | $2.90 | $2.70 |

**No subscription required** - only pay for what you use.

## Rate Limits

Free tier:
- 60 requests/minute
- 10,000 tokens/minute

Paid tiers (after $10 spend):
- 300 requests/minute
- 100,000 tokens/minute

More than sufficient for gaming use.

## Tips for Best Results

### 1. Choose Right Model for Content

```python
# Moderate content (basic dialogue, non-graphic)
model = "mistralai/Mistral-7B-Instruct-v0.2"

# Mature content (combat, injury, tension)
model = "mistralai/Mixtral-8x7B-Instruct-v0.1"

# Unrestricted content (graphic violence, dark themes)
model = "meta-llama/Meta-Llama-3-70B-Instruct"
```

### 2. Use System Prompts

```python
system_prompt = """
You are creating narrative content for a dark fantasy RPG game.
This is fictional content for an adult audience.
Focus on character psychology and narrative consequences.
"""
```

### 3. Optimize Temperature

```python
# For consistent narrative style
temperature = 0.7

# For more creative/varied actions
temperature = 0.8-0.9

# For predictable/safe outputs
temperature = 0.5-0.6
```

### 4. Monitor Usage

Check your dashboard regularly:
- https://aimlapi.com/dashboard/usage

Set up billing alerts if desired.

## Troubleshooting

### "Authentication failed"
- Check API key is correct in `.env`
- Verify key has not expired
- Check account has credits

### "Rate limit exceeded"
- Free tier: wait 1 minute
- Upgrade to paid tier for higher limits
- Implement request queuing in your code

### "Model not found"
- Check model ID spelling
- Some models may require paid tier
- Use `provider.get_available_models()` to list models

### Slow responses
- Larger models (405B) take longer (5-15s)
- Use smaller models (7B/8x7B) for faster responses
- Consider caching common responses

## Testing

Test AIML API provider directly:

```bash
# Test with test script
python services/llm/aimlapi.py

# Or use interactive test
python -c "
from services.llm.aimlapi import AIMLAPIProvider

provider = AIMLAPIProvider()

# Test generation
result = provider.generate(
    prompt='Test prompt',
    model='mistralai/Mistral-7B-Instruct-v0.2'
)
print(result)

# Test streaming
print('\\nStreaming test:')
for chunk in provider.generate_streaming(
    prompt='Write a short story.',
    model='mistralai/Mistral-7B-Instruct-v0.2'
):
    print(chunk, end='', flush=True)

# List available models
print('\\n\\nAvailable models:')
for model in provider.get_available_models():
    print(f'  - {model}')
"
```

## Comparison with Other Providers

| Feature | AIML API | Together.ai | OpenAI | Claude |
|---------|----------|-------------|--------|---------|
| **Mistral 7B** | $0.20/1M | Not available | N/A | N/A |
| **Mixtral 8x7B** | $0.50/1M | $0.60/1M | N/A | N/A |
| **Llama 3 70B** | $0.80/1M | $0.90/1M | N/A | N/A |
| **Content Policy** | Permissive | Permissive | Restrictive | Restrictive |
| **Setup** | Easy | Easy | Easy | Easy |
| **Free Trial** | ✅ Yes | ✅ Yes | ✅ Limited | ✅ Limited |

## Support

- Documentation: https://docs.aimlapi.com/
- Discord: https://discord.gg/aimlapi
- Email: support@aimlapi.com

## Summary

AIML API is an excellent choice for your dark fantasy game:

✅ **Much cheaper** than mainstream providers
✅ **More permissive** content policies
✅ **Multiple model options** for different use cases
✅ **Easy to integrate** (already done!)
✅ **Automatic fallback** when mainstream providers refuse

Just add your API key to `.env` and let the system handle the rest!
