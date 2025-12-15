# Qdrant API Update - search() to query_points()

## Issue

The game was encountering this error:
```
Error in semantic search: 'QdrantClient' object has no attribute 'search'
```

## Root Cause

The Qdrant Python client API changed between versions:
- **Old API**: Used `client.search()` method for vector similarity search
- **New API**: Uses `client.query_points()` as a universal endpoint for all query operations

## Changes Made

### 1. Updated `services/item_store.py`

**Location**: Line 611-621

**Before**:
```python
results = self.client.search(
    collection_name=self.collection_name,
    query_vector=query_embedding,
    query_filter=search_filter,
    limit=limit,
    score_threshold=score_threshold,
    with_payload=True
)

items = [hit.payload for hit in results]
```

**After**:
```python
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
```

### 2. Updated `services/vector_store.py`

**Location**: Line 199-218

**Before**:
```python
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
```

**After**:
```python
response = self.client.query_points(
    collection_name=self.collection_name,
    query=query_embedding,
    limit=limit,
    score_threshold=score_threshold,
    query_filter=filter_conditions,
    with_payload=True,
    with_vectors=False
)

# Format results
memories = []
for result in response.points:
    memories.append({
        'id': result.id,
        'score': result.score,
        'metadata': result.payload
    })
```

## API Differences

### Parameter Changes

| Old API (`search`) | New API (`query_points`) |
|-------------------|-------------------------|
| `query_vector` | `query` |
| Returns list directly | Returns `QueryResponse` object |
| Access items via iteration | Access via `.points` attribute |

### New Features in `query_points()`

The `query_points()` method is more flexible and supports:
- **Multiple query types**: Can accept vectors, point IDs, documents, images
- **Prefetch queries**: For complex multi-stage searches
- **Pagination**: Built-in offset support
- **Universal endpoint**: Single method for search, recommendation, discovery

### Response Structure

**Old API**:
```python
results = client.search(...)  # Returns list of ScoredPoint
for hit in results:
    payload = hit.payload
```

**New API**:
```python
response = client.query_points(...)  # Returns QueryResponse object
for hit in response.points:  # Access via .points attribute
    payload = hit.payload
```

## Testing

Created test script: `scripts/test_semantic_search.py`

**Test Results**:
```
Test 1: Semantic search for 'clothing' (no location filter)
[OK] Found 5 items

Test 2: Semantic search for 'furniture' at location 7
[OK] Found 5 items

Test 3: Find item by name 'bed' at location 7
[OK] Found item: Four-Poster Bed

[SUCCESS] All tests passed!
```

## Impact

This fix resolves:
- ✅ Semantic search errors in item system
- ✅ Item lookup failures during gameplay
- ✅ "Item not found" errors when LLM tries to find items
- ✅ Memory search functionality in vector store

## Migration Guide

If you're using the old Qdrant API elsewhere in the codebase:

```python
# Replace this:
results = client.search(
    collection_name="my_collection",
    query_vector=[0.1, 0.2, ...],
    limit=10
)
for hit in results:
    print(hit.payload)

# With this:
response = client.query_points(
    collection_name="my_collection",
    query=[0.1, 0.2, ...],
    limit=10,
    with_payload=True,
    with_vectors=False
)
for hit in response.points:
    print(hit.payload)
```

## Related Files

- `services/item_store.py` - Item semantic search
- `services/vector_store.py` - Memory semantic search
- `scripts/test_semantic_search.py` - Test suite for semantic search

## References

- [Qdrant Query API Documentation](https://qdrant.tech/documentation/concepts/points/#query-api)
- Qdrant Python Client: Uses `query_points()` as the universal search endpoint
