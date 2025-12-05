# Character JSON Import Guide

## Overview

This guide documents how to incorporate data from `characters.json` into the current character model, identifying field mappings, redundancies, and recommended additions.

## Field Mapping Analysis

### Direct Mappings (No Changes Needed)

| JSON Field | Current Model Field | Type | Notes |
|------------|---------------------|------|-------|
| `characterid` | `character_id` | UUID | Primary key |
| `charactername` | `name` | TEXT | Character full name |
| `appearancedescription` | `physical_appearance` | TEXT | Physical description |
| `backgrounddescription` | `backstory` | TEXT | Character background |
| `characterrole` | `role_responsibilities` | TEXT | Role/job |
| `personalitytraits` | `personality_traits` | JSONB array | Comma-separated → array |
| `speechpatterns` | `speech_style` | TEXT | How they speak |
| `secrets` | `secrets` | JSONB array | Hidden information |
| `reputation` | `reputation` | JSONB object | Social standing |
| `mood` | `current_emotional_state` | TEXT | Current mood |
| `locationid` | `current_location_id` | INTEGER | Current location |
| `superstitions` | `superstitions` | TEXT[] | Beliefs/superstitions |
| `imageurl` | → `character_image` table | TEXT | Use new image system |

### Fields Requiring Transformation

| JSON Field | Current Model Field | Transformation Required |
|------------|---------------------|-------------------------|
| `desires` | `motivations_long_term` | Convert to JSONB array |
| `motivations` | `motivations_short_term` | Convert to JSONB array |
| `likes` | `preferences.likes` | Add to preferences JSONB |
| `dislikes` | `preferences.dislikes` | Add to preferences JSONB |
| `sexuality` | `preferences.sexuality` | Add to preferences JSONB |
| `attracted_to` | `preferences.attraction_types.attracted_to` | Add to preferences JSONB |
| `unattracted_to` | `preferences.attraction_types.unattracted_to` | Add to preferences JSONB |
| `sexual_desires` | `preferences.sexual_desires` | Add to preferences JSONB |
| `turn_ons` | `preferences.turn_ons` | Add to preferences JSONB |
| `turn_offs` | `preferences.turn_offs` | Add to preferences JSONB |

### Fields to Skip (Redundant/Empty)

| JSON Field | Reason |
|------------|--------|
| `gamerealmid` | Not needed for single-game system |
| `createdat` | Use model's `created_at` |
| `updatedat` | Use model's `updated_at` |
| `characteristics_json` | Empty in all characters |
| `status_json` | Empty in all characters |
| `thumburl` | New image system handles thumbnails |
| `possesions` | Typo; use `character_inventory` table |

### Recommended New Fields

These fields from the JSON should be added to the character model:

| JSON Field | Recommended Model Field | Type | Justification |
|------------|-------------------------|------|---------------|
| `shortname` | `short_name` | TEXT | Useful for UI/dialogue |
| `gender` | `gender` | TEXT | Important for pronouns/LLM context |
| `age` | `age` | INTEGER | Character age in years |
| `quirks` | Add to `personality_traits` | JSONB | Part of personality |
| `characterflaws` | Add to `personality_traits` | JSONB | Part of personality |
| `fears` | `fears` | JSONB array | Important for motivation |
| `innerconflict` | `inner_conflict` | TEXT | Drives character decisions |
| `mainvalues` | `core_values` | JSONB array | Character moral compass |
| `IntroSummary` | `intro_summary` | TEXT | Optional intro text |

## Recommended Schema Changes

### Migration: Add Missing Character Fields

```sql
-- database/migrations/008_add_character_profile_fields.sql

-- Add new character profile fields
ALTER TABLE character.character
ADD COLUMN IF NOT EXISTS short_name TEXT,
ADD COLUMN IF NOT EXISTS gender TEXT,
ADD COLUMN IF NOT EXISTS age INTEGER CHECK (age > 0 AND age < 200),
ADD COLUMN IF NOT EXISTS fears JSONB DEFAULT '[]'::jsonb,
ADD COLUMN IF NOT EXISTS inner_conflict TEXT,
ADD COLUMN IF NOT EXISTS core_values JSONB DEFAULT '[]'::jsonb,
ADD COLUMN IF NOT EXISTS intro_summary TEXT;

-- Add comments
COMMENT ON COLUMN character.character.short_name IS 'Shortened/nickname version of name';
COMMENT ON COLUMN character.character.gender IS 'Gender identity (Male, Female, Non-binary, etc.)';
COMMENT ON COLUMN character.character.age IS 'Character age in years';
COMMENT ON COLUMN character.character.fears IS 'JSONB array of things the character fears';
COMMENT ON COLUMN character.character.inner_conflict IS 'Internal struggle driving character decisions';
COMMENT ON COLUMN character.character.core_values IS 'JSONB array of core values/beliefs';
COMMENT ON COLUMN character.character.intro_summary IS 'Optional introductory scene/summary text';

-- Create index for common queries
CREATE INDEX IF NOT EXISTS idx_character_age ON character.character(age) WHERE age IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_character_gender ON character.character(gender) WHERE gender IS NOT NULL;
```

## Expanded Preferences Structure

The `preferences` JSONB field should be structured as:

