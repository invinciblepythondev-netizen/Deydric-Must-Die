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
from config import get_config

# Load environment variables
load_dotenv()

def create_app():
    """
    Create and configure the Flask application.

    Returns:
        Flask application instance
    """
    app = Flask(__name__)

    # Load configuration from config.py
    env = os.getenv('FLASK_ENV', 'development')
    config_class = get_config(env)
    app.config.from_object(config_class)

    # Ensure psycopg driver is used
    database_url = app.config['SQLALCHEMY_DATABASE_URI']
    if database_url and 'postgresql://' in database_url:
        # Replace postgresql:// with postgresql+psycopg:// to use psycopg3
        database_url = database_url.replace('postgresql://', 'postgresql+psycopg://')
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url

    # Initialize extensions (includes database connection error handling)
    init_db(app)

    # Register blueprints
    from routes.game import game_bp
    app.register_blueprint(game_bp)

    # Simple home route
    @app.route('/')
    def index():
        from flask import render_template
        return render_template('index.html')

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
