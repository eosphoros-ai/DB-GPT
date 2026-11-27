from typing import List

import pytest

pytest.importorskip("chromadb")

from dbgpt_ext.storage.vector_store.chroma_store import ChromaStore  # noqa: E402


class FailingFirstBatchCollection:
    """A collection that rejects the first deletion batch."""

    def __init__(self, ids: List[str]):
        self.ids = set(ids)
        self.calls = 0

    def delete(self, ids: List[str]):
        self.calls += 1
        if self.calls == 1:
            raise ValueError("delete failed")
        self.ids.difference_update(ids)


def test_delete_by_ids_raises_after_deleting_remaining_batches():
    store = ChromaStore.__new__(ChromaStore)
    collection = FailingFirstBatchCollection(["a", "b", "c"])
    store._collection = collection

    with pytest.raises(RuntimeError):
        store.delete_by_ids("a,b,c", batch_size=2)

    # The failed batch is kept and the later batch is still deleted.
    assert collection.ids == {"a", "b"}
