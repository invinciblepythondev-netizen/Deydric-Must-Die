"""
Database connection setup for Flask-SQLAlchemy.

This module provides the Flask-SQLAlchemy database instance
for use throughout the application.
"""

import logging
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import OperationalError
from sqlalchemy import event
from sqlalchemy.pool import Pool

logger = logging.getLogger(__name__)

# Create SQLAlchemy instance
db = SQLAlchemy()


@event.listens_for(Pool, "connect")
def receive_connect(dbapi_conn, connection_record):
    """Handle new connections."""
    logger.debug("New database connection established")


@event.listens_for(Pool, "checkout")
def receive_checkout(dbapi_conn, connection_record, connection_proxy):
    """Test connection health on checkout from pool."""
    try:
        # Quick test query
        cursor = dbapi_conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
    except OperationalError:
        # Connection is stale, invalidate it
        logger.warning("Stale connection detected, invalidating")
        raise


def init_db(app):
    """
    Initialize the database with the Flask app.

    Args:
        app: Flask application instance
    """
    db.init_app(app)

    # Override Flask-SQLAlchemy's teardown to handle connection errors gracefully
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        """
        Gracefully handle database session cleanup.
        Catches connection errors that occur during teardown.
        """
        try:
            db.session.remove()
        except OperationalError as e:
            # Connection already closed - this is fine during teardown
            # The request already completed successfully
            logger.debug(f"Database connection closed during teardown: {str(e)[:100]}")
        except Exception as e:
            # Log unexpected errors but don't crash
            logger.error(f"Error during session teardown: {e}", exc_info=True)

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
