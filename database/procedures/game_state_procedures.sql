-- Game State Stored Procedures
-- Procedures for managing game state including time tracking

-- Get current game state
CREATE OR REPLACE FUNCTION game_state_get(p_game_state_id UUID)
RETURNS TABLE(
    game_state_id UUID,
    current_turn INTEGER,
    turn_order JSONB,
    is_active BOOLEAN,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    game_settings JSONB,
    game_day INTEGER,
    minutes_since_midnight INTEGER,
    minutes_per_turn INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        gs.game_state_id,
        gs.current_turn,
        gs.turn_order,
        gs.is_active,
        gs.created_at,
        gs.updated_at,
        gs.game_settings,
        gs.game_day,
        gs.minutes_since_midnight,
        gs.minutes_per_turn
    FROM game.game_state gs
    WHERE gs.game_state_id = p_game_state_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION game_state_get IS 'Retrieve game state by ID including time tracking';

-- Create or update game state
CREATE OR REPLACE FUNCTION game_state_upsert(
    p_game_state_id UUID,
    p_current_turn INTEGER DEFAULT 1,
    p_turn_order JSONB DEFAULT NULL,
    p_is_active BOOLEAN DEFAULT true,
    p_game_settings JSONB DEFAULT '{}'::jsonb,
    p_game_day INTEGER DEFAULT 1,
    p_minutes_since_midnight INTEGER DEFAULT 420,
    p_minutes_per_turn INTEGER DEFAULT 6
)
RETURNS UUID AS $$
DECLARE
    v_game_state_id UUID;
BEGIN
    INSERT INTO game.game_state (
        game_state_id,
        current_turn,
        turn_order,
        is_active,
        game_settings,
        game_day,
        minutes_since_midnight,
        minutes_per_turn
    ) VALUES (
        COALESCE(p_game_state_id, gen_random_uuid()),
        p_current_turn,
        p_turn_order,
        p_is_active,
        p_game_settings,
        p_game_day,
        p_minutes_since_midnight,
        p_minutes_per_turn
    )
    ON CONFLICT (game_state_id) DO UPDATE SET
        current_turn = EXCLUDED.current_turn,
        turn_order = EXCLUDED.turn_order,
        is_active = EXCLUDED.is_active,
        game_settings = EXCLUDED.game_settings,
        game_day = EXCLUDED.game_day,
        minutes_since_midnight = EXCLUDED.minutes_since_midnight,
        minutes_per_turn = EXCLUDED.minutes_per_turn,
        updated_at = CURRENT_TIMESTAMP
    RETURNING game_state_id INTO v_game_state_id;

    RETURN v_game_state_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION game_state_upsert IS 'Create or update game state including time settings';

-- Advance time by the configured minutes per turn
CREATE OR REPLACE FUNCTION game_state_advance_time(p_game_state_id UUID)
RETURNS TABLE(
    game_day INTEGER,
    minutes_since_midnight INTEGER,
    time_of_day TEXT
) AS $$
DECLARE
    v_minutes_per_turn INTEGER;
    v_new_minutes INTEGER;
    v_new_day INTEGER;
BEGIN
    -- Get current state
    SELECT gs.minutes_per_turn, gs.minutes_since_midnight, gs.game_day
    INTO v_minutes_per_turn, v_new_minutes, v_new_day
    FROM game.game_state gs
    WHERE gs.game_state_id = p_game_state_id;

    -- Add minutes for this turn
    v_new_minutes := v_new_minutes + v_minutes_per_turn;

    -- Handle day rollover (1440 minutes in a day)
    WHILE v_new_minutes >= 1440 LOOP
        v_new_minutes := v_new_minutes - 1440;
        v_new_day := v_new_day + 1;
    END LOOP;

    -- Update the game state
    UPDATE game.game_state
    SET
        minutes_since_midnight = v_new_minutes,
        game_day = v_new_day,
        updated_at = CURRENT_TIMESTAMP
    WHERE game_state_id = p_game_state_id;

    -- Return the new time
    RETURN QUERY
    SELECT
        v_new_day,
        v_new_minutes,
        game_state_format_time(v_new_minutes);
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION game_state_advance_time IS 'Advance in-game time by one turn (default 6 minutes)';

-- Format minutes since midnight to HH:MM AM/PM
CREATE OR REPLACE FUNCTION game_state_format_time(p_minutes INTEGER)
RETURNS TEXT AS $$
DECLARE
    v_hours INTEGER;
    v_minutes INTEGER;
    v_period TEXT;
    v_display_hour INTEGER;
BEGIN
    v_hours := p_minutes / 60;
    v_minutes := p_minutes % 60;

    -- Determine AM/PM
    IF v_hours < 12 THEN
        v_period := 'AM';
    ELSE
        v_period := 'PM';
    END IF;

    -- Convert to 12-hour format
    IF v_hours = 0 THEN
        v_display_hour := 12;
    ELSIF v_hours > 12 THEN
        v_display_hour := v_hours - 12;
    ELSE
        v_display_hour := v_hours;
    END IF;

    RETURN v_display_hour || ':' || LPAD(v_minutes::TEXT, 2, '0') || ' ' || v_period;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION game_state_format_time IS 'Convert minutes since midnight to readable time format (e.g., "7:00 AM")';

-- Get time of day category
CREATE OR REPLACE FUNCTION game_state_time_of_day(p_minutes INTEGER)
RETURNS TEXT AS $$
BEGIN
    -- Night: 10pm - 5am (1320-1439, 0-299)
    IF p_minutes >= 1320 OR p_minutes < 300 THEN
        RETURN 'night';
    -- Dawn: 5am - 7am (300-419)
    ELSIF p_minutes >= 300 AND p_minutes < 420 THEN
        RETURN 'dawn';
    -- Morning: 7am - 12pm (420-719)
    ELSIF p_minutes >= 420 AND p_minutes < 720 THEN
        RETURN 'morning';
    -- Afternoon: 12pm - 5pm (720-1019)
    ELSIF p_minutes >= 720 AND p_minutes < 1020 THEN
        RETURN 'afternoon';
    -- Evening: 5pm - 7pm (1020-1139)
    ELSIF p_minutes >= 1020 AND p_minutes < 1140 THEN
        RETURN 'evening';
    -- Dusk: 7pm - 10pm (1140-1319)
    ELSE
        RETURN 'dusk';
    END IF;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION game_state_time_of_day IS 'Get time of day category (dawn, morning, afternoon, evening, dusk, night)';

-- Check if it's daytime (between sunrise and sunset)
CREATE OR REPLACE FUNCTION game_state_is_daytime(p_minutes INTEGER)
RETURNS BOOLEAN AS $$
BEGIN
    -- Daytime is 7am to 7pm (420 to 1139 minutes)
    RETURN p_minutes >= 420 AND p_minutes < 1140;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION game_state_is_daytime IS 'Returns true if time is between 7am and 7pm (sun up to sun down)';

-- Get full time context (for LLM prompts)
CREATE OR REPLACE FUNCTION game_state_get_time_context(p_game_state_id UUID)
RETURNS TABLE(
    game_day INTEGER,
    formatted_time TEXT,
    time_of_day TEXT,
    is_daytime BOOLEAN,
    minutes_since_midnight INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        gs.game_day,
        game_state_format_time(gs.minutes_since_midnight) AS formatted_time,
        game_state_time_of_day(gs.minutes_since_midnight) AS time_of_day,
        game_state_is_daytime(gs.minutes_since_midnight) AS is_daytime,
        gs.minutes_since_midnight
    FROM game.game_state gs
    WHERE gs.game_state_id = p_game_state_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION game_state_get_time_context IS 'Get comprehensive time information for context assembly';

-- Increment turn and advance time in one operation
CREATE OR REPLACE FUNCTION game_state_advance_turn(p_game_state_id UUID)
RETURNS TABLE(
    current_turn INTEGER,
    game_day INTEGER,
    formatted_time TEXT,
    time_of_day TEXT
) AS $$
DECLARE
    v_new_turn INTEGER;
    v_game_day INTEGER;
    v_minutes INTEGER;
BEGIN
    -- Increment turn
    UPDATE game.game_state
    SET current_turn = current_turn + 1
    WHERE game_state_id = p_game_state_id
    RETURNING current_turn INTO v_new_turn;

    -- Advance time
    PERFORM game_state_advance_time(p_game_state_id);

    -- Get updated time info
    SELECT
        gs.game_day,
        gs.minutes_since_midnight
    INTO v_game_day, v_minutes
    FROM game.game_state gs
    WHERE gs.game_state_id = p_game_state_id;

    -- Return comprehensive info
    RETURN QUERY
    SELECT
        v_new_turn,
        v_game_day,
        game_state_format_time(v_minutes),
        game_state_time_of_day(v_minutes);
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION game_state_advance_turn IS 'Increment turn number and advance time simultaneously';
