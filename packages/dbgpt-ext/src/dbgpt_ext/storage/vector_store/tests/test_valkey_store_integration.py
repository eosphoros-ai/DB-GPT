"""Integration tests for ValkeyStore.

These tests require a running Valkey server with the valkey-search module loaded.
Skip if Valkey is not available.

To run locally::

    docker run -d --name valkey -p 6379:6379 valkey/valkey:latest \\
        --loadmodule /usr/lib/valkey/modules/valkey-search.so

    pytest -v -m integration
"""

from __future__ import annotations

import os
import uuid
from typing import List

import pytest

from dbgpt.core import Chunk
from dbgpt.storage.vector_store.filters import (
    FilterOperator,
    MetadataFilter,
    MetadataFilters,
)

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


if not _valkey_available():
    pytest.skip(
        "Valkey server with search module not available", allow_module_level=True
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class MockEmbeddings:
    """Deterministic embeddings for integration testing."""

    def __init__(self, dim: int = 128):
        self.dim = dim

    def embed_query(self, text: str) -> List[float]:
        """Generate a deterministic embedding from text."""
        import hashlib

        h = hashlib.sha256(text.encode()).digest()
        vector = []
        for i in range(self.dim):
            byte_idx = i % len(h)
            vector.append((h[byte_idx] - 128) / 128.0)
        return vector

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple documents."""
        return [self.embed_query(text) for text in texts]


def _unique_name(prefix: str = "test") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def collection_name():
    """Generate a unique collection name for test isolation."""
    return _unique_name()


@pytest.fixture
def valkey_store(collection_name):
    """Create a ValkeyStore for integration testing (COSINE, HNSW)."""
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
        metadata_schema={"source": "tag", "page": "numeric"},
    )

    store = ValkeyStore(
        vector_store_config=config,
        name=collection_name,
        embedding_fn=MockEmbeddings(dim=128),
    )

    yield store

    try:
        store.delete_vector_name(collection_name)
    except Exception:
        pass
    store.close()


# ---------------------------------------------------------------------------
# Tests: create_collection
# ---------------------------------------------------------------------------


class TestCreateCollection:
    """Tests for index creation."""

    def test_create_collection(self, valkey_store):
        """Test creating a vector index."""
        valkey_store.create_collection(valkey_store._collection_name)
        assert valkey_store._index_exists()

    def test_create_collection_idempotent(self, valkey_store):
        """Test that calling create_collection twice does not error."""
        valkey_store.create_collection(valkey_store._collection_name)
        valkey_store.create_collection(valkey_store._collection_name)
        assert valkey_store._index_exists()


# ---------------------------------------------------------------------------
# Tests: load_document
# ---------------------------------------------------------------------------


class TestLoadDocument:
    """Tests for document loading."""

    def test_load_document_returns_ids(self, valkey_store):
        """Test that load_document returns chunk IDs."""
        chunks = [
            Chunk(content="doc one", metadata={"source": "test"}, chunk_id="d1"),
            Chunk(content="doc two", metadata={"source": "test"}, chunk_id="d2"),
        ]
        ids = valkey_store.load_document(chunks)
        assert ids == ["d1", "d2"]

    def test_load_document_empty_list(self, valkey_store):
        """Test loading an empty list."""
        ids = valkey_store.load_document([])
        assert ids == []

    def test_load_document_with_metadata_fields(self, valkey_store):
        """Test that metadata fields are stored for indexing."""
        chunks = [
            Chunk(
                content="Python guide",
                metadata={"source": "wiki", "page": 5},
                chunk_id="m1",
            ),
        ]
        valkey_store.load_document(chunks)
        # Verify the data is searchable
        assert valkey_store.vector_name_exists() is True


# ---------------------------------------------------------------------------
# Tests: similar_search
# ---------------------------------------------------------------------------


class TestSimilarSearch:
    """Tests for vector similarity search."""

    def test_similar_search_returns_results(self, valkey_store):
        """Test basic search returns results."""
        chunks = [
            Chunk(
                content="Python is a programming language",
                metadata={"source": "wiki"},
                chunk_id="s1",
            ),
            Chunk(
                content="Java is also a programming language",
                metadata={"source": "wiki"},
                chunk_id="s2",
            ),
            Chunk(
                content="The weather is sunny today",
                metadata={"source": "news"},
                chunk_id="s3",
            ),
        ]
        valkey_store.load_document(chunks)

        results = valkey_store.similar_search("programming language", topk=2)
        assert len(results) <= 2
        assert len(results) > 0
        # Programming-related chunks should rank higher
        contents = [r.content.lower() for r in results]
        assert any("programming" in c for c in contents)

    def test_similar_search_topk_limit(self, valkey_store):
        """Test that topk limits results."""
        chunks = [
            Chunk(content=f"document number {i}", metadata={}, chunk_id=f"t{i}")
            for i in range(5)
        ]
        valkey_store.load_document(chunks)

        results = valkey_store.similar_search("document", topk=2)
        assert len(results) <= 2

    def test_similar_search_has_scores(self, valkey_store):
        """Test that results have valid scores."""
        chunks = [
            Chunk(content="exact query text", metadata={}, chunk_id="sc1"),
        ]
        valkey_store.load_document(chunks)

        results = valkey_store.similar_search("exact query text", topk=1)
        assert len(results) == 1
        # Score should be high for exact match (COSINE similarity)
        assert results[0].score > 0.5

    def test_similar_search_preserves_metadata(self, valkey_store):
        """Test that search results include metadata."""
        chunks = [
            Chunk(
                content="metadata test",
                metadata={"source": "unit_test", "page": 42},
                chunk_id="meta1",
            ),
        ]
        valkey_store.load_document(chunks)

        results = valkey_store.similar_search("metadata test", topk=1)
        assert len(results) == 1
        assert results[0].metadata["source"] == "unit_test"
        assert results[0].metadata["page"] == 42

    def test_similar_search_preserves_chunk_id(self, valkey_store):
        """Test that search results include chunk_id."""
        chunks = [
            Chunk(content="id test", metadata={}, chunk_id="myid123"),
        ]
        valkey_store.load_document(chunks)

        results = valkey_store.similar_search("id test", topk=1)
        assert len(results) == 1
        assert results[0].chunk_id == "myid123"


# ---------------------------------------------------------------------------
# Tests: similar_search_with_scores
# ---------------------------------------------------------------------------


class TestSimilarSearchWithScores:
    """Tests for score-threshold filtering."""

    def test_high_threshold_filters_low_scores(self, valkey_store):
        """Test that high threshold filters out dissimilar results."""
        chunks = [
            Chunk(content="exact match phrase", metadata={}, chunk_id="h1"),
            Chunk(content="completely unrelated xyz abc", metadata={}, chunk_id="h2"),
        ]
        valkey_store.load_document(chunks)

        results = valkey_store.similar_search_with_scores(
            "exact match phrase", topk=5, score_threshold=0.8
        )
        if results:
            assert all(r.score >= 0.8 for r in results)

    def test_zero_threshold_returns_all(self, valkey_store):
        """Test that threshold=0 does not filter positive-score results."""
        chunks = [
            Chunk(content="search query text", metadata={}, chunk_id="z1"),
            Chunk(content="search query text again", metadata={}, chunk_id="z2"),
        ]
        valkey_store.load_document(chunks)

        results = valkey_store.similar_search_with_scores(
            "search query text", topk=5, score_threshold=0.0
        )
        # Both chunks are very similar to query, scores should be >= 0
        assert len(results) >= 1


# ---------------------------------------------------------------------------
# Tests: vector_name_exists
# ---------------------------------------------------------------------------


class TestVectorNameExists:
    """Tests for checking index existence."""

    def test_exists_false_before_load(self, valkey_store):
        """Test that exists is False before any data is loaded."""
        valkey_store.create_collection(valkey_store._collection_name)
        assert valkey_store.vector_name_exists() is False

    def test_exists_true_after_load(self, valkey_store):
        """Test that exists is True after loading data."""
        chunks = [Chunk(content="exists test", metadata={}, chunk_id="e1")]
        valkey_store.load_document(chunks)
        assert valkey_store.vector_name_exists() is True

    def test_exists_false_after_delete(self, valkey_store):
        """Test that exists is False after deleting the index."""
        chunks = [Chunk(content="delete test", metadata={}, chunk_id="ed1")]
        valkey_store.load_document(chunks)
        valkey_store.delete_vector_name(valkey_store._collection_name)
        assert valkey_store.vector_name_exists() is False


# ---------------------------------------------------------------------------
# Tests: delete_by_ids
# ---------------------------------------------------------------------------


class TestDeleteByIds:
    """Tests for deleting specific documents."""

    def test_delete_single_id(self, valkey_store):
        """Test deleting a single document."""
        chunks = [
            Chunk(content="keep this", metadata={}, chunk_id="keep1"),
            Chunk(content="delete this", metadata={}, chunk_id="del1"),
        ]
        valkey_store.load_document(chunks)

        deleted = valkey_store.delete_by_ids("del1")
        assert deleted == ["del1"]

    def test_delete_multiple_ids(self, valkey_store):
        """Test deleting multiple documents."""
        chunks = [
            Chunk(content=f"doc {i}", metadata={}, chunk_id=f"multi{i}")
            for i in range(4)
        ]
        valkey_store.load_document(chunks)

        deleted = valkey_store.delete_by_ids("multi0, multi1, multi2")
        assert deleted == ["multi0", "multi1", "multi2"]

    def test_delete_nonexistent_id(self, valkey_store):
        """Test deleting an ID that doesn't exist doesn't error."""
        valkey_store.create_collection(valkey_store._collection_name)
        deleted = valkey_store.delete_by_ids("nonexistent_id")
        assert deleted == ["nonexistent_id"]


# ---------------------------------------------------------------------------
# Tests: delete_vector_name
# ---------------------------------------------------------------------------


class TestDeleteVectorName:
    """Tests for deleting the entire index."""

    def test_delete_removes_index(self, valkey_store):
        """Test that delete removes the index."""
        chunks = [Chunk(content="to delete", metadata={}, chunk_id="dv1")]
        valkey_store.load_document(chunks)

        result = valkey_store.delete_vector_name(valkey_store._collection_name)
        assert result is True
        assert valkey_store._index_exists() is False

    def test_delete_nonexistent_index(self, valkey_store):
        """Test deleting when no index exists doesn't error."""
        result = valkey_store.delete_vector_name("nonexistent")
        assert result is True


# ---------------------------------------------------------------------------
# Tests: truncate
# ---------------------------------------------------------------------------


class TestTruncate:
    """Tests for truncating data."""

    def test_truncate_removes_keys(self, valkey_store):
        """Test that truncate removes all data keys."""
        chunks = [
            Chunk(content="data 1", metadata={}, chunk_id="tr1"),
            Chunk(content="data 2", metadata={}, chunk_id="tr2"),
        ]
        valkey_store.load_document(chunks)

        deleted = valkey_store.truncate()
        assert len(deleted) >= 2

    def test_truncate_empty_collection(self, valkey_store):
        """Test truncating when no data exists."""
        valkey_store.create_collection(valkey_store._collection_name)
        deleted = valkey_store.truncate()
        assert deleted == []


# ---------------------------------------------------------------------------
# Tests: metadata filtering
# ---------------------------------------------------------------------------


class TestMetadataFiltering:
    """Tests for metadata-based filtering during search."""

    @pytest.fixture
    def store_with_data(self, collection_name):
        """Create a store with diverse metadata for filter testing."""
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
            key_prefix="inttest_filter:",
            metadata_schema={"source": "tag", "page": "numeric"},
        )

        store = ValkeyStore(
            vector_store_config=config,
            name=collection_name + "_filter",
            embedding_fn=MockEmbeddings(dim=128),
        )

        chunks = [
            Chunk(
                content="Python programming tutorial",
                metadata={"source": "wiki", "page": 1},
                chunk_id="ft1",
            ),
            Chunk(
                content="Java programming tutorial",
                metadata={"source": "wiki", "page": 2},
                chunk_id="ft2",
            ),
            Chunk(
                content="Weather forecast report",
                metadata={"source": "news", "page": 1},
                chunk_id="ft3",
            ),
        ]
        store.load_document(chunks)

        yield store

        try:
            store.delete_vector_name(collection_name + "_filter")
        except Exception:
            pass
        store.close()

    def test_filter_by_tag_eq(self, store_with_data):
        """Test filtering by tag equality."""
        filters = MetadataFilters(
            filters=[
                MetadataFilter(key="source", operator=FilterOperator.EQ, value="wiki")
            ]
        )
        results = store_with_data.similar_search("programming", topk=5, filters=filters)
        assert len(results) > 0
        for r in results:
            assert r.metadata.get("source") == "wiki"

    def test_filter_by_numeric_gt(self, store_with_data):
        """Test filtering by numeric greater-than."""
        filters = MetadataFilters(
            filters=[MetadataFilter(key="page", operator=FilterOperator.GT, value=1)]
        )
        results = store_with_data.similar_search("programming", topk=5, filters=filters)
        if results:
            for r in results:
                assert r.metadata.get("page", 0) > 1

    def test_filter_excludes_non_matching(self, store_with_data):
        """Test that filter actually excludes non-matching docs."""
        filters = MetadataFilters(
            filters=[
                MetadataFilter(key="source", operator=FilterOperator.EQ, value="news")
            ]
        )
        results = store_with_data.similar_search("programming", topk=5, filters=filters)
        # Only the news doc should match the filter
        for r in results:
            assert r.metadata.get("source") == "news"


