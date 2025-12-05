# Character Image System

## Overview

The Character Image System provides complete image storage and retrieval capabilities for character images using Google Cloud Storage. Characters can have multiple images of different types (profile, portraits, various outfits), with support for primary image selection and ordering.

## Components

### Database Layer
- **Table**: `character.character_image` - Stores image metadata
- **Stored Procedures**: Located in `database/procedures/character_image_procedures.sql`
  - `character_image_get(image_id)` - Get a specific image
  - `character_image_list_by_character(character_id)` - List all images for a character
  - `character_image_get_by_type(character_id, image_type)` - Get images of a specific type
  - `character_image_get_primary(character_id, image_type)` - Get primary image for a type
  - `character_image_get_all_primary(character_id)` - Get all primary images
  - `character_image_upsert(...)` - Create or update an image
  - `character_image_delete(image_id)` - Delete an image
  - `character_image_set_primary(image_id)` - Set an image as primary

### Application Layer
- **Service**: `services/image_storage.py` - Google Cloud Storage operations
- **Model**: `models/character.py` - Image-related methods added to Character model
- **Routes**: `routes/character_images.py` - Flask API endpoints

## Setup

### 1. Environment Configuration

Add the following to your `.env` file:

```bash
# Google Cloud Storage
gc_project_id=your-project-id
gc_bucket_name=your-bucket-name

# Optional: Path to service account key JSON
# GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
```

### 2. Google Cloud Storage Setup

#### Option A: Application Default Credentials (Development)
```bash
# Install gcloud CLI and authenticate
gcloud auth application-default login
```

#### Option B: Service Account Key (Production)
1. Create a service account in Google Cloud Console
2. Grant it "Storage Object Admin" role for your bucket
3. Download the JSON key file
4. Set `GOOGLE_APPLICATION_CREDENTIALS` in `.env` to point to the key file

### 3. Create and Configure Bucket

```bash
# Create bucket (if not already created)
gsutil mb -p your-project-id gs://your-bucket-name

# Make bucket public (optional, for public image access)
gsutil iam ch allUsers:objectViewer gs://your-bucket-name
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

This installs `google-cloud-storage==2.14.0` and other required packages.

### 5. Apply Database Migration

```bash
# Apply the migration
python scripts/migrate_db.py

# Or initialize the database (if starting fresh)
python scripts/init_db.py
```

## Image Types

The system supports the following image types:

- `profile` - Main profile picture
- `portrait` - Character portrait (face/head shot)
- `outfit_casual` - Casual clothing
- `outfit_formal` - Formal/fancy clothing
- `outfit_combat` - Combat gear/armor
- `outfit_work` - Work/professional attire
- `outfit_sleep` - Sleepwear
- `outfit_travel` - Travel clothing
- `outfit_custom` - Custom outfit

Each type can have multiple images, with one marked as primary.

## API Endpoints

### Get All Images for a Character
```http
GET /api/characters/{character_id}/images
```

**Response:**
```json
{
  "success": true,
  "images": [
    {
      "image_id": "uuid",
      "character_id": "uuid",
      "image_type": "profile",
      "image_url": "https://storage.googleapis.com/...",
      "gcs_path": "characters/uuid/profile_20250105_143000.jpg",
      "file_name": "character.jpg",
      "file_size": 123456,
      "mime_type": "image/jpeg",
      "display_name": "Main Profile",
      "description": "Character's main profile picture",
      "is_primary": true,
      "display_order": 0,
      "uploaded_at": "2025-01-05T14:30:00Z",
      "created_at": "2025-01-05T14:30:00Z",
      "updated_at": "2025-01-05T14:30:00Z"
    }
  ]
}
```

### Get Images by Type
```http
GET /api/characters/{character_id}/images/{image_type}
```

### Get Primary Image for a Type
```http
GET /api/characters/{character_id}/images/{image_type}/primary
```

### Get All Primary Images
```http
GET /api/characters/{character_id}/images/primary
```

Returns one primary image for each type the character has.

### Upload an Image
```http
POST /api/characters/{character_id}/images/upload
Content-Type: multipart/form-data
```

**Form Data:**
- `file` (required) - Image file
- `image_type` (required) - Type of image (profile, outfit_casual, etc.)
- `display_name` (optional) - Human-readable name
- `description` (optional) - Description
- `is_primary` (optional) - "true" or "false" (default: false)

**Example with cURL:**
```bash
curl -X POST \
  http://localhost:5000/api/characters/550e8400-e29b-41d4-a716-446655440000/images/upload \
  -F "file=@character.jpg" \
  -F "image_type=profile" \
  -F "display_name=Main Profile" \
  -F "is_primary=true"
```

**Response:**
```json
{
  "success": true,
  "message": "Image uploaded successfully",
  "image": {
    "image_id": "uuid",
    "character_id": "uuid",
    "image_type": "profile",
    "image_url": "https://storage.googleapis.com/...",
    ...
  }
}
```

### Set Image as Primary
```http
PUT /api/characters/{character_id}/images/{image_id}/set-primary
```

**Response:**
```json
{
  "success": true,
  "message": "Image set as primary"
}
```

### Delete an Image
```http
DELETE /api/characters/{character_id}/images/{image_id}
```

**Response:**
```json
{
  "success": true,
  "message": "Image deleted successfully"
}
```

## Python Usage Examples

### Using the Model

```python
from models.character import Character
from services.image_storage import get_image_storage_service
from uuid import UUID

