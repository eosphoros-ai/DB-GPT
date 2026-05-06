"""Unit tests for ValkeyStore.

These tests use mocked valkey-glide client and do not require a running Valkey server.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dbgpt.core import Chunk
from dbgpt.storage.vector_store.filters import (
    FilterCondition,
    FilterOperator,
    MetadataFilter,
    MetadataFilters,
)
from dbgpt_ext.storage.vector_store.valkey_store import (
    ValkeyStore,
    ValkeyVectorConfig,
    _escape_tag_value,
)


@pytest.fixture
def mock_embedding_fn():
    """Create a mock embedding function."""
    embedding = MagicMock()
    embedding.embed_query.return_value = [0.1, 0.2, 0.3, 0.4]
    embedding.embed_documents.return_value = [
        [0.1, 0.2, 0.3, 0.4],
        [0.5, 0.6, 0.7, 0.8],
    ]
    return embedding


@pytest.fixture
def valkey_config():
    """Create a ValkeyVectorConfig for testing."""
    return ValkeyVectorConfig(
        host="localhost",
        port=6379,
        password=None,
        db=0,
        use_ssl=False,
        index_type="HNSW",
        distance_metric="COSINE",
        key_prefix="test_vec:",
        hnsw_m=16,
        hnsw_ef_construction=200,
        hnsw_ef_runtime=10,
    )


@pytest.fixture
def mock_client():
    """Create a mock Valkey client."""
    client = AsyncMock()
    client.hset = AsyncMock(return_value=None)
    client.delete = AsyncMock(return_value=1)
    client.custom_command = AsyncMock(return_value=[b"0", []])
    return client


@pytest.fixture
def valkey_store(valkey_config, mock_embedding_fn, mock_client):
    """Create a ValkeyStore with mocked client."""
    with (
        patch.object(ValkeyStore, "_create_client", return_value=mock_client),
        patch.object(ValkeyStore, "_index_exists", return_value=True),
    ):
        store = ValkeyStore(
            vector_store_config=valkey_config,
            name="test_collection",
            embedding_fn=mock_embedding_fn,
        )
        store._client = mock_client
        return store


class TestValkeyVectorConfig:
    """Tests for ValkeyVectorConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ValkeyVectorConfig()
        assert config.host == "localhost"
        assert config.port == 6379
        assert config.index_type == "HNSW"
        assert config.distance_metric == "COSINE"
        assert config.hnsw_m == 16
        assert config.hnsw_ef_construction == 200
        assert config.hnsw_ef_runtime == 10

    def test_custom_config(self, valkey_config):
        """Test custom configuration values."""
        assert valkey_config.host == "localhost"
        assert valkey_config.port == 6379
        assert valkey_config.key_prefix == "test_vec:"
        assert valkey_config.index_type == "HNSW"
        assert valkey_config.distance_metric == "COSINE"

    def test_config_type(self, valkey_config):
        """Test that __type__ is set correctly."""
        assert valkey_config.__type__ == "valkey"

    def test_flat_index_config(self):
        """Test FLAT index type configuration."""
        config = ValkeyVectorConfig(index_type="FLAT")
        assert config.index_type == "FLAT"

    def test_distance_metrics(self):
        """Test different distance metric configurations."""
        for metric in ["COSINE", "L2", "IP"]:
            config = ValkeyVectorConfig(distance_metric=metric)
            assert config.distance_metric == metric

    def test_create_store(self, valkey_config, mock_embedding_fn, mock_client):
        """Test create_store factory method."""
        with (
            patch.object(ValkeyStore, "_create_client", return_value=mock_client),
            patch.object(ValkeyStore, "_index_exists", return_value=True),
        ):
            store = valkey_config.create_store(
                name="test", embedding_fn=mock_embedding_fn
            )
            assert store is not None
            assert store._collection_name == "test"


