"""
Initialize recurring objective templates (standalone version).
These templates are used to auto-generate recurring needs (sleep, hunger, etc.)
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


RECURRING_TEMPLATES = [
    {
        'name': 'Daily Sleep',
        'description_template': 'Get at least 6-8 hours of sleep',
        'success_criteria_template': 'Sleep for sufficient hours to reduce fatigue',
        'default_priority': 'medium',
        'recurs_every_turns': None,
        'recurs_daily': True,
        'decay_after_turns': None,  # Never decays - always important
        'metadata_template': {
            'template_name': 'Daily Sleep',
            'hours_needed': 7,
            'fatigue_threshold': 60
        },
        'priority_increase_rules': {
            'thresholds': [
                {'fatigue_level': 60, 'new_priority': 'high'},
                {'fatigue_level': 80, 'new_priority': 'critical'}
            ]
        }
    },
    {
        'name': 'Hunger',
        'description_template': 'Find and consume food',
        'success_criteria_template': 'Eat a meal to satisfy hunger',
        'default_priority': 'medium',
        'recurs_every_turns': 15,  # Every ~15 turns
        'recurs_daily': False,
        'decay_after_turns': None,
        'metadata_template': {
            'template_name': 'Hunger',
            'hunger_threshold': 70
        },
        'priority_increase_rules': {
            'thresholds': [
                {'hunger_level': 70, 'new_priority': 'high'},
                {'hunger_level': 90, 'new_priority': 'critical'}
            ]
        }
    },
    {
        'name': 'Hygiene',
        'description_template': 'Maintain personal cleanliness',
        'success_criteria_template': 'Bathe or clean oneself',
        'default_priority': 'low',
        'recurs_every_turns': None,
        'recurs_daily': True,
        'decay_after_turns': 50,  # Can forget if low priority for too long
        'metadata_template': {
            'template_name': 'Hygiene',
            'cleanliness_threshold': 30
        },
        'priority_increase_rules': {
            'thresholds': [
                {'turns_inactive': 30, 'new_priority': 'medium'},
                {'turns_inactive': 50, 'new_priority': 'high'}
            ]
        }
    },
    {
        'name': 'Social Interaction',
        'description_template': 'Engage in meaningful social interaction',
        'success_criteria_template': 'Have a conversation or social activity',
        'default_priority': 'low',
        'recurs_every_turns': 10,
        'recurs_daily': False,
        'decay_after_turns': 30,
        'metadata_template': {
            'template_name': 'Social Interaction',
            'social_need_threshold': 60
        },
        'priority_increase_rules': {
            'thresholds': [
                {'social_need': 60, 'new_priority': 'medium'},
                {'social_need': 80, 'new_priority': 'high'}
            ]
        }
    }
]


def init_templates():
    """Initialize recurring objective templates."""

    print("=" * 60)
    print("Initializing Recurring Objective Templates")
    print("=" * 60)

    # Connect to database
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        for template_data in RECURRING_TEMPLATES:
            print(f"\nCreating template: {template_data['name']}")

            # Check if template already exists
            existing = session.execute(
                text("""
                    SELECT template_id FROM objective.recurring_objective_template
                    WHERE name = :name
                """),
                {'name': template_data['name']}
            ).fetchone()

            if existing:
                print(f"  ⚠ Template '{template_data['name']}' already exists, skipping...")
                continue

            result = session.execute(
                text("""
                    INSERT INTO objective.recurring_objective_template (
                        name, description_template, success_criteria_template,
                        default_priority, recurs_every_turns, recurs_daily,
                        decay_after_turns, metadata_template, priority_increase_rules
                    ) VALUES (
                        :name, :description_template, :success_criteria_template,
                        CAST(:default_priority AS objective.priority_level),
                        :recurs_every_turns, :recurs_daily,
                        :decay_after_turns, CAST(:metadata_template AS jsonb),
                        CAST(:priority_increase_rules AS jsonb)
                    )
                    RETURNING template_id
                """),
                {
                    'name': template_data['name'],
                    'description_template': template_data['description_template'],
                    'success_criteria_template': template_data['success_criteria_template'],
                    'default_priority': template_data['default_priority'],
                    'recurs_every_turns': template_data['recurs_every_turns'],
                    'recurs_daily': template_data['recurs_daily'],
                    'decay_after_turns': template_data['decay_after_turns'],
                    'metadata_template': json.dumps(template_data['metadata_template']),
                    'priority_increase_rules': json.dumps(template_data['priority_increase_rules'])
                }
            )

            template_id = result.scalar()
            print(f"  ✓ Created with ID: {template_id}")

        session.commit()

        print("\n" + "=" * 60)
        print("✓ All recurring templates initialized!")
        print("=" * 60)

        # Display summary
        print("\nTemplate Summary:")
        result = session.execute(
            text("""
                SELECT name, description_template, default_priority
                FROM objective.recurring_objective_template
                WHERE is_active = TRUE
            """)
        )

        for row in result:
            print(f"  • {row.name} [{row.default_priority}]: {row.description_template}")

    except Exception as e:
        print(f"\n✗ Error initializing templates: {str(e)}")
        session.rollback()
        sys.exit(1)
    finally:
        session.close()


if __name__ == '__main__':
    init_templates()
