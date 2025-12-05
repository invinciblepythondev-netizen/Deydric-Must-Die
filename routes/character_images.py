"""
Character image upload and management routes.

Handles image uploads to Google Cloud Storage and character image metadata.
"""

from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from uuid import UUID
import logging
from typing import Optional

from models.character import Character
from services.image_storage import get_image_storage_service

logger = logging.getLogger(__name__)

# Create blueprint
character_images_bp = Blueprint('character_images', __name__, url_prefix='/api/characters')


def get_db_session():
    """Get database session from Flask app context."""
    from flask import current_app
    return current_app.config['DB_SESSION']


@character_images_bp.route('/<character_id>/images', methods=['GET'])
def get_character_images(character_id: str):
    """
    Get all images for a character.

    Returns:
        JSON list of image objects
    """
    try:
        character_uuid = UUID(character_id)
        db_session = get_db_session()

        images = Character.get_images(db_session, character_uuid)

        return jsonify({
            'success': True,
            'images': images
        }), 200

    except ValueError:
        return jsonify({
            'success': False,
            'error': 'Invalid character ID format'
        }), 400
    except Exception as e:
        logger.error(f"Error getting images for character {character_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@character_images_bp.route('/<character_id>/images/<image_type>', methods=['GET'])
def get_character_images_by_type(character_id: str, image_type: str):
    """
    Get images of a specific type for a character.

    Args:
        character_id: Character UUID
        image_type: Type of image (profile, outfit_casual, etc.)

    Returns:
        JSON list of image objects
    """
    try:
        character_uuid = UUID(character_id)
        db_session = get_db_session()

        images = Character.get_images_by_type(db_session, character_uuid, image_type)

        return jsonify({
            'success': True,
            'images': images
        }), 200

    except ValueError:
        return jsonify({
            'success': False,
            'error': 'Invalid character ID format'
        }), 400
    except Exception as e:
        logger.error(f"Error getting images by type for character {character_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@character_images_bp.route('/<character_id>/images/<image_type>/primary', methods=['GET'])
def get_primary_image(character_id: str, image_type: str):
    """
    Get the primary image for a character by type.

    Args:
        character_id: Character UUID
        image_type: Type of image

    Returns:
        JSON image object or null if not found
    """
    try:
        character_uuid = UUID(character_id)
        db_session = get_db_session()

        image = Character.get_primary_image(db_session, character_uuid, image_type)

        return jsonify({
            'success': True,
            'image': image
        }), 200

    except ValueError:
        return jsonify({
            'success': False,
            'error': 'Invalid character ID format'
        }), 400
    except Exception as e:
        logger.error(f"Error getting primary image for character {character_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@character_images_bp.route('/<character_id>/images/primary', methods=['GET'])
def get_all_primary_images(character_id: str):
    """
    Get all primary images for a character (one per type).

    Args:
        character_id: Character UUID

    Returns:
        JSON list of primary image objects
    """
    try:
        character_uuid = UUID(character_id)
        db_session = get_db_session()

        images = Character.get_all_primary_images(db_session, character_uuid)

        return jsonify({
            'success': True,
            'images': images
        }), 200

    except ValueError:
        return jsonify({
            'success': False,
            'error': 'Invalid character ID format'
        }), 400
    except Exception as e:
        logger.error(f"Error getting all primary images for character {character_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@character_images_bp.route('/<character_id>/images/upload', methods=['POST'])
def upload_character_image(character_id: str):
    """
    Upload a character image to Google Cloud Storage.

    Expected form data:
        - file: Image file
        - image_type: Type of image (profile, outfit_casual, etc.)
        - display_name: Optional display name
        - description: Optional description
        - is_primary: Optional boolean (default: false)

    Returns:
        JSON with image metadata
    """
    try:
        character_uuid = UUID(character_id)
        db_session = get_db_session()

        # Check if file is present
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No file provided'
            }), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400

        # Get image type (required)
        image_type = request.form.get('image_type')
        if not image_type:
            return jsonify({
                'success': False,
                'error': 'image_type is required'
            }), 400

        # Validate image type
        valid_types = [
            'profile', 'portrait', 'outfit_casual', 'outfit_formal',
            'outfit_combat', 'outfit_work', 'outfit_sleep', 'outfit_travel', 'outfit_custom'
        ]
        if image_type not in valid_types:
            return jsonify({
                'success': False,
                'error': f'Invalid image_type. Must be one of: {", ".join(valid_types)}'
            }), 400

        # Get optional fields
        display_name = request.form.get('display_name')
        description = request.form.get('description')
        is_primary = request.form.get('is_primary', 'false').lower() == 'true'

        # Read file data
        file_data = file.read()
        file_name = secure_filename(file.filename)

        # Upload to GCS
        storage_service = get_image_storage_service()
        public_url, gcs_path, file_size = storage_service.upload_image(
            character_id=str(character_uuid),
            image_type=image_type,
            file_data=file_data,
            file_name=file_name,
            content_type=file.content_type
        )

        # Save to database
        image_id = Character.add_image(
            db_session=db_session,
            character_id=character_uuid,
            image_type=image_type,
            image_url=public_url,
            gcs_path=gcs_path,
            file_name=file_name,
            file_size=file_size,
            mime_type=file.content_type or 'image/jpeg',
            display_name=display_name,
            description=description,
            is_primary=is_primary
        )

        # Get the created image
        images = Character.get_images_by_type(db_session, character_uuid, image_type)
        created_image = next((img for img in images if str(img['image_id']) == str(image_id)), None)

        return jsonify({
            'success': True,
            'message': 'Image uploaded successfully',
            'image': created_image
        }), 201

    except ValueError as e:
        logger.error(f"Validation error uploading image: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        logger.error(f"Error uploading image for character {character_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@character_images_bp.route('/<character_id>/images/<image_id>/set-primary', methods=['PUT'])
def set_image_as_primary(character_id: str, image_id: str):
    """
    Set an image as the primary image for its type.

    Args:
        character_id: Character UUID
        image_id: Image UUID

    Returns:
        JSON success message
    """
    try:
        image_uuid = UUID(image_id)
        db_session = get_db_session()

        success = Character.set_primary_image(db_session, image_uuid)

        if success:
            return jsonify({
                'success': True,
                'message': 'Image set as primary'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to set image as primary'
            }), 500

    except ValueError:
        return jsonify({
            'success': False,
            'error': 'Invalid image ID format'
        }), 400
    except Exception as e:
        logger.error(f"Error setting image {image_id} as primary: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@character_images_bp.route('/<character_id>/images/<image_id>', methods=['DELETE'])
def delete_character_image(character_id: str, image_id: str):
    """
    Delete a character image.

    Args:
        character_id: Character UUID
        image_id: Image UUID

    Returns:
        JSON success message
    """
    try:
        character_uuid = UUID(character_id)
        image_uuid = UUID(image_id)
        db_session = get_db_session()

        # Get image metadata before deleting
        images = Character.get_images(db_session, character_uuid)
        image_to_delete = next((img for img in images if str(img['image_id']) == image_id), None)

        if not image_to_delete:
            return jsonify({
                'success': False,
                'error': 'Image not found'
            }), 404

        # Delete from GCS
        storage_service = get_image_storage_service()
        gcs_deleted = storage_service.delete_image(image_to_delete['gcs_path'])

        if not gcs_deleted:
            logger.warning(f"Failed to delete image from GCS: {image_to_delete['gcs_path']}")

        # Delete from database
        db_deleted = Character.delete_image(db_session, image_uuid)

        if db_deleted:
            return jsonify({
                'success': True,
                'message': 'Image deleted successfully'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to delete image from database'
            }), 500

    except ValueError:
        return jsonify({
            'success': False,
            'error': 'Invalid ID format'
        }), 400
    except Exception as e:
        logger.error(f"Error deleting image {image_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
