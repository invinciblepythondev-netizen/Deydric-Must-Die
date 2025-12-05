"""
Assign cognitive traits to characters and initialize recurring objectives.

This script:
1. Reads character trait recommendations from JSON
2. Assigns cognitive traits to each character
3. Recalculates planning capacity for each character
4. Initializes recurring objectives (sleep, hunger, etc.)
"""

import os
import sys
from pathlib import Path
import json
from uuid import UUID
from sqlalchemy import text
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Must import after adding to path
from app import app
from database import db

# Load environment variables
load_dotenv()


def assign_traits_and_objectives(game_id: str, dry_run: bool = False):
    """
    Assign cognitive traits to characters and initialize objectives.

    Args:
        game_id: UUID of the game state
        dry_run: If True, preview changes without committing
    """

    print("=" * 80)
    print("Character Trait Assignment & Objective Initialization")
    print("=" * 80)

    if dry_run:
        print("\n[DRY RUN MODE - No changes will be made]\n")

    # Load recommendations
    recommendations_file = project_root / 'character_trait_recommendations.json'

    if not recommendations_file.exists():
        print(f"[FAIL] Recommendations file not found: {recommendations_file}")
        print("Run analyze_character_personalities.py first!")
        return False

    with open(recommendations_file, 'r', encoding='utf-8') as f:
        recommendations = json.load(f)

    print(f"Loaded recommendations for {len(recommendations)} characters\n")

    with app.app_context():
        try:
            # Get all cognitive traits
            traits_result = db.session.execute(
                text("SELECT trait_id, trait_name FROM objective.cognitive_trait WHERE is_active = TRUE")
            ).fetchall()

            trait_map = {name: str(trait_id) for trait_id, name in traits_result}

            print("Available Traits:")
            for name in trait_map.keys():
                print(f"  - {name}")
            print()

            # Get all recurring templates
            templates_result = db.session.execute(
                text("SELECT template_id, name FROM objective.recurring_objective_template WHERE is_active = TRUE")
            ).fetchall()

            print(f"Found {len(templates_result)} recurring objective templates\n")

            success_count = 0

            # Process each character
            for char_id_str, char_data in recommendations.items():
                char_id = UUID(char_id_str)
                char_name = char_data['name']
                char_short = char_data['short_name']
                traits = char_data['traits']

                print("=" * 80)
                print(f"Processing: {char_name} ({char_short})")
                print("=" * 80)

                # Assign each trait
                print(f"\nAssigning {len(traits)} cognitive traits:")
                for trait_name, score in traits:
                    trait_id = trait_map.get(trait_name)

                    if not trait_id:
                        print(f"  [WARN] Trait not found: {trait_name}")
                        continue

                    print(f"  - {trait_name}: score {score}/10", end='')

                    if not dry_run:
                        # Assign trait
                        db.session.execute(
                            text("""
                                INSERT INTO objective.character_cognitive_trait_score
                                    (character_id, trait_id, score)
                                VALUES (:character_id, :trait_id, :score)
                                ON CONFLICT (character_id, trait_id)
                                DO UPDATE SET
                                    score = EXCLUDED.score,
                                    updated_at = CURRENT_TIMESTAMP
                            """),
                            {
                                "character_id": str(char_id),
                                "trait_id": trait_id,
                                "score": score
                            }
                        )
                        print(" [OK]")
                    else:
                        print(" [SKIP - Dry Run]")

                # Recalculate planning capacity
                print("\nRecalculating planning capacity...", end='')

                if not dry_run:
                    db.session.execute(
                        text("SELECT objective.character_planning_state_recalculate(:character_id)"),
                        {"character_id": str(char_id)}
                    )
                    print(" [OK]")

                    # Get planning state
                    planning_state = db.session.execute(
                        text("""
                            SELECT
                                max_active_high_priority,
                                max_objective_depth,
                                planning_frequency_turns,
                                focus_score
                            FROM objective.character_planning_state
                            WHERE character_id = :character_id
                        """),
                        {"character_id": str(char_id)}
                    ).fetchone()

                    if planning_state:
                        print(f"\n  Planning Capacity:")
                        print(f"    Max high-priority objectives: {planning_state[0]}")
                        print(f"    Max objective depth: {planning_state[1]}")
                        print(f"    Planning frequency: every {planning_state[2]} turns")
                        print(f"    Focus score: {planning_state[3]:.1f}/10")
                else:
                    print(" [SKIP - Dry Run]")

                # Initialize recurring objectives
                print("\nInitializing recurring objectives...")

                if not dry_run:
                    for template_id, template_name in templates_result:
                        print(f"  - {template_name}...", end='')

                        # Get template data
                        template = db.session.execute(
                            text("""
                                SELECT description_template, success_criteria_template, default_priority
                                FROM objective.recurring_objective_template
                                WHERE template_id = :template_id
                            """),
                            {"template_id": str(template_id)}
                        ).fetchone()

                        if template:
                            # Create objective using stored procedure
                            db.session.execute(
                                text("""
                                    SELECT objective.character_objective_upsert(
                                        NULL, :character_id, :game_id, NULL,
                                        'recurring'::objective.objective_type,
                                        :description, :success_criteria,
                                        :priority::objective.priority_level,
                                        'active'::objective.objective_status,
                                        'automatic'::objective.objective_source,
                                        NULL, NULL, FALSE,
                                        NULL, NULL, 0,
                                        NULL, TRUE, '{}'::jsonb,
                                        0, 0
                                    )
                                """),
                                {
                                    "character_id": str(char_id),
                                    "game_id": game_id,
                                    "description": template[0],
                                    "success_criteria": template[1],
                                    "priority": template[2]
                                }
                            )
                            print(" [OK]")
                        else:
                            print(" [SKIP - Template not found]")
                else:
                    for _, template_name in templates_result:
                        print(f"  - {template_name} [SKIP - Dry Run]")

                if not dry_run:
                    db.session.commit()

                success_count += 1
                print(f"\n[OK] {char_name} integration complete")

            print("\n" + "=" * 80)
            if dry_run:
                print(f"[DRY RUN] Would process {success_count}/{len(recommendations)} characters")
            else:
                print(f"[OK] Successfully integrated {success_count}/{len(recommendations)} characters")
            print("=" * 80)

            return True

        except Exception as e:
            print(f"\n[FAIL] Error during assignment: {str(e)}")
            if not dry_run:
                db.session.rollback()
            import traceback
            traceback.print_exc()
            return False


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Assign cognitive traits to characters')
    parser.add_argument('--game-id', required=True, help='Game state ID')
    parser.add_argument('--dry-run', action='store_true', help='Preview without making changes')
    args = parser.parse_args()

    try:
        success = assign_traits_and_objectives(args.game_id, dry_run=args.dry_run)
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n[FAIL] Script failed: {e}")
        exit(1)
