"""Update turn_history_get_witnessed procedure with turn_duration fields."""
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

def update_procedure():
    """Drop and recreate turn_history_get_witnessed procedure."""
    load_dotenv()
    db_url = os.getenv('NEON_DATABASE_URL')
    if not db_url:
        print("[ERROR] NEON_DATABASE_URL not set")
        return False

    engine = create_engine(db_url)

    try:
        with engine.connect() as conn:
            with conn.begin():
                # Drop the existing function
                print("Dropping existing function...")
                conn.execute(text("DROP FUNCTION IF EXISTS turn_history_get_witnessed(uuid, uuid, integer)"))

                # Create new version with turn_duration and remaining_duration
                print("Creating updated function...")
                conn.execute(text("""
                    CREATE FUNCTION turn_history_get_witnessed(
                        p_game_state_id UUID,
                        p_character_id UUID,
                        p_last_n_turns INTEGER DEFAULT 10
                    )
                    RETURNS TABLE (
                        turn_id UUID,
                        turn_number INTEGER,
                        sequence_number INTEGER,
                        character_id UUID,
                        character_name TEXT,
                        action_type TEXT,
                        action_description TEXT,
                        is_private BOOLEAN,
                        outcome_description TEXT,
                        turn_duration INTEGER,
                        remaining_duration INTEGER,
                        created_at TIMESTAMP
                    ) AS $$
                    BEGIN
                        RETURN QUERY
                        SELECT
                            th.turn_id, th.turn_number, th.sequence_number, th.character_id, c.name,
                            th.action_type, th.action_description, th.is_private,
                            th.outcome_description, th.turn_duration, th.remaining_duration, th.created_at
                        FROM memory.turn_history th
                        JOIN character.character c ON c.character_id = th.character_id
                        WHERE th.game_state_id = p_game_state_id
                          AND th.action_type != 'atmospheric'
                          AND (
                              th.character_id = p_character_id
                              OR (th.is_private = false AND th.witnesses @> to_jsonb(p_character_id::text))
                          )
                        ORDER BY th.turn_number DESC, th.sequence_number DESC
                        LIMIT p_last_n_turns * 5;
                    END;
                    $$ LANGUAGE plpgsql;
                """))

        print("[OK] turn_history_get_witnessed procedure updated successfully!")
        return True

    except Exception as e:
        print(f"[ERROR] Failed to update procedure: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    update_procedure()
