"""
Seed cognitive traits into the database (standalone version).
These traits define how characters plan and manage objectives.
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv('NEON_DATABASE_URL')

if not DATABASE_URL:
    print("ERROR: NEON_DATABASE_URL not found in environment variables")
    sys.exit(1)


COGNITIVE_TRAITS = [
    {
        'trait_name': 'Methodical Planner',
        'description': 'Carefully plans multiple steps ahead with detailed breakdown',
        'planning_capacity_modifier': 0.5,  # +0.5 objectives per point
        'focus_modifier': 1.0,  # +1.0 focus per point
        'max_depth_modifier': 0.3,  # +0.3 depth levels per point
        'planning_frequency_modifier': -0.5,  # Plans 0.5 turns MORE frequently per point
        'effects': {
            'deadline_sensitivity': 1.2,
            'completion_threshold': 0.95
        }
    },
    {
        'trait_name': 'Impulsive',
        'description': 'Acts on immediate desires without extensive planning',
        'planning_capacity_modifier': -0.3,
        'focus_modifier': -1.0,
        'max_depth_modifier': -0.2,
        'planning_frequency_modifier': 1.0,  # Plans LESS frequently
        'effects': {
            'abandonment_threshold': 0.6,
            'immediate_gratification_bonus': 1.5
        }
    },
    {
        'trait_name': 'Detail-Oriented',
        'description': 'Breaks objectives into fine-grained steps',
        'planning_capacity_modifier': 0.0,
        'focus_modifier': 0.5,
        'max_depth_modifier': 0.5,
        'planning_frequency_modifier': -0.3,
        'effects': {
            'completion_threshold': 0.95
        }
    },
    {
        'trait_name': 'Scattered',
        'description': 'Difficulty maintaining focus, jumps between objectives',
        'planning_capacity_modifier': 0.2,
        'focus_modifier': -1.5,
        'max_depth_modifier': 0.0,
        'planning_frequency_modifier': 0.5,
        'effects': {
            'multitask_penalty': 0.15
        }
    },
    {
        'trait_name': 'Single-Minded',
        'description': 'Laser focus on one goal at a time',
        'planning_capacity_modifier': -0.5,
        'focus_modifier': 2.0,
        'max_depth_modifier': 0.1,
        'planning_frequency_modifier': 0.0,
        'effects': {
            'secondary_objective_penalty': 0.5
        }
    },
    {
        'trait_name': 'Anxious',
        'description': 'Highly aware of deadlines and consequences',
        'planning_capacity_modifier': 0.0,
        'focus_modifier': 0.2,
        'max_depth_modifier': 0.1,
        'planning_frequency_modifier': -0.8,
        'effects': {
            'deadline_sensitivity': 2.0,
            'blocked_objective_stress': 1.5
        }
    },
    {
        'trait_name': 'Laid-Back',
        'description': 'Relaxed approach to planning and deadlines',
        'planning_capacity_modifier': 0.0,
        'focus_modifier': -0.5,
        'max_depth_modifier': -0.1,
        'planning_frequency_modifier': 1.5,
        'effects': {
            'deadline_sensitivity': 0.5,
            'abandonment_ease': 0.3
        }
    },
    {
        'trait_name': 'Strategic Thinker',
        'description': 'Long-term planning with contingencies',
        'planning_capacity_modifier': 0.8,
        'focus_modifier': 0.5,
        'max_depth_modifier': 0.4,
        'planning_frequency_modifier': -1.0,
        'effects': {
            'contingency_planning': True,
            'blocked_reroute': 1.5
        }
    }
]


def seed_traits():
    """Seed cognitive traits into database."""

    print("=" * 60)
    print("Seeding Cognitive Traits")
    print("=" * 60)

    # Connect to database
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        for trait_data in COGNITIVE_TRAITS:
            print(f"\nCreating trait: {trait_data['trait_name']}")

            result = session.execute(
                text("""
                    SELECT objective.cognitive_trait_upsert(
                        NULL,
                        :trait_name,
                        :description,
                        :planning_capacity_modifier,
                        :focus_modifier,
                        :max_depth_modifier,
                        :planning_frequency_modifier,
                        0,
                        10,
                        CAST(:effects AS jsonb),
                        TRUE
                    ) as trait_id
                """),
                {
                    'trait_name': trait_data['trait_name'],
                    'description': trait_data['description'],
                    'planning_capacity_modifier': trait_data['planning_capacity_modifier'],
                    'focus_modifier': trait_data['focus_modifier'],
                    'max_depth_modifier': trait_data['max_depth_modifier'],
                    'planning_frequency_modifier': trait_data['planning_frequency_modifier'],
                    'effects': json.dumps(trait_data['effects'])
                }
            )

            trait_id = result.scalar()
            print(f"  ✓ Created with ID: {trait_id}")

        session.commit()

        print("\n" + "=" * 60)
        print("✓ All cognitive traits seeded successfully!")
        print("=" * 60)

        # Display summary
        print("\nTrait Summary:")
        result = session.execute(
            text("SELECT trait_name, description FROM objective.cognitive_trait WHERE is_active = TRUE")
        )

        for row in result:
            print(f"  • {row.trait_name}: {row.description}")

    except Exception as e:
        print(f"\n✗ Error seeding traits: {str(e)}")
        session.rollback()
        sys.exit(1)
    finally:
        session.close()


if __name__ == '__main__':
    seed_traits()
