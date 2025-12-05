"""
Location Model - Thin wrapper for location stored procedures

Handles location CRUD operations and connections.
All operations use stored procedures from database/procedures/location_procedures.sql
"""

from sqlalchemy import text
from typing import List, Dict, Any, Optional
import logging
import json

logger = logging.getLogger(__name__)


class Location:
    """Thin wrapper for location operations via stored procedures"""

    @staticmethod
    def get(db_session, location_id: int) -> Optional[Dict[str, Any]]:
        """
        Get location by ID.

        Args:
            db_session: SQLAlchemy session
            location_id: Location ID

        Returns:
            Location dictionary or None
        """
        result = db_session.execute(text("""
            SELECT * FROM location_get(:location_id)
        """), {
            "location_id": location_id
        })

        row = result.fetchone()
        if not row:
            return None

        return {
            'location_id': row.location_id,
            'name': row.name,
            'description': row.description,
            'connections': row.connections,
            'environment_type': row.environment_type,
            'lighting': row.lighting,
            'temperature': row.temperature,
            'is_public': row.is_public,
            'items': row.items,
            'properties': row.properties,
            'created_at': row.created_at,
            'updated_at': row.updated_at
        }

    @staticmethod
    def list_all(db_session) -> List[Dict[str, Any]]:
        """
        Get all locations.

        Args:
            db_session: SQLAlchemy session

        Returns:
            List of location dictionaries (basic info)
        """
        result = db_session.execute(text("""
            SELECT * FROM location_list()
        """))

        locations = []
        for row in result.fetchall():
            locations.append({
                'location_id': row.location_id,
                'name': row.name,
                'description': row.description,
                'environment_type': row.environment_type,
                'is_public': row.is_public
            })

        return locations

    @staticmethod
    def create_or_update(
        db_session,
        location_id: int,
        name: str,
        description: str,
        connections: Optional[Dict] = None,
        environment_type: Optional[str] = None,
        lighting: str = 'bright',
        temperature: str = 'comfortable',
        is_public: bool = True,
        items: Optional[List] = None,
        properties: Optional[Dict] = None
    ) -> int:
        """
        Create or update a location.

        Args:
            db_session: SQLAlchemy session
            location_id: Location ID
            name: Location name
            description: Full description
            connections: Dict of direction -> location_id (e.g., {"north": 2, "east": 3})
            environment_type: Type of environment
            lighting: Lighting level
            temperature: Temperature description
            is_public: Whether location is publicly accessible
            items: List of items at location
            properties: Additional properties

        Returns:
            Location ID
        """
        result = db_session.execute(text("""
            SELECT location_upsert(
                p_location_id := :location_id,
                p_name := :name,
                p_description := :description,
                p_connections := :connections::jsonb,
                p_environment_type := :environment_type,
                p_lighting := :lighting,
                p_temperature := :temperature,
                p_is_public := :is_public,
                p_items := :items::jsonb,
                p_properties := :properties::jsonb
            )
        """), {
            "location_id": location_id,
            "name": name,
            "description": description,
            "connections": json.dumps(connections) if connections else '{}',
            "environment_type": environment_type,
            "lighting": lighting,
            "temperature": temperature,
            "is_public": is_public,
            "items": json.dumps(items) if items else '[]',
            "properties": json.dumps(properties) if properties else '{}'
        })

        new_location_id = result.scalar()
        db_session.commit()

        logger.info(f"Created/updated location: {name} ({new_location_id})")

        return new_location_id

    @staticmethod
    def get_connections(db_session, location_id: int) -> List[Dict[str, Any]]:
        """
        Get all connected locations.

        Args:
            db_session: SQLAlchemy session
            location_id: Location ID

        Returns:
            List of connection dictionaries with direction, connected_location_id, and name
        """
        result = db_session.execute(text("""
            SELECT * FROM location_get_connections(:location_id)
        """), {
            "location_id": location_id
        })

        connections = []
        for row in result.fetchall():
            connections.append({
                'direction': row.direction,
                'connected_location_id': row.connected_location_id,
                'location_name': row.location_name
            })

        return connections

    @staticmethod
    def get_characters_at(db_session, location_id: int) -> List[Dict[str, Any]]:
        """
        Get all characters at this location.

        Args:
            db_session: SQLAlchemy session
            location_id: Location ID

        Returns:
            List of character dictionaries (from Character.list_by_location)
        """
        from models.character import Character
        return Character.list_by_location(db_session, location_id)

    @staticmethod
    def delete(db_session, location_id: int) -> bool:
        """
        Delete a location.

        Args:
            db_session: SQLAlchemy session
            location_id: Location ID

        Returns:
            True if deleted
        """
        result = db_session.execute(text("""
            SELECT location_delete(:location_id)
        """), {
            "location_id": location_id
        })

        success = result.scalar()
        db_session.commit()

        if success:
            logger.info(f"Deleted location {location_id}")

        return success
