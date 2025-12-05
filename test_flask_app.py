"""
Quick test script to verify Flask app and database connection.
"""

from app import app
from sqlalchemy import text
from database import db

def test_app():
    """Test Flask app creation and database connection."""
    print("=" * 60)
    print("Testing Flask Application")
    print("=" * 60)

    # Test app creation
    print("\n1. Testing app creation...")
    print(f"   App name: {app.name}")
    print(f"   Debug mode: {app.debug}")
    print(f"   [OK] App created successfully")

    # Test database connection
    print("\n2. Testing database connection...")
    with app.app_context():
        try:
            result = db.session.execute(text('SELECT 1')).scalar()
            print(f"   Query result: {result}")
            print("   [OK] Database connected successfully")

            # Test objective schema
            result = db.session.execute(text("""
                SELECT COUNT(*) FROM objective.cognitive_trait WHERE is_active = TRUE
            """)).scalar()
            print(f"\n3. Testing objective schema...")
            print(f"   Cognitive traits found: {result}")
            print("   [OK] Objective schema accessible")

            # Test character count
            result = db.session.execute(text("""
                SELECT COUNT(*) FROM character.character
            """)).scalar()
            print(f"\n4. Testing character schema...")
            print(f"   Characters found: {result}")
            print("   [OK] Character schema accessible")

            print("\n" + "=" * 60)
            print("[OK] ALL TESTS PASSED - Flask app is ready!")
            print("=" * 60)

        except Exception as e:
            print(f"   [FAIL] Database connection failed: {str(e)}")
            return False

    return True


if __name__ == '__main__':
    success = test_app()
    exit(0 if success else 1)
