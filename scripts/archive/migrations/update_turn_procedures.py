"""Update turn procedures in database."""
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

def update_procedures():
    """Apply turn procedures to database."""
    load_dotenv()
    db_url = os.getenv('NEON_DATABASE_URL')
    if not db_url:
        print("[ERROR] NEON_DATABASE_URL not set")
        return False

    engine = create_engine(db_url)

    try:
        with open('database/procedures/turn_procedures.sql', 'r') as f:
            sql = f.read()

        with engine.connect() as conn:
            with conn.begin():
                conn.execute(text(sql))

        print("[OK] Turn procedures updated successfully!")
        return True

    except Exception as e:
        print(f"[ERROR] Failed to update procedures: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    update_procedures()
