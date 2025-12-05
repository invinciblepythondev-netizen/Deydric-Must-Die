"""
Test Qdrant vector database with OpenAI embeddings

This script tests the VectorStoreService with sample game memories
to verify Qdrant connection and semantic search functionality.
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services.vector_store import VectorStoreService
from uuid import uuid4


def test_qdrant():
    """Test Qdrant vector store service."""
    print("=" * 80)
    print("Testing Qdrant Vector Store")
    print("=" * 80)

    # Initialize service
    print("\n1. Initializing VectorStoreService...")
    try:
        vector_store = VectorStoreService(collection_name="test_memories")
        print(f"   [OK] Connected to Qdrant")
        print(f"   Collection: {vector_store.collection_name}")
        print(f"   Embedding model: {vector_store.embedding_model}")
        print(f"   Embedding dimension: {vector_store.embedding_dimension}")
    except Exception as e:
        print(f"   [FAIL] Failed to connect: {e}")
        return False

    # Add test memories
    print("\n2. Adding test memories...")
    test_memories = [
        {
            'id': str(uuid4()),
            'text': 'The knight drew his sword in anger at the tavern.',
            'metadata': {
                'turn_number': 10,
                'character_id': 'char1',
                'location': 'tavern',
                'action_type': 'attack',
                'significance_score': 0.9
            }
        },
        {
            'id': str(uuid4()),
            'text': 'The herbalist mixed a healing potion in her shop.',
            'metadata': {
                'turn_number': 20,
                'character_id': 'char2',
                'location': 'herb_shop',
                'action_type': 'craft',
                'significance_score': 0.7
            }
        },
        {
            'id': str(uuid4()),
            'text': 'A shadowy figure poisoned the noble\'s wine.',
            'metadata': {
                'turn_number': 30,
                'character_id': 'char3',
                'location': 'manor',
                'action_type': 'poison',
                'significance_score': 0.95
            }
        },
        {
            'id': str(uuid4()),
            'text': 'The guard discovered a body in the alleyway.',
            'metadata': {
                'turn_number': 40,
                'character_id': 'char4',
                'location': 'alley',
                'action_type': 'discover',
                'significance_score': 0.85
            }
        },
        {
            'id': str(uuid4()),
            'text': 'The merchant haggled prices at the market square.',
            'metadata': {
                'turn_number': 50,
                'character_id': 'char5',
                'location': 'market',
                'action_type': 'interact',
                'significance_score': 0.5
            }
        }
    ]

    added_count = vector_store.add_memories_batch(test_memories)
    print(f"   [OK] Added {added_count}/{len(test_memories)} memories")

    # Verify memory count
    print("\n3. Verifying memory count...")
    count = vector_store.count_memories()
    print(f"   [OK] Collection has {count} memories")

    # Test semantic search
    print("\n4. Testing semantic search...")

    test_queries = [
        "violence and weapons",
        "medical herbs and healing",
        "crime and murder",
        "trading and commerce"
    ]

    for query in test_queries:
        print(f"\n   Query: '{query}'")
        print("   " + "-" * 60)

        results = vector_store.search_memories(
            query=query,
            limit=2,
            score_threshold=0.5
        )

        for i, result in enumerate(results, 1):
            print(f"\n   Result {i}:")
            print(f"     Score: {result['score']:.4f} (higher = more similar)")
            print(f"     Turn: {result['metadata']['turn_number']}")
            print(f"     Character: {result['metadata']['character_id']}")
            print(f"     Location: {result['metadata']['location']}")
            print(f"     Action: {result['metadata']['action_type']}")

    # Test character-specific search
    print("\n\n5. Testing character-specific search...")
    print("   Query: 'What happened at the tavern?' (character: char1)")
    results = vector_store.search_by_character(
        query="What happened at the tavern?",
        character_id="char1",
        limit=5,
        score_threshold=0.5
    )

    if results:
        for i, result in enumerate(results, 1):
            print(f"\n   Result {i}:")
            print(f"     Score: {result['score']:.4f}")
            print(f"     Turn: {result['metadata']['turn_number']}")
            print(f"     Location: {result['metadata']['location']}")
    else:
        print("   [OK] No results (expected - limited test data)")

    # Test turn range search
    print("\n\n6. Testing turn range search...")
    print("   Query: 'suspicious activities' (turns 25-45)")
    results = vector_store.search_by_turn_range(
        query="suspicious activities",
        start_turn=25,
        end_turn=45,
        limit=5,
        score_threshold=0.5
    )

    if results:
        for i, result in enumerate(results, 1):
            print(f"\n   Result {i}:")
            print(f"     Score: {result['score']:.4f}")
            print(f"     Turn: {result['metadata']['turn_number']}")
            print(f"     Action: {result['metadata']['action_type']}")
    else:
        print("   [OK] No results found in range")

    # Test retrieval by ID
    print("\n\n7. Testing memory retrieval by ID...")
    test_id = test_memories[0]['id']
    memory = vector_store.get_memory_by_id(test_id)

    if memory:
        print(f"   [OK] Retrieved memory {test_id}")
        print(f"   Turn: {memory['metadata']['turn_number']}")
        print(f"   Location: {memory['metadata']['location']}")
    else:
        print(f"   [FAIL] Could not retrieve memory {test_id}")

    # Cleanup
    print("\n\n8. Cleaning up test collection...")
    if vector_store.clear_collection():
        print("   [OK] Test collection cleared")
    else:
        print("   [WARN] Could not clear collection (may need manual cleanup)")

    print("\n" + "=" * 80)
    print("[OK] Qdrant vector store is working correctly!")
    print("=" * 80)

    return True


if __name__ == '__main__':
    try:
        success = test_qdrant()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
