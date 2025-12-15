"""
Import characters from characters.json into the database.

This script reads the characters.json file, transforms the data to match
the current character model, and imports them into the database.

Usage:
    python scripts/import_characters_json.py [--dry-run] [--with-images]
"""

import json
import os
import sys
import re
import argparse
import requests
from pathlib import Path
from uuid import UUID
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv('NEON_DATABASE_URL')

if not DATABASE_URL:
    print("ERROR: NEON_DATABASE_URL not found in environment variables")
    sys.exit(1)


def clean_appearance_description(description: str) -> str:
    """
    Clean the appearance description by removing redundant role information
    that was appended to the end.
    """
    # Remove the "Aged X years, identifying as..." redundant text
    pattern = r'\.\. Aged \d+ years.*?\.\.\.?$'
    cleaned = re.sub(pattern, '.', description)
    return cleaned.strip()


def parse_comma_separated(text: str) -> list:
    """Parse comma-separated string into array."""
    if not text:
        return []
    return [item.strip() for item in text.split(',')]


def build_personality_traits(traits_str: str, quirks_str: str, flaws_str: str) -> list:
    """
    Merge personality traits, quirks, and flaws into a single array.
    """
    traits = []

    # Add base traits
    if traits_str:
        traits.extend(parse_comma_separated(traits_str))

    # Add quirks with prefix
    if quirks_str:
        quirks = quirks_str.split(',') if ',' in quirks_str else [quirks_str]
        for quirk in quirks:
            quirk = quirk.strip()
            if quirk:
                traits.append(f"quirk: {quirk}")

    # Add flaws with prefix
    if flaws_str:
        flaws = flaws_str.split(',') if ',' in flaws_str else [flaws_str]
        for flaw in flaws:
            flaw = flaw.strip()
            if flaw:
                traits.append(f"flaw: {flaw}")

    return traits


def build_preferences(char_data: dict) -> dict:
    """
    Build preferences JSONB object from various character fields.
    """
    preferences = {}

    # Simple lists
    if char_data.get('likes'):
        preferences['likes'] = parse_comma_separated(char_data['likes'])

    if char_data.get('dislikes'):
        preferences['dislikes'] = parse_comma_separated(char_data['dislikes'])

    # Sexuality and attraction
    if char_data.get('sexuality'):
        preferences['sexuality'] = char_data['sexuality']

    if char_data.get('attracted_to') or char_data.get('unattracted_to'):
        preferences['attraction_types'] = {}
        if char_data.get('attracted_to'):
            preferences['attraction_types']['attracted_to'] = char_data['attracted_to']
        if char_data.get('unattracted_to'):
            preferences['attraction_types']['unattracted_to'] = char_data['unattracted_to']

    # Sexual preferences (if needed for mature content)
    if char_data.get('sexual_desires'):
        preferences['sexual_desires'] = char_data['sexual_desires']

    if char_data.get('turn_ons'):
        preferences['turn_ons'] = char_data['turn_ons']

    if char_data.get('turn_offs'):
        preferences['turn_offs'] = char_data['turn_offs']

    return preferences


def parse_fears(fears_str: str) -> list:
    """Parse fears string into array."""
    if not fears_str:
        return []
    # Split by common delimiters
    fears = re.split(r',|\band\b', fears_str)
    return [f.strip() for f in fears if f.strip()]


def parse_values(values_str: str) -> list:
    """Parse main values string into array."""
    if not values_str:
        return []
    return parse_comma_separated(values_str)


def parse_motivations(motivation_str: str) -> list:
    """Parse motivations/desires string into array."""
    if not motivation_str:
        return []
    # Check if it contains multiple items separated by commas or 'and'
    motivations = re.split(r',|\band\b', motivation_str)
    return [m.strip() for m in motivations if m.strip()]


