"""
Manual Fallback System

When all LLM providers fail, prompt the user/player to provide the response manually.
Validates the structure to ensure it matches expected format.

This is a BLOCKING system - it will wait for valid input before proceeding.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from jsonschema import validate, ValidationError, Draft7Validator

logger = logging.getLogger(__name__)


class ManualFallbackHandler:
    """
    Handles manual input when all LLM providers fail.

    Prompts the user for input and validates structure.
    BLOCKS until valid input is provided.
    """

    # JSON schemas for different response types
    ACTION_SCHEMA = {
        "type": "array",
        "items": {
            "type": "object",
            "required": ["thought", "action", "action_type"],
            "properties": {
                "thought": {"type": "string"},
                "speech": {"type": ["string", "null"]},
                "action": {"type": "string"},
                "action_type": {
                    "type": "string",
                    "enum": ["speak", "move", "interact", "attack", "observe", "wait", "think"]
                }
            }
        },
        "minItems": 1
    }

    OBJECTIVE_SCHEMA = {
        "type": "object",
        "required": ["objectives"],
        "properties": {
            "objectives": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["description", "priority"],
                    "properties": {
                        "description": {"type": "string"},
                        "priority": {
                            "type": "string",
                            "enum": ["critical", "high", "medium", "low"]
                        },
                        "success_criteria": {"type": "string"},
                        "mood_impact_positive": {"type": "integer"},
                        "mood_impact_negative": {"type": "integer"}
                    }
                }
            }
        }
    }

    @staticmethod
    def prompt_for_actions(
        character_name: str,
        context_summary: str,
        num_options: int,
        attempted_providers: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Prompt user to manually provide action options.

        BLOCKS until valid input is provided.

        Args:
            character_name: Name of character needing actions
            context_summary: Brief context description
            num_options: Number of actions needed
            attempted_providers: List of providers that failed

        Returns:
            List of action dictionaries

        Raises:
            ValueError: If user explicitly cancels
        """
        print("\n" + "="*70)
        print("WARNING: ALL LLM PROVIDERS FAILED")
        print("="*70)
        print(f"\nAttempted providers: {', '.join(attempted_providers)}")
        print(f"\nCharacter: {character_name}")
        print(f"Context: {context_summary}")
        print(f"\nPlease provide {num_options} action options manually.")
        print("\n" + "-"*70)

        # Show example format
        print("\nRequired JSON format:")
        print(json.dumps([
            {
                "thought": "What the character is thinking (private)",
                "speech": "What they say (or null if silent)",
                "action": "What they physically do",
                "action_type": "speak|move|interact|attack|observe|wait"
            }
        ], indent=2))
        print("-"*70)

        # Prompt for input
        print("\nEnter JSON array of actions (or 'cancel' to abort):")
        print("(You can paste multi-line JSON)")
        print("(Press Enter twice after pasting to submit)")
        print("")

        # Collect multi-line input
        lines = []
        empty_line_count = 0

        while True:
            try:
                line = input()

                # Check for cancel
                if line.strip().lower() == 'cancel':
                    raise ValueError("User cancelled manual input")

                # Track empty lines for submission detection
                if line.strip() == '':
                    empty_line_count += 1
                    if empty_line_count >= 2:
                        # Two empty lines = submit
                        break
                else:
                    empty_line_count = 0
                    lines.append(line)

                # Try to parse JSON after closing bracket
                if line.strip().endswith(']') or line.strip().endswith('}'):
                    try:
                        combined = '\n'.join(lines)
                        actions = json.loads(combined)

                        # Validate structure
                        validate(instance=actions, schema=ManualFallbackHandler.ACTION_SCHEMA)

                        logger.info(f"Manual input validated: {len(actions)} actions")
                        print(f"\n[SUCCESS] Valid input received: {len(actions)} actions")
                        return actions

                    except json.JSONDecodeError:
                        # Not complete JSON yet, keep reading
                        continue
                    except ValidationError as e:
                        print(f"\n[ERROR] Invalid structure: {e.message}")
                        print("\nPlease try again (or 'cancel' to abort):")
                        lines = []
                        empty_line_count = 0

            except EOFError:
                # End of input without valid JSON
                if lines:
                    # Try to parse what we have
                    try:
                        combined = '\n'.join(lines)
                        actions = json.loads(combined)
                        validate(instance=actions, schema=ManualFallbackHandler.ACTION_SCHEMA)
                        logger.info(f"Manual input validated: {len(actions)} actions")
                        return actions
                    except (json.JSONDecodeError, ValidationError) as e:
                        raise ValueError(f"Invalid or incomplete JSON input: {e}")
                else:
                    raise ValueError("No input provided")

    @staticmethod
    def prompt_for_objectives(
        character_name: str,
        character_profile: Dict[str, Any],
        attempted_providers: List[str]
    ) -> Dict[str, Any]:
        """
        Prompt user to manually provide objectives.

        BLOCKS until valid input is provided.

        Args:
            character_name: Name of character needing objectives
            character_profile: Character data for context
            attempted_providers: List of providers that failed

        Returns:
            Objectives data dictionary

        Raises:
            ValueError: If user explicitly cancels
        """
        print("\n" + "="*70)
        print("WARNING: ALL LLM PROVIDERS FAILED - OBJECTIVE PLANNING")
        print("="*70)
        print(f"\nAttempted providers: {', '.join(attempted_providers)}")
        print(f"\nCharacter: {character_name}")
        print(f"Motivations: {character_profile.get('motivations_short_term')}")
        print("\nPlease provide objectives manually.")
        print("\n" + "-"*70)

        # Show example format
        print("\nRequired JSON format:")
        print(json.dumps({
            "objectives": [
                {
                    "description": "Objective description",
                    "priority": "high",
                    "success_criteria": "What defines completion",
                    "mood_impact_positive": 5,
                    "mood_impact_negative": -5
                }
            ]
        }, indent=2))
        print("-"*70)

        print("\nEnter JSON (or 'cancel' to abort):")
        print("(Press Enter twice after pasting to submit)")
        print("")

        lines = []
        empty_line_count = 0

        while True:
            try:
                line = input()

                if line.strip().lower() == 'cancel':
                    raise ValueError("User cancelled manual input")

                if line.strip() == '':
                    empty_line_count += 1
                    if empty_line_count >= 2:
                        break
                else:
                    empty_line_count = 0
                    lines.append(line)

                if line.strip().endswith('}'):
                    try:
                        combined = '\n'.join(lines)
                        objectives_data = json.loads(combined)

                        # Validate structure
                        validate(instance=objectives_data, schema=ManualFallbackHandler.OBJECTIVE_SCHEMA)

                        logger.info(
                            f"Manual objectives validated: "
                            f"{len(objectives_data['objectives'])} objectives"
                        )
                        print(f"\n[SUCCESS] Valid input received: {len(objectives_data['objectives'])} objectives")
                        return objectives_data

                    except json.JSONDecodeError:
                        continue
                    except ValidationError as e:
                        print(f"\n[ERROR] Invalid structure: {e.message}")
                        print("\nPlease try again (or 'cancel' to abort):")
                        lines = []
                        empty_line_count = 0

            except EOFError:
                if lines:
                    try:
                        combined = '\n'.join(lines)
                        objectives_data = json.loads(combined)
                        validate(instance=objectives_data, schema=ManualFallbackHandler.OBJECTIVE_SCHEMA)
                        logger.info(f"Manual objectives validated")
                        return objectives_data
                    except (json.JSONDecodeError, ValidationError) as e:
                        raise ValueError(f"Invalid or incomplete JSON input: {e}")
                else:
                    raise ValueError("No input provided")

    @staticmethod
    def prompt_for_summary(
        turns: List[Dict[str, Any]],
        attempted_providers: List[str]
    ) -> str:
        """
        Prompt user to manually provide a summary.

        BLOCKS until input is provided.

        Args:
            turns: Turn history to summarize
            attempted_providers: List of providers that failed

        Returns:
            Summary text

        Raises:
            ValueError: If user cancels
        """
        print("\n" + "="*70)
        print("WARNING: ALL LLM PROVIDERS FAILED - MEMORY SUMMARIZATION")
        print("="*70)
        print(f"\nAttempted providers: {', '.join(attempted_providers)}")
        print(f"\nTurns to summarize ({len(turns)} turns):")

        for turn in turns[:5]:  # Show first 5
            desc = turn.get('action_description', '')
            print(f"  Turn {turn['turn_number']}: {desc[:80]}...")

        if len(turns) > 5:
            print(f"  ... and {len(turns) - 5} more turns")

        print("\nPlease provide a 2-3 paragraph summary:")
        print("(Type 'END' on a new line when done, or 'cancel' to abort)")
        print("-"*70)
        print("")

        lines = []
        while True:
            try:
                line = input()
                if line.strip().lower() == 'cancel':
                    raise ValueError("User cancelled manual input")
                if line.strip().upper() == 'END':
                    break
                lines.append(line)
            except EOFError:
                break

        summary = '\n'.join(lines).strip()

        if not summary:
            raise ValueError("Empty summary provided")

        logger.info(f"Manual summary provided ({len(summary)} characters)")
        print(f"\n[SUCCESS] Summary received ({len(summary)} characters)")
        return summary

    @staticmethod
    def get_validation_errors(data: Any, schema: Dict) -> List[str]:
        """
        Get all validation errors for data against schema.

        Args:
            data: Data to validate
            schema: JSON schema

        Returns:
            List of error messages
        """
        validator = Draft7Validator(schema)
        errors = sorted(validator.iter_errors(data), key=lambda e: e.path)

        return [
            f"Field '{'.'.join(str(p) for p in error.path)}': {error.message}"
            for error in errors
        ]
