"""
Character Model - Thin wrapper for character stored procedures

Handles character CRUD operations and location management.
All operations use stored procedures from database/procedures/character_procedures.sql
"""

from sqlalchemy import text
from typing import List, Dict, Any, Optional
from uuid import UUID
import logging
import json

logger = logging.getLogger(__name__)


class Character:
    """Thin wrapper for character operations via stored procedures"""

    @staticmethod
    def get(db_session, character_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get character by ID.

        Args:
            db_session: SQLAlchemy session
            character_id: Character UUID

        Returns:
            Character dictionary or None
        """
        result = db_session.execute(text("""
            SELECT * FROM character_get(:character_id)
        """), {
            "character_id": str(character_id)
        })

        row = result.fetchone()
        if not row:
            return None

        return {
            'character_id': row.character_id,
            'name': row.name,
            'short_name': row.short_name,
            'is_player': row.is_player,
            'gender': row.gender,
            'age': row.age,
            'backstory': row.backstory,
            'physical_appearance': row.physical_appearance,
            'current_clothing': row.current_clothing,
            'role_responsibilities': row.role_responsibilities,
            'intro_summary': row.intro_summary,
            'personality_traits': row.personality_traits,
            'speech_style': row.speech_style,
            'education_level': row.education_level,
            'current_emotional_state': row.current_emotional_state,
            'motivations_short_term': row.motivations_short_term,
            'motivations_long_term': row.motivations_long_term,
            'preferences': row.preferences,
            'skills': row.skills,
            'superstitions': row.superstitions,
            'hobbies': row.hobbies,
            'social_class': row.social_class,
            'reputation': row.reputation,
            'secrets': row.secrets,
            'fears': row.fears,
            'inner_conflict': row.inner_conflict,
            'core_values': row.core_values,
            'current_stance': row.current_stance,
            'current_location_id': row.current_location_id,
            'fatigue': row.fatigue,
            'hunger': row.hunger,
            'created_at': row.created_at,
            'updated_at': row.updated_at
        }

    @staticmethod
    def list_by_location(db_session, location_id: int) -> List[Dict[str, Any]]:
        """
        Get all characters at a specific location.

        Args:
            db_session: SQLAlchemy session
            location_id: Location ID

        Returns:
            List of character dictionaries (basic info only)
        """
        result = db_session.execute(text("""
            SELECT * FROM character_list_by_location(:location_id)
        """), {
            "location_id": location_id
        })

        characters = []
        for row in result.fetchall():
            characters.append({
                'character_id': row.character_id,
                'name': row.name,
                'is_player': row.is_player,
                'physical_appearance': row.physical_appearance,
                'current_clothing': row.current_clothing,
                'current_stance': row.current_stance,
                'current_emotional_state': row.current_emotional_state,
                'fatigue': row.fatigue,
                'hunger': row.hunger
            })

        return characters

    @staticmethod
    def create_or_update(
        db_session,
        character_id: Optional[UUID],
        name: str,
        is_player: bool = False,
        short_name: Optional[str] = None,
        gender: Optional[str] = None,
        age: Optional[int] = None,
        backstory: Optional[str] = None,
        physical_appearance: Optional[str] = None,
        current_clothing: Optional[str] = None,
        role_responsibilities: Optional[str] = None,
        intro_summary: Optional[str] = None,
        personality_traits: Optional[List] = None,
        speech_style: Optional[str] = None,
        education_level: Optional[str] = None,
        current_emotional_state: Optional[str] = None,
        motivations_short_term: Optional[List] = None,
        motivations_long_term: Optional[List] = None,
        preferences: Optional[Dict] = None,
        skills: Optional[Dict] = None,
        superstitions: Optional[List[str]] = None,
        hobbies: Optional[List[str]] = None,
        social_class: Optional[str] = None,
        reputation: Optional[Dict] = None,
        secrets: Optional[List] = None,
        fears: Optional[List] = None,
        inner_conflict: Optional[str] = None,
        core_values: Optional[List] = None,
        current_stance: Optional[str] = None,
        current_location_id: Optional[int] = None,
        fatigue: int = 0,
        hunger: int = 0
    ) -> UUID:
        """
        Create or update a character.

        Args:
            db_session: SQLAlchemy session
            character_id: UUID (None to create new)
            name: Character name
            ... (all other character attributes)

        Returns:
            Character UUID
        """
        result = db_session.execute(text("""
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
                p_personality_traits := :personality_traits::jsonb,
                p_speech_style := :speech_style,
                p_education_level := :education_level,
                p_current_emotional_state := :current_emotional_state,
                p_motivations_short_term := :motivations_short_term::jsonb,
                p_motivations_long_term := :motivations_long_term::jsonb,
                p_preferences := :preferences::jsonb,
                p_skills := :skills::jsonb,
                p_superstitions := :superstitions,
                p_hobbies := :hobbies,
                p_social_class := :social_class,
                p_reputation := :reputation::jsonb,
                p_secrets := :secrets::jsonb,
                p_fears := :fears::jsonb,
                p_inner_conflict := :inner_conflict,
                p_core_values := :core_values::jsonb,
                p_current_stance := :current_stance,
                p_current_location_id := :current_location_id,
                p_fatigue := :fatigue,
                p_hunger := :hunger
            )
        """), {
            "character_id": str(character_id) if character_id else None,
            "name": name,
            "is_player": is_player,
            "short_name": short_name,
            "gender": gender,
            "age": age,
            "backstory": backstory,
            "physical_appearance": physical_appearance,
            "current_clothing": current_clothing,
            "role_responsibilities": role_responsibilities,
            "intro_summary": intro_summary,
            "personality_traits": json.dumps(personality_traits) if personality_traits else '[]',
            "speech_style": speech_style,
            "education_level": education_level,
            "current_emotional_state": current_emotional_state,
            "motivations_short_term": json.dumps(motivations_short_term) if motivations_short_term else '[]',
            "motivations_long_term": json.dumps(motivations_long_term) if motivations_long_term else '[]',
            "preferences": json.dumps(preferences) if preferences else '{}',
            "skills": json.dumps(skills) if skills else '{}',
            "superstitions": superstitions,
            "hobbies": hobbies,
            "social_class": social_class,
            "reputation": json.dumps(reputation) if reputation else '{}',
            "secrets": json.dumps(secrets) if secrets else '[]',
            "fears": json.dumps(fears) if fears else '[]',
            "inner_conflict": inner_conflict,
            "core_values": json.dumps(core_values) if core_values else '[]',
            "current_stance": current_stance,
            "current_location_id": current_location_id,
            "fatigue": fatigue,
            "hunger": hunger
        })

        new_character_id = result.scalar()
        db_session.commit()

        logger.info(f"Created/updated character: {name} ({new_character_id})")

        return UUID(new_character_id)

    @staticmethod
    def update_location(db_session, character_id: UUID, location_id: int) -> bool:
        """
        Move character to new location.

        Args:
            db_session: SQLAlchemy session
            character_id: Character UUID
            location_id: New location ID

        Returns:
            True if successful
        """
        result = db_session.execute(text("""
            SELECT character_update_location(
                p_character_id := :character_id,
                p_location_id := :location_id
            )
        """), {
            "character_id": str(character_id),
            "location_id": location_id
        })

        success = result.scalar()
        db_session.commit()

        if success:
            logger.info(f"Moved character {character_id} to location {location_id}")

        return success

    @staticmethod
    def delete(db_session, character_id: UUID) -> bool:
        """
        Delete a character.

        Args:
            db_session: SQLAlchemy session
            character_id: Character UUID

        Returns:
            True if deleted
        """
        result = db_session.execute(text("""
            SELECT character_delete(:character_id)
        """), {
            "character_id": str(character_id)
        })

        success = result.scalar()
        db_session.commit()

        if success:
            logger.info(f"Deleted character {character_id}")

        return success

    @staticmethod
    def get_images(db_session, character_id: UUID) -> List[Dict[str, Any]]:
        """
        Get all images for a character.

        Args:
            db_session: SQLAlchemy session
            character_id: Character UUID

        Returns:
            List of image dictionaries
        """
        result = db_session.execute(text("""
            SELECT * FROM character_image_list_by_character(:character_id)
        """), {
            "character_id": str(character_id)
        })

        images = []
        for row in result.fetchall():
            images.append({
                'image_id': row.image_id,
                'character_id': row.character_id,
                'image_type': row.image_type,
                'image_url': row.image_url,
                'gcs_path': row.gcs_path,
                'file_name': row.file_name,
                'file_size': row.file_size,
                'mime_type': row.mime_type,
                'display_name': row.display_name,
                'description': row.description,
                'is_primary': row.is_primary,
                'display_order': row.display_order,
                'uploaded_at': row.uploaded_at,
                'created_at': row.created_at,
                'updated_at': row.updated_at
            })

        return images

    @staticmethod
    def get_images_by_type(db_session, character_id: UUID, image_type: str) -> List[Dict[str, Any]]:
        """
        Get images of a specific type for a character.

        Args:
            db_session: SQLAlchemy session
            character_id: Character UUID
            image_type: Type of image (profile, outfit_casual, etc.)

        Returns:
            List of image dictionaries
        """
        result = db_session.execute(text("""
            SELECT * FROM character_image_get_by_type(:character_id, :image_type)
        """), {
            "character_id": str(character_id),
            "image_type": image_type
        })

        images = []
        for row in result.fetchall():
            images.append({
                'image_id': row.image_id,
                'character_id': row.character_id,
                'image_type': row.image_type,
                'image_url': row.image_url,
                'gcs_path': row.gcs_path,
                'file_name': row.file_name,
                'file_size': row.file_size,
                'mime_type': row.mime_type,
                'display_name': row.display_name,
                'description': row.description,
                'is_primary': row.is_primary,
                'display_order': row.display_order,
                'uploaded_at': row.uploaded_at,
                'created_at': row.created_at,
                'updated_at': row.updated_at
            })

        return images

    @staticmethod
    def get_primary_image(db_session, character_id: UUID, image_type: str) -> Optional[Dict[str, Any]]:
        """
        Get the primary image for a character by type.

        Args:
            db_session: SQLAlchemy session
            character_id: Character UUID
            image_type: Type of image (profile, outfit_casual, etc.)

        Returns:
            Image dictionary or None
        """
        result = db_session.execute(text("""
            SELECT * FROM character_image_get_primary(:character_id, :image_type)
        """), {
            "character_id": str(character_id),
            "image_type": image_type
        })

        row = result.fetchone()
        if not row:
            return None

        return {
            'image_id': row.image_id,
            'character_id': row.character_id,
            'image_type': row.image_type,
            'image_url': row.image_url,
            'gcs_path': row.gcs_path,
            'file_name': row.file_name,
            'file_size': row.file_size,
            'mime_type': row.mime_type,
            'display_name': row.display_name,
            'description': row.description,
            'is_primary': row.is_primary,
            'display_order': row.display_order,
            'uploaded_at': row.uploaded_at,
            'created_at': row.created_at,
            'updated_at': row.updated_at
        }

    @staticmethod
    def get_all_primary_images(db_session, character_id: UUID) -> List[Dict[str, Any]]:
        """
        Get all primary images for a character (one per type).

        Args:
            db_session: SQLAlchemy session
            character_id: Character UUID

        Returns:
            List of image dictionaries
        """
        result = db_session.execute(text("""
            SELECT * FROM character_image_get_all_primary(:character_id)
        """), {
            "character_id": str(character_id)
        })

        images = []
        for row in result.fetchall():
            images.append({
                'image_id': row.image_id,
                'character_id': row.character_id,
                'image_type': row.image_type,
                'image_url': row.image_url,
                'gcs_path': row.gcs_path,
                'file_name': row.file_name,
                'file_size': row.file_size,
                'mime_type': row.mime_type,
                'display_name': row.display_name,
                'description': row.description,
                'is_primary': row.is_primary,
                'display_order': row.display_order,
                'uploaded_at': row.uploaded_at,
                'created_at': row.created_at,
                'updated_at': row.updated_at
            })

        return images

    @staticmethod
    def add_image(
        db_session,
        character_id: UUID,
        image_type: str,
        image_url: str,
        gcs_path: str,
        file_name: str,
        file_size: int,
        mime_type: str,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        is_primary: bool = False,
        display_order: int = 0,
        image_id: Optional[UUID] = None
    ) -> UUID:
        """
        Add or update a character image.

        Args:
            db_session: SQLAlchemy session
            character_id: Character UUID
            image_type: Type of image
            image_url: Public URL to the image
            gcs_path: Path in GCS bucket
            file_name: Original filename
            file_size: Size in bytes
            mime_type: MIME type
            display_name: Optional display name
            description: Optional description
            is_primary: Whether this is the primary image for this type
            display_order: Display order
            image_id: Optional UUID for update

        Returns:
            Image UUID
        """
        result = db_session.execute(text("""
            SELECT character_image_upsert(
                p_image_id := :image_id,
                p_character_id := :character_id,
                p_image_type := :image_type,
                p_image_url := :image_url,
                p_gcs_path := :gcs_path,
                p_file_name := :file_name,
                p_file_size := :file_size,
                p_mime_type := :mime_type,
                p_display_name := :display_name,
                p_description := :description,
                p_is_primary := :is_primary,
                p_display_order := :display_order
            )
        """), {
            "image_id": str(image_id) if image_id else None,
            "character_id": str(character_id),
            "image_type": image_type,
            "image_url": image_url,
            "gcs_path": gcs_path,
            "file_name": file_name,
            "file_size": file_size,
            "mime_type": mime_type,
            "display_name": display_name,
            "description": description,
            "is_primary": is_primary,
            "display_order": display_order
        })

        new_image_id = result.scalar()
        db_session.commit()

        logger.info(f"Added/updated image for character {character_id}: {image_type} ({new_image_id})")

        return UUID(new_image_id)

    @staticmethod
    def delete_image(db_session, image_id: UUID) -> bool:
        """
        Delete a character image.

        Args:
            db_session: SQLAlchemy session
            image_id: Image UUID

        Returns:
            True if deleted
        """
        result = db_session.execute(text("""
            SELECT character_image_delete(:image_id)
        """), {
            "image_id": str(image_id)
        })

        success = result.scalar()
        db_session.commit()

        if success:
            logger.info(f"Deleted image {image_id}")

        return success

    @staticmethod
    def set_primary_image(db_session, image_id: UUID) -> bool:
        """
        Set an image as the primary image for its type.

        Args:
            db_session: SQLAlchemy session
            image_id: Image UUID

        Returns:
            True if successful
        """
        result = db_session.execute(text("""
            SELECT character_image_set_primary(:image_id)
        """), {
            "image_id": str(image_id)
        })

        success = result.scalar()
        db_session.commit()

        if success:
            logger.info(f"Set image {image_id} as primary")

        return success
