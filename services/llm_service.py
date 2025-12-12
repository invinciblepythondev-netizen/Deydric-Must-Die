"""
LLM Service Factory

Provides LLM providers configured for different use cases:
- Action generation (resilient, handles dark fantasy content)
- Objective planning (resilient, handles complex reasoning)
- Memory summarization (cheap, uses Claude Haiku)
- Quick decisions (cheap, for simple AI choices)
"""

import os
import logging
from enum import Enum
from typing import Optional, Dict
from dotenv import load_dotenv
from .llm.resilient_generator import ResilientActionGenerator, AllProvidersFailedError
from .llm.provider import LLMProvider
from .llm.claude import ClaudeProvider
from .llm.openai import OpenAIProvider
from .llm.aimlapi import AIMLAPIProvider
from .llm.provider_strategy import get_provider_strategy
from .llm.manual_fallback import ManualFallbackHandler
from .llm.prompt_templates import ProviderPromptTemplate

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


class LLMUseCase(Enum):
    """Different use cases for LLM services"""
    ACTION_GENERATION = "action_generation"
    OBJECTIVE_PLANNING = "objective_planning"
    MEMORY_SUMMARIZATION = "memory_summarization"
    QUICK_DECISIONS = "quick_decisions"


class LLMServiceFactory:
    """
    Factory for creating LLM service instances.

    Uses ResilientActionGenerator with fallback chain for most use cases.
    Uses cheaper models (Haiku) for summarization and quick decisions.
    """

    def __init__(self):
        """Initialize provider strategy and cache instances."""
        self.strategy = get_provider_strategy()
        self._cached_generators: Dict[str, ResilientActionGenerator] = {}
        self._cached_providers: Dict[str, LLMProvider] = {}

        # Initialize providers that are available
        self._init_providers()

    def _init_providers(self):
        """Initialize all available LLM providers."""
        providers = {}

        # Try Anthropic (Claude)
        try:
            claude = ClaudeProvider()
            providers["anthropic"] = claude
            logger.info("✓ Anthropic Claude provider initialized")
        except Exception as e:
            logger.warning(f"Could not initialize Anthropic provider: {e}")

        # Try OpenAI
        try:
            openai = OpenAIProvider()
            providers["openai"] = openai
            logger.info("✓ OpenAI provider initialized")
        except Exception as e:
            logger.warning(f"Could not initialize OpenAI provider: {e}")

        # Try AIML API
        try:
            aimlapi = AIMLAPIProvider()
            providers["aimlapi"] = aimlapi
            logger.info("✓ AIML API provider initialized")
        except Exception as e:
            logger.warning(f"Could not initialize AIML API provider: {e}")

        # Try Together.ai
        try:
            from .llm.together_ai import TogetherAIProvider
            together = TogetherAIProvider()
            providers["together_ai"] = together
            logger.info("✓ Together.ai provider initialized")
        except Exception as e:
            logger.warning(f"Could not initialize Together.ai provider: {e}")

        self._cached_providers = providers

        if not providers:
            raise RuntimeError(
                "No LLM providers could be initialized. "
                "Please check your API keys in .env file."
            )

    def get_action_generator(self) -> ResilientActionGenerator:
        """
        Get action generator with fallback chain.

        Uses ResilientActionGenerator which automatically tries providers
        in order until one succeeds. Handles dark fantasy content.

        Returns:
            ResilientActionGenerator instance
        """
        cache_key = "action_generator"

        if cache_key not in self._cached_generators:
            generator = ResilientActionGenerator(
                strategy=self.strategy,
                providers=self._cached_providers
            )
            self._cached_generators[cache_key] = generator
            logger.info("Created action generator with fallback chain")

        return self._cached_generators[cache_key]

    def get_objective_planner_provider(self) -> ResilientActionGenerator:
        """
        Get provider for objective planning.

        Uses same resilient approach as action generation since
        objective planning may involve complex/sensitive reasoning.

        Returns:
            ResilientActionGenerator instance
        """
        # Same as action generator - uses full fallback chain
        return self.get_action_generator()

    def get_summarization_provider(self) -> LLMProvider:
        """
        Get provider for memory summarization.

        Uses Claude Haiku specifically for cost efficiency.
        Haiku is 10x cheaper than Sonnet and sufficient for summarization.

        Returns:
            LLMProvider instance (Claude Haiku preferred)

        Raises:
            RuntimeError: If no suitable provider available
        """
        cache_key = "summarization"

        if cache_key not in self._cached_providers:
            # Try to use Claude Haiku (cheapest, good quality)
            if "anthropic" in self._cached_providers:
                self._cached_providers[cache_key] = self._cached_providers["anthropic"]
                logger.info("Using Claude Haiku for memory summarization")
            # Fallback to AIML Mistral (also cheap)
            elif "aimlapi" in self._cached_providers:
                self._cached_providers[cache_key] = self._cached_providers["aimlapi"]
                logger.info("Using AIML Mistral for memory summarization (Claude not available)")
            # Fallback to GPT-3.5 (also cheap)
            elif "openai" in self._cached_providers:
                self._cached_providers[cache_key] = self._cached_providers["openai"]
                logger.info("Using GPT-3.5 for memory summarization (Claude and AIML not available)")
            else:
                raise RuntimeError(
                    "No suitable provider for summarization. "
                    "Need Anthropic (Claude Haiku), AIML API, or OpenAI (GPT-3.5)."
                )

        return self._cached_providers[cache_key]

    def get_quick_decision_provider(self) -> LLMProvider:
        """
        Get provider for quick AI decisions.

        Uses cheap models for simple choices (e.g., which action to pick).

        Returns:
            LLMProvider instance (Haiku or GPT-3.5)
        """
        # Same as summarization - use cheap models
        return self.get_summarization_provider()

    def get_for_use_case(self, use_case: LLMUseCase):
        """
        Get appropriate provider/generator for a use case.

        Args:
            use_case: The use case enum value

        Returns:
            Either ResilientActionGenerator or LLMProvider
        """
        if use_case == LLMUseCase.ACTION_GENERATION:
            return self.get_action_generator()
        elif use_case == LLMUseCase.OBJECTIVE_PLANNING:
            return self.get_objective_planner_provider()
        elif use_case == LLMUseCase.MEMORY_SUMMARIZATION:
            return self.get_summarization_provider()
        elif use_case == LLMUseCase.QUICK_DECISIONS:
            return self.get_quick_decision_provider()
        else:
            raise ValueError(f"Unknown use case: {use_case}")


