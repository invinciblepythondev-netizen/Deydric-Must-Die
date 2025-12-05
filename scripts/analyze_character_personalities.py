"""
Analyze character personalities and suggest cognitive trait assignments.

This script reads character data and suggests which cognitive traits
should be assigned based on personality descriptions.
"""

import os
import sys
from pathlib import Path
import json
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


# Cognitive trait definitions for reference
TRAIT_DEFINITIONS = {
    'Methodical Planner': 'Carefully plans multiple steps ahead with detailed breakdown',
    'Impulsive': 'Acts on immediate desires without extensive planning',
    'Detail-Oriented': 'Breaks objectives into fine-grained steps',
    'Scattered': 'Difficulty maintaining focus, jumps between objectives',
    'Single-Minded': 'Laser focus on one goal at a time',
    'Anxious': 'Highly aware of deadlines and consequences',
    'Laid-Back': 'Relaxed approach to planning and deadlines',
    'Strategic Thinker': 'Long-term planning with contingencies'
}


def analyze_personalities():
    """Analyze character personalities and suggest trait assignments."""

    print("=" * 80)
    print("Character Personality Analysis")
    print("=" * 80)

    with app.app_context():
        # Get all characters
        result = db.session.execute(
            text("""
                SELECT
                    character_id,
                    name,
                    short_name,
                    personality_traits,
                    role_responsibilities,
                    motivations_short_term,
                    motivations_long_term,
                    inner_conflict,
                    core_values
                FROM character.character
                ORDER BY name
            """)
        ).fetchall()

        print(f"\nFound {len(result)} characters\n")

        # Get available traits
        traits = db.session.execute(
            text("SELECT trait_id, trait_name FROM objective.cognitive_trait WHERE is_active = TRUE")
        ).fetchall()

        trait_map = {trait[1]: trait[0] for trait in traits}

        print("\nAvailable Cognitive Traits:")
        for trait_name, description in TRAIT_DEFINITIONS.items():
            print(f"  - {trait_name}: {description}")

        print("\n" + "=" * 80)
        print("Character Analysis & Trait Recommendations")
        print("=" * 80)

        recommendations = {}

        for row in result:
            char_id = row[0]
            name = row[1]
            short_name = row[2]
            personality = row[3] if row[3] else []
            role = row[4] or ''
            motivations_short = row[5] if row[5] else []
            motivations_long = row[6] if row[6] else []
            inner_conflict = row[7] or ''
            core_values = row[8] if row[8] else []

            print(f"\n{'='*80}")
            print(f"Character: {name} ({short_name})")
            print(f"{'='*80}")
            print(f"Role: {role}")
            print(f"\nPersonality Traits:")
            for trait in personality[:5]:  # Show first 5
                print(f"  - {trait}")

            print(f"\nShort-term Goals:")
            for goal in motivations_short[:3]:
                print(f"  - {goal}")

            print(f"\nCore Values:")
            for value in core_values[:3]:
                print(f"  - {value}")

            if inner_conflict:
                print(f"\nInner Conflict: {inner_conflict[:200]}...")

            # Analyze and suggest traits
            print(f"\nSuggested Cognitive Traits:")

            personality_text = ' '.join(personality).lower() if personality else ''
            role_text = role.lower()
            conflict_text = inner_conflict.lower() if inner_conflict else ''

            suggested_traits = []

            # Methodical Planner: organized, careful, planning keywords
            if any(word in personality_text for word in ['methodical', 'organized', 'careful', 'disciplined']):
                suggested_traits.append(('Methodical Planner', 8))

            # Strategic Thinker: strategic, cunning, long-term thinker
            if any(word in personality_text for word in ['strategic', 'cunning', 'ambitious']):
                suggested_traits.append(('Strategic Thinker', 7))

            # Detail-Oriented: perfectionist, meticulous, detail
            if any(word in personality_text for word in ['detail', 'perfectionist', 'meticulous', 'precise']):
                suggested_traits.append(('Detail-Oriented', 7))

            # Anxious: anxious, fearful, worried, paranoid
            if any(word in personality_text for word in ['anxious', 'fearful', 'worried', 'paranoid', 'suspicious']):
                suggested_traits.append(('Anxious', 7))

            # Impulsive: impulsive, rash, spontaneous
            if any(word in personality_text for word in ['impulsive', 'rash', 'spontaneous', 'reckless']):
                suggested_traits.append(('Impulsive', 7))

            # Laid-Back: relaxed, calm, easygoing
            if any(word in personality_text for word in ['relaxed', 'calm', 'easygoing', 'laid-back', 'patient']):
                suggested_traits.append(('Laid-Back', 6))

            # Single-Minded: focused, determined, driven
            if any(word in personality_text for word in ['focused', 'determined', 'driven', 'obsessive']):
                suggested_traits.append(('Single-Minded', 7))

            # Scattered: distracted, chaotic, disorganized
            if any(word in personality_text for word in ['scattered', 'distracted', 'chaotic', 'disorganized']):
                suggested_traits.append(('Scattered', 6))

            # If no traits matched, assign defaults based on role
            if not suggested_traits:
                if 'lord' in role_text or 'leader' in role_text:
                    suggested_traits = [('Strategic Thinker', 7), ('Methodical Planner', 6)]
                elif 'advisor' in role_text or 'scholar' in role_text:
                    suggested_traits = [('Detail-Oriented', 7), ('Methodical Planner', 7)]
                elif 'guard' in role_text or 'soldier' in role_text:
                    suggested_traits = [('Single-Minded', 7), ('Laid-Back', 5)]
                else:
                    suggested_traits = [('Methodical Planner', 6), ('Detail-Oriented', 5)]

            for trait_name, score in suggested_traits:
                print(f"  - {trait_name}: score {score}/10")

            recommendations[char_id] = {
                'name': name,
                'short_name': short_name,
                'traits': suggested_traits
            }

        print("\n" + "=" * 80)
        print("Summary of Recommendations")
        print("=" * 80)

        for char_id, data in recommendations.items():
            print(f"\n{data['name']} ({data['short_name']}):")
            for trait_name, score in data['traits']:
                print(f"  - {trait_name}: {score}/10")

        # Save recommendations to JSON
        output_file = project_root / 'character_trait_recommendations.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            # Convert UUID to string for JSON serialization
            json_recommendations = {}
            for char_id, data in recommendations.items():
                json_recommendations[str(char_id)] = data

            json.dump(json_recommendations, f, indent=2, ensure_ascii=False)

        print(f"\n[OK] Recommendations saved to: character_trait_recommendations.json")

        return recommendations


if __name__ == '__main__':
    try:
        analyze_personalities()
        exit(0)
    except Exception as e:
        print(f"\n[FAIL] Error analyzing personalities: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
