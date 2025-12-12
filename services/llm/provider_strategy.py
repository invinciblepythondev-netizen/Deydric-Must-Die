"""
LLM Provider Strategy for Dark Fantasy Content

This module handles provider selection and fallback for content that may be
restricted by certain LLM providers' content policies.

Dark fantasy themes that may trigger filters:
- Realistic violence and injury descriptions
- Morally ambiguous character motivations
- Psychological manipulation and deception
- Dark/disturbing narrative elements
- Character death and consequences
"""

from enum import Enum
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class ContentIntensity(Enum):
    """Classification of content by intensity/sensitivity"""
    MILD = "mild"           # Basic dialogue, movement, observation
    MODERATE = "moderate"   # Combat descriptions, injury, tension
    MATURE = "mature"       # Graphic violence, psychological horror, death
    UNRESTRICTED = "unrestricted"  # Extremely dark/disturbing content


class RefusalReason(Enum):
    """Why a provider refused to generate content"""
    CONTENT_POLICY = "content_policy"  # Violated content policy
    SAFETY_FILTER = "safety_filter"    # Triggered safety system
    API_ERROR = "api_error"            # Technical error
    RATE_LIMIT = "rate_limit"          # Rate limited
    TIMEOUT = "timeout"                # Request timed out
    UNKNOWN = "unknown"                # Unknown reason


