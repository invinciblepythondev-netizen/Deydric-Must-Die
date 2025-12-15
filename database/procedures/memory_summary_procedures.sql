-- Memory Summary Procedures
-- Manage tiered memory summaries with descriptive and condensed versions

-- Create or update a memory summary
CREATE OR REPLACE FUNCTION memory_summary_upsert(
    p_game_state_id UUID,
    p_character_id UUID,
    p_window_type TEXT,
    p_start_turn INTEGER,
    p_end_turn INTEGER,
    p_descriptive_summary TEXT,
    p_condensed_summary TEXT
) RETURNS UUID AS $$
DECLARE
    v_summary_id UUID;
BEGIN
    -- Check if summary already exists for this character/window/turn range
    SELECT summary_id INTO v_summary_id
    FROM memory.memory_summary
    WHERE game_state_id = p_game_state_id
      AND character_id = p_character_id
      AND window_type = p_window_type
      AND start_turn = p_start_turn
      AND end_turn = p_end_turn;

    IF v_summary_id IS NOT NULL THEN
        -- Update existing summary
        UPDATE memory.memory_summary
        SET descriptive_summary = p_descriptive_summary,
            condensed_summary = p_condensed_summary,
            summary_text = p_condensed_summary  -- Backwards compatibility with old column
        WHERE summary_id = v_summary_id;
    ELSE
        -- Insert new summary
        INSERT INTO memory.memory_summary (
            game_state_id,
            character_id,
            window_type,
            start_turn,
            end_turn,
            descriptive_summary,
            condensed_summary,
            summary_text  -- Backwards compatibility with old column
        ) VALUES (
            p_game_state_id,
            p_character_id,
            p_window_type,
            p_start_turn,
            p_end_turn,
            p_descriptive_summary,
            p_condensed_summary,
            p_condensed_summary  -- Use condensed version for old column
        )
        RETURNING summary_id INTO v_summary_id;
    END IF;

    RETURN v_summary_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION memory_summary_upsert IS 'Create or update a memory summary with both descriptive and condensed versions';


