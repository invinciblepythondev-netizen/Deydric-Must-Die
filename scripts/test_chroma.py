"""
Test Chroma vector database with OpenAI embeddings
"""
import chromadb
from chromadb.utils import embedding_functions
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize client
client = chromadb.PersistentClient(path="./chroma_db")

# Create OpenAI embedding function
openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=os.getenv("OPENAI_API_KEY"),
    model_name="text-embedding-3-small"
)

# Create test collection
collection = client.get_or_create_collection(
    name="test_memories",
    embedding_function=openai_ef
)

# Add test memories
test_memories = [
    "The knight drew his sword in anger at the tavern.",
    "The herbalist mixed a healing potion in her shop.",
    "A shadowy figure poisoned the noble's wine.",
    "The guard discovered a body in the alleyway.",
    "The merchant haggled prices at the market square."
]

for i, memory in enumerate(test_memories):
    collection.add(
        documents=[memory],
        metadatas=[{"turn": i * 10, "character_id": i % 3}],
        ids=[f"test_memory_{i}"]
    )

print(f"Added {len(test_memories)} test memories")

# Test semantic search
queries = [
    "violence and weapons",
    "medical herbs and healing",
    "crime and murder"
]

for query in queries:
    print(f"\n{'='*60}")
    print(f"Query: '{query}'")
    print('='*60)

    results = collection.query(
        query_texts=[query],
        n_results=2
    )

    for i, (doc, metadata, distance) in enumerate(zip(
        results['documents'][0],
        results['metadatas'][0],
        results['distances'][0]
    )):
        print(f"\n  Result {i+1}:")
        print(f"    Memory: {doc}")
        print(f"    Turn: {metadata['turn']}, Character: {metadata['character_id']}")
        print(f"    Distance: {distance:.4f} (lower = more similar)")

# Cleanup
client.delete_collection("test_memories")
print("\n\n✅ Test collection deleted. Chroma is working correctly!")