# Get all images for a character
character_id = UUID('550e8400-e29b-41d4-a716-446655440000')
images = Character.get_images(db_session, character_id)

# Get primary profile image
profile_image = Character.get_primary_image(db_session, character_id, 'profile')
if profile_image:
    print(f"Profile image URL: {profile_image['image_url']}")

# Upload an image
storage_service = get_image_storage_service()

with open('character.jpg', 'rb') as f:
    file_data = f.read()

public_url, gcs_path, file_size = storage_service.upload_image(
    character_id=str(character_id),
    image_type='profile',
    file_data=file_data,
    file_name='character.jpg'
)

# Save to database
image_id = Character.add_image(
    db_session=db_session,
    character_id=character_id,
    image_type='profile',
    image_url=public_url,
    gcs_path=gcs_path,
    file_name='character.jpg',
    file_size=file_size,
    mime_type='image/jpeg',
    is_primary=True
)

# Get all primary images
primary_images = Character.get_all_primary_images(db_session, character_id)
for image in primary_images:
    print(f"{image['image_type']}: {image['image_url']}")

# Delete an image
Character.delete_image(db_session, image_id)
```

### Direct Storage Service Usage

```python
from services.image_storage import get_image_storage_service

storage_service = get_image_storage_service()

# Upload
public_url, gcs_path, file_size = storage_service.upload_image(
    character_id='character-uuid',
    image_type='profile',
    file_data=binary_data,
    file_name='image.jpg'
)

# Check if exists
exists = storage_service.image_exists(gcs_path)

# Delete
storage_service.delete_image(gcs_path)

# List all images for a character in GCS
gcs_paths = storage_service.list_character_images('character-uuid')
```

## Database Schema

### character_image Table

```sql
CREATE TABLE character.character_image (
    image_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    character_id UUID NOT NULL REFERENCES character.character(character_id) ON DELETE CASCADE,

    -- Image metadata
    image_type TEXT NOT NULL,
    image_url TEXT NOT NULL,
    gcs_path TEXT NOT NULL,

    -- File details
    file_name TEXT NOT NULL,
    file_size INTEGER,
    mime_type TEXT DEFAULT 'image/jpeg',

    -- Display metadata
    display_name TEXT,
    description TEXT,
    is_primary BOOLEAN DEFAULT false,

    -- Ordering
    display_order INTEGER DEFAULT 0,

    -- Metadata
    uploaded_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CHECK (image_type IN ('profile', 'portrait', 'outfit_casual', 'outfit_formal',
                         'outfit_combat', 'outfit_work', 'outfit_sleep', 'outfit_travel', 'outfit_custom')),
    CHECK (mime_type IN ('image/jpeg', 'image/png', 'image/webp', 'image/gif')),

    -- Only one primary image per character per type
    UNIQUE(character_id, image_type, is_primary) WHERE is_primary = true
);
```

## Integration with Flask App

To register the routes in your Flask application:

```python
from flask import Flask
from routes.character_images import character_images_bp

app = Flask(__name__)

# Register the blueprint
app.register_blueprint(character_images_bp)

# Configure database session (example)
app.config['DB_SESSION'] = your_db_session

# Run the app
if __name__ == '__main__':
    app.run(debug=True)
```

## Security Considerations

1. **File Size Limits**: Consider adding file size limits in the upload endpoint
2. **File Type Validation**: Currently validates MIME types, but consider additional validation
3. **Authentication**: Add authentication/authorization to routes before production use
4. **Rate Limiting**: Consider rate limiting upload endpoints
5. **Bucket Permissions**: Use appropriate IAM policies for the GCS bucket

## Cost Optimization

- **Storage**: Google Cloud Storage charges per GB stored
- **Network**: Charges for data egress (downloads)
- **Operations**: Minimal charges for operations (upload, delete)

**Recommendations:**
- Use image compression before upload
- Consider using Cloud CDN for frequently accessed images
- Set lifecycle policies to delete old images
- Use appropriate storage class (Standard for frequently accessed)

## Troubleshooting

### Authentication Issues

**Error**: "Could not authenticate with Google Cloud"

**Solutions:**
1. Run `gcloud auth application-default login`
2. Or set `GOOGLE_APPLICATION_CREDENTIALS` environment variable
3. Verify service account has correct permissions

### Upload Failures

**Error**: "Failed to upload image"

**Solutions:**
1. Check bucket name is correct in `.env`
2. Verify bucket exists: `gsutil ls gs://your-bucket-name`
3. Check IAM permissions for service account
4. Verify file is a valid image format

### Image Not Accessible

**Error**: Image URL returns 403 Forbidden

**Solutions:**
1. Make bucket public: `gsutil iam ch allUsers:objectViewer gs://bucket-name`
2. Or use signed URLs for private access (see `get_signed_url()` method)

## Future Enhancements

- [ ] Image resizing/thumbnail generation
- [ ] Multiple image sizes (thumbnail, medium, full)
- [ ] Image compression before upload
- [ ] Batch upload support
- [ ] Image cropping/editing
- [ ] CDN integration
- [ ] Private images with signed URLs
- [ ] Image metadata extraction (dimensions, EXIF)
