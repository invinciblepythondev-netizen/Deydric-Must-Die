"""Apply turn_duration migration directly to database."""
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

def apply_migration():
    """Apply the turn_duration migration."""
    load_dotenv()
    db_url = os.getenv('NEON_DATABASE_URL')
    if not db_url:
        print("[ERROR] NEON_DATABASE_URL not set")
        return False

    engine = create_engine(db_url)

    try:
        with engine.connect() as conn:
            # Start transaction
            with conn.begin():
                # Check if columns exist
                result = conn.execute(text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'memory'
                    AND table_name = 'turn_history'
                    AND column_name IN ('turn_duration', 'remaining_duration')
                """)).fetchall()

                existing_cols = [r[0] for r in result]
                print(f"Existing columns: {existing_cols}")

                # Add turn_duration if not exists
                if 'turn_duration' not in existing_cols:
                    print("Adding turn_duration column...")
                    conn.execute(text("""
                        ALTER TABLE memory.turn_history
                        ADD COLUMN turn_duration INTEGER DEFAULT 1 CHECK (turn_duration >= 1)
                    """))
                    conn.execute(text("""
                        COMMENT ON COLUMN memory.turn_history.turn_duration
                        IS 'Total number of turns this action takes (1 turn = ~30 seconds)'
                    """))
                    print("[OK] Added turn_duration column")
                else:
                    print("[OK] turn_duration column already exists")

                # Add remaining_duration if not exists
                if 'remaining_duration' not in existing_cols:
                    print("Adding remaining_duration column...")
                    conn.execute(text("""
                        ALTER TABLE memory.turn_history
                        ADD COLUMN remaining_duration INTEGER DEFAULT 0 CHECK (remaining_duration >= 0)
                    """))
                    conn.execute(text("""
                        COMMENT ON COLUMN memory.turn_history.remaining_duration
                        IS 'Number of turns remaining for this action to complete (0 = action complete this turn)'
                    """))
                    print("[OK] Added remaining_duration column")
                else:
                    print("[OK] remaining_duration column already exists")

                # Create index if not exists
                print("Creating index for ongoing actions...")
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_turn_history_ongoing_actions
                    ON memory.turn_history(character_id, remaining_duration)
                    WHERE remaining_duration > 0
                """))
                print("[OK] Index created or already exists")

        print("\n[OK] Migration applied successfully!")
        return True

    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    apply_migration()
