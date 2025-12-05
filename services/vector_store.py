"""
Qdrant Vector Store Service

Handles semantic memory storage and retrieval using Qdrant vector database.
Stores embeddings of significant game events for long-term memory search.
"""
import os
from typing import List, Dict, Any, Optional
from uuid import UUID
import openai
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from dotenv import load_dotenv

load_dotenv()


class VectorStoreService:
    """
    Service for managing semantic memory in Qdrant vector database.

    Handles:
    - Embedding turn history events
    - Semantic search for relevant memories
    - Collection management
    """

    def __init__(
        self,
        collection_name: str = "game_memories",
        embedding_model: str = None,
        embedding_dimension: int = None
    ):
        """
        Initialize Qdrant vector store.

        Args:
            collection_name: Name of the Qdrant collection
            embedding_model: OpenAI embedding model (default: from .env)
            embedding_dimension: Size of embeddings (default: from .env)
        """
        # Get configuration from environment
        self.qdrant_host = os.getenv("QDRANT_HOST")
        self.qdrant_api_key = os.getenv("QDRANT_API_KEY")
        self.embedding_model = embedding_model or os.getenv("EMBEDDINGS_MODEL", "text-embedding-3-small")
        self.embedding_dimension = embedding_dimension or int(os.getenv("EMBEDDINGS_DIMENSION", "1536"))

        if not self.qdrant_host or not self.qdrant_api_key:
            raise ValueError("QDRANT_HOST and QDRANT_API_KEY must be set in .env")

        # Initialize OpenAI client for embeddings
        openai.api_key = os.getenv("OPENAI_API_KEY")
        if not openai.api_key:
            raise ValueError("OPENAI_API_KEY must be set in .env for embeddings")

        # Initialize Qdrant client
        self.client = QdrantClient(
            url=self.qdrant_host,
            api_key=self.qdrant_api_key,
        )

        self.collection_name = collection_name
        self._ensure_collection_exists()

    def _ensure_collection_exists(self):
        """Create collection if it doesn't exist."""
        collections = self.client.get_collections().collections
        collection_names = [col.name for col in collections]

        if self.collection_name not in collection_names:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.embedding_dimension,
                    distance=Distance.COSINE
                )
            )
            print(f"[OK] Created Qdrant collection: {self.collection_name}")

    def _get_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text using OpenAI.

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector
        """
        response = openai.embeddings.create(
            model=self.embedding_model,
            input=text
        )
        return response.data[0].embedding

    def add_memory(
        self,
        memory_id: str,
        text: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Add a memory to the vector store.

        Args:
            memory_id: Unique ID for this memory (e.g., turn_id from database)
            text: The text content to embed and store
            metadata: Additional data (turn_number, character_id, etc.)

        Returns:
            True if successful
        """
        try:
            # Generate embedding
            embedding = self._get_embedding(text)

            # Create point
            point = PointStruct(
                id=memory_id,
                vector=embedding,
                payload=metadata
            )

            # Upsert to Qdrant
            self.client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )

            return True
        except Exception as e:
            print(f"[ERROR] Failed to add memory {memory_id}: {e}")
            return False

    def add_memories_batch(
        self,
        memories: List[Dict[str, Any]]
    ) -> int:
        """
        Add multiple memories in a batch.

        Args:
            memories: List of dicts with keys: id, text, metadata

        Returns:
            Number of memories successfully added
        """
        points = []

        for memory in memories:
            try:
                embedding = self._get_embedding(memory['text'])
                point = PointStruct(
                    id=memory['id'],
                    vector=embedding,
                    payload=memory.get('metadata', {})
                )
                points.append(point)
            except Exception as e:
                print(f"[WARN] Failed to process memory {memory.get('id')}: {e}")

        if points:
            try:
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=points
                )
                return len(points)
            except Exception as e:
                print(f"[ERROR] Batch upsert failed: {e}")
                return 0

        return 0

    def search_memories(
        self,
        query: str,
        limit: int = 5,
        score_threshold: float = 0.7,
        filter_conditions: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant memories using semantic similarity.

        Args:
            query: The search query text
            limit: Maximum number of results to return
            score_threshold: Minimum similarity score (0-1)
            filter_conditions: Optional Qdrant filter dict

        Returns:
            List of dicts with keys: id, score, text, metadata
        """
        try:
            # Generate query embedding
            query_embedding = self._get_embedding(query)

            # Search Qdrant
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=limit,
                score_threshold=score_threshold,
                query_filter=filter_conditions
            )

            # Format results
            memories = []
            for result in results:
                memories.append({
                    'id': result.id,
                    'score': result.score,
                    'metadata': result.payload
                })

            return memories

        except Exception as e:
            print(f"[ERROR] Memory search failed: {e}")
            return []

    def search_by_character(
        self,
        query: str,
        character_id: str,
        limit: int = 5,
        score_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Search memories related to a specific character.

        Args:
            query: The search query text
            character_id: UUID of the character
            limit: Maximum number of results
            score_threshold: Minimum similarity score

        Returns:
            List of relevant memories
        """
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        filter_conditions = Filter(
            must=[
                FieldCondition(
                    key="character_id",
                    match=MatchValue(value=character_id)
                )
            ]
        )

        return self.search_memories(
            query=query,
            limit=limit,
            score_threshold=score_threshold,
            filter_conditions=filter_conditions
        )

    def search_by_turn_range(
        self,
        query: str,
        start_turn: int,
        end_turn: int,
        limit: int = 5,
        score_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Search memories within a specific turn range.

        Args:
            query: The search query text
            start_turn: Start of turn range (inclusive)
            end_turn: End of turn range (inclusive)
            limit: Maximum number of results
            score_threshold: Minimum similarity score

        Returns:
            List of relevant memories
        """
        from qdrant_client.models import Filter, FieldCondition, Range

        filter_conditions = Filter(
            must=[
                FieldCondition(
                    key="turn_number",
                    range=Range(gte=start_turn, lte=end_turn)
                )
            ]
        )

        return self.search_memories(
            query=query,
            limit=limit,
            score_threshold=score_threshold,
            filter_conditions=filter_conditions
        )

    def get_memory_by_id(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific memory by ID.

        Args:
            memory_id: The ID of the memory to retrieve

        Returns:
            Memory dict or None if not found
        """
        try:
            result = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[memory_id]
            )

            if result:
                point = result[0]
                return {
                    'id': point.id,
                    'metadata': point.payload
                }

            return None

        except Exception as e:
            print(f"[ERROR] Failed to retrieve memory {memory_id}: {e}")
            return None

    def delete_memory(self, memory_id: str) -> bool:
        """
        Delete a memory from the vector store.

        Args:
            memory_id: ID of the memory to delete

        Returns:
            True if successful
        """
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=[memory_id]
            )
            return True
        except Exception as e:
            print(f"[ERROR] Failed to delete memory {memory_id}: {e}")
            return False

    def count_memories(self) -> int:
        """
        Get the total number of memories in the collection.

        Returns:
            Count of memories
        """
        try:
            collection_info = self.client.get_collection(self.collection_name)
            return collection_info.points_count
        except Exception as e:
            print(f"[ERROR] Failed to count memories: {e}")
            return 0

    def clear_collection(self) -> bool:
        """
        Delete all memories from the collection.

        WARNING: This is destructive and cannot be undone.

        Returns:
            True if successful
        """
        try:
            self.client.delete_collection(self.collection_name)
            self._ensure_collection_exists()
            return True
        except Exception as e:
            print(f"[ERROR] Failed to clear collection: {e}")
            return False


# Convenience function for easy import
def get_vector_store(collection_name: str = "game_memories") -> VectorStoreService:
    """
    Get a vector store instance.

    Args:
        collection_name: Name of the collection to use

    Returns:
        VectorStoreService instance
    """
    return VectorStoreService(collection_name=collection_name)
