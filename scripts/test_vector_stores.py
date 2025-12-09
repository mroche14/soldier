#!/usr/bin/env python3
"""Test script to verify Jina embeddings + vector stores work end-to-end.

Usage:
    # Test in-memory store only (no API keys needed)
    uv run python scripts/test_vector_stores.py --inmemory

    # Test Qdrant store (requires QDRANT_URL and QDRANT_API_KEY)
    uv run python scripts/test_vector_stores.py --qdrant

    # Test pgvector store (requires DATABASE_URL with pgvector extension)
    uv run python scripts/test_vector_stores.py --pgvector

    # Test all stores
    uv run python scripts/test_vector_stores.py --all
"""

import argparse
import asyncio
import os
import sys
from uuid import uuid4

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from focal.vector.stores.base import EntityType, VectorDocument, VectorMetadata
from focal.vector.stores.inmemory import InMemoryVectorStore
from focal.vector.stores.qdrant import QdrantVectorStore


async def get_jina_embedding(text: str) -> list[float]:
    """Get embedding from Jina API."""
    from focal.providers.embedding.jina import JinaEmbeddingProvider

    api_key = os.environ.get("JINA_API_KEY")
    if not api_key:
        raise ValueError("JINA_API_KEY environment variable not set")

    provider = JinaEmbeddingProvider(api_key=api_key, dimensions=1024)
    embedding = await provider.embed_query(text)
    return embedding


async def test_store(store_name: str, store, embedding: list[float]) -> bool:
    """Test a vector store with upsert, search, and delete operations."""
    print(f"\n{'='*60}")
    print(f"Testing {store_name}")
    print("=" * 60)

    # Test data
    tenant_id = uuid4()
    agent_id = uuid4()
    doc_id = str(uuid4())
    collection = "test_collection"

    try:
        # 1. Ensure collection exists
        print("\n1. Creating collection...")
        await store.ensure_collection(
            collection=collection,
            dimensions=len(embedding),
            distance_metric="cosine",
        )
        print(f"   ✓ Collection '{collection}' ready")

        # 2. Upsert document
        print("\n2. Upserting document...")
        test_text = "Hello, this is a test document for vector storage."
        doc = VectorDocument(
            id=doc_id,
            vector=embedding,
            metadata=VectorMetadata(
                tenant_id=tenant_id,
                agent_id=agent_id,
                entity_type=EntityType.RULE,
                entity_id=uuid4(),
            ),
            text=test_text,
        )
        count = await store.upsert([doc], collection=collection)
        print(f"   ✓ Upserted {count} document(s)")

        # 3. Search and confirm document exists
        print("\n3. Searching for document...")
        results = await store.search(
            query_vector=embedding,
            tenant_id=tenant_id,
            agent_id=agent_id,
            collection=collection,
            limit=5,
            min_score=0.0,
        )
        print(f"   ✓ Found {len(results)} result(s)")

        if results:
            top_result = results[0]
            print(f"   ✓ Top result ID: {top_result.id}")
            print(f"   ✓ Top result score: {top_result.score:.4f}")
            print(f"   ✓ Entity type: {top_result.metadata.entity_type.value}")

            # Verify it's our document
            assert top_result.id == doc_id, "Document ID mismatch!"
            assert top_result.score > 0.99, "Score should be ~1.0 for same vector"
            print("   ✓ Document verified in store!")
        else:
            print("   ✗ No results found!")
            return False

        # 4. Delete document
        print("\n4. Deleting document...")
        deleted = await store.delete([doc_id], collection=collection)
        print(f"   ✓ Deleted {deleted} document(s)")

        # 5. Confirm deletion
        print("\n5. Confirming deletion...")
        results_after = await store.search(
            query_vector=embedding,
            tenant_id=tenant_id,
            agent_id=agent_id,
            collection=collection,
            limit=5,
            min_score=0.0,
        )
        if len(results_after) == 0:
            print("   ✓ Document successfully removed from store!")
        else:
            print(f"   ✗ Document still exists! Found {len(results_after)} results")
            return False

        print(f"\n✅ {store_name} test PASSED!")
        return True

    except Exception as e:
        print(f"\n❌ {store_name} test FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_inmemory(embedding: list[float]) -> bool:
    """Test InMemoryVectorStore."""
    store = InMemoryVectorStore(dimensions=len(embedding))
    return await test_store("InMemoryVectorStore", store, embedding)


async def test_qdrant(embedding: list[float]) -> bool:
    """Test QdrantVectorStore."""
    url = os.environ.get("QDRANT_URL")
    api_key = os.environ.get("QDRANT_API_KEY")

    if not url:
        print("\n⚠️  QDRANT_URL not set, skipping Qdrant test")
        return True

    store = QdrantVectorStore(
        url=url,
        api_key=api_key,
        collection_prefix="test_focal",
        timeout=30.0,
    )
    return await test_store("QdrantVectorStore", store, embedding)


async def test_pgvector(embedding: list[float]) -> bool:
    """Test PgVectorStore."""
    from focal.db.pool import PostgresPool
    from focal.vector.stores.pgvector import PgVectorStore

    dsn = os.environ.get("DATABASE_URL") or os.environ.get("FOCAL_DATABASE_URL")

    if not dsn:
        print("\n⚠️  DATABASE_URL not set, skipping pgvector test")
        return True

    pool = PostgresPool(dsn=dsn)
    try:
        await pool.connect()
        store = PgVectorStore(pool=pool, table_prefix="test_focal")
        result = await test_store("PgVectorStore", store, embedding)

        # Cleanup: drop the test table
        async with pool.acquire() as conn:
            await conn.execute("DROP TABLE IF EXISTS test_focal_test_collection_vectors")

        return result
    finally:
        await pool.close()


async def main():
    parser = argparse.ArgumentParser(description="Test vector stores with Jina embeddings")
    parser.add_argument("--inmemory", action="store_true", help="Test InMemoryVectorStore")
    parser.add_argument("--qdrant", action="store_true", help="Test QdrantVectorStore")
    parser.add_argument("--pgvector", action="store_true", help="Test PgVectorStore")
    parser.add_argument("--all", action="store_true", help="Test all stores")
    parser.add_argument(
        "--mock-embedding",
        action="store_true",
        help="Use mock embedding instead of Jina API",
    )
    args = parser.parse_args()

    # Default to all if nothing specified
    if not args.inmemory and not args.qdrant and not args.pgvector and not args.all:
        args.all = True

    # Get embedding
    print("=" * 60)
    print("Vector Store Test Script")
    print("=" * 60)

    test_text = "Hello, this is a test document for vector storage."

    if args.mock_embedding:
        print("\nUsing mock embedding (random vector)...")
        import random

        embedding = [random.random() for _ in range(1024)]
        # Normalize
        magnitude = sum(x * x for x in embedding) ** 0.5
        embedding = [x / magnitude for x in embedding]
    else:
        print(f"\nGenerating embedding for: '{test_text}'")
        print("Calling Jina API...")
        embedding = await get_jina_embedding(test_text)

    print(f"✓ Got embedding with {len(embedding)} dimensions")
    print(f"  First 5 values: {embedding[:5]}")

    # Run tests
    results = []

    if args.inmemory or args.all:
        results.append(("InMemory", await test_inmemory(embedding)))

    if args.qdrant or args.all:
        results.append(("Qdrant", await test_qdrant(embedding)))

    if args.pgvector or args.all:
        results.append(("PgVector", await test_pgvector(embedding)))

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    all_passed = True
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False

    print()
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
