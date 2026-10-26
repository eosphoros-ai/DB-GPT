"""Unit tests for QdrantStore metadata payload indexes."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("qdrant_client")

from qdrant_client.models import PayloadSchemaType  # noqa: E402

from dbgpt_ext.storage.vector_store.qdrant_store import (  # noqa: E402
    QdrantStore,
    QdrantVectorConfig,
)


def _make_store(metadata_indexes, payload_schema):
    embedding = MagicMock()
    embedding.embed_query.return_value = [1.0, 0.0]
    with patch("qdrant_client.QdrantClient") as client_cls:
        client = client_cls.return_value
        client.collection_exists.return_value = True
        client.get_collection.return_value.payload_schema = payload_schema
        QdrantStore(
            QdrantVectorConfig(metadata_indexes=metadata_indexes),
            name="test",
            embedding_fn=embedding,
        )
    return client


def test_creates_missing_metadata_indexes():
    client = _make_store(
        "session_id, page:Integer", {"metadata.session_id": MagicMock()}
    )
    # session_id is already indexed, so only page is created
    client.create_payload_index.assert_called_once_with(
        collection_name="test",
        field_name="metadata.page",
        field_schema=PayloadSchemaType.INTEGER,
    )


def test_invalid_metadata_index():
    with pytest.raises(ValueError, match="Invalid Qdrant metadata index"):
        _make_store("page:number", {})