# Global singleton instance
_factory_instance: Optional[LLMServiceFactory] = None


def get_llm_service_factory() -> LLMServiceFactory:
    """Get or create the global LLM service factory."""
    global _factory_instance
    if _factory_instance is None:
        _factory_instance = LLMServiceFactory()
    return _factory_instance


def get_llm_service(use_case: LLMUseCase):
    """
    Convenience function to get LLM service for a use case.

    Args:
        use_case: The use case enum value

    Returns:
        Appropriate LLM service instance

    Example:
        action_gen = get_llm_service(LLMUseCase.ACTION_GENERATION)
        actions = action_gen.generate_action_options(character, context)
    """
    factory = get_llm_service_factory()
    return factory.get_for_use_case(use_case)


class UnifiedLLMService:
    """
    Unified high-level LLM service with manual fallback.

    Provides simple methods for each use case with automatic fallback to manual input.
    """

    def __init__(self):
        """Initialize unified service."""
        self.factory = get_llm_service_factory()
        self.manual_fallback = ManualFallbackHandler()
        self.prompt_templates = ProviderPromptTemplate()

    def generate_actions(
        self,
        character: Dict,
        game_context: Dict,
        num_options: int = 5
    ) -> list:
        """
        Generate character actions with automatic fallback.

        Returns:
            List of action dictionaries
        """
        logger.info(f"Generating {num_options} actions for {character.get('name')}")
        print("UnifiedLLMService.generate_actions called")
        try:
            generator = self.factory.get_action_generator()
            actions = generator.generate_action_options(
                character=character,
                context=game_context,
                num_options=num_options
            )
            print  (f"Generated actions: {actions}")
            return actions

        except AllProvidersFailedError as e:
            logger.warning("All providers failed, falling back to manual input")
            return self.manual_fallback.prompt_for_actions(
                character_name=character.get('name'),
                context_summary=game_context.get('situation_summary', 'Current game'),
                num_options=num_options,
                attempted_providers=e.attempted_providers
            )

    def plan_objectives(
        self,
        character_profile: Dict,
        planning_context: str
    ) -> Dict:
        """
        Plan objectives with automatic fallback.

        Returns:
            Objectives data dictionary
        """
        logger.info(f"Planning objectives for {character_profile.get('name')}")

        try:
            generator = self.factory.get_objective_planner_provider()
            # Use resilient generator for objectives
            # This is a simplified implementation - full version would need proper integration
            raise NotImplementedError("Objective planning via resilient generator needs full integration")

        except (AllProvidersFailedError, NotImplementedError) as e:
            logger.warning("Falling back to manual input for objectives")
            return self.manual_fallback.prompt_for_objectives(
                character_name=character_profile.get('name'),
                character_profile=character_profile,
                attempted_providers=getattr(e, 'attempted_providers', ['primary'])
            )

    def summarize_memory(
        self,
        turns: list,
        importance: str = "routine"
    ) -> str:
        """
        Summarize turns with automatic fallback.

        Returns:
            Summary text
        """
        logger.info(f"Summarizing {len(turns)} turns")

        try:
            provider = self.factory.get_summarization_provider()
            prompt = self.prompt_templates.format_memory_summary_prompt(
                provider="anthropic",  # Assuming Claude for summarization
                turns=turns,
                importance=importance
            )

            response = provider.generate(
                prompt=prompt,
                system_prompt="You are a narrative AI that summarizes game events.",
                temperature=0.5,
                max_tokens=500
            )
            return response

        except Exception as e:
            logger.warning(f"Summarization failed: {e}, falling back to manual input")
            return self.manual_fallback.prompt_for_summary(
                turns=turns,
                attempted_providers=["summarization_provider"]
            )


# Global unified service instance
_unified_service_instance: Optional[UnifiedLLMService] = None


def get_unified_llm_service() -> UnifiedLLMService:
    """Get or create the global unified LLM service."""
    global _unified_service_instance
    if _unified_service_instance is None:
        _unified_service_instance = UnifiedLLMService()
    return _unified_service_instance


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("Initializing LLM services...")
    factory = get_llm_service_factory()

    print("\nAvailable providers:")
    for name, provider in factory._cached_providers.items():
        print(f"  - {name}: {provider.__class__.__name__}")

    print("\nGetting services for different use cases:")

    action_gen = get_llm_service(LLMUseCase.ACTION_GENERATION)
    print(f"  Action generation: {action_gen.__class__.__name__}")

    obj_planner = get_llm_service(LLMUseCase.OBJECTIVE_PLANNING)
    print(f"  Objective planning: {obj_planner.__class__.__name__}")

    summarizer = get_llm_service(LLMUseCase.MEMORY_SUMMARIZATION)
    print(f"  Memory summarization: {summarizer.__class__.__name__}")

    quick_decide = get_llm_service(LLMUseCase.QUICK_DECISIONS)
    print(f"  Quick decisions: {quick_decide.__class__.__name__}")
