"""
Anthropic Claude Provider

Implementation of LLM provider for Anthropic's Claude models.
"""

import os
import logging
from typing import Optional
from anthropic import Anthropic
from .provider import LLMProvider

logger = logging.getLogger(__name__)


class ClaudeProvider(LLMProvider):
    """
    Provider implementation for Anthropic Claude models.

    Supports:
    - Claude 3.5 Sonnet (most capable)
    - Claude 3.5 Haiku (fast and cheap)
    - Claude 3 Opus (legacy, most capable)
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Claude provider.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)

        Raises:
            ValueError: If no API key provided or found in environment
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")

        if not self.api_key:
            raise ValueError(
                "Anthropic API key required. Set ANTHROPIC_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.client = Anthropic(api_key=self.api_key)
        self.default_model = "claude-3-5-haiku-20241022"  # Using Haiku (Sonnet not available on this API tier)

        logger.info(f"Initialized ClaudeProvider with default model: {self.default_model}")
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
        Generate text using Claude.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            model: Model to use (defaults to Sonnet 3.5)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional Anthropic-specific parameters

        Returns:
            Generated text

        Raises:
            Exception: On API errors or content policy violations
        """
        model = model or self.default_model

        logger.debug(
            f"Generating with Claude {model} "
            f"(temp={temperature}, max_tokens={max_tokens})"
        )

        # Build messages
        messages = [{"role": "user", "content": prompt}]
        print("sending prompt to Claude prompt")
        try:
            response = self.client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt or "",
                messages=messages,
                **kwargs
            )

            # Extract text from response
            text = response.content[0].text

            logger.debug(f"Generated {len(text)} characters")

            return text

        except Exception as e:
            logger.error(f"Claude generation failed: {e}")
            
            raise

    def get_default_model(self) -> str:
        """Get default Claude model."""
        return self.default_model

    def get_available_models(self) -> list:
        """Get list of available Claude models."""
        return [
            "claude-3-5-sonnet-20241022",  # Latest Sonnet
            "claude-3-5-haiku-20241022",   # Latest Haiku
            "claude-3-opus-20240229",       # Opus (legacy)
            "claude-3-sonnet-20240229",     # Sonnet 3.0 (legacy)
            "claude-3-haiku-20240307"       # Haiku 3.0 (legacy)
        ]
