"""
Together.ai Provider Implementation

Provides access to open-source models hosted on Together.ai:
- Mixtral 8x7B (good balance of quality and permissiveness)
- Llama 3 70B (high quality, very permissive)
- Llama 3.1 405B (highest quality for unrestricted content)

CONTENT FILTERING:
------------------
Open-source models on Together.ai are naturally permissive with no content filtering.
These models (Mixtral, Llama 3, etc.) do not have built-in safety filters and will
generate adult/mature content without restrictions.

For maximum permissiveness:
1. Use Llama 3.1 405B model (highest quality, most permissive)
2. No special parameters needed - models are unrestricted by default
3. Open-source models are generally more permissive than commercial APIs

API Documentation: https://docs.together.ai/reference/inference
"""

import os
import logging
from typing import Optional
from openai import OpenAI  # Together.ai uses OpenAI-compatible API
from .provider import LLMProvider

logger = logging.getLogger(__name__)


class TogetherAIProvider(LLMProvider):
    """
    Provider for Together.ai hosted open-source models.

    Together.ai provides API access to models like Mixtral and Llama 3,
    which are generally more permissive than mainstream providers.
    """

    # Available models on Together.ai
    AVAILABLE_MODELS = {
        "mixtral-8x7b": "mistralai/Mixtral-8x7B-Instruct-v0.1",
        "llama-3-70b": "meta-llama/Llama-3-70b-chat-hf",
        "llama-3.1-405b": "meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo"
    }

    def __init__(self, model: Optional[str] = None):
        """
        Initialize Together.ai provider.

        Args:
            model: Model to use (defaults to Mixtral 8x7B)

        Raises:
            ValueError: If TOGETHER_API_KEY not found in environment
        """
        self.api_key = os.getenv("TOGETHER_API_KEY")
        if not self.api_key:
            raise ValueError(
                "TOGETHER_API_KEY not found in environment variables. "
                "Add it to your .env file to use Together.ai models."
            )

        # Together.ai uses OpenAI-compatible API
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.together.xyz/v1"
        )

        # Set default model
        self.default_model = model or self.AVAILABLE_MODELS["mixtral-8x7b"]

        logger.info(
            f"Initialized Together.ai provider with model: {self.default_model}"
        )

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs
    ) -> str:
        """
        Generate text using Together.ai API.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            model: Model override (use default if not specified)
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional Together.ai-specific parameters

        Returns:
            Generated text

        Raises:
            Exception: If API call fails
        """
        model = model or self.default_model

        logger.info(f"Generating with Together.ai model: {model}")

        # Build messages array
        messages = []

        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })

        messages.append({
            "role": "user",
            "content": prompt
        })

        # Note: Together.ai uses open-source models which are naturally permissive
        # No content filtering parameter needed - models like Llama 3 are unrestricted by default
        logger.info("Using Together.ai open-source model (naturally permissive, no content filtering)")

        print("sending prompt to Together.ai (open-source model, no content filters)")

        try:
            # Call Together.ai API (OpenAI-compatible)
            # Don't pass safety_model parameter - it's not supported
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )

            result = response.choices[0].message.content

            logger.info(
                f"✓ Together.ai generation successful "
                f"({response.usage.total_tokens} tokens)"
            )

            return result

        except Exception as e:
            logger.error(f"Together.ai API error: {e}")
            raise

    def get_default_model(self) -> str:
        """
        Get the default model for this provider.

        Returns:
            Model identifier string
        """
        return self.default_model

    def get_available_models(self) -> list:
        """
        Get list of available models on Together.ai.

        Returns:
            List of model identifier strings
        """
        return list(self.AVAILABLE_MODELS.values())

    @classmethod
    def get_model_by_alias(cls, alias: str) -> str:
        """
        Get full model name from friendly alias.

        Args:
            alias: Friendly name (e.g., "mixtral-8x7b")

        Returns:
            Full model identifier

        Raises:
            KeyError: If alias not found
        """
        return cls.AVAILABLE_MODELS[alias]
