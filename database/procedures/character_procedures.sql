-- Character CRUD Procedures

-- Get a single character by ID
CREATE OR REPLACE FUNCTION character_get(p_character_id UUID)
RETURNS TABLE (
    character_id UUID,
    name TEXT,
    short_name TEXT,
    is_player BOOLEAN,
    gender TEXT,
    age INTEGER,
    backstory TEXT,
    physical_appearance TEXT,
    current_clothing TEXT,
    role_responsibilities TEXT,
    intro_summary TEXT,
    personality_traits JSONB,
    speech_style TEXT,
    education_level TEXT,
    current_emotional_state TEXT,
    motivations_short_term JSONB,
    motivations_long_term JSONB,
    preferences JSONB,
    skills JSONB,
    superstitions TEXT[],
    hobbies TEXT[],
    social_class TEXT,
    reputation JSONB,
    secrets JSONB,
    fears JSONB,
    inner_conflict TEXT,
    core_values JSONB,
    current_stance TEXT,
    current_location_id INTEGER,
    fatigue INTEGER,
    hunger INTEGER,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.character_id, c.name, c.short_name, c.is_player, c.gender, c.age,
        c.backstory, c.physical_appearance, c.current_clothing, c.role_responsibilities,
        c.intro_summary, c.personality_traits, c.speech_style, c.education_level,
        c.current_emotional_state, c.motivations_short_term, c.motivations_long_term,
        c.preferences, c.skills, c.superstitions, c.hobbies, c.social_class,
        c.reputation, c.secrets, c.fears, c.inner_conflict, c.core_values,
        c.current_stance, c.current_location_id, c.fatigue, c.hunger,
        c.created_at, c.updated_at
    FROM character.character c
    WHERE c.character_id = p_character_id;
END;
$$ LANGUAGE plpgsql;

-- List all characters at a specific location
CREATE OR REPLACE FUNCTION character_list_by_location(p_location_id INTEGER)
RETURNS TABLE (
    character_id UUID,
    name TEXT,
    is_player BOOLEAN,
    physical_appearance TEXT,
    current_clothing TEXT,
    current_stance TEXT,
    current_emotional_state TEXT,
    fatigue INTEGER,
    hunger INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.character_id, c.name, c.is_player, c.physical_appearance,
        c.current_clothing, c.current_stance, c.current_emotional_state,
        c.fatigue, c.hunger
    FROM character.character c
    WHERE c.current_location_id = p_location_id;
END;
$$ LANGUAGE plpgsql;

-- Upsert character (insert or update)
CREATE OR REPLACE FUNCTION character_upsert(
    p_character_id UUID,
    p_name TEXT,
    p_is_player BOOLEAN DEFAULT false,
    p_short_name TEXT DEFAULT NULL,
    p_gender TEXT DEFAULT NULL,
    p_age INTEGER DEFAULT NULL,
    p_backstory TEXT DEFAULT NULL,
    p_physical_appearance TEXT DEFAULT NULL,
    p_current_clothing TEXT DEFAULT NULL,
    p_role_responsibilities TEXT DEFAULT NULL,
    p_intro_summary TEXT DEFAULT NULL,
    p_personality_traits JSONB DEFAULT '[]'::jsonb,
    p_speech_style TEXT DEFAULT NULL,
    p_education_level TEXT DEFAULT NULL,
    p_current_emotional_state TEXT DEFAULT NULL,
    p_motivations_short_term JSONB DEFAULT '[]'::jsonb,
    p_motivations_long_term JSONB DEFAULT '[]'::jsonb,
    p_preferences JSONB DEFAULT '{}'::jsonb,
    p_skills JSONB DEFAULT '{}'::jsonb,
    p_superstitions TEXT[] DEFAULT NULL,
    p_hobbies TEXT[] DEFAULT NULL,
    p_social_class TEXT DEFAULT NULL,
    p_reputation JSONB DEFAULT '{}'::jsonb,
    p_secrets JSONB DEFAULT '[]'::jsonb,
    p_fears JSONB DEFAULT '[]'::jsonb,
    p_inner_conflict TEXT DEFAULT NULL,
    p_core_values JSONB DEFAULT '[]'::jsonb,
    p_current_stance TEXT DEFAULT NULL,
    p_current_location_id INTEGER DEFAULT NULL,
    p_fatigue INTEGER DEFAULT 0,
    p_hunger INTEGER DEFAULT 0
)
RETURNS UUID AS $$
DECLARE
    v_character_id UUID;
BEGIN
    -- Use provided ID or generate new one
    v_character_id := COALESCE(p_character_id, gen_random_uuid());

    INSERT INTO character.character (
        character_id, name, short_name, is_player, gender, age,
        backstory, physical_appearance, current_clothing, role_responsibilities,
        intro_summary, personality_traits, speech_style, education_level,
        current_emotional_state, motivations_short_term, motivations_long_term,
        preferences, skills, superstitions, hobbies, social_class,
        reputation, secrets, fears, inner_conflict, core_values,
        current_stance, current_location_id, fatigue, hunger
    ) VALUES (
        v_character_id, p_name, p_short_name, p_is_player, p_gender, p_age,
        p_backstory, p_physical_appearance, p_current_clothing, p_role_responsibilities,
        p_intro_summary, p_personality_traits, p_speech_style, p_education_level,
        p_current_emotional_state, p_motivations_short_term, p_motivations_long_term,
        p_preferences, p_skills, p_superstitions, p_hobbies, p_social_class,
        p_reputation, p_secrets, p_fears, p_inner_conflict, p_core_values,
        p_current_stance, p_current_location_id, p_fatigue, p_hunger
    )
    ON CONFLICT (character_id) DO UPDATE SET
        name = EXCLUDED.name,
        short_name = EXCLUDED.short_name,
        is_player = EXCLUDED.is_player,
        gender = EXCLUDED.gender,
        age = EXCLUDED.age,
        backstory = EXCLUDED.backstory,
        physical_appearance = EXCLUDED.physical_appearance,
        current_clothing = EXCLUDED.current_clothing,
        role_responsibilities = EXCLUDED.role_responsibilities,
        intro_summary = EXCLUDED.intro_summary,
        personality_traits = EXCLUDED.personality_traits,
        speech_style = EXCLUDED.speech_style,
        education_level = EXCLUDED.education_level,
        current_emotional_state = EXCLUDED.current_emotional_state,
        motivations_short_term = EXCLUDED.motivations_short_term,
        motivations_long_term = EXCLUDED.motivations_long_term,
        preferences = EXCLUDED.preferences,
        skills = EXCLUDED.skills,
        superstitions = EXCLUDED.superstitions,
        hobbies = EXCLUDED.hobbies,
        social_class = EXCLUDED.social_class,
        reputation = EXCLUDED.reputation,
        secrets = EXCLUDED.secrets,
        fears = EXCLUDED.fears,
        inner_conflict = EXCLUDED.inner_conflict,
        core_values = EXCLUDED.core_values,
        current_stance = EXCLUDED.current_stance,
        current_location_id = EXCLUDED.current_location_id,
        fatigue = EXCLUDED.fatigue,
        hunger = EXCLUDED.hunger,
        updated_at = CURRENT_TIMESTAMP;

    RETURN v_character_id;
END;
$$ LANGUAGE plpgsql;

-- Update character location
CREATE OR REPLACE FUNCTION character_update_location(
    p_character_id UUID,
    p_location_id INTEGER
)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE character.character
    SET current_location_id = p_location_id,
        updated_at = CURRENT_TIMESTAMP
    WHERE character_id = p_character_id;

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

-- Delete character
CREATE OR REPLACE FUNCTION character_delete(p_character_id UUID)
RETURNS BOOLEAN AS $$
BEGIN
    DELETE FROM character.character
    WHERE character_id = p_character_id;

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;