class TestValkeyStoreInit:
    """Tests for ValkeyStore initialization."""

    def test_init_without_embedding_raises(self, valkey_config):
        """Test that init without embedding_fn raises ValueError."""
        with pytest.raises(ValueError, match="embedding_fn is required"):
            ValkeyStore(vector_store_config=valkey_config, name="test")

    def test_init_sets_collection_name(self, valkey_store):
        """Test that collection name is set correctly."""
        assert valkey_store._collection_name == "test_collection"

    def test_init_sets_index_name(self, valkey_store):
        """Test that index name is derived from collection name."""
        assert valkey_store._index_name == "idx:test_collection"

    def test_init_sets_key_prefix(self, valkey_store):
        """Test that key prefix includes collection name."""
        assert valkey_store._key_prefix == "test_vec:test_collection:"

    def test_get_config(self, valkey_store, valkey_config):
        """Test get_config returns the config."""
        assert valkey_store.get_config() == valkey_config


class TestValkeyStoreLoadDocument:
    """Tests for document loading."""

    def test_load_document(self, valkey_store):
        """Test loading documents into Valkey."""
        chunks = [
            Chunk(content="Hello world", metadata={"source": "test"}, chunk_id="c1"),
            Chunk(content="Foo bar", metadata={"source": "test2"}, chunk_id="c2"),
        ]

        calls = []

        def track_run_async(coro):
            calls.append(coro)
            return None

        with patch.object(valkey_store, "create_collection"):
            valkey_store._run_async = track_run_async
            result = valkey_store.load_document(chunks)

        assert result == ["c1", "c2"]
        assert len(calls) == 2  # Two hset calls

    def test_load_document_empty(self, valkey_store):
        """Test loading empty document list."""
        with patch.object(valkey_store, "create_collection"):
            result = valkey_store.load_document([])
            assert result == []


class TestValkeyStoreSearch:
    """Tests for search operations."""

    def test_similar_search(self, valkey_store):
        """Test similar_search delegates to _search."""
        mock_chunks = [Chunk(content="result", score=0.9, chunk_id="c1")]
        with patch.object(valkey_store, "_search", return_value=mock_chunks):
            result = valkey_store.similar_search("query text", topk=5)
            assert result == mock_chunks

    def test_similar_search_with_scores(self, valkey_store):
        """Test similar_search_with_scores applies threshold."""
        mock_chunks = [
            Chunk(content="high score", score=0.9, chunk_id="c1"),
            Chunk(content="low score", score=0.3, chunk_id="c2"),
        ]

        with patch.object(valkey_store, "_search", return_value=mock_chunks):
            result = valkey_store.similar_search_with_scores(
                "query", topk=5, score_threshold=0.5
            )
            assert len(result) == 1
            assert result[0].content == "high score"

    def test_search_with_no_results(self, valkey_store):
        """Test search returning empty results."""
        with patch.object(valkey_store, "_search", return_value=[]):
            result = valkey_store.similar_search("query", topk=5)
            assert result == []


class TestValkeyStoreDelete:
    """Tests for delete operations."""

    def test_delete_by_ids(self, valkey_store):
        """Test deleting vectors by IDs."""
        with patch.object(valkey_store, "_run_async", return_value=1):
            result = valkey_store.delete_by_ids("c1, c2, c3")
        assert result == ["c1", "c2", "c3"]

    def test_delete_by_ids_single(self, valkey_store):
        """Test deleting a single vector by ID."""
        with patch.object(valkey_store, "_run_async", return_value=1):
            result = valkey_store.delete_by_ids("c1")
        assert result == ["c1"]

    def test_delete_vector_name(self, valkey_store):
        """Test deleting the entire vector index."""
        with (
            patch.object(valkey_store, "_run_async", return_value=None),
            patch.object(
                valkey_store, "_delete_keys_with_prefix", return_value=["k1", "k2"]
            ),
        ):
            result = valkey_store.delete_vector_name("test_collection")
            assert result is True

    def test_truncate(self, valkey_store):
        """Test truncating all data."""
        with patch.object(
            valkey_store,
            "_delete_keys_with_prefix",
            return_value=["test_vec:test_collection:c1", "test_vec:test_collection:c2"],
        ):
            result = valkey_store.truncate()
            assert len(result) == 2


