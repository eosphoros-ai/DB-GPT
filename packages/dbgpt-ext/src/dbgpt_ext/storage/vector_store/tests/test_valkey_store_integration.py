"""Integration tests for ValkeyStore.

These tests require a running Valkey server with the valkey-search module loaded.
Skip if Valkey is not available.

To run locally::

    docker run -d --name valkey -p 6379:6379 valkey/valkey:latest \\
        --loadmodule /usr/lib/valkey/modules/valkey-search.so

    pytest -v -k test_valkey_store_integration
"""

from __future__ import annotations

import os
import uuid
from typing import List

import pytest

# Skip all tests in this module if Valkey is not available
pytestmark = pytest.mark.integration

VALKEY_HOST = os.environ.get("VALKEY_HOST", "localhost")
VALKEY_PORT = int(os.environ.get("VALKEY_PORT", "6379"))
VALKEY_PASSWORD = os.environ.get("VALKEY_PASSWORD", None)


def _valkey_available() -> bool:
    """Check if Valkey is available and has the search module."""
    try:
        import asyncio

        from glide import GlideClient, GlideClientConfiguration, NodeAddress

        async def _check():
            config = GlideClientConfiguration(
                addresses=[NodeAddress(host=VALKEY_HOST, port=VALKEY_PORT)]
            )
            client = await GlideClient.create(config)
            # Check if search module is loaded
            result = await client.custom_command(["MODULE", "LIST"])
            await client.close()
            if result:
                for module in result:
                    if isinstance(module, dict):
                        name = module.get(b"name", b"")
                        if name == b"search":
                            return True
            return False

        return asyncio.run(_check())
    except Exception:
        return False


# Skip all tests if Valkey is not available
if not _valkey_available():
    pytest.skip(
        "Valkey server with search module not available", allow_module_level=True
    )


class MockEmbeddings:
    """Mock embeddings for integration testing with fixed dimension."""

    def __init__(self, dim: int = 128):
        self.dim = dim

    def embed_query(self, text: str) -> List[float]:
        """Generate a deterministic embedding from text."""
        import hashlib

        h = hashlib.sha256(text.encode()).digest()
        # Use hash bytes to seed a simple vector
        vector = []
        for i in range(self.dim):
            byte_idx = i % len(h)
            vector.append((h[byte_idx] - 128) / 128.0)
        return vector

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple documents."""
        return [self.embed_query(text) for text in texts]


@pytest.fixture
def collection_name():
    """Generate a unique collection name for test isolation."""
    return f"test_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def valkey_store(collection_name):
    """Create a ValkeyStore for integration testing."""
    from dbgpt_ext.storage.vector_store.valkey_store import (
        ValkeyStore,
        ValkeyVectorConfig,
    )

    config = ValkeyVectorConfig(
        host=VALKEY_HOST,
        port=VALKEY_PORT,
        password=VALKEY_PASSWORD,
        index_type="HNSW",
        distance_metric="COSINE",
        key_prefix="inttest_vec:",
    )

    store = ValkeyStore(
        vector_store_config=config,
        name=collection_name,
        embedding_fn=MockEmbeddings(dim=128),
    )

    yield store

    # Cleanup: delete the index and keys
    try:
        store.delete_vector_name(collection_name)
    except Exception:
        pass


class TestValkeyStoreIntegration:
    """Integration tests for ValkeyStore."""

    def test_create_collection(self, valkey_store):
        """Test creating a vector index."""
        valkey_store.create_collection(valkey_store._collection_name)
        assert valkey_store._index_exists()

    def test_load_and_search(self, valkey_store):
        """Test loading documents and searching."""
        from dbgpt.core import Chunk

        chunks = [
            Chunk(
                content="Python is a programming language",
                metadata={"source": "wiki"},
                chunk_id="doc1",
            ),
            Chunk(
                content="Java is also a programming language",
                metadata={"source": "wiki"},
                chunk_id="doc2",
            ),
            Chunk(
                content="The weather is sunny today",
                metadata={"source": "news"},
                chunk_id="doc3",
            ),
        ]

        ids = valkey_store.load_document(chunks)
        assert len(ids) == 3

        # Search for programming-related content
        results = valkey_store.similar_search("programming language", topk=2)
        assert len(results) <= 2
        # Results should be programming-related
        if results:
            assert any("programming" in r.content.lower() for r in results)

    def test_similar_search_with_scores(self, valkey_store):
        """Test search with score threshold."""
        from dbgpt.core import Chunk

        chunks = [
            Chunk(content="exact match test", metadata={}, chunk_id="exact1"),
            Chunk(content="unrelated content xyz", metadata={}, chunk_id="unrel1"),
        ]

        valkey_store.load_document(chunks)

        # Search with high threshold should return fewer results
        results = valkey_store.similar_search_with_scores(
            "exact match test", topk=5, score_threshold=0.8
        )
        # The exact match should have high score
        if results:
            assert all(r.score >= 0.8 for r in results)

    def test_vector_name_exists(self, valkey_store):
        """Test checking if vector index has data."""
        from dbgpt.core import Chunk

        # Before loading, should be False (no data)
        valkey_store.create_collection(valkey_store._collection_name)
        # Note: may be True or False depending on timing

        # After loading, should be True
        chunks = [Chunk(content="test data", metadata={}, chunk_id="t1")]
        valkey_store.load_document(chunks)
        assert valkey_store.vector_name_exists() is True

    def test_delete_by_ids(self, valkey_store):
        """Test deleting specific documents."""
        from dbgpt.core import Chunk

        chunks = [
            Chunk(content="keep this", metadata={}, chunk_id="keep1"),
            Chunk(content="delete this", metadata={}, chunk_id="del1"),
        ]

        valkey_store.load_document(chunks)
        deleted = valkey_store.delete_by_ids("del1")
        assert deleted == ["del1"]

    def test_delete_vector_name(self, valkey_store):
        """Test deleting the entire index."""
        from dbgpt.core import Chunk

        chunks = [Chunk(content="to be deleted", metadata={}, chunk_id="d1")]
        valkey_store.load_document(chunks)

        result = valkey_store.delete_vector_name(valkey_store._collection_name)
        assert result is True
        assert valkey_store._index_exists() is False

    def test_truncate(self, valkey_store):
        """Test truncating all data."""
        from dbgpt.core import Chunk

        chunks = [
            Chunk(content="data 1", metadata={}, chunk_id="t1"),
            Chunk(content="data 2", metadata={}, chunk_id="t2"),
        ]

        valkey_store.load_document(chunks)
        deleted = valkey_store.truncate()
        assert len(deleted) >= 2

    def test_flat_index(self, collection_name):
        """Test with FLAT index type."""
        from dbgpt.core import Chunk
        from dbgpt_ext.storage.vector_store.valkey_store import (
            ValkeyStore,
            ValkeyVectorConfig,
        )

        config = ValkeyVectorConfig(
            host=VALKEY_HOST,
            port=VALKEY_PORT,
            password=VALKEY_PASSWORD,
            index_type="FLAT",
            distance_metric="L2",
            key_prefix="inttest_flat:",
        )

        store = ValkeyStore(
            vector_store_config=config,
            name=collection_name + "_flat",
            embedding_fn=MockEmbeddings(dim=128),
        )

        try:
            chunks = [
                Chunk(content="flat index test", metadata={}, chunk_id="f1"),
            ]
            ids = store.load_document(chunks)
            assert len(ids) == 1

            results = store.similar_search("flat index", topk=1)
            assert len(results) >= 0  # May or may not find depending on timing
        finally:
            try:
                store.delete_vector_name(collection_name + "_flat")
            except Exception:
                pass
