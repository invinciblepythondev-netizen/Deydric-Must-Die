"""
Google Cloud Storage service for character images.

Handles uploading, retrieving, and deleting character images from GCS.
"""

import os
import uuid
import mimetypes
from datetime import datetime, timedelta
from typing import Optional, Tuple
from google.cloud import storage
from google.oauth2 import service_account
import logging

logger = logging.getLogger(__name__)


class ImageStorageService:
    """Service for managing character images in Google Cloud Storage."""

    def __init__(self):
        """Initialize GCS client."""
        self.project_id = os.getenv('gc_project_id')
        self.bucket_name = os.getenv('gc_bucket_name')

        if not self.project_id or not self.bucket_name:
            raise ValueError("Missing required GCS configuration: gc_project_id and gc_bucket_name must be set in .env")

        # Initialize the GCS client
        # Note: This assumes Application Default Credentials (ADC) are set up
        # For local development, run: gcloud auth application-default login
        # For production, set GOOGLE_APPLICATION_CREDENTIALS to point to service account key JSON
        credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')

        if credentials_path and os.path.exists(credentials_path):
            credentials = service_account.Credentials.from_service_account_file(credentials_path)
            self.client = storage.Client(project=self.project_id, credentials=credentials)
        else:
            # Use ADC (Application Default Credentials)
            self.client = storage.Client(project=self.project_id)

        self.bucket = self.client.bucket(self.bucket_name)

        logger.info(f"ImageStorageService initialized with project={self.project_id}, bucket={self.bucket_name}")

    def _generate_gcs_path(self, character_id: str, image_type: str, file_extension: str) -> str:
        """
        Generate a unique GCS path for an image.

        Args:
            character_id: UUID of the character
            image_type: Type of image (profile, outfit_casual, etc.)
            file_extension: File extension (jpg, png, etc.)

        Returns:
            GCS path string (e.g., 'characters/uuid/image_type_timestamp.jpg')
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{image_type}_{timestamp}.{file_extension}"
        return f"characters/{character_id}/{filename}"

    def upload_image(
        self,
        character_id: str,
        image_type: str,
        file_data: bytes,
        file_name: str,
        content_type: Optional[str] = None
    ) -> Tuple[str, str, int]:
        """
        Upload an image to Google Cloud Storage.

        Args:
            character_id: UUID of the character
            image_type: Type of image (profile, outfit_casual, etc.)
            file_data: Binary image data
            file_name: Original filename
            content_type: MIME type (auto-detected if not provided)

        Returns:
            Tuple of (public_url, gcs_path, file_size)

        Raises:
            Exception: If upload fails
        """
        try:
            # Detect content type if not provided
            if not content_type:
                content_type, _ = mimetypes.guess_type(file_name)
                if not content_type:
                    content_type = 'image/jpeg'  # Default to JPEG

            # Validate content type
            allowed_types = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']
            if content_type not in allowed_types:
                raise ValueError(f"Unsupported content type: {content_type}. Allowed: {allowed_types}")

            # Get file extension
            file_extension = file_name.split('.')[-1].lower()
            if file_extension not in ['jpg', 'jpeg', 'png', 'webp', 'gif']:
                file_extension = 'jpg'  # Default extension

            # Generate GCS path
            gcs_path = self._generate_gcs_path(character_id, image_type, file_extension)

            # Create blob
            blob = self.bucket.blob(gcs_path)

            # Set cache control for better performance
            blob.cache_control = 'public, max-age=86400'  # 1 day

            # Upload the file
            blob.upload_from_string(
                file_data,
                content_type=content_type
            )

            # Make the blob publicly accessible
            blob.make_public()

            # Get public URL
            public_url = blob.public_url
            file_size = len(file_data)

            logger.info(f"Uploaded image for character {character_id}: {gcs_path} ({file_size} bytes)")

            return public_url, gcs_path, file_size

        except Exception as e:
            logger.error(f"Failed to upload image for character {character_id}: {e}")
            raise

    def delete_image(self, gcs_path: str) -> bool:
        """
        Delete an image from Google Cloud Storage.

        Args:
            gcs_path: Path to the image in GCS

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            blob = self.bucket.blob(gcs_path)
            blob.delete()
            logger.info(f"Deleted image: {gcs_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete image {gcs_path}: {e}")
            return False

    def get_signed_url(self, gcs_path: str, expiration_minutes: int = 60) -> Optional[str]:
        """
        Generate a signed URL for temporary access to a private image.

        Note: This is useful if images are not public. Currently, images are public,
        so this is optional functionality for future use.

        Args:
            gcs_path: Path to the image in GCS
            expiration_minutes: How long the URL should be valid

        Returns:
            Signed URL string or None if failed
        """
        try:
            blob = self.bucket.blob(gcs_path)
            url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(minutes=expiration_minutes),
                method="GET"
            )
            return url
        except Exception as e:
            logger.error(f"Failed to generate signed URL for {gcs_path}: {e}")
            return None

    def image_exists(self, gcs_path: str) -> bool:
        """
        Check if an image exists in GCS.

        Args:
            gcs_path: Path to the image in GCS

        Returns:
            True if image exists, False otherwise
        """
        try:
            blob = self.bucket.blob(gcs_path)
            return blob.exists()
        except Exception as e:
            logger.error(f"Failed to check if image exists {gcs_path}: {e}")
            return False

    def list_character_images(self, character_id: str) -> list:
        """
        List all images for a character in GCS.

        Args:
            character_id: UUID of the character

        Returns:
            List of blob names (GCS paths)
        """
        try:
            prefix = f"characters/{character_id}/"
            blobs = self.bucket.list_blobs(prefix=prefix)
            return [blob.name for blob in blobs]
        except Exception as e:
            logger.error(f"Failed to list images for character {character_id}: {e}")
            return []


# Singleton instance
_image_storage_service = None


def get_image_storage_service() -> ImageStorageService:
    """
    Get or create the singleton ImageStorageService instance.

    Returns:
        ImageStorageService instance
    """
    global _image_storage_service
    if _image_storage_service is None:
        _image_storage_service = ImageStorageService()
    return _image_storage_service