class TestValkeyStoreVectorNameExists:
    """Tests for vector_name_exists."""

    def test_vector_name_exists_true(self, valkey_store):
        """Test vector_name_exists when index has data."""
        with (
            patch.object(valkey_store, "_index_exists", return_value=True),
            patch.object(
                valkey_store, "_run_async", return_value={b"num_docs": b"5"}
            ),
        ):
            assert valkey_store.vector_name_exists() is True

    def test_vector_name_exists_false_no_index(self, valkey_store):
        """Test vector_name_exists when index doesn't exist."""
        with patch.object(valkey_store, "_index_exists", return_value=False):
            assert valkey_store.vector_name_exists() is False

    def test_vector_name_exists_false_empty(self, valkey_store):
        """Test vector_name_exists when index exists but has no data."""
        with (
            patch.object(valkey_store, "_index_exists", return_value=True),
            patch.object(
                valkey_store, "_run_async", return_value={b"num_docs": b"0"}
            ),
        ):
            assert valkey_store.vector_name_exists() is False


class TestValkeyStoreFilters:
    """Tests for metadata filter conversion."""

    def test_no_filters(self, valkey_store):
        """Test that no filters returns wildcard."""
        result = valkey_store._build_filter_expression(None)
        assert result == "*"

    def test_empty_filters(self, valkey_store):
        """Test that empty filter list returns wildcard."""
        filters = MetadataFilters(filters=[])
        result = valkey_store._build_filter_expression(filters)
        assert result == "*"

    def test_eq_string_filter(self, valkey_store):
        """Test equality filter for string values."""
        filters = MetadataFilters(
            filters=[
                MetadataFilter(key="source", operator=FilterOperator.EQ, value="web")
            ]
        )
        result = valkey_store._build_filter_expression(filters)
        assert "@source:{web}" in result

    def test_eq_numeric_filter(self, valkey_store):
        """Test equality filter for numeric values."""
        filters = MetadataFilters(
            filters=[MetadataFilter(key="page", operator=FilterOperator.EQ, value=5)]
        )
        result = valkey_store._build_filter_expression(filters)
        assert "@page:[5 5]" in result

    def test_gt_filter(self, valkey_store):
        """Test greater-than filter."""
        filters = MetadataFilters(
            filters=[MetadataFilter(key="score", operator=FilterOperator.GT, value=0.5)]
        )
        result = valkey_store._build_filter_expression(filters)
        assert "@score:[(0.5 +inf]" in result

    def test_lt_filter(self, valkey_store):
        """Test less-than filter."""
        filters = MetadataFilters(
            filters=[MetadataFilter(key="score", operator=FilterOperator.LT, value=0.8)]
        )
        result = valkey_store._build_filter_expression(filters)
        assert "@score:[-inf (0.8]" in result

    def test_in_filter(self, valkey_store):
        """Test IN filter."""
        filters = MetadataFilters(
            filters=[
                MetadataFilter(
                    key="category", operator=FilterOperator.IN, value=["a", "b", "c"]
                )
            ]
        )
        result = valkey_store._build_filter_expression(filters)
        assert "@category:{a|b|c}" in result

    def test_ne_filter(self, valkey_store):
        """Test not-equal filter."""
        filters = MetadataFilters(
            filters=[
                MetadataFilter(key="status", operator=FilterOperator.NE, value="draft")
            ]
        )
        result = valkey_store._build_filter_expression(filters)
        assert "-@status:{draft}" in result

    def test_and_condition(self, valkey_store):
        """Test AND condition with multiple filters."""
        filters = MetadataFilters(
            condition=FilterCondition.AND,
            filters=[
                MetadataFilter(key="source", operator=FilterOperator.EQ, value="web"),
                MetadataFilter(key="page", operator=FilterOperator.GT, value=1),
            ],
        )
        result = valkey_store._build_filter_expression(filters)
        assert "@source:{web}" in result
        assert "@page:[(1 +inf]" in result

    def test_or_condition(self, valkey_store):
        """Test OR condition with multiple filters."""
        filters = MetadataFilters(
            condition=FilterCondition.OR,
            filters=[
                MetadataFilter(key="source", operator=FilterOperator.EQ, value="web"),
                MetadataFilter(key="source", operator=FilterOperator.EQ, value="pdf"),
            ],
        )
        result = valkey_store._build_filter_expression(filters)
        assert " | " in result


