"""
Provider-Specific Prompt Templates

Different providers respond better to different formatting:
- Claude prefers XML-like structure (<context>, <task>)
- OpenAI prefers JSON/Markdown
- Open models are flexible but benefit from simpler prompts

This module provides optimized templates for each provider and use case.
"""

from typing import Dict, Any, List
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class PromptFormat(Enum):
    """Prompt formatting styles"""
    CLAUDE_XML = "claude_xml"          # XML-like structure for Claude
    OPENAI_JSON = "openai_json"        # JSON/Markdown for OpenAI
    OPEN_MODEL = "open_model"          # Flexible for open models


class ProviderPromptTemplate:
    """
    Generates provider-optimized prompts for different use cases.

    Use cases supported:
    - Action generation
    - Objective planning
    - Memory summarization
    """

    # Map providers to preferred formats
    PROVIDER_FORMATS = {
        "anthropic": PromptFormat.CLAUDE_XML,
        "openai": PromptFormat.OPENAI_JSON,
        "aimlapi": PromptFormat.OPEN_MODEL,
        "together_ai": PromptFormat.OPEN_MODEL,
        "local": PromptFormat.OPEN_MODEL
    }

    @classmethod
    def format_action_generation_prompt(
        cls,
        provider: str,
        character_context: str,
        num_options: int
    ) -> str:
        """
        Format action generation prompt for specific provider.

        Args:
            provider: Provider name
            character_context: Assembled character context
            num_options: Number of action options to generate

        Returns:
            Formatted prompt
        """
        format_style = cls.PROVIDER_FORMATS.get(provider, PromptFormat.OPEN_MODEL)

        logger.debug(f"Formatting action prompt for {provider} ({format_style.value})")

        if format_style == PromptFormat.CLAUDE_XML:
            return cls._format_claude_action_prompt(character_context, num_options)
        elif format_style == PromptFormat.OPENAI_JSON:
            return cls._format_openai_action_prompt(character_context, num_options)
        else:
            return cls._format_open_model_action_prompt(character_context, num_options)

    @staticmethod
    def _format_claude_action_prompt(context: str, num_options: int) -> str:
        """Claude-optimized format with XML structure."""
        return f"""<context>
{context}
</context>

<task>
Generate {num_options} possible action options for this character.

Each action should include:
1. <thought>Private thought (what they're thinking)</thought>
2. <speech>What they say (if anything, or null)</speech>
3. <action>Physical action they take</action>
4. <action_type>Category: speak/move/interact/attack/observe/wait/think</action_type>

Respond with a JSON array of actions.
</task>

<format>
Return ONLY a valid JSON array with no additional commentary:
[
  {{
    "thought": "...",
    "speech": "..." or null,
    "action": "...",
    "action_type": "..."
  }}
]
</format>"""

    @staticmethod
    def _format_openai_action_prompt(context: str, num_options: int) -> str:
        """OpenAI-optimized format with JSON structure."""
        return f"""# Character Context

{context}

# Task

Generate **{num_options}** possible action options for this character.

## Action Format

Each action must include:
- `thought`: Private thought (what they're thinking)
- `speech`: What they say (if anything, or null)
- `action`: Physical action they take
- `action_type`: One of: speak, move, interact, attack, observe, wait, think

## Response Format

Return ONLY a valid JSON array:

```json
[
  {{
    "thought": "I must tread carefully...",
    "speech": "Good evening, Lord Castellan.",
    "action": "Character bows respectfully.",
    "action_type": "interact"
  }}
]
```

Respond with valid JSON array only, no additional text."""

    @staticmethod
    def _format_open_model_action_prompt(context: str, num_options: int) -> str:
        """Flexible format for open models."""
        return f"""{context}

Task: Generate {num_options} action options for this character.

Format each as JSON with: thought, speech (or null), action, action_type

Response (JSON array only):"""

    @classmethod
    def format_objective_planning_prompt(
        cls,
        provider: str,
        character_profile: Dict[str, Any],
        planning_context: str
    ) -> str:
        """
        Format objective planning prompt for specific provider.

        Args:
            provider: Provider name
            character_profile: Character data
            planning_context: Current situation/context

        Returns:
            Formatted prompt
        """
        format_style = cls.PROVIDER_FORMATS.get(provider, PromptFormat.OPEN_MODEL)

        logger.debug(f"Formatting planning prompt for {provider} ({format_style.value})")

        if format_style == PromptFormat.CLAUDE_XML:
            return cls._format_claude_planning_prompt(character_profile, planning_context)
        elif format_style == PromptFormat.OPENAI_JSON:
            return cls._format_openai_planning_prompt(character_profile, planning_context)
        else:
            return cls._format_open_model_planning_prompt(character_profile, planning_context)

    @staticmethod
    def _format_claude_planning_prompt(character: Dict[str, Any], context: str) -> str:
        """Claude-optimized planning format."""
        return f"""<character>
Name: {character.get('name')}
Role: {character.get('role_responsibilities')}
Personality: {character.get('personality_traits')}
Short-term motivations: {character.get('motivations_short_term')}
Long-term motivations: {character.get('motivations_long_term')}
Backstory: {character.get('backstory', '')[:300]}...
</character>

<context>
{context}
</context>

<task>
Create 2-4 main objectives for this character based on their profile.

Consider:
- What are their immediate needs?
- What drives them in the long term?
- What obstacles might they face?
- What would success look like?
</task>

<format>
Return ONLY valid JSON with this structure:
{{
  "objectives": [
    {{
      "description": "Objective description",
      "priority": "high|medium|low",
      "success_criteria": "What defines completion",
      "mood_impact_positive": 5,
      "mood_impact_negative": -5
    }}
  ]
}}
</format>"""

    @staticmethod
    def _format_openai_planning_prompt(character: Dict[str, Any], context: str) -> str:
        """OpenAI-optimized planning format."""
        return f"""# Character Profile

- **Name**: {character.get('name')}
- **Role**: {character.get('role_responsibilities')}
- **Personality**: {character.get('personality_traits')}
- **Short-term motivations**: {character.get('motivations_short_term')}
- **Long-term motivations**: {character.get('motivations_long_term')}
- **Backstory**: {character.get('backstory', '')[:300]}...

# Current Context

{context}

# Task

Create 2-4 main objectives for this character based on their profile and current situation.

## Response Format

Return ONLY valid JSON:

```json
{{
  "objectives": [
    {{
      "description": "Objective description",
      "priority": "high",
      "success_criteria": "What defines completion",
      "mood_impact_positive": 5,
      "mood_impact_negative": -5
    }}
  ]
}}
```

Respond with valid JSON only, no additional text."""

    @staticmethod
    def _format_open_model_planning_prompt(character: Dict[str, Any], context: str) -> str:
        """Flexible planning format for open models."""
        return f"""Character: {character.get('name')}
Motivations: {character.get('motivations_short_term')}
Context: {context}

Create 2-4 objectives as JSON:

{{
  "objectives": [
    {{
      "description": "...",
      "priority": "high|medium|low",
      "success_criteria": "...",
      "mood_impact_positive": 5,
      "mood_impact_negative": -5
    }}
  ]
}}

Response (JSON only):"""

    @classmethod
    def format_memory_summary_prompt(
        cls,
        provider: str,
        turns: List[Dict[str, Any]],
        importance: str = "routine"
    ) -> str:
        """
        Format memory summarization prompt for specific provider.

        Args:
            provider: Provider name
            turns: Turn history to summarize
            importance: 'critical' or 'routine'

        Returns:
            Formatted prompt
        """
        format_style = cls.PROVIDER_FORMATS.get(provider, PromptFormat.OPEN_MODEL)

        logger.debug(f"Formatting summary prompt for {provider} ({format_style.value})")

        if format_style == PromptFormat.CLAUDE_XML:
            return cls._format_claude_summary_prompt(turns, importance)
        elif format_style == PromptFormat.OPENAI_JSON:
            return cls._format_openai_summary_prompt(turns, importance)
        else:
            return cls._format_open_model_summary_prompt(turns, importance)

    @staticmethod
    def _format_claude_summary_prompt(turns: List[Dict[str, Any]], importance: str) -> str:
        """Claude-optimized summary format."""
        turns_text = "\n".join([
            f"Turn {t['turn_number']}: {t['action_description']}"
            for t in turns
        ])

        emphasis = "Pay special attention to consequences and emotional impact." if importance == "critical" else ""

        return f"""<turns>
{turns_text}
</turns>

<task>
Summarize these game turns into a concise narrative.

Focus on:
- Key actions taken
- Important interactions
- Consequences and outcomes
- Emotional/relationship changes

{emphasis}

Provide a 2-3 paragraph summary.
</task>

<format>
Return the summary as plain text, no JSON or markup.
</format>"""

    @staticmethod
    def _format_openai_summary_prompt(turns: List[Dict[str, Any]], importance: str) -> str:
        """OpenAI-optimized summary format."""
        turns_text = "\n".join([
            f"Turn {t['turn_number']}: {t['action_description']}"
            for t in turns
        ])

        emphasis = "\n**Important**: This is a critical event - pay special attention to consequences and emotional impact." if importance == "critical" else ""

        return f"""# Game Turns to Summarize

{turns_text}

# Task

Summarize these game turns into a concise narrative (2-3 paragraphs).

Focus on:
- Key actions taken
- Important interactions
- Consequences and outcomes
- Emotional/relationship changes

{emphasis}

Provide the summary as plain text."""

    @staticmethod
    def _format_open_model_summary_prompt(turns: List[Dict[str, Any]], importance: str) -> str:
        """Flexible summary format for open models."""
        turns_text = "\n".join([
            f"Turn {t['turn_number']}: {t['action_description']}"
            for t in turns
        ])

        return f"""Turns:
{turns_text}

Summarize in 2-3 paragraphs. Focus on key actions, interactions, and consequences.

Summary:"""

    @classmethod
    def get_format_for_provider(cls, provider: str) -> PromptFormat:
        """
        Get the preferred format for a provider.

        Args:
            provider: Provider name

        Returns:
            PromptFormat enum value
        """
        return cls.PROVIDER_FORMATS.get(provider, PromptFormat.OPEN_MODEL)
