"""
Flask application entry point for Deydric Must Die.

This is a turn-based text adventure game with LLM-generated content,
set in a dark fantasy/gothic world with realistic injury mechanics
and complex character relationships.
"""

import os
from flask import Flask
from dotenv import load_dotenv
from database import db, init_db

# Load environment variables
load_dotenv()

def create_app():
    """
    Create and configure the Flask application.

    Returns:
        Flask application instance
    """
    app = Flask(__name__)

    # Configuration
    app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

    # Get database URL and ensure it uses psycopg (psycopg3) driver
    database_url = os.getenv('NEON_DATABASE_URL')
    if database_url and 'postgresql://' in database_url:
        # Replace postgresql:// with postgresql+psycopg:// to use psycopg3
        database_url = database_url.replace('postgresql://', 'postgresql+psycopg://')

    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,  # Verify connections before using them
        'pool_recycle': 300,     # Recycle connections after 5 minutes
    }

    # Initialize extensions
    init_db(app)

    # Register blueprints (when routes are created)
    # from routes import game_bp, character_bp, admin_bp
    # app.register_blueprint(game_bp)
    # app.register_blueprint(character_bp)
    # app.register_blueprint(admin_bp)

    # Simple health check route
    @app.route('/')
    def index():
        return {
            'status': 'online',
            'game': 'Deydric Must Die',
            'description': 'Turn-based text adventure with LLM-generated content'
        }

    @app.route('/health')
    def health():
        """Health check endpoint for monitoring."""
        try:
            # Test database connection
            from sqlalchemy import text
            with db.engine.connect() as conn:
                conn.execute(text('SELECT 1'))
            return {'status': 'healthy', 'database': 'connected'}
        except Exception as e:
            return {'status': 'unhealthy', 'error': str(e)}, 500

    return app


# Create the app instance
app = create_app()


if __name__ == '__main__':
    # Development server
    debug_mode = os.getenv('DEBUG', 'False').lower() == 'true'
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=debug_mode
    )
