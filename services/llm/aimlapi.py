"""
AIML API Provider

Provider for api.aimlapi.com - unified API for various open source models.
Supports Llama, Mistral, and other open models with competitive pricing.

API Documentation: https://docs.aimlapi.com/
"""

import os
import json
import logging
from typing import Optional, Dict, Any
import requests
from .provider import LLMProvider

logger = logging.getLogger(__name__)


class AIMLAPIProvider(LLMProvider):
    """
    AIML API provider for open source models.

    Features:
    - Access to Llama 3 70B, 405B
    - Mistral and Mixtral models
    - Competitive pricing
    - More permissive than mainstream providers
    - OpenAI-compatible API format
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize AIML API provider.

        Args:
            api_key: AIML API key. If not provided, reads from AIMLAPI_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("AIMLAPI_API_KEY")

        if not self.api_key:
            raise ValueError(
                "AIML API key not provided. Set AIMLAPI_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.base_url = "https://api.aimlapi.com/v1"
        self.timeout = 90  # Longer timeout for larger models

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: str = "meta-llama/Meta-Llama-3-70B-Instruct",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs
    ) -> str:
        """
        Generate text using AIML API.

        Args:
            prompt: User prompt
            system_prompt: System prompt (optional)
            model: Model identifier (e.g., "meta-llama/Meta-Llama-3-70B-Instruct")
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Returns:
            Generated text

        Raises:
            Exception: If API call fails
        """
        logger.info(f"Generating with AIML API model: {model}")

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

        # Build request payload (OpenAI-compatible format)
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        # Add any additional parameters
        for key, value in kwargs.items():
            if key not in payload:
                payload[key] = value

        # Make API request
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.timeout
            )

            response.raise_for_status()

            # Parse response
            result = response.json()

            # Extract generated text
            if "choices" in result and len(result["choices"]) > 0:
                message = result["choices"][0].get("message", {})
                content = message.get("content", "")

                logger.info(f"✓ Generated {len(content)} characters")

                return content
            else:
                raise Exception("No content in API response")

        except requests.exceptions.Timeout:
            logger.error(f"AIML API request timed out after {self.timeout}s")
            raise Exception(f"Request timed out after {self.timeout} seconds")

        except requests.exceptions.HTTPError as e:
            # Parse error details
            try:
                error_data = e.response.json()
                error_message = error_data.get("error", {}).get("message", str(e))
            except:
                error_message = str(e)

            logger.error(f"AIML API HTTP error: {error_message}")

            # Check for content policy violations
            if "content" in error_message.lower() or "policy" in error_message.lower():
                raise Exception(f"Content policy violation: {error_message}")

            raise Exception(f"API error: {error_message}")

        except requests.exceptions.RequestException as e:
            logger.error(f"AIML API request error: {e}")
            raise Exception(f"Request failed: {str(e)}")

        except Exception as e:
            logger.error(f"Unexpected error in AIML API call: {e}")
            raise

    def generate_streaming(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: str = "meta-llama/Meta-Llama-3-70B-Instruct",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs
    ):
        """
        Generate text with streaming (yields chunks as they arrive).

        Args:
            prompt: User prompt
            system_prompt: System prompt (optional)
            model: Model identifier
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Yields:
            Text chunks as they are generated
        """
        logger.info(f"Streaming generation with AIML API model: {model}")

        # Build messages
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

        # Build request payload
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True  # Enable streaming
        }

        # Add any additional parameters
        for key, value in kwargs.items():
            if key not in payload:
                payload[key] = value

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.timeout,
                stream=True
            )

            response.raise_for_status()

            # Process streaming response
            for line in response.iter_lines():
                if line:
                    line_text = line.decode('utf-8')

                    # Skip empty lines and "data: [DONE]"
                    if not line_text.startswith("data: "):
                        continue

                    if line_text == "data: [DONE]":
                        break

                    # Parse JSON chunk
                    try:
                        json_str = line_text[6:]  # Remove "data: " prefix
                        chunk = json.loads(json_str)

                        # Extract content delta
                        if "choices" in chunk and len(chunk["choices"]) > 0:
                            delta = chunk["choices"][0].get("delta", {})
                            content = delta.get("content", "")

                            if content:
                                yield content

                    except json.JSONDecodeError:
                        continue

        except Exception as e:
            logger.error(f"Error in streaming generation: {e}")
            raise

    def count_tokens(self, text: str) -> int:
        """
        Estimate token count for text.

        Args:
            text: Text to count tokens for

        Returns:
            Estimated token count
        """
        # Rough estimation: ~4 characters per token
        # More accurate would use tiktoken or model-specific tokenizer
        return len(text) // 4

    def get_available_models(self) -> list:
        """
        Get list of available models from AIML API.

        Returns:
            List of model identifiers
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}"
            }

            response = requests.get(
                f"{self.base_url}/models",
                headers=headers,
                timeout=10
            )

            response.raise_for_status()
            result = response.json()

            models = [model["id"] for model in result.get("data", [])]
            return models

        except Exception as e:
            logger.error(f"Error fetching available models: {e}")
            return []


# Example usage
if __name__ == "__main__":
    # Test AIML API provider
    import sys

    provider = AIMLAPIProvider()

    # Test basic generation
    print("Testing AIML API provider...")
    print("="*60)

    try:
        response = provider.generate(
            prompt="Generate a dark fantasy character description for a morally ambiguous assassin.",
            system_prompt="You are creating content for a dark fantasy RPG game.",
            model="meta-llama/Meta-Llama-3-70B-Instruct",
            temperature=0.7,
            max_tokens=500
        )

        print("Response:")
        print(response)
        print()
        print("✓ Generation successful!")

    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)

    # Test streaming
    print("\n" + "="*60)
    print("Testing streaming generation...")
    print("="*60)

    try:
        print("Response (streaming):")
        for chunk in provider.generate_streaming(
            prompt="Write a brief combat scene.",
            system_prompt="You are creating content for a dark fantasy RPG game.",
            model="mistralai/Mistral-7B-Instruct-v0.2"
        ):
            print(chunk, end="", flush=True)

        print("\n\n✓ Streaming successful!")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)

    # List available models
    print("\n" + "="*60)
    print("Available models:")
    print("="*60)

    models = provider.get_available_models()
    for model in models:
        print(f"  - {model}")
