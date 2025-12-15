"""
Provider Configuration

Configure which LLM providers to use and in what order.
This can be adjusted based on your API access and preferences.
"""

import os
from typing import Dict, Any

# Provider configuration
PROVIDER_CONFIG: Dict[str, Any] = {
    # Primary providers (mainstream, good quality, some content restrictions)
    "primary": [
        {
            "provider": "anthropic",
            "model": "claude-3-5-sonnet-20241022",
            "enabled": bool(os.getenv("ANTHROPIC_API_KEY")),
            "priority": 1,
            "use_for": ["mild", "moderate"]  # Content intensities
        },
        {
            "provider": "openai",
            "model": "gpt-4",
            "enabled": bool(os.getenv("OPENAI_API_KEY")),
            "priority": 2,
            "use_for": ["mild", "moderate"]
        }
    ],

    # Secondary providers (open models via API, more permissive)
    "secondary": [
        {
            "provider": "aimlapi",
            "model": "mistralai/Mistral-7B-Instruct-v0.2",
            "enabled": bool(os.getenv("AIMLAPI_API_KEY")),
            "priority": 3,
            "use_for": ["moderate"],
            "notes": "Fast and cheap for moderate content"
        },
        {
            "provider": "aimlapi",
            "model": "mistralai/Mixtral-8x7B-Instruct-v0.1",
            "enabled": bool(os.getenv("AIMLAPI_API_KEY")),
            "priority": 4,
            "use_for": ["moderate", "mature"],
            "notes": "Good balance of quality and permissiveness"
        },
        {
            "provider": "together_ai",
            "model": "mistralai/Mixtral-8x7B-Instruct-v0.1",
            "enabled": bool(os.getenv("TOGETHER_API_KEY")),
            "priority": 5,
            "use_for": ["moderate", "mature"],
            "notes": "Together.ai backup for Mixtral"
        },
        {
            "provider": "aimlapi",
            "model": "meta-llama/Meta-Llama-3-70B-Instruct",
            "enabled": bool(os.getenv("AIMLAPI_API_KEY")),
            "priority": 6,
            "use_for": ["mature", "unrestricted"],
            "notes": "Large model, very permissive"
        },
        {
            "provider": "together_ai",
            "model": "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
            "enabled": bool(os.getenv("TOGETHER_API_KEY")),
            "priority": 7,
            "use_for": ["mature", "unrestricted"],
            "notes": "Together.ai Llama 3.1 70B Instruct (more permissive than chat-hf)"
        },
        {
            "provider": "aimlapi",
            "model": "meta-llama/Meta-Llama-3.1-405B-Instruct",
            "enabled": bool(os.getenv("AIMLAPI_API_KEY")),
            "priority": 8,
            "use_for": ["unrestricted"],
            "notes": "Highest quality open model for extreme content"
        }
    ],

    # Tertiary providers (local models, no restrictions)
    "local": [
        {
            "provider": "local",
            "model": "llama-3-70b-instruct",
            "enabled": bool(os.getenv("LOCAL_MODEL_ENABLED")),
            "priority": 5,
            "use_for": ["unrestricted"],
            "notes": "Requires local GPU with at least 80GB VRAM"
        }
    ]
}


# Cost optimization settings
COST_SETTINGS = {
    # Prefer cheaper models when possible
    "prefer_cheap_for_simple_actions": True,

    # Use cheaper models for non-critical content
    "cheap_for_mild": True,  # Use GPT-3.5/Haiku for basic dialogue

    # Budget limits (USD per day)
    "daily_budget": float(os.getenv("LLM_DAILY_BUDGET", "10.0")),

    # Fallback to free options if budget exceeded
    "fallback_to_free_on_budget": True
}


# Content classification settings
CONTENT_CLASSIFICATION = {
    # Automatic intensity detection based on context
    "auto_classify": True,

    # Keywords that trigger higher intensity classification
    "mature_keywords": [
        "attack", "wound", "blood", "death", "kill", "torture",
        "severe", "critical", "mortal", "dying"
    ],

    "unrestricted_keywords": [
        "execute", "dismember", "mutilate", "corpse",
        "extremely graphic", "sadistic"
    ],

    # Default intensity when classification is uncertain
    "default_intensity": "moderate"
}


# Retry and fallback settings
RETRY_SETTINGS = {
    # Maximum attempts across all providers
    "max_total_attempts": 5,

    # Retry delay (seconds)
    "retry_delay": 1.0,

    # Exponential backoff for rate limits
    "use_exponential_backoff": True,

    # Log all refusals for analysis
    "log_refusals": True,
    "refusal_log_path": "logs/provider_refusals.json"
}


# Provider-specific settings
PROVIDER_SPECIFIC = {
    "anthropic": {
        "timeout": 60,  # seconds
        "max_tokens": 2048,
        "temperature": 0.7
    },
    "openai": {
        "timeout": 60,
        "max_tokens": 2048,
        "temperature": 0.7
    },
    "aimlapi": {
        "timeout": 90,  # Similar to other API providers
        "max_tokens": 2048,
        "temperature": 0.7,
        "base_url": "https://api.aimlapi.com/v1"
    },
    "together_ai": {
        "timeout": 90,  # Open models may be slower
        "max_tokens": 2048,
        "temperature": 0.7
    },
    "local": {
        "timeout": 120,  # Local inference can be slow
        "max_tokens": 2048,
        "temperature": 0.7,
        "context_length": 8192
    }
}


def get_enabled_providers():
    """Get list of all enabled providers."""
    enabled = []

    for category in ["primary", "secondary", "local"]:
        for provider_config in PROVIDER_CONFIG.get(category, []):
            if provider_config["enabled"]:
                enabled.append(provider_config)

    # Sort by priority
    enabled.sort(key=lambda x: x["priority"])

    return enabled


def get_providers_for_intensity(intensity: str):
    """Get list of providers that can handle given intensity."""
    enabled = get_enabled_providers()

    capable = [
        p for p in enabled
        if intensity in p["use_for"]
    ]

    return capable


# Example usage:
if __name__ == "__main__":
    print("Enabled Providers:")
    for p in get_enabled_providers():
        print(f"  {p['provider']}/{p['model']} (priority {p['priority']})")

    print("\nProviders for 'mature' content:")
    for p in get_providers_for_intensity("mature"):
        print(f"  {p['provider']}/{p['model']}")