def transform_character(char_data: dict) -> dict:
    """
    Transform a character from characters.json format to the current model format.
    """
    # Parse age
    age = None
    if char_data.get('age'):
        try:
            age = int(char_data['age'])
        except (ValueError, TypeError):
            age = None

    # Parse location ID
    location_id = None
    if char_data.get('locationid'):
        try:
            location_id = int(char_data['locationid'])
        except (ValueError, TypeError):
            pass

    # Build transformed character
    transformed = {
        'character_id': char_data.get('characterid'),
        'name': char_data.get('charactername'),
        'short_name': char_data.get('shortname'),
        'is_player': False,  # All imported characters are NPCs
        'gender': char_data.get('gender'),
        'age': age,
        'backstory': char_data.get('backgrounddescription'),
        'physical_appearance': clean_appearance_description(char_data.get('appearancedescription', '')),
        'current_clothing': None,  # Extract from appearance if needed
        'role_responsibilities': char_data.get('characterrole'),
        'intro_summary': char_data.get('IntroSummary'),
        'personality_traits': build_personality_traits(
            char_data.get('personalitytraits', ''),
            char_data.get('quirks', ''),
            char_data.get('characterflaws', '')
        ),
        'speech_style': char_data.get('speechpatterns'),
        'education_level': None,  # Could be inferred from role
        'current_emotional_state': char_data.get('mood'),
        'motivations_short_term': parse_motivations(char_data.get('motivations', '')),
        'motivations_long_term': parse_motivations(char_data.get('desires', '')),
        'preferences': build_preferences(char_data),
        'skills': {},  # Could be inferred from role
        'superstitions': parse_comma_separated(char_data.get('superstitions', '')),
        'hobbies': [],  # Could extract from likes
        'social_class': None,  # Could be inferred from role
        'reputation': {},  # Empty for now
        'secrets': parse_comma_separated(char_data.get('secrets', '')),
        'fears': parse_fears(char_data.get('fears', '')),
        'inner_conflict': char_data.get('innerconflict'),
        'core_values': parse_values(char_data.get('mainvalues', '')),
        'current_stance': None,
        'current_location_id': location_id,
        'fatigue': 0,
        'hunger': 0
    }

    return transformed


def import_character(session, char_data: dict, dry_run: bool = False) -> bool:
    """
    Import a single character into the database.

    Returns True if successful, False otherwise.
    """
    try:
        transformed = transform_character(char_data)

        print(f"\n{'[DRY RUN] ' if dry_run else ''}Importing: {transformed['name']} ({transformed['short_name']})")
        print(f"  Role: {transformed['role_responsibilities']}")
        print(f"  Age: {transformed['age']}, Gender: {transformed['gender']}")
        print(f"  Personality: {len(transformed['personality_traits'])} traits")
        print(f"  Fears: {len(transformed['fears'])} fears")
        print(f"  Values: {len(transformed['core_values'])} core values")

        if dry_run:
            print("  [SKIPPED - Dry Run]")
            return True

        # Prepare parameters with JSON strings
        params = {
            **transformed,
            'personality_traits': json.dumps(transformed['personality_traits']),
            'motivations_short_term': json.dumps(transformed['motivations_short_term']),
            'motivations_long_term': json.dumps(transformed['motivations_long_term']),
            'preferences': json.dumps(transformed['preferences']),
            'skills': json.dumps(transformed['skills']),
            'reputation': json.dumps(transformed['reputation']),
            'secrets': json.dumps(transformed['secrets']),
            'fears': json.dumps(transformed['fears']),
            'core_values': json.dumps(transformed['core_values'])
        }

        # Call character_upsert stored procedure (now includes all new fields)
        result = session.execute(text("""
            SELECT character_upsert(
                p_character_id := :character_id,
                p_name := :name,
                p_is_player := :is_player,
                p_short_name := :short_name,
                p_gender := :gender,
                p_age := :age,
                p_backstory := :backstory,
                p_physical_appearance := :physical_appearance,
                p_current_clothing := :current_clothing,
                p_role_responsibilities := :role_responsibilities,
                p_intro_summary := :intro_summary,
                p_personality_traits := CAST(:personality_traits AS jsonb),
                p_speech_style := :speech_style,
                p_education_level := :education_level,
                p_current_emotional_state := :current_emotional_state,
                p_motivations_short_term := CAST(:motivations_short_term AS jsonb),
                p_motivations_long_term := CAST(:motivations_long_term AS jsonb),
                p_preferences := CAST(:preferences AS jsonb),
                p_skills := CAST(:skills AS jsonb),
                p_superstitions := :superstitions,
                p_hobbies := :hobbies,
                p_social_class := :social_class,
                p_reputation := CAST(:reputation AS jsonb),
                p_secrets := CAST(:secrets AS jsonb),
                p_fears := CAST(:fears AS jsonb),
                p_inner_conflict := :inner_conflict,
                p_core_values := CAST(:core_values AS jsonb),
                p_current_stance := :current_stance,
                p_current_location_id := :current_location_id,
                p_fatigue := :fatigue,
                p_hunger := :hunger
            )
        """), params)

        session.commit()
        print(f"  ✓ Imported successfully")
        return True

    except Exception as e:
        print(f"  ✗ Error: {e}")
        session.rollback()
        return False