class TestValkeyStoreParseResults:
    """Tests for search result parsing."""

    def test_parse_empty_results(self, valkey_store):
        """Test parsing empty search results."""
        assert valkey_store._parse_search_results(None) == []
        assert valkey_store._parse_search_results([]) == []

    def test_parse_structured_results(self, valkey_store):
        """Test parsing structured results with .results attribute."""
        mock_doc = MagicMock(spec=[])
        mock_doc.fields = {
            "content": "test content",
            "metadata": '{"source": "test"}',
            "chunk_id": "c1",
            "score": "0.1",
        }

        mock_result = MagicMock(spec=[])
        mock_result.results = [mock_doc]

        chunks = valkey_store._parse_search_results(mock_result)
        assert len(chunks) == 1
        assert chunks[0].content == "test content"
        assert chunks[0].chunk_id == "c1"
        assert chunks[0].score == 0.9  # 1.0 - 0.1 distance

    def test_doc_to_chunk_with_bytes(self, valkey_store):
        """Test parsing document with bytes values."""
        doc = {
            "content": b"byte content",
            "metadata": b'{"key": "val"}',
            "chunk_id": b"c1",
            "score": b"0.2",
        }
        chunk = valkey_store._doc_to_chunk(doc)
        assert chunk is not None
        assert chunk.content == "byte content"
        assert chunk.metadata == {"key": "val"}
        assert chunk.chunk_id == "c1"
        assert chunk.score == pytest.approx(0.8)

    def test_doc_to_chunk_with_strings(self, valkey_store):
        """Test parsing document with string values."""
        doc = {
            "content": "string content",
            "metadata": '{"key": "val"}',
            "chunk_id": "c2",
            "score": "0.0",
        }
        chunk = valkey_store._doc_to_chunk(doc)
        assert chunk is not None
        assert chunk.content == "string content"
        assert chunk.score == pytest.approx(1.0)


class TestEscapeTagValue:
    """Tests for tag value escaping."""

    def test_simple_value(self):
        """Test that simple values pass through."""
        assert _escape_tag_value("hello") == "hello"

    def test_special_chars(self):
        """Test that special characters are escaped."""
        assert _escape_tag_value("hello world") == "hello\\ world"

    def test_multiple_special_chars(self):
        """Test escaping multiple special characters."""
        assert _escape_tag_value("a.b,c") == "a\\.b\\,c"


class TestValkeyStoreIndexSchema:
    """Tests for index schema building."""

    def test_hnsw_config_values(self, valkey_config):
        """Test HNSW index configuration values."""
        assert valkey_config.index_type == "HNSW"
        assert valkey_config.distance_metric == "COSINE"
        assert valkey_config.hnsw_m == 16
        assert valkey_config.hnsw_ef_construction == 200
        assert valkey_config.hnsw_ef_runtime == 10

    def test_flat_config_values(self):
        """Test FLAT index type configuration."""
        flat_config = ValkeyVectorConfig(index_type="FLAT", distance_metric="L2")
        assert flat_config.index_type == "FLAT"
        assert flat_config.distance_metric == "L2"