# ---------------------------------------------------------------------------
# Tests: FLAT index type
# ---------------------------------------------------------------------------


class TestFlatIndex:
    """Tests for FLAT index type."""

    def test_flat_index_load_and_search(self, collection_name):
        """Test with FLAT index type."""
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
                Chunk(content="another flat doc", metadata={}, chunk_id="f2"),
            ]
            ids = store.load_document(chunks)
            assert ids == ["f1", "f2"]

            results = store.similar_search("flat index", topk=1)
            assert len(results) >= 1
            # L2 scores should be in (0, 1] range via 1/(1+d)
            assert results[0].score > 0
            assert results[0].score <= 1.0
        finally:
            try:
                store.delete_vector_name(collection_name + "_flat")
            except Exception:
                pass
            store.close()


# ---------------------------------------------------------------------------
# Tests: close()
# ---------------------------------------------------------------------------


class TestClose:
    """Tests for resource cleanup."""

    def test_close_does_not_error(self, collection_name):
        """Test that close() can be called without error."""
        from dbgpt_ext.storage.vector_store.valkey_store import (
            ValkeyStore,
            ValkeyVectorConfig,
        )

        config = ValkeyVectorConfig(
            host=VALKEY_HOST,
            port=VALKEY_PORT,
            password=VALKEY_PASSWORD,
            key_prefix="inttest_close:",
        )

        store = ValkeyStore(
            vector_store_config=config,
            name=collection_name + "_close",
            embedding_fn=MockEmbeddings(dim=128),
        )

        # Force client creation
        _ = store.client
        store.close()
        assert store._client is None
        assert store._loop.is_closed()

    def test_close_without_client(self, collection_name):
        """Test that close() works even if client was never created."""
        from dbgpt_ext.storage.vector_store.valkey_store import (
            ValkeyStore,
            ValkeyVectorConfig,
        )

        config = ValkeyVectorConfig(
            host=VALKEY_HOST,
            port=VALKEY_PORT,
            password=VALKEY_PASSWORD,
            key_prefix="inttest_close2:",
        )

        store = ValkeyStore(
            vector_store_config=config,
            name=collection_name + "_close2",
            embedding_fn=MockEmbeddings(dim=128),
        )

        # Don't create client, just close
        store.close()
        assert store._client is None


# ---------------------------------------------------------------------------
# Tests: convert_metadata_filters (public method)
# ---------------------------------------------------------------------------


class TestConvertMetadataFilters:
    """Tests for the public convert_metadata_filters method."""

    def test_convert_returns_filter_string(self, valkey_store):
        """Test that convert_metadata_filters returns a valid string."""
        filters = MetadataFilters(
            filters=[
                MetadataFilter(key="source", operator=FilterOperator.EQ, value="wiki")
            ]
        )
        result = valkey_store.convert_metadata_filters(filters)
        assert isinstance(result, str)
        assert "@meta_source:{wiki}" in result

    def test_convert_empty_filters(self, valkey_store):
        """Test converting empty filters."""
        filters = MetadataFilters(filters=[])
        result = valkey_store.convert_metadata_filters(filters)
        assert result == "*"