-- Get summaries for a character at a specific window type
CREATE OR REPLACE FUNCTION memory_summary_get_for_character(
    p_game_state_id UUID,
    p_character_id UUID,
    p_window_type TEXT DEFAULT NULL, -- If NULL, returns all window types
    p_use_descriptive BOOLEAN DEFAULT true -- true = descriptive, false = condensed
) RETURNS TABLE (
    summary_id UUID,
    window_type TEXT,
    start_turn INTEGER,
    end_turn INTEGER,
    summary_text TEXT,
    created_at TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ms.summary_id,
        ms.window_type,
        ms.start_turn,
        ms.end_turn,
        CASE
            WHEN p_use_descriptive THEN ms.descriptive_summary
            ELSE ms.condensed_summary
        END as summary_text,
        ms.created_at
    FROM memory.memory_summary ms
    WHERE ms.game_state_id = p_game_state_id
      AND ms.character_id = p_character_id
      AND (p_window_type IS NULL OR ms.window_type = p_window_type)
    ORDER BY ms.end_turn DESC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION memory_summary_get_for_character IS 'Get memory summaries for a character, with option to select descriptive or condensed version';


-- Get latest summary for each window type for a character
CREATE OR REPLACE FUNCTION memory_summary_get_latest_tiers(
    p_game_state_id UUID,
    p_character_id UUID,
    p_use_descriptive BOOLEAN DEFAULT true
) RETURNS TABLE (
    window_type TEXT,
    start_turn INTEGER,
    end_turn INTEGER,
    summary_text TEXT,
    turn_span INTEGER
) AS $$
BEGIN
    RETURN QUERY
    WITH latest_per_window AS (
        SELECT DISTINCT ON (ms.window_type)
            ms.window_type,
            ms.start_turn,
            ms.end_turn,
            CASE
                WHEN p_use_descriptive THEN ms.descriptive_summary
                ELSE ms.condensed_summary
            END as summary_text,
            ms.created_at
        FROM memory.memory_summary ms
        WHERE ms.game_state_id = p_game_state_id
          AND ms.character_id = p_character_id
        ORDER BY ms.window_type, ms.end_turn DESC
    )
    SELECT
        lpw.window_type,
        lpw.start_turn,
        lpw.end_turn,
        lpw.summary_text,
        (lpw.end_turn - lpw.start_turn + 1) as turn_span
    FROM latest_per_window lpw
    ORDER BY lpw.end_turn DESC; -- Most recent first
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION memory_summary_get_latest_tiers IS 'Get the latest summary for each time window tier for a character';


-- Delete old summaries for a character (keep only latest N per window type)
CREATE OR REPLACE FUNCTION memory_summary_cleanup_old(
    p_game_state_id UUID,
    p_character_id UUID,
    p_keep_per_window INTEGER DEFAULT 3 -- Keep last 3 summaries per window type
) RETURNS INTEGER AS $$
DECLARE
    v_deleted_count INTEGER;
BEGIN
    WITH summaries_to_keep AS (
        SELECT summary_id
        FROM (
            SELECT
                summary_id,
                ROW_NUMBER() OVER (
                    PARTITION BY window_type
                    ORDER BY end_turn DESC
                ) as rn
            FROM memory.memory_summary
            WHERE game_state_id = p_game_state_id
              AND character_id = p_character_id
        ) ranked
        WHERE rn <= p_keep_per_window
    )
    DELETE FROM memory.memory_summary
    WHERE game_state_id = p_game_state_id
      AND character_id = p_character_id
      AND summary_id NOT IN (SELECT summary_id FROM summaries_to_keep);

    GET DIAGNOSTICS v_deleted_count = ROW_COUNT;
    RETURN v_deleted_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION memory_summary_cleanup_old IS 'Remove old summaries, keeping only the latest N per window type';


-- Check which summaries need to be generated for a character at current turn
CREATE OR REPLACE FUNCTION memory_summary_check_needed(
    p_game_state_id UUID,
    p_character_id UUID,
    p_current_turn INTEGER
) RETURNS TABLE (
    window_type TEXT,
    start_turn INTEGER,
    end_turn INTEGER,
    is_needed BOOLEAN,
    reason TEXT
) AS $$
BEGIN
    RETURN QUERY
    WITH window_definitions AS (
        -- Define the turn windows
        -- recent_10: Last 10 turns (included in working memory, not summarized)
        SELECT 'recent_10' as wtype, GREATEST(1, p_current_turn - 9) as wstart, p_current_turn as wend, 10 as min_turn_requirement
        UNION ALL
        -- rolling_50: Turns 11-60 from current (excludes last 10 turns which are in working memory)
        SELECT 'rolling_50', GREATEST(1, p_current_turn - 59), GREATEST(1, p_current_turn - 10), 60
        UNION ALL
        -- rolling_100: Up to 100 turns, excluding last 10 turns (which are in working memory)
        -- Spans from current-109 to current-10 (100 turns when enough data available)
        -- Only created after turn 20
        SELECT 'rolling_100', GREATEST(1, p_current_turn - 109), GREATEST(1, p_current_turn - 10), 20
        UNION ALL
        -- deep_720: Up to 720 turns, excluding last 100 turns (which are in rolling summaries)
        -- Spans from current-819 to current-100 (720 turns when enough data available)
        -- Only created after turn 200
        SELECT 'deep_720', GREATEST(1, p_current_turn - 819), GREATEST(1, p_current_turn - 100), 200
        UNION ALL
        -- deep_1440: Up to 1440 turns, excluding last 100 turns
        -- Only created after turn 200
        SELECT 'deep_1440', GREATEST(1, p_current_turn - 1539), GREATEST(1, p_current_turn - 100), 200
        UNION ALL
        -- deep_2880: Up to 2880 turns, excluding last 100 turns
        -- Only created after turn 200
        SELECT 'deep_2880', GREATEST(1, p_current_turn - 2979), GREATEST(1, p_current_turn - 100), 200
        UNION ALL
        -- deep_5760: Up to 5760 turns, excluding last 100 turns
        -- Only created after turn 200
        SELECT 'deep_5760', GREATEST(1, p_current_turn - 5859), GREATEST(1, p_current_turn - 100), 200
    ),
    latest_summaries AS (
        SELECT DISTINCT ON (ms.window_type)
            ms.window_type,
            ms.end_turn
        FROM memory.memory_summary ms
        WHERE ms.game_state_id = p_game_state_id
          AND ms.character_id = p_character_id
        ORDER BY ms.window_type, ms.end_turn DESC
    )
    SELECT
        wd.wtype as window_type,
        wd.wstart as start_turn,
        wd.wend as end_turn,
        CASE
            -- Check if we have enough turns to generate this summary
            WHEN p_current_turn < wd.min_turn_requirement THEN false
            -- Generate every 10 turns, or if never generated
            WHEN ls.end_turn IS NULL THEN true
            WHEN p_current_turn % 10 = 0 AND p_current_turn > ls.end_turn THEN true
            ELSE false
        END as is_needed,
        CASE
            WHEN p_current_turn < wd.min_turn_requirement THEN 'Not enough turns yet (need ' || wd.min_turn_requirement || ')'
            WHEN ls.end_turn IS NULL THEN 'Never generated'
            WHEN p_current_turn % 10 = 0 AND p_current_turn > ls.end_turn THEN 'Turn milestone reached'
            ELSE 'Up to date'
        END as reason
    FROM window_definitions wd
    LEFT JOIN latest_summaries ls ON ls.window_type = wd.wtype
    WHERE wd.wend >= 1 -- Always check all windows
    ORDER BY wd.wend - wd.wstart; -- Smallest window first
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION memory_summary_check_needed IS 'Check which summary windows need to be generated/updated for a character';


-- Mark a summary as embedded in vector database
CREATE OR REPLACE FUNCTION memory_summary_mark_embedded(
    p_summary_id UUID,
    p_embedding_id TEXT,
    p_embedding_version TEXT DEFAULT 'descriptive'
) RETURNS BOOLEAN AS $$
BEGIN
    UPDATE memory.memory_summary
    SET is_embedded = true,
        embedding_id = p_embedding_id,
        embedding_version = p_embedding_version
    WHERE summary_id = p_summary_id;

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION memory_summary_mark_embedded IS 'Mark a summary as embedded in Qdrant with its embedding ID';


-- Get summaries that need to be embedded
CREATE OR REPLACE FUNCTION memory_summary_get_not_embedded(
    p_game_state_id UUID DEFAULT NULL,
    p_character_id UUID DEFAULT NULL,
    p_limit INTEGER DEFAULT 100
) RETURNS TABLE (
    summary_id UUID,
    game_state_id UUID,
    character_id UUID,
    window_type TEXT,
    start_turn INTEGER,
    end_turn INTEGER,
    descriptive_summary TEXT,
    condensed_summary TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ms.summary_id,
        ms.game_state_id,
        ms.character_id,
        ms.window_type,
        ms.start_turn,
        ms.end_turn,
        ms.descriptive_summary,
        ms.condensed_summary
    FROM memory.memory_summary ms
    WHERE ms.is_embedded = false
      AND (p_game_state_id IS NULL OR ms.game_state_id = p_game_state_id)
      AND (p_character_id IS NULL OR ms.character_id = p_character_id)
    ORDER BY ms.created_at ASC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION memory_summary_get_not_embedded IS 'Get summaries that have not been embedded in vector database yet';


-- Get a summary by its embedding ID
CREATE OR REPLACE FUNCTION memory_summary_get_by_embedding_id(
    p_embedding_id TEXT
) RETURNS TABLE (
    summary_id UUID,
    game_state_id UUID,
    character_id UUID,
    window_type TEXT,
    start_turn INTEGER,
    end_turn INTEGER,
    descriptive_summary TEXT,
    condensed_summary TEXT,
    embedding_version TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ms.summary_id,
        ms.game_state_id,
        ms.character_id,
        ms.window_type,
        ms.start_turn,
        ms.end_turn,
        ms.descriptive_summary,
        ms.condensed_summary,
        ms.embedding_version
    FROM memory.memory_summary ms
    WHERE ms.embedding_id = p_embedding_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION memory_summary_get_by_embedding_id IS 'Retrieve a summary by its vector database embedding ID';
