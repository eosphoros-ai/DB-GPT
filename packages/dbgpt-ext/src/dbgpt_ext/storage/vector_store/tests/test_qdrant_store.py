"""Unit tests for QdrantStore full text search.

These tests run against an in-memory Qdrant client, so no server is needed.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

qdrant_models = pytest.importorskip("qdrant_client.models")
if not hasattr(qdrant_models, "TextQuery"):
    pytest.skip("qdrant-client >= 1.20 is required", allow_module_level=True)

from qdrant_client import QdrantClient  # noqa: E402

from dbgpt.core import Chunk  # noqa: E402
from dbgpt.storage.vector_store.filters import (  # noqa: E402
    FilterOperator,
    MetadataFilter,
    MetadataFilters,
)
from dbgpt_ext.storage.vector_store.qdrant_store import (  # noqa: E402
    QdrantStore,
    QdrantVectorConfig,
)

_DOCS = {
    "a": ("Qdrant supports BM25 ranking on text indexes", "x"),
    "b": ("BM25 keyword search BM25 scoring", "y"),
    "c": ("Dense vectors capture semantic meaning", "x"),
}


def _make_store(client, **config):
    embedding = MagicMock()
    embedding.embed_query.return_value = [1.0, 0.0]
    embedding.embed_documents.side_effect = lambda texts: [[1.0, 0.0]] * len(texts)
    with patch("qdrant_client.QdrantClient", side_effect=lambda **kwargs: client):
        return QdrantStore(
            QdrantVectorConfig(**config), name="test", embedding_fn=embedding
        )


@pytest.fixture
def store():
    """Create a QdrantStore backed by an in-memory client with 3 docs."""
    s = _make_store(QdrantClient(location=":memory:"))
    s.load_document(
        [
            Chunk(content=content, chunk_id=cid, metadata={"category": cat})
            for cid, (content, cat) in _DOCS.items()
        ]
    )
    return s


def test_full_text_search_supported(store):
    assert store.is_support_full_text_search()


def test_full_text_search_ranks_by_bm25(store):
    result = store.full_text_search("BM25", topk=5)
    assert [c.chunk_id for c in result] == ["b", "a"]
    assert all(c.retriever == "full_text" for c in result)
    assert result[0].score > result[1].score


def test_full_text_search_no_match(store):
    assert store.full_text_search("nothing matches", topk=5) == []


def test_full_text_search_with_filters(store):
    filters = MetadataFilters(
        filters=[MetadataFilter(key="category", operator=FilterOperator.EQ, value="x")]
    )
    result = store.full_text_search("BM25", topk=5, filters=filters)
    assert [c.chunk_id for c in result] == ["a"]


def test_full_text_search_unsupported_server():
    client = QdrantClient(location=":memory:")
    client.info = lambda: MagicMock(version="1.19.2")
    s = _make_store(client)
    assert not s.is_support_full_text_search()
    with pytest.raises(NotImplementedError):
        s.full_text_search("BM25", topk=5)


def test_invalid_tokenizer():
    with pytest.raises(ValueError, match="Unsupported Qdrant tokenizer"):
        _make_store(QdrantClient(location=":memory:"), tokenizer="chinese")
