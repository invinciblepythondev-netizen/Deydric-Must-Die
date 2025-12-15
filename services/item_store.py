"""
Item Store Service - Qdrant-based item storage and retrieval

Stores game items in Qdrant vector database with embeddings for semantic search.
Items can be contained by other items or carried by characters.
"""

import logging
import os
from typing import List, Dict, Any, Optional
from uuid import UUID, uuid4
from datetime import datetime
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue, Range
)
import requests

logger = logging.getLogger(__name__)


class ItemStore:
    """
    Manages item storage in Qdrant with semantic search capabilities.

    SIZE SCALE (1-10000):
    - 1-10: Tiny items (pin, needle, coin)
    - 11-50: Small items (ring, key, scroll, letter)
    - 51-150: Medium items (book, dagger, shirt, bottle)
    - 151-500: Large items (sword, chair, cloak, bag)
    - 501-2000: Very large items (chest, table, wardrobe, door)
    - 2001-10000: Massive items (bed, carriage, large furniture)

    WEIGHT SCALE (1-10000):
    - 1-10: Feather-light (paper, cloth, feather)
    - 11-50: Light (book, dagger, empty bottle)
    - 51-200: Medium (sword, full bottle, small bag of coins)
    - 201-800: Heavy (chair, armor, full backpack)
    - 801-3000: Very heavy (chest of items, table, person)
    - 3001-10000: Extremely heavy (wardrobe, bed, stone statue)

    CAPACITY SCALE (0-size*0.8):
    **IMPORTANT**: Capacity represents interior volume and must be less than size!
    - 0: Cannot contain items
    - Capacity should be 50-80% of item's size (items have walls/structure)
    - Examples:
      * Small chest (size=600) → capacity ~400-480
      * Wardrobe (size=1500) → capacity ~1000-1200
      * Backpack (size=300) → capacity ~200-240
    - Cannot contain items larger than capacity
    - Total size of contained items cannot exceed capacity
    """

    def __init__(self, collection_name: str = "game_items"):
        """
        Initialize item store.

        Args:
            collection_name: Name of Qdrant collection for items
        """
        self.collection_name = collection_name

        # Get Qdrant configuration
        qdrant_host = os.getenv('QDRANT_HOST')
        qdrant_api_key = os.getenv('QDRANT_API_KEY')

        if not qdrant_host:
            raise ValueError("QDRANT_HOST not found in environment variables")

        # Initialize Qdrant client
        self.client = QdrantClient(
            url=qdrant_host,
            api_key=qdrant_api_key,
            timeout=30
        )

        # Embedding configuration
        self.embeddings_model = os.getenv('EMBEDDINGS_MODEL', 'text-embedding-3-small')
        self.embeddings_dimension = int(os.getenv('EMBEDDINGS_DIMENSION', 1536))

        # API keys for embedding providers (priority order)
        self.voyage_api_key = os.getenv('VOYAGE_API_KEY')
        self.openai_api_key = os.getenv('OPENAI_API_KEY')

        # Ensure collection exists
        self._ensure_collection()

    def _ensure_collection(self):
        """Create collection if it doesn't exist."""
        try:
            # Check if collection exists
            collections = self.client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)

            if not exists:
                logger.info(f"Creating Qdrant collection: {self.collection_name}")
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.embeddings_dimension,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"✓ Collection '{self.collection_name}' created")
            else:
                logger.debug(f"Collection '{self.collection_name}' already exists")

        except Exception as e:
            logger.error(f"Error ensuring collection exists: {e}")
            raise

    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """
        Get embedding vector for text using available providers with fallback.

        Priority order:
        1. Voyage AI (voyage-3-lite)
        2. OpenAI (text-embedding-3-small)

        Args:
            text: Text to embed

        Returns:
            Embedding vector or None on error
        """
        # Try Voyage AI first (preferred for cost and quality)
        if self.voyage_api_key:
            try:
                logger.debug("Trying Voyage AI embeddings...")
                response = requests.post(
                    'https://api.voyageai.com/v1/embeddings',
                    headers={
                        'Authorization': f'Bearer {self.voyage_api_key}',
                        'Content-Type': 'application/json'
                    },
                    json={
                        'model': 'voyage-large-2',  # 1536 dims (matches OpenAI)
                        'input': text
                    },
                    timeout=30
                )

                if response.status_code == 200:
                    embedding = response.json()['data'][0]['embedding']
                    logger.debug("Successfully got Voyage AI embedding")
                    return embedding
                else:
                    logger.warning(f"Voyage AI embedding failed: {response.status_code} - {response.text}")
            except Exception as e:
                logger.warning(f"Voyage AI embedding error: {e}")

        # Fallback to OpenAI
        if self.openai_api_key:
            try:
                logger.debug("Trying OpenAI embeddings...")
                response = requests.post(
                    'https://api.openai.com/v1/embeddings',
                    headers={
                        'Authorization': f'Bearer {self.openai_api_key}',
                        'Content-Type': 'application/json'
                    },
                    json={
                        'model': self.embeddings_model,
                        'input': text
                    },
                    timeout=30
                )

                if response.status_code == 200:
                    embedding = response.json()['data'][0]['embedding']
                    logger.debug("Successfully got OpenAI embedding")
                    return embedding
                else:
                    logger.error(f"OpenAI embedding failed: {response.status_code} - {response.text}")
            except Exception as e:
                logger.error(f"OpenAI embedding error: {e}")

        # All providers failed
        logger.error("All embedding providers failed")
        return None

    def add_item(
        self,
        item_id: UUID,
        location_id: Optional[int],
        item_type: str,
        item_name: str,
        item_description: str,
        item_description_short: str,
        size: int,
        weight: int,
        capacity: int = 0,
        contained_by_item_id: Optional[UUID] = None,
        carried_by_character_id: Optional[UUID] = None,
        current_state: Optional[str] = None,
        created_turn: int = 0,
        # New fields for Hybrid Approach
        importance_level: str = "mundane",
        visibility_level: str = "visible",
        position_type: Optional[str] = None,
        positioned_at_item_id: Optional[UUID] = None,
        has_contents: bool = False,
        contents_generated: bool = False,
        worn_slot: Optional[str] = None,
        carry_method: Optional[str] = None
    ) -> bool:
        """
        Add or update an item in the store.

        Args:
            item_id: Unique item identifier
            location_id: SQL database location.location_id (null if contained/carried)
            item_type: Type category of item
            item_name: Display name
            item_description: Detailed description for embedding
            item_description_short: Brief description
            size: Size scale 1-10000
            weight: Weight scale 1-10000
            capacity: Storage capacity (0 for non-containers, max 80% of size for containers)
            contained_by_item_id: Container item ID if contained
            carried_by_character_id: Character ID if carried
            current_state: Current state description (deviations from base description)
            created_turn: Turn number when created (negative for pre-game items)
            importance_level: crucial, notable, mundane, trivial
            visibility_level: obvious, visible, hidden, concealed
            position_type: on, in, under, beside, behind, hanging_from, leaning_against
            positioned_at_item_id: UUID of item it's positioned relative to
            has_contents: Container has ungenerated contents (lazy generation flag)
            contents_generated: Container contents have been generated
            worn_slot: head, torso, legs, feet, hands, neck, finger, waist, back (None if not worn)
            carry_method: carried, worn, wielded (how character holds/wears it)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate capacity doesn't exceed size
            if capacity > 0:
                max_capacity = int(size * 0.8)
                if capacity > max_capacity:
                    logger.warning(
                        f"Item {item_name}: capacity ({capacity}) exceeds 80% of size ({size}). "
                        f"Clamping to {max_capacity}"
                    )
                    capacity = max_capacity

            # If being contained, check if it fits in the container
            if contained_by_item_id:
                container = self.get_item(contained_by_item_id)
                if container:
                    if not self.can_fit_in_container(size, contained_by_item_id):
                        logger.error(
                            f"Item {item_name} (size={size}) cannot fit in container "
                            f"{container.get('item_name')} (capacity={container.get('capacity')})"
                        )
                        return False
            # Create embedding from description
            embedding_text = f"{item_name}. {item_description}"
            embedding = self._get_embedding(embedding_text)

            if not embedding:
                logger.error(f"Failed to create embedding for item {item_id}")
                return False

            # Create point with payload
            point = PointStruct(
                id=str(item_id),
                vector=embedding,
                payload={
                    "item_id": str(item_id),
                    "location_id": str(location_id) if location_id is not None else None,
                    "item_type": item_type,
                    "item_name": item_name,
                    "item_description": item_description,
                    "item_description_short": item_description_short,
                    "size": size,
                    "weight": weight,
                    "capacity": capacity,
                    "contained_by_item_id": str(contained_by_item_id) if contained_by_item_id else None,
                    "carried_by_character_id": str(carried_by_character_id) if carried_by_character_id else None,
                    "current_state": current_state,
                    "created_turn": created_turn,
                    # Hybrid approach fields
                    "importance_level": importance_level,
                    "visibility_level": visibility_level,
                    "position_type": position_type,
                    "positioned_at_item_id": str(positioned_at_item_id) if positioned_at_item_id else None,
                    "has_contents": has_contents,
                    "contents_generated": contents_generated,
                    "worn_slot": worn_slot,
                    "carry_method": carry_method,
                    # Timestamps
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                }
            )

            # Upsert point
            self.client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )

            logger.info(f"Added/updated item: {item_name} (ID: {item_id})")
            return True

        except Exception as e:
            logger.error(f"Error adding item {item_id}: {e}")
            return False

    def get_items_at_location(self, location_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get all items at a specific location (not contained or carried).

        Args:
            location_id: Location ID to search
            limit: Maximum number of items to return

        Returns:
            List of item dictionaries
        """
        try:
            # Search with filter for location_id only
            # Then filter out contained/carried items in Python (Qdrant doesn't support null checks well)
            # Note: location_id must be string for keyword index matching
            results = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="location_id",
                            match=MatchValue(value=str(location_id))
                        )
                    ]
                ),
                limit=limit * 2,  # Get more to account for filtering
                with_payload=True,
                with_vectors=False
            )

            # Filter out items that are contained or carried
            items = [
                hit.payload for hit in results[0]
                if not hit.payload.get('contained_by_item_id')
                and not hit.payload.get('carried_by_character_id')
            ]
            items = items[:limit]  # Trim to requested limit

            logger.debug(f"Found {len(items)} items at location {location_id}")
            return items

        except Exception as e:
            logger.error(f"Error getting items at location {location_id}: {e}")
            return []

    def get_items_carried_by(self, character_id: UUID, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all items carried by a character."""
        try:
            results = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="carried_by_character_id",
                            match=MatchValue(value=str(character_id))
                        )
                    ]
                ),
                limit=limit,
                with_payload=True,
                with_vectors=False
            )

            return [hit.payload for hit in results[0]]

        except Exception as e:
            logger.error(f"Error getting items for character {character_id}: {e}")
            return []

    def get_items_in_container(self, container_id: UUID, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all items contained in another item."""
        try:
            results = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="contained_by_item_id",
                            match=MatchValue(value=str(container_id))
                        )
                    ]
                ),
                limit=limit,
                with_payload=True,
                with_vectors=False
            )

            return [hit.payload for hit in results[0]]

        except Exception as e:
            logger.error(f"Error getting items in container {container_id}: {e}")
            return []

    def get_item(self, item_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get a single item by ID.

        Args:
            item_id: Item UUID

        Returns:
            Item dictionary or None if not found
        """
        try:
            result = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[str(item_id)],
                with_payload=True,
                with_vectors=False
            )

            if result:
                return result[0].payload
            return None

        except Exception as e:
            logger.error(f"Error getting item {item_id}: {e}")
            return None

    def can_fit_in_container(self, item_size: int, container_id: UUID) -> bool:
        """
        Check if an item can fit in a container.

        Validates:
        1. Item size <= container capacity
        2. Total size of items in container + new item <= capacity

        Args:
            item_size: Size of item to add
            container_id: UUID of container

        Returns:
            True if item fits, False otherwise
        """
        try:
            # Get container
            container = self.get_item(container_id)
            if not container:
                logger.error(f"Container {container_id} not found")
                return False

            container_capacity = container.get('capacity', 0)

            # Check if container has capacity
            if container_capacity == 0:
                logger.error(f"Container {container.get('item_name')} cannot contain items (capacity=0)")
                return False

            # Check if item is too large
            if item_size > container_capacity:
                logger.warning(
                    f"Item (size={item_size}) is larger than container capacity ({container_capacity})"
                )
                return False

            # Get current contents
            contained_items = self.get_items_in_container(container_id)
            current_total_size = sum(item.get('size', 0) for item in contained_items)

            # Check if adding this item would exceed capacity
            if current_total_size + item_size > container_capacity:
                logger.warning(
                    f"Adding item (size={item_size}) would exceed container capacity. "
                    f"Current: {current_total_size}, Capacity: {container_capacity}"
                )
                return False

            return True

        except Exception as e:
            logger.error(f"Error checking container fit: {e}")
            return False

    def update_item(self, item_id: UUID, **kwargs) -> bool:
        """
        Update specific fields of an item.

        Args:
            item_id: Item UUID
            **kwargs: Fields to update (any field from add_item)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get existing item
            existing = self.get_item(item_id)
            if not existing:
                logger.error(f"Item {item_id} not found for update")
                return False

            # Merge updates with existing data
            updated_data = {**existing, **kwargs}
            updated_data['updated_at'] = datetime.utcnow().isoformat()

            # Re-embed if description changed
            if 'item_description' in kwargs or 'item_name' in kwargs:
                embedding_text = f"{updated_data['item_name']}. {updated_data['item_description']}"
                embedding = self._get_embedding(embedding_text)
                if not embedding:
                    logger.error(f"Failed to create embedding for updated item {item_id}")
                    return False
            else:
                # Retrieve existing vector
                result = self.client.retrieve(
                    collection_name=self.collection_name,
                    ids=[str(item_id)],
                    with_vectors=True
                )
                embedding = result[0].vector if result else None

            if not embedding:
                logger.error(f"No embedding available for item {item_id}")
                return False

            # Create updated point
            point = PointStruct(
                id=str(item_id),
                vector=embedding,
                payload={
                    "item_id": str(updated_data['item_id']),
                    "location_id": str(updated_data['location_id']) if updated_data.get('location_id') is not None else None,
                    "item_type": updated_data['item_type'],
                    "item_name": updated_data['item_name'],
                    "item_description": updated_data['item_description'],
                    "item_description_short": updated_data['item_description_short'],
                    "size": updated_data['size'],
                    "weight": updated_data['weight'],
                    "capacity": updated_data['capacity'],
                    "contained_by_item_id": updated_data.get('contained_by_item_id'),
                    "carried_by_character_id": updated_data.get('carried_by_character_id'),
                    "current_state": updated_data.get('current_state'),
                    "created_turn": updated_data['created_turn'],
                    "importance_level": updated_data.get('importance_level', 'mundane'),
                    "visibility_level": updated_data.get('visibility_level', 'visible'),
                    "position_type": updated_data.get('position_type'),
                    "positioned_at_item_id": updated_data.get('positioned_at_item_id'),
                    "has_contents": updated_data.get('has_contents', False),
                    "contents_generated": updated_data.get('contents_generated', False),
                    "worn_slot": updated_data.get('worn_slot'),
                    "carry_method": updated_data.get('carry_method'),
                    "created_at": updated_data.get('created_at'),
                    "updated_at": updated_data['updated_at']
                }
            )

            # Upsert
            self.client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )

            logger.info(f"Updated item: {updated_data['item_name']} (ID: {item_id})")
            return True

        except Exception as e:
            logger.error(f"Error updating item {item_id}: {e}")
            return False

    def semantic_search(
        self,
        query_text: str,
        location_id: Optional[int] = None,
        limit: int = 10,
        score_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Semantic search for items using vector similarity.

        Args:
            query_text: Text to search for (e.g., "sharp objects", "books about magic")
            location_id: Optional filter by location
            limit: Maximum results
            score_threshold: Minimum similarity score (0-1)

        Returns:
            List of items sorted by relevance
        """
        try:
            # Get query embedding
            query_embedding = self._get_embedding(query_text)
            if not query_embedding:
                logger.error("Failed to create query embedding")
                return []

            # Build filter
            filter_conditions = []
            if location_id is not None:
                # Convert to string for keyword index matching
                filter_conditions.append(
                    FieldCondition(
                        key="location_id",
                        match=MatchValue(value=str(location_id))
                    )
                )

            search_filter = Filter(must=filter_conditions) if filter_conditions else None

            # Search using query_points (new Qdrant API)
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_embedding,
                query_filter=search_filter,
                limit=limit,
                score_threshold=score_threshold,
                with_payload=True,
                with_vectors=False
            )

            items = [hit.payload for hit in results.points]
            logger.debug(f"Semantic search for '{query_text}' found {len(items)} items")
            return items

        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            return []

    def find_item_by_name(
        self,
        item_name: str,
        location_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Find item by name (fuzzy matching via semantic search).

        Args:
            item_name: Name to search for
            location_id: Optional filter by location

        Returns:
            Best matching item or None
        """
        try:
            # Use semantic search to find by name
            results = self.semantic_search(
                query_text=item_name,
                location_id=location_id,
                limit=1,
                score_threshold=0.6
            )

            return results[0] if results else None

        except Exception as e:
            logger.error(f"Error finding item by name '{item_name}': {e}")
            return None

    def search_items(
        self,
        location_id: Optional[int] = None,
        importance_levels: Optional[List[str]] = None,
        visibility_levels: Optional[List[str]] = None,
        item_types: Optional[List[str]] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Filter items by metadata.

        Args:
            location_id: Filter by location
            importance_levels: Filter by importance (crucial, notable, mundane, trivial)
            visibility_levels: Filter by visibility (obvious, visible, hidden, concealed)
            item_types: Filter by type (furniture, clothing, weapon, etc.)
            limit: Maximum results

        Returns:
            Filtered items
        """
        try:
            filter_conditions = []

            if location_id is not None:
                # Convert to string for keyword index matching
                filter_conditions.append(
                    FieldCondition(
                        key="location_id",
                        match=MatchValue(value=str(location_id))
                    )
                )

            # Note: Qdrant doesn't support OR conditions easily, so we'll retrieve all and filter
            results = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(must=filter_conditions) if filter_conditions else None,
                limit=limit * 2,  # Get more to filter
                with_payload=True,
                with_vectors=False
            )

            items = [hit.payload for hit in results[0]]

            # Filter by importance
            if importance_levels:
                items = [item for item in items if item.get('importance_level') in importance_levels]

            # Filter by visibility
            if visibility_levels:
                items = [item for item in items if item.get('visibility_level') in visibility_levels]

            # Filter by type
            if item_types:
                items = [item for item in items if item.get('item_type') in item_types]

            logger.debug(f"Filtered search found {len(items)} items")
            return items[:limit]

        except Exception as e:
            logger.error(f"Error in search_items: {e}")
            return []

    def get_worn_items(self, character_id: UUID) -> List[Dict[str, Any]]:
        """Get all items worn by a character (clothing, armor, jewelry)."""
        try:
            results = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="carried_by_character_id",
                            match=MatchValue(value=str(character_id))
                        ),
                        FieldCondition(
                            key="carry_method",
                            match=MatchValue(value="worn")
                        )
                    ]
                ),
                limit=100,
                with_payload=True,
                with_vectors=False
            )

            return [hit.payload for hit in results[0]]

        except Exception as e:
            logger.error(f"Error getting worn items for character {character_id}: {e}")
            return []

    def get_carried_items_not_worn(self, character_id: UUID) -> List[Dict[str, Any]]:
        """Get items carried but not worn (in hands, in bags)."""
        try:
            all_carried = self.get_items_carried_by(character_id)
            not_worn = [item for item in all_carried if item.get('carry_method') != 'worn']
            return not_worn

        except Exception as e:
            logger.error(f"Error getting carried (not worn) items for character {character_id}: {e}")
            return []

    def get_total_carried_weight(
        self,
        character_id: UUID,
        include_worn: bool = True
    ) -> int:
        """
        Calculate total weight carried by character.

        Args:
            character_id: Character UUID
            include_worn: Whether to include worn items in weight calculation

        Returns:
            Total weight (sum of item weights)
        """
        try:
            if include_worn:
                items = self.get_items_carried_by(character_id)
            else:
                items = self.get_carried_items_not_worn(character_id)

            total_weight = sum(item.get('weight', 0) for item in items)
            logger.debug(f"Character {character_id} carrying {total_weight} weight")
            return total_weight

        except Exception as e:
            logger.error(f"Error calculating carried weight for character {character_id}: {e}")
            return 0
