"""Unit tests for ValkeyStore.

These tests cover pure logic that does not require a running Valkey server
or heavy mocking. Integration tests cover actual Valkey operations.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

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

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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
        use_ssl=False,
        index_type="HNSW",
        distance_metric="COSINE",
        key_prefix="test_vec:",
        hnsw_m=16,
        hnsw_ef_construction=200,
        hnsw_ef_runtime=10,
        metadata_schema={
            "source": "tag",
            "page": "numeric",
            "score": "numeric",
            "category": "tag",
            "status": "tag",
        },
    )


@pytest.fixture
def valkey_store(valkey_config, mock_embedding_fn):
    """Create a ValkeyStore with mocked client for pure logic tests."""
    mock_client = MagicMock()
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


# ---------------------------------------------------------------------------
# ValkeyVectorConfig tests (pure dataclass logic)
# ---------------------------------------------------------------------------


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
        assert config.metadata_schema is None

    def test_custom_config(self, valkey_config):
        """Test custom configuration values."""
        assert valkey_config.host == "localhost"
        assert valkey_config.port == 6379
        assert valkey_config.key_prefix == "test_vec:"
        assert valkey_config.index_type == "HNSW"
        assert valkey_config.distance_metric == "COSINE"
        assert valkey_config.metadata_schema == {
            "source": "tag",
            "page": "numeric",
            "score": "numeric",
            "category": "tag",
            "status": "tag",
        }

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


# ---------------------------------------------------------------------------
# Store initialization tests (pure validation logic)
# ---------------------------------------------------------------------------


class TestValkeyStoreInit:
    """Tests for ValkeyStore initialization logic."""

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

    def test_init_default_collection_name(self, valkey_config, mock_embedding_fn):
        """Test default collection name when none is provided."""
        mock_client = MagicMock()
        with (
            patch.object(ValkeyStore, "_create_client", return_value=mock_client),
            patch.object(ValkeyStore, "_index_exists", return_value=True),
        ):
            store = ValkeyStore(
                vector_store_config=valkey_config,
                embedding_fn=mock_embedding_fn,
            )
            assert store._collection_name == "dbgpt_collection"

    def test_get_config(self, valkey_store, valkey_config):
        """Test get_config returns the config."""
        assert valkey_store.get_config() == valkey_config


# ---------------------------------------------------------------------------
# Filter expression building (pure string logic)
# ---------------------------------------------------------------------------


class TestValkeyStoreFilters:
    """Tests for metadata filter conversion — pure logic, no I/O."""

    def test_no_filters(self, valkey_store):
        """Test that no filters returns wildcard."""
        assert valkey_store._build_filter_expression(None) == "*"

    def test_empty_filters(self, valkey_store):
        """Test that empty filter list returns wildcard."""
        filters = MetadataFilters(filters=[])
        assert valkey_store._build_filter_expression(filters) == "*"

    def test_eq_string_filter(self, valkey_store):
        """Test equality filter for string values."""
        filters = MetadataFilters(
            filters=[
                MetadataFilter(key="source", operator=FilterOperator.EQ, value="web")
            ]
        )
        result = valkey_store._build_filter_expression(filters)
        assert "@meta_source:{web}" in result

    def test_eq_numeric_filter(self, valkey_store):
        """Test equality filter for numeric values."""
        filters = MetadataFilters(
            filters=[MetadataFilter(key="page", operator=FilterOperator.EQ, value=5)]
        )
        result = valkey_store._build_filter_expression(filters)
        assert "@meta_page:[5 5]" in result

    def test_gt_filter(self, valkey_store):
        """Test greater-than filter."""
        filters = MetadataFilters(
            filters=[MetadataFilter(key="score", operator=FilterOperator.GT, value=0.5)]
        )
        result = valkey_store._build_filter_expression(filters)
        assert "@meta_score:[(0.5 +inf]" in result

    def test_gte_filter(self, valkey_store):
        """Test greater-than-or-equal filter."""
        filters = MetadataFilters(
            filters=[
                MetadataFilter(key="score", operator=FilterOperator.GTE, value=0.5)
            ]
        )
        result = valkey_store._build_filter_expression(filters)
        assert "@meta_score:[0.5 +inf]" in result

    def test_lt_filter(self, valkey_store):
        """Test less-than filter."""
        filters = MetadataFilters(
            filters=[MetadataFilter(key="score", operator=FilterOperator.LT, value=0.8)]
        )
        result = valkey_store._build_filter_expression(filters)
        assert "@meta_score:[-inf (0.8]" in result

    def test_lte_filter(self, valkey_store):
        """Test less-than-or-equal filter."""
        filters = MetadataFilters(
            filters=[
                MetadataFilter(key="score", operator=FilterOperator.LTE, value=0.8)
            ]
        )
        result = valkey_store._build_filter_expression(filters)
        assert "@meta_score:[-inf 0.8]" in result

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
        assert "@meta_category:{a|b|c}" in result

    def test_nin_filter(self, valkey_store):
        """Test NOT IN filter."""
        filters = MetadataFilters(
            filters=[
                MetadataFilter(
                    key="category", operator=FilterOperator.NIN, value=["x", "y"]
                )
            ]
        )
        result = valkey_store._build_filter_expression(filters)
        assert "-@meta_category:{x|y}" in result

    def test_ne_string_filter(self, valkey_store):
        """Test not-equal filter for strings."""
        filters = MetadataFilters(
            filters=[
                MetadataFilter(key="status", operator=FilterOperator.NE, value="draft")
            ]
        )
        result = valkey_store._build_filter_expression(filters)
        assert "-@meta_status:{draft}" in result

    def test_ne_numeric_filter(self, valkey_store):
        """Test not-equal filter for numeric values."""
        filters = MetadataFilters(
            filters=[MetadataFilter(key="page", operator=FilterOperator.NE, value=3)]
        )
        result = valkey_store._build_filter_expression(filters)
        assert "-@meta_page:[3 3]" in result

    def test_and_condition(self, valkey_store):
        """Test AND condition joins with space."""
        filters = MetadataFilters(
            condition=FilterCondition.AND,
            filters=[
                MetadataFilter(key="source", operator=FilterOperator.EQ, value="web"),
                MetadataFilter(key="page", operator=FilterOperator.GT, value=1),
            ],
        )
        result = valkey_store._build_filter_expression(filters)
        assert "@meta_source:{web}" in result
        assert "@meta_page:[(1 +inf]" in result
        # AND uses space separator
        assert " | " not in result

    def test_or_condition(self, valkey_store):
        """Test OR condition joins with pipe."""
        filters = MetadataFilters(
            condition=FilterCondition.OR,
            filters=[
                MetadataFilter(key="source", operator=FilterOperator.EQ, value="web"),
                MetadataFilter(key="source", operator=FilterOperator.EQ, value="pdf"),
            ],
        )
        result = valkey_store._build_filter_expression(filters)
        assert " | " in result

    def test_filters_without_metadata_schema(self, mock_embedding_fn):
        """Test that filters raise ValueError when no metadata_schema is set."""
        config = ValkeyVectorConfig(key_prefix="test_vec:", metadata_schema=None)
        mock_client = MagicMock()
        with (
            patch.object(ValkeyStore, "_create_client", return_value=mock_client),
            patch.object(ValkeyStore, "_index_exists", return_value=True),
        ):
            store = ValkeyStore(
                vector_store_config=config,
                name="test_no_schema",
                embedding_fn=mock_embedding_fn,
            )
            store._client = mock_client

        filters = MetadataFilters(
            filters=[
                MetadataFilter(key="source", operator=FilterOperator.EQ, value="web")
            ]
        )
        with pytest.raises(ValueError, match="no metadata_schema configured"):
            store._build_filter_expression(filters)


# ---------------------------------------------------------------------------
# Result parsing (pure logic)
# ---------------------------------------------------------------------------


class TestValkeyStoreParseResults:
    """Tests for search result parsing — pure logic, no I/O."""

    def test_parse_empty_results(self, valkey_store):
        """Test parsing None and empty list."""
        assert valkey_store._parse_search_results(None) == []
        assert valkey_store._parse_search_results([]) == []

    def test_parse_structured_results(self, valkey_store):
        """Test parsing results with .results attribute (newer glide)."""
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
        assert chunks[0].score == pytest.approx(0.9)

    def test_parse_list_results_with_dict(self, valkey_store):
        """Test parsing list-based results with dict format."""
        result = [
            1,  # total count
            {
                b"key1": {
                    b"content": b"hello",
                    b"metadata": b'{"k": "v"}',
                    b"chunk_id": b"id1",
                    b"score": b"0.3",
                }
            },
        ]
        chunks = valkey_store._parse_search_results(result)
        assert len(chunks) == 1
        assert chunks[0].content == "hello"
        assert chunks[0].chunk_id == "id1"
        assert chunks[0].score == pytest.approx(0.7)

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

    def test_doc_to_chunk_with_flat_list(self, valkey_store):
        """Test parsing flat list format [field, value, field, value, ...]."""
        doc = [
            "content",
            "list content",
            "metadata",
            "{}",
            "chunk_id",
            "c3",
            "score",
            "0.5",
        ]
        chunk = valkey_store._doc_to_chunk(doc)
        assert chunk is not None
        assert chunk.content == "list content"
        assert chunk.chunk_id == "c3"
        assert chunk.score == pytest.approx(0.5)

    def test_doc_to_chunk_invalid_returns_none(self, valkey_store):
        """Test that invalid doc types return None."""
        assert valkey_store._doc_to_chunk(42) is None
        assert valkey_store._doc_to_chunk("invalid") is None


# ---------------------------------------------------------------------------
# Score conversion for different metrics (pure logic)
# ---------------------------------------------------------------------------


class TestScoreConversion:
    """Tests for distance-to-similarity score conversion."""

    def _make_store_with_metric(self, metric, mock_embedding_fn):
        """Helper to create a store with a specific distance metric."""
        config = ValkeyVectorConfig(
            key_prefix="test_vec:",
            distance_metric=metric,
        )
        mock_client = MagicMock()
        with (
            patch.object(ValkeyStore, "_create_client", return_value=mock_client),
            patch.object(ValkeyStore, "_index_exists", return_value=True),
        ):
            store = ValkeyStore(
                vector_store_config=config,
                name="test",
                embedding_fn=mock_embedding_fn,
            )
            store._client = mock_client
            return store

    def test_cosine_score(self, mock_embedding_fn):
        """COSINE: score = 1.0 - distance."""
        store = self._make_store_with_metric("COSINE", mock_embedding_fn)
        doc = {"content": "x", "metadata": "{}", "chunk_id": "c1", "score": "0.3"}
        chunk = store._doc_to_chunk(doc)
        assert chunk.score == pytest.approx(0.7)

    def test_l2_score(self, mock_embedding_fn):
        """L2: score = 1/(1+distance)."""
        store = self._make_store_with_metric("L2", mock_embedding_fn)
        doc = {"content": "x", "metadata": "{}", "chunk_id": "c1", "score": "4.0"}
        chunk = store._doc_to_chunk(doc)
        assert chunk.score == pytest.approx(0.2)  # 1/(1+4)

    def test_l2_score_zero_distance(self, mock_embedding_fn):
        """L2: identical vectors have distance 0, score = 1.0."""
        store = self._make_store_with_metric("L2", mock_embedding_fn)
        doc = {"content": "x", "metadata": "{}", "chunk_id": "c1", "score": "0.0"}
        chunk = store._doc_to_chunk(doc)
        assert chunk.score == pytest.approx(1.0)

    def test_ip_score(self, mock_embedding_fn):
        """IP: score = 1.0 + distance (distance is negative inner product)."""
        store = self._make_store_with_metric("IP", mock_embedding_fn)
        doc = {"content": "x", "metadata": "{}", "chunk_id": "c1", "score": "-0.8"}
        chunk = store._doc_to_chunk(doc)
        assert chunk.score == pytest.approx(0.2)  # 1.0 + (-0.8)


# ---------------------------------------------------------------------------
# Tag value escaping (pure function)
# ---------------------------------------------------------------------------


class TestEscapeTagValue:
    """Tests for tag value escaping."""

    def test_simple_value(self):
        """Test that simple values pass through."""
        assert _escape_tag_value("hello") == "hello"

    def test_space(self):
        """Test that spaces are escaped."""
        assert _escape_tag_value("hello world") == "hello\\ world"

    def test_dot_and_comma(self):
        """Test escaping dots and commas."""
        assert _escape_tag_value("a.b,c") == "a\\.b\\,c"

    def test_special_chars_comprehensive(self):
        """Test all special chars that need escaping."""
        # Braces are special in Valkey tag queries
        assert _escape_tag_value("a{b}c") == "a\\{b\\}c"
        assert _escape_tag_value("x@y") == "x\\@y"
        assert _escape_tag_value("path/to") == "path\\/to"

    def test_pipe_escaped(self):
        """Test that pipe character is escaped to prevent OR injection."""
        assert _escape_tag_value("foo|bar") == "foo\\|bar"

    def test_empty_string(self):
        """Test empty string passes through."""
        assert _escape_tag_value("") == ""
