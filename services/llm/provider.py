"""
Base LLM Provider Interface

Defines the abstract interface that all LLM providers must implement.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    All provider implementations (Claude, OpenAI, etc.) must implement this interface.
    """

    @abstractmethod
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
        Generate text from the LLM.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            model: Optional model override (use default if not specified)
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Returns:
            Generated text

        Raises:
            Exception: If generation fails (content policy, API error, etc.)
        """
        pass

    @abstractmethod
    def get_default_model(self) -> str:
        """
        Get the default model for this provider.

        Returns:
            Model identifier string
        """
        pass

    @abstractmethod
    def get_available_models(self) -> list:
        """
        Get list of available models for this provider.

        Returns:
            List of model identifier strings
        """
        pass