```json
{
  "food": ["soups", "stews", "sweet foods"],
  "clothing_style": ["simple tunics", "aprons"],
  "activities": ["cooking", "listening to gossip"],
  "locations": ["kitchen", "quiet corners"],
  "likes": ["quiet moments", "sharing stories"],
  "dislikes": ["cruelty", "injustice", "being invisible"],
  "sexuality": "Heteroflexible",
  "attraction_types": {
    "attracted_to": "kind, empathetic people who value intelligence",
    "unattracted_to": "cruel, arrogant, dismissive people"
  },
  "sexual_desires": "desires physical intimacy and connection...",
  "turn_ons": ["acts of kindness", "understanding", "sweet foods"],
  "turn_offs": ["roughness", "insensitivity", "stale ale"]
}
```

## Personality Traits Expansion

Merge `personalitytraits`, `quirks`, and `characterflaws` into a single `personality_traits` array:

```json
{
  "traits": ["Cheerful", "quick-witted", "observant", "cautious", "resentful"],
  "quirks": ["Darts eyes around like a sparrow", "wears thin leather bracelet"],
  "flaws": ["Smoldering resentment", "fear of poverty", "insecurity about status"]
}
```

Or keep as a flat array for simplicity:
```json
[
  "Cheerful",
  "quick-witted",
  "observant",
  "cautious",
  "resentful",
  "quirk: darts eyes around like a sparrow",
  "flaw: smoldering resentment towards nobility"
]
```

## Import Script Structure

The import process should:

1. **Read characters.json**
2. **Transform each character**:
   - Map fields to current model
   - Convert comma-separated strings to arrays
   - Build preferences JSONB object
   - Merge personality traits, quirks, flaws
3. **Upload images**:
   - Download from `imageurl`
   - Upload to Google Cloud Storage
   - Create character_image record
4. **Create character via stored procedure**
5. **Handle errors gracefully**

## Example Character Transformation

### Input (JSON):
```json
{
  "charactername": "Lysa Darnog",
  "shortname": "Lysa",
  "gender": "Female",
  "age": "23",
  "personalitytraits": "Cheerful, quick-witted, observant, cautious, resentful",
  "quirks": "Darts her green eyes around like a sparrow...",
  "characterflaws": "Smoldering resentment towards the nobility...",
  "likes": "Quiet moments, listening to gossip...",
  "dislikes": "Cruelty, injustice...",
  "fears": "Poverty, loss of job...",
  "sexuality": "Heteroflexible",
  "attracted_to": "kind, empathetic people...",
  "desires": "To avenge her brother's death...",
  "motivations": "To survive, earn enough coin..."
}
```

### Output (Model):
```python
{
    "character_id": "266cf37e-286b-49ab-ae8d-4dcc36f61c1d",
    "name": "Lysa Darnog",
    "short_name": "Lysa",
    "gender": "Female",
    "age": 23,
    "personality_traits": [
        "Cheerful", "quick-witted", "observant", "cautious", "resentful",
        "quirk: darts eyes like a sparrow",
        "flaw: smoldering resentment towards nobility"
    ],
    "fears": [
        "Poverty",
        "Loss of job",
        "Consequences of revenge"
    ],
    "preferences": {
        "likes": ["Quiet moments", "listening to gossip", "simple meals"],
        "dislikes": ["Cruelty", "injustice", "being treated as invisible"],
        "sexuality": "Heteroflexible",
        "attraction_types": {
            "attracted_to": "kind, empathetic, aware of injustice",
            "unattracted_to": "cruel, arrogant, dismissive"
        },
        "sexual_desires": "desires physical intimacy and connection...",
        "turn_ons": ["kindness", "understanding", "sweet foods"],
        "turn_offs": ["roughness", "insensitivity", "boisterousness"]
    },
    "motivations_long_term": [
        "Avenge brother's death",
        "Expose injustices of nobility",
        "Escape life as servant"
    ],
    "motivations_short_term": [
        "Survive",
        "Earn enough coin for freedom",
        "Bring justice to wronged"
    ]
}
```

## Data Quality Considerations

### Issues Found in characters.json:

1. **Inconsistent field types**: Age is string ("23") instead of integer
2. **Very long fields**: Some `appearancedescription` fields have redundant role info appended
3. **Explicit content**: Sexual content fields are very detailed - may need filtering
4. **Plot spoilers**: Some fields reveal assassination plots (may want to move to `secrets`)
5. **Empty fields**: Many `reputation`, `possesions`, `locationid` are empty strings

### Recommendations:

1. **Clean `appearancedescription`**: Remove redundant role info from end of field
2. **Parse ages**: Convert "23" → 23 (integer)
3. **Handle explicit content**: Keep in preferences but ensure LLM context management handles appropriately
4. **Review motivations**: Some are very plot-specific (assassination plans) - ensure they're in secrets too
5. **Default values**: Empty strings should map to NULL or appropriate defaults

## Next Steps

1. **Create migration** (008_add_character_profile_fields.sql)
2. **Update stored procedures** to handle new fields
3. **Update Character model** with new field accessors
4. **Create import script** (scripts/import_characters_json.py)
5. **Test import** on development database
6. **Verify LLM context** includes new fields appropriately

## Summary

**Fields to Add**: short_name, gender, age, fears, inner_conflict, core_values, intro_summary

**Fields to Expand**: preferences (add sexuality, attraction, sexual content), personality_traits (merge quirks/flaws)

**Fields to Skip**: gamerealmid, characteristics_json, status_json, thumburl, possesions (typo)

**Total Characters**: 8 characters ready to import
