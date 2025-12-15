"""
Generate LLM-driven objectives for test characters

Creates initial objectives for Fizrae Yinai and Sir Gelarthon Findraell
using LLM to analyze their character profiles and generate appropriate goals.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from database import db
from sqlalchemy import text
from uuid import UUID
from services.llm_service import get_llm_service, LLMUseCase
from services.objective_planner import ObjectivePlanner
import json

# Test character names
TEST_CHARACTERS = [
    "Fizrae Yinai",
    "Sir Gelarthon Findraell"
]

def get_character_profile(character_id: UUID) -> dict:
    """Get full character profile from database."""
    result = db.session.execute(
        text("""
            SELECT
                character_id, name, backstory, physical_appearance,
                current_clothing, role_responsibilities, personality_traits,
                speech_style, education_level, current_emotional_state,
                motivations_short_term, motivations_long_term,
                preferences, skills, social_class, hobbies,
                superstitions, secrets
            FROM character.character
            WHERE character_id = :character_id
        """),
        {"character_id": str(character_id)}
    )

    row = result.fetchone()
    if not row:
        raise ValueError(f"Character {character_id} not found")

    return {
        "character_id": str(row.character_id),
        "name": row.name,
        "backstory": row.backstory,
        "physical_appearance": row.physical_appearance,
        "current_clothing": row.current_clothing,
        "role_responsibilities": row.role_responsibilities,
        "personality_traits": row.personality_traits,
        "speech_style": row.speech_style,
        "education_level": row.education_level,
        "current_emotional_state": row.current_emotional_state,
        "motivations_short_term": row.motivations_short_term,
        "motivations_long_term": row.motivations_long_term,
        "preferences": row.preferences,
        "skills": row.skills,
        "social_class": row.social_class,
        "hobbies": row.hobbies,
        "superstitions": row.superstitions,
        "secrets": row.secrets
    }


def main():
    print("="*70)
    print("LLM-Driven Objective Generation for Test Characters")
    print("="*70)
    print()

    with app.app_context():
        # Get game state
        result = db.session.execute(
            text("SELECT game_state_id, current_turn FROM game.game_state LIMIT 1")
        )
        game_row = result.fetchone()

        if not game_row:
            print("[ERR] No game state found!")
            return 1

        game_id = game_row.game_state_id if isinstance(game_row.game_state_id, UUID) else UUID(game_row.game_state_id)
        current_turn = game_row.current_turn

        print(f"Game State ID: {game_id}")
        print(f"Current Turn: {current_turn}")
        print()

        # Initialize LLM service for objective planning
        print("Initializing LLM service...")
        # Use Claude Haiku (confirmed working, Sonnet not available on this API tier)
        from services.llm.claude import ClaudeProvider
        llm_provider = ClaudeProvider()
        objective_planner = ObjectivePlanner(llm_provider)
        print("[OK] LLM service initialized (Claude Haiku 3.5)")
        print()

        # Get test characters
        result = db.session.execute(
            text("""
                SELECT character_id, name
                FROM character.character
                WHERE name = ANY(:names)
            """),
            {"names": TEST_CHARACTERS}
        )

        characters = [(row.character_id if isinstance(row.character_id, UUID) else UUID(row.character_id), row.name) for row in result]

        if len(characters) != len(TEST_CHARACTERS):
            print(f"[ERR] Expected {len(TEST_CHARACTERS)} characters, found {len(characters)}")
            return 1

        print(f"Found {len(characters)} test characters:")
        for char_id, name in characters:
            print(f"  - {name}")
        print()

        # Generate objectives for each character
        for char_id, name in characters:
            print("-" * 70)
            print(f"Generating objectives for: {name}")
            print("-" * 70)

            # Get character profile
            profile = get_character_profile(char_id)

            print(f"  Role: {profile['role_responsibilities']}")
            print(f"  Personality: {json.dumps(profile['personality_traits'], indent=4)}")
            print(f"  Short-term motivations: {json.dumps(profile['motivations_short_term'], indent=4)}")
            print(f"  Long-term motivations: {json.dumps(profile['motivations_long_term'], indent=4)}")
            print()

            try:
                # Generate initial objectives using LLM
                print("  Calling LLM to generate objectives...")
                objective_ids = objective_planner.create_initial_objectives(
                    character_id=char_id,
                    game_id=game_id,
                    character_profile=profile,
                    current_turn=current_turn
                )

                print(f"  [OK] Created {len(objective_ids)} main objectives")

                # Get and display created objectives
                for obj_id in objective_ids:
                    result = db.session.execute(
                        text("""
                            SELECT description, priority, objective_type, is_atomic
                            FROM objective.character_objective
                            WHERE objective_id = :obj_id
                        """),
                        {"obj_id": str(obj_id)}
                    )
                    obj = result.fetchone()

                    print(f"    [{obj.priority}] {obj.description}")
                    print(f"           Type: {obj.objective_type}, Atomic: {obj.is_atomic}")

                    # Try to break down non-atomic objectives
                    if not obj.is_atomic:
                        print(f"           Breaking down into child objectives...")
                        try:
                            child_ids = objective_planner.break_down_objective(
                                objective_id=obj_id,
                                character_id=char_id,
                                game_id=game_id,
                                character_profile=profile,
                                context={},  # Empty context for initial breakdown
                                current_turn=current_turn
                            )

                            if child_ids:
                                print(f"           [OK] Created {len(child_ids)} child objectives")

                                # Display child objectives
                                for child_id in child_ids:
                                    result = db.session.execute(
                                        text("""
                                            SELECT description, priority, is_atomic
                                            FROM objective.character_objective
                                            WHERE objective_id = :obj_id
                                        """),
                                        {"obj_id": str(child_id)}
                                    )
                                    child = result.fetchone()
                                    atomic_marker = "[ATOMIC]" if child.is_atomic else ""
                                    print(f"             • [{child.priority}] {child.description} {atomic_marker}")
                            else:
                                print(f"           → No breakdown needed (objective is specific enough)")

                        except Exception as e:
                            print(f"           [ERR] Breakdown failed: {e}")

                print()

            except Exception as e:
                print(f"  [ERR] Failed to generate objectives: {e}")
                import traceback
                traceback.print_exc()
                print()
                continue

        print("="*70)
        print("[OK] Objective generation complete!")
        print("="*70)

        # Summary
        result = db.session.execute(
            text("""
                SELECT
                    c.name,
                    COUNT(o.objective_id) as obj_count,
                    SUM(CASE WHEN o.priority = 'high' THEN 1 ELSE 0 END) as high_priority,
                    SUM(CASE WHEN o.is_atomic = true THEN 1 ELSE 0 END) as atomic_count
                FROM character.character c
                LEFT JOIN objective.character_objective o ON o.character_id = c.character_id
                WHERE c.name = ANY(:names)
                GROUP BY c.name
            """),
            {"names": TEST_CHARACTERS}
        )

        print("\nSummary:")
        for row in result:
            print(f"  {row.name}:")
            print(f"    Total objectives: {row.obj_count}")
            print(f"    High priority: {row.high_priority}")
            print(f"    Atomic (actionable): {row.atomic_count}")

        return 0


if __name__ == "__main__":
    sys.exit(main())
