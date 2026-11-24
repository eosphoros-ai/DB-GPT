"""Tests for ChromaStore metadata filters."""

import pytest

pytest.importorskip("chromadb")

from dbgpt.core import Chunk, Embeddings  # noqa: E402
from dbgpt.storage.vector_store.filters import (  # noqa: E402
    FilterCondition,
    FilterOperator,
    MetadataFilter,
    MetadataFilters,
)
from dbgpt_ext.storage.vector_store.chroma_store import (  # noqa: E402
    ChromaStore,
    ChromaVectorConfig,
)


class _ConstantEmbeddings(Embeddings):
    def embed_documents(self, texts):
        return [[1.0, 0.5] for _ in texts]

    def embed_query(self, text):
        return [1.0, 0.5]

    async def aembed_documents(self, texts):
        return self.embed_documents(texts)

    async def aembed_query(self, text):
        return self.embed_query(text)


@pytest.fixture
def store(tmp_path):
    chroma_store = ChromaStore(
        ChromaVectorConfig(persist_path=str(tmp_path)),
        name="filters",
        embedding_fn=_ConstantEmbeddings(),
    )
    chroma_store.load_document(
        [
            Chunk(content=f"chunk {i}", metadata={"n": i, "tag": tag})
            for i, tag in enumerate(["red", "green", "blue", "red"])
        ]
    )
    return chroma_store


def _search(store, *filters, condition=FilterCondition.AND):
    chunks = store.similar_search_with_scores(
        "query",
        topk=10,
        score_threshold=0.0,
        filters=MetadataFilters(condition=condition, filters=list(filters)),
    )
    return sorted(chunk.metadata["n"] for chunk in chunks)


def test_in_and_nin_are_converted():
    store = ChromaStore.__new__(ChromaStore)
    filters = MetadataFilters(
        filters=[
            MetadataFilter(key="tag", operator=FilterOperator.IN, value=["a", "b"]),
            MetadataFilter(key="n", operator=FilterOperator.NIN, value=[1]),
        ]
    )
    assert store.convert_metadata_filters(filters) == {
        "$and": [{"tag": {"$in": ["a", "b"]}}, {"n": {"$nin": [1]}}]
    }


def test_in_filter(store):
    in_filter = MetadataFilter(
        key="tag", operator=FilterOperator.IN, value=["red", "blue"]
    )
    assert _search(store, in_filter) == [0, 2, 3]


def test_nin_filter(store):
    nin_filter = MetadataFilter(key="n", operator=FilterOperator.NIN, value=[0, 3])
    assert _search(store, nin_filter) == [1, 2]


def test_in_combined_with_or(store):
    assert _search(
        store,
        MetadataFilter(key="tag", operator=FilterOperator.IN, value=["green"]),
        MetadataFilter(key="n", operator=FilterOperator.GT, value=2),
        condition=FilterCondition.OR,
    ) == [1, 3]
