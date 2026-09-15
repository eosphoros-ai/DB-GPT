"""Tests for non-retryable embedding failures."""

import asyncio
from typing import List, Optional

import pytest

from dbgpt.core import Chunk
from dbgpt.storage.base import IndexStoreBase, IndexStoreConfig


class _Store(IndexStoreBase):
    def __init__(self, error_message="401 Unauthorized"):
        super().__init__()
        self.calls: List[int] = []
        self.error_message = error_message

    def get_config(self) -> IndexStoreConfig:
        return IndexStoreConfig()

    def load_document(self, chunks: List[Chunk]) -> List[str]:
        self.calls.append(len(chunks))
        raise RuntimeError(self.error_message)

    async def aload_document(
        self, chunks: List[Chunk], file_id: Optional[str] = None
    ) -> List[str]:
        self.calls.append(len(chunks))
        raise RuntimeError(self.error_message)

    def similar_search_with_scores(self, text, topk, score_threshold, filters=None):
        return []

    def delete_by_ids(self, ids: str) -> List[str]:
        return []

    def truncate(self) -> List[str]:
        return []

    def delete_vector_name(self, index_name: str):
        return None


def test_non_retryable_sync_load_does_not_retry_each_chunk():
    store = _Store()

    try:
        store._safe_load_group([Chunk(content="one"), Chunk(content="two")])
    except RuntimeError as error:
        assert "401" in str(error)
    else:
        raise AssertionError("the authentication failure should be propagated")

    assert store.calls == [2]


def test_non_retryable_async_load_does_not_retry_each_chunk():
    store = _Store()

    async def run():
        try:
            await store._safe_aload_group(
                [Chunk(content="one"), Chunk(content="two")]
            )
        except RuntimeError as error:
            assert "401" in str(error)
        else:
            raise AssertionError("the authentication failure should be propagated")

    asyncio.run(run())
    assert store.calls == [2]


def test_non_retryable_status_code_is_detected():
    class _ResponseError(Exception):
        status_code = 403

    assert IndexStoreBase._is_non_retryable_load_error(_ResponseError()) is True


@pytest.mark.parametrize("error_message", ["401 Unauthorized", "403 Forbidden"])
def test_non_retryable_async_load_limit_propagates_authentication_errors(
    error_message,
):
    store = _Store(error_message)

    async def run():
        with pytest.raises(RuntimeError, match=error_message.split()[0]):
            await store.aload_document_with_limit(
                [Chunk(content="one"), Chunk(content="two")],
                max_chunks_once_load=2,
                max_threads=1,
            )

    asyncio.run(run())
    assert store.calls == [2]
