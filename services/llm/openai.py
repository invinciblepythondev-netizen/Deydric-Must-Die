"""
OpenAI Provider

Implementation of LLM provider for OpenAI's GPT models.
"""

import os
import logging
from typing import Optional
from openai import OpenAI
from .provider import LLMProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """
    Provider implementation for OpenAI GPT models.

    Supports:
    - GPT-4 Turbo
    - GPT-4
    - GPT-3.5 Turbo
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)

        Raises:
            ValueError: If no API key provided or found in environment
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")

        if not self.api_key:
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.client = OpenAI(api_key=self.api_key)
        self.default_model = "gpt-4-turbo-preview"

        logger.info(f"Initialized OpenAIProvider with default model: {self.default_model}")

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
        Generate text using OpenAI GPT.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            model: Model to use (defaults to GPT-4 Turbo)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional OpenAI-specific parameters

        Returns:
            Generated text

        Raises:
            Exception: On API errors or content policy violations
        """
        model = model or self.default_model

        logger.debug(
            f"Generating with OpenAI {model} "
            f"(temp={temperature}, max_tokens={max_tokens})"
        )

        # Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        print("sending prompt to OpenAI")
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )

            # Extract text from response
            text = response.choices[0].message.content

            logger.debug(f"Generated {len(text)} characters")

            return text

        except Exception as e:
            logger.error(f"OpenAI generation failed: {e}")
            raise

    def get_default_model(self) -> str:
        """Get default OpenAI model."""
        return self.default_model

    def get_available_models(self) -> list:
        """Get list of available OpenAI models."""
        return [
            "gpt-4-turbo-preview",
            "gpt-4-1106-preview",
            "gpt-4",
            "gpt-4-0613",
            "gpt-3.5-turbo",
            "gpt-3.5-turbo-16k"
        ]