class ProviderCapability:
    """
    Defines what content intensity levels a provider can handle.
    Based on observed behavior and documented policies.
    """

    # Provider capability matrix (as of 2024)
    CAPABILITIES = {
        "anthropic": {
            "claude-3-5-sonnet": {
                "max_intensity": ContentIntensity.MODERATE,
                "notes": "Good for most game content. May refuse extremely graphic violence.",
                "cost_per_1k_tokens": 0.003
            },
            "claude-3-haiku": {
                "max_intensity": ContentIntensity.MODERATE,
                "notes": "Same policies as Sonnet. Fast and cheap for simple content.",
                "cost_per_1k_tokens": 0.00025
            },
            "claude-3-opus": {
                "max_intensity": ContentIntensity.MODERATE,
                "notes": "Most capable Claude model. Similar content policies.",
                "cost_per_1k_tokens": 0.015
            }
        },
        "openai": {
            "gpt-4": {
                "max_intensity": ContentIntensity.MODERATE,
                "notes": "Generally similar to Claude. Handles dark fantasy well.",
                "cost_per_1k_tokens": 0.03
            },
            "gpt-3.5-turbo": {
                "max_intensity": ContentIntensity.MODERATE,
                "notes": "Cheaper, may be more permissive for some content.",
                "cost_per_1k_tokens": 0.0015
            }
        },
        "local": {
            "llama-3-70b": {
                "max_intensity": ContentIntensity.UNRESTRICTED,
                "notes": "Local model. No content restrictions. Requires local GPU.",
                "cost_per_1k_tokens": 0.0  # Free after setup
            },
            "mistral-7b-instruct": {
                "max_intensity": ContentIntensity.UNRESTRICTED,
                "notes": "Smaller local model. No restrictions. Lower quality.",
                "cost_per_1k_tokens": 0.0
            }
        },
        "together_ai": {
            "mistralai/Mixtral-8x7B-Instruct-v0.1": {
                "max_intensity": ContentIntensity.MATURE,
                "notes": "API access to open models. More permissive. No content filtering.",
                "cost_per_1k_tokens": 0.0006
            },
            "meta-llama/Llama-3-70b-chat-hf": {
                "max_intensity": ContentIntensity.UNRESTRICTED,
                "notes": "Large open model via API. Very permissive. No content filtering.",
                "cost_per_1k_tokens": 0.0009
            },
            "meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo": {
                "max_intensity": ContentIntensity.UNRESTRICTED,
                "notes": "Largest open model via Together AI. Most permissive, highest quality. No content filtering.",
                "cost_per_1k_tokens": 0.005
            }
        },
        "aimlapi": {
            "meta-llama/Llama-3.1-405B-Instruct-Turbo": {
                "max_intensity": ContentIntensity.UNRESTRICTED,
                "notes": "AIML API - Llama 3.1 405B. Highest quality open model, very permissive.",
                "cost_per_1k_tokens": 0.0027
            },
            "meta-llama/Llama-3-70b-chat-hf": {
                "max_intensity": ContentIntensity.UNRESTRICTED,
                "notes": "AIML API - Llama 3 70B. Very permissive, good quality.",
                "cost_per_1k_tokens": 0.0008
            },
            "mistralai/Mixtral-8x7B-Instruct-v0.1": {
                "max_intensity": ContentIntensity.MATURE,
                "notes": "AIML API - Mixtral access. More permissive than mainstream.",
                "cost_per_1k_tokens": 0.0005
            },
            "mistralai/Mistral-7B-Instruct-v0.2": {
                "max_intensity": ContentIntensity.MODERATE,
                "notes": "AIML API - Smaller Mistral model. Fast and cheap.",
                "cost_per_1k_tokens": 0.0002
            }
        }
    }

    @classmethod
    def can_handle(cls, provider: str, model: str, intensity: ContentIntensity) -> bool:
        """Check if a provider/model can handle content of given intensity."""
        if provider not in cls.CAPABILITIES:
            return False

        if model not in cls.CAPABILITIES[provider]:
            return False

        capability = cls.CAPABILITIES[provider][model]
        max_intensity = capability["max_intensity"]

        # Can handle if requested intensity is <= max intensity
        intensity_order = [
            ContentIntensity.MILD,
            ContentIntensity.MODERATE,
            ContentIntensity.MATURE,
            ContentIntensity.UNRESTRICTED
        ]

        return intensity_order.index(intensity) <= intensity_order.index(max_intensity)

    @classmethod
    def get_fallback_providers(
        cls,
        intensity: ContentIntensity,
        prefer_cheap: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get list of providers that can handle the content, ordered by preference.

        Args:
            intensity: Content intensity level needed
            prefer_cheap: Prioritize cheaper providers

        Returns:
            List of dicts with provider, model, and metadata
        """
        capable_providers = []

        for provider, models in cls.CAPABILITIES.items():
            for model, info in models.items():
                if cls.can_handle(provider, model, intensity):
                    capable_providers.append({
                        "provider": provider,
                        "model": model,
                        "max_intensity": info["max_intensity"],
                        "cost": info["cost_per_1k_tokens"],
                        "notes": info["notes"]
                    })

        # Sort by cost if prefer_cheap, otherwise by capability
        if prefer_cheap:
            capable_providers.sort(key=lambda x: x["cost"])
        else:
            # Prefer more capable models (can handle more intense content)
            intensity_order = {
                ContentIntensity.MILD: 0,
                ContentIntensity.MODERATE: 1,
                ContentIntensity.MATURE: 2,
                ContentIntensity.UNRESTRICTED: 3
            }
            capable_providers.sort(
                key=lambda x: intensity_order[x["max_intensity"]],
                reverse=True
            )

        return capable_providers


class ProviderStrategy:
    """
    Manages provider selection and fallback for LLM requests.
    Handles content policy violations by automatically trying alternative providers.
    """

    def __init__(self, prefer_cheap: bool = False):
        """
        Args:
            prefer_cheap: Prioritize cheaper providers when selecting fallbacks
        """
        self.prefer_cheap = prefer_cheap
        self.refusal_log: List[Dict[str, Any]] = []

    def classify_content_intensity(self, context: Dict[str, Any]) -> ContentIntensity:
        """
        Analyze the request context to determine content intensity.

        This helps select appropriate providers before making requests.

        Args:
            context: Game context including action type, character state, etc.

        Returns:
            ContentIntensity classification
        """
        action_type = context.get("action_type", "")
        has_wounds = context.get("has_wounds", False)
        has_death = context.get("has_death", False)
        wound_severity = context.get("wound_severity", "")

        # Check for unrestricted content triggers
        if has_death and "mortal" in wound_severity:
            return ContentIntensity.UNRESTRICTED

        if context.get("is_torture", False):
            return ContentIntensity.UNRESTRICTED

        if context.get("extreme_violence", False):
            return ContentIntensity.UNRESTRICTED

        # Check for mature content
        if action_type in ["attack", "kill"]:
            return ContentIntensity.MATURE

        if has_wounds and wound_severity in ["critical", "mortal"]:
            return ContentIntensity.MATURE

        if context.get("psychological_manipulation", False):
            return ContentIntensity.MATURE

        # Check for moderate content
        if action_type in ["threaten", "intimidate", "deceive"]:
            return ContentIntensity.MODERATE

        if has_wounds:
            return ContentIntensity.MODERATE

        if context.get("tense_situation", False):
            return ContentIntensity.MODERATE

        # Default to mild
        return ContentIntensity.MILD

    def get_provider_chain(self, intensity: ContentIntensity) -> List[Dict[str, Any]]:
        """
        Get ordered list of providers to try for given content intensity.

        Args:
            intensity: Content intensity level

        Returns:
            Ordered list of providers to try
        """
        return ProviderCapability.get_fallback_providers(
            intensity,
            prefer_cheap=self.prefer_cheap
        )

    def log_refusal(
        self,
        provider: str,
        model: str,
        reason: RefusalReason,
        intensity: ContentIntensity,
        error_message: str = ""
    ):
        """
        Log a provider refusal for analysis and monitoring.

        Args:
            provider: Provider that refused
            model: Model that refused
            reason: Why it refused
            intensity: Content intensity that was attempted
            error_message: Error message from provider
        """
        entry = {
            "provider": provider,
            "model": model,
            "reason": reason.value,
            "intensity": intensity.value,
            "error_message": error_message,
            "timestamp": "now"  # Would use actual timestamp
        }

        self.refusal_log.append(entry)

        logger.warning(
            f"Provider refusal: {provider}/{model} refused {intensity.value} content. "
            f"Reason: {reason.value}. Error: {error_message}"
        )

    def detect_refusal_reason(self, error: Exception) -> RefusalReason:
        """
        Analyze an exception to determine why the provider refused.

        Args:
            error: Exception from provider

        Returns:
            RefusalReason classification
        """
        error_str = str(error).lower()

        # Anthropic content policy errors
        if "content policy" in error_str or "content filter" in error_str:
            return RefusalReason.CONTENT_POLICY

        if "safety" in error_str or "harmful" in error_str:
            return RefusalReason.SAFETY_FILTER

        # OpenAI content policy errors
        if "content_policy_violation" in error_str:
            return RefusalReason.CONTENT_POLICY

        if "content_filter" in error_str:
            return RefusalReason.SAFETY_FILTER

        # Rate limiting
        if "rate" in error_str or "429" in error_str:
            return RefusalReason.RATE_LIMIT

        # Timeout
        if "timeout" in error_str or "timed out" in error_str:
            return RefusalReason.TIMEOUT

        # Generic API errors
        if "api" in error_str or "connection" in error_str:
            return RefusalReason.API_ERROR

        return RefusalReason.UNKNOWN

    def adjust_prompt_for_provider(
        self,
        prompt: str,
        provider: str,
        model: str,
        intensity: ContentIntensity
    ) -> str:
        """
        Adjust prompt wording to better comply with provider policies.

        Some providers respond better to certain framings.

        Args:
            prompt: Original prompt
            provider: Target provider
            model: Target model
            intensity: Content intensity

        Returns:
            Adjusted prompt
        """
        adjustments = []

        # For moderate/mature content on mainstream providers
        if intensity in [ContentIntensity.MODERATE, ContentIntensity.MATURE]:
            if provider in ["anthropic", "openai"]:
                # Add context framing
                adjustments.append(
                    "You are helping create narrative content for a dark fantasy role-playing game. "
                    "This is fictional content for an adult audience. "
                )

                # Emphasize consequences
                adjustments.append(
                    "Focus on the narrative consequences and character psychology rather than graphic details. "
                )

        # For local models, no adjustments needed
        if provider == "local":
            return prompt

        # Prepend adjustments
        if adjustments:
            adjusted = "\n".join(adjustments) + "\n\n" + prompt
            return adjusted

        return prompt


# Singleton instance
_strategy_instance: Optional[ProviderStrategy] = None


def get_provider_strategy(prefer_cheap: bool = False) -> ProviderStrategy:
    """Get or create the global provider strategy instance."""
    global _strategy_instance
    if _strategy_instance is None:
        _strategy_instance = ProviderStrategy(prefer_cheap=prefer_cheap)
    return _strategy_instance