def import_character_image(session, char_id: str, image_url: str, dry_run: bool = False) -> bool:
    """
    Import character image from URL to Google Cloud Storage.

    Note: This requires the image storage service to be set up.
    """
    if dry_run:
        print(f"  [DRY RUN] Would download and upload image: {image_url}")
        return True

    try:
        from services.image_storage import get_image_storage_service
        from models.character import Character

        # Download image
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()

        # Get file extension from URL
        file_name = image_url.split('/')[-1]
        if '.' not in file_name:
            file_name = f"{char_id}.png"

        # Upload to GCS
        storage_service = get_image_storage_service()
        public_url, gcs_path, file_size = storage_service.upload_image(
            character_id=char_id,
            image_type='profile',
            file_data=response.content,
            file_name=file_name,
            content_type=response.headers.get('Content-Type', 'image/png')
        )

        # Save to database
        Character.add_image(
            db_session=session,
            character_id=UUID(char_id),
            image_type='profile',
            image_url=public_url,
            gcs_path=gcs_path,
            file_name=file_name,
            file_size=file_size,
            mime_type=response.headers.get('Content-Type', 'image/png'),
            is_primary=True
        )

        print(f"  ✓ Image uploaded successfully")
        return True

    except Exception as e:
        print(f"  ✗ Image upload failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Import characters from characters.json')
    parser.add_argument('--dry-run', action='store_true', help='Preview import without making changes')
    parser.add_argument('--with-images', action='store_true', help='Also download and upload character images')
    parser.add_argument('--file', default='characters.json', help='Path to characters.json file')
    args = parser.parse_args()

    print("=" * 70)
    print("Character Import from characters.json")
    print("=" * 70)

    if args.dry_run:
        print("\n[DRY RUN MODE - No changes will be made]\n")

    # Load characters.json
    json_path = project_root / args.file
    if not json_path.exists():
        print(f"ERROR: {args.file} not found")
        sys.exit(1)

    with open(json_path, 'r', encoding='utf-8') as f:
        characters = json.load(f)

    print(f"Loaded {len(characters)} characters from {args.file}\n")

    # Connect to database
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        success_count = 0
        image_count = 0

        for char_data in characters:
            success = import_character(session, char_data, dry_run=args.dry_run)
            if success:
                success_count += 1

                # Import image if requested
                if args.with_images and char_data.get('imageurl') and not args.dry_run:
                    if import_character_image(session, char_data['characterid'], char_data['imageurl'], dry_run=args.dry_run):
                        image_count += 1

        print("\n" + "=" * 70)
        print(f"Import {'preview' if args.dry_run else 'complete'}: {success_count}/{len(characters)} characters")
        if args.with_images:
            print(f"Images: {image_count}/{success_count}")
        print("=" * 70)

    finally:
        session.close()


if __name__ == '__main__':
    main()
