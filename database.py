"""
Database connection setup for Flask-SQLAlchemy.

This module provides the Flask-SQLAlchemy database instance
for use throughout the application.
"""

from flask_sqlalchemy import SQLAlchemy

# Create SQLAlchemy instance
db = SQLAlchemy()


def init_db(app):
    """
    Initialize the database with the Flask app.

    Args:
        app: Flask application instance
    """
    db.init_app(app)

    with app.app_context():
        # Import models here to ensure they are registered with SQLAlchemy
        # This is needed for the application to work properly
        pass  # Models will be imported in their respective modules


def get_db():
    """
    Get the database instance.

    Returns:
        SQLAlchemy database instance
    """
    return db
