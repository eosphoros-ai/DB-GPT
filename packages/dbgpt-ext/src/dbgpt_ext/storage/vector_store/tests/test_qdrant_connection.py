"""Unit tests for QdrantStore local (embedded) mode.

These tests use a local Qdrant folder, so no server is needed.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

pytest.importorskip("qdrant_client")

from dbgpt.core import Chunk  # noqa: E402
from dbgpt_ext.storage.vector_store import qdrant_store  # noqa: E402
from dbgpt_ext.storage.vector_store.qdrant_store import (  # noqa: E402
    QdrantStore,
    QdrantVectorConfig,
)


def test_path_stores_share_client(tmp_path):
    embedding = MagicMock()
    embedding.embed_query.return_value = [1.0, 0.0]
    embedding.embed_documents.side_effect = lambda texts: [[1.0, 0.0]] * len(texts)
    config = QdrantVectorConfig(path=str(tmp_path))

    try:
        # Local mode locks its folder, so a second store on the same path must
        # reuse the first client instead of opening a new one.
        s1 = QdrantStore(config, name="space1", embedding_fn=embedding)
        s2 = QdrantStore(config, name="space2", embedding_fn=embedding)
        assert s1._client is s2._client

        s1.load_document([Chunk(content="hello", chunk_id="c1")])
        assert [c.chunk_id for c in s1.similar_search("q", topk=5)] == ["c1"]
        assert s2.similar_search("q", topk=5) == []
    finally:
        for client in qdrant_store._LOCAL_CLIENTS.values():
            client.close()
        qdrant_store._LOCAL_CLIENTS.clear()
