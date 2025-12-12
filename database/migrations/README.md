# Content Settings Setup

This directory contains the migration and setup scripts for the `content_settings` table.

## What is Content Settings?

The `content_settings` table controls the maximum intensity levels for different types of content in the game:

- **Violence**: 0 (None) → 4 (Unrestricted gore)
- **Intimacy**: 0 (None) → 4 (Unrestricted explicit)
- **Horror**: 0 (None) → 4 (Unrestricted extreme)
- **Profanity**: 0 (None) → 4 (Unrestricted)

## Rating Presets

Instead of setting individual levels, you can use these presets:

| Preset | Violence | Intimacy | Horror | Profanity | Description |
|--------|----------|----------|--------|-----------|-------------|
| **G** | 0 | 0 | 0 | 0 | General Audiences |
| **PG** | 1 | 0 | 1 | 1 | Parental Guidance |
| **PG-13** | 2 | 1 | 2 | 2 | Parents Strongly Cautioned *(default)* |
| **R** | 3 | 2 | 3 | 3 | Restricted |
| **Mature** | 3 | 3 | 3 | 3 | Mature Audiences Only |
| **Unrestricted** | 4 | 4 | 4 | 4 | No Limits *(recommended for development)* |

## Quick Setup

### Option 1: All-in-One Setup (Recommended)

Run this single script to create the table, procedures, and populate settings:

```bash
# For development (no content limits)
python scripts/setup_content_settings.py --preset Unrestricted

# For production (default PG-13)
python scripts/setup_content_settings.py --preset PG-13

# For mature content
python scripts/setup_content_settings.py --preset Mature
```

### Option 2: Manual Step-by-Step

If you prefer to run each step manually:

```bash
# Step 1: Apply the migration
python scripts/migrate_db.py

# Step 2: Populate settings for existing games
python scripts/populate_content_settings.py --preset Unrestricted

# Step 3: Update mood procedures
python scripts/init_db.py
```

## Files Included

### Migration
- **`001_add_content_settings.sql`** - Creates the `game.content_settings` table and all stored procedures

### Scripts
- **`setup_content_settings.py`** - All-in-one setup script (recommended)
- **`populate_content_settings.py`** - Populate settings for existing game states

### Python Model
- **`models/content_settings.py`** - Python wrapper for easy access

## Using Content Settings in Code

### Get content settings for a game

```python
from models.content_settings import ContentSettings

# Get existing settings
settings = ContentSettings.get(db_session, game_state_id)

# Get or create with defaults
settings = ContentSettings.get_or_create_default(db_session, game_state_id)
```

### Create/Update settings

```python
# Using a preset (recommended)
ContentSettings.set_from_preset(db_session, game_state_id, 'Unrestricted')

# Custom levels
ContentSettings.upsert(
    db_session,
    game_state_id,
    violence_max_level=3,
    intimacy_max_level=4,
    horror_max_level=2,
    profanity_max_level=3,
    rating_preset='Custom'
)
```

### Get level descriptions

```python
desc = ContentSettings.get_level_description('violence', 3)
# Returns: "Strong (realistic violence, injury detail)"
```

## Database Procedures

The migration creates these stored procedures:

- `content_settings_get(game_state_id)` - Get settings for a game
- `content_settings_upsert(...)` - Create or update settings
- `content_settings_set_from_preset(game_state_id, preset)` - Set using a preset

## How It Affects Gameplay

The mood system (`scene_mood_get_action_guidance`) uses these settings to:

1. **Limit escalation** - Prevents scenes from exceeding your content limits
2. **Warn near boundaries** - Flags when approaching max intensity
3. **Guide action generation** - LLM respects content boundaries

## Troubleshooting

### Error: "relation game.content_settings does not exist"

**Solution**: Run the setup script:
```bash
python scripts/setup_content_settings.py
```

### Want to change settings for all existing games?

```bash
# This will update ALL game states to use the new preset
python scripts/populate_content_settings.py --preset Unrestricted
```

### Want different settings per game?

Use the Python API to set custom settings for each game:

```python
ContentSettings.set_from_preset(db_session, game_state_id_1, 'PG-13')
ContentSettings.set_from_preset(db_session, game_state_id_2, 'Unrestricted')
```

## For Development

**Recommended**: Use `Unrestricted` preset during development to avoid any LLM content filtering:

```bash
python scripts/setup_content_settings.py --preset Unrestricted
```

This allows the dark fantasy themes to play out naturally without artificial limits.
