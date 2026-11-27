"""Tests for clearing the hybrid memory."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict, List, Optional

import pytest

from dbgpt.agent.core.memory.agent_memory import AgentMemoryFragment
from dbgpt.agent.core.memory.base import SensoryMemory, ShortTermMemory
from dbgpt.agent.core.memory.hybrid import HybridMemory
from dbgpt.agent.core.memory.long_term import LongTermMemory
from dbgpt.core import Chunk
from dbgpt.storage.vector_store.base import VectorStoreBase, VectorStoreConfig


class _FakeVectorStore(VectorStoreBase):
    """A dict backed vector store that returns every stored chunk."""

    def __init__(self):
        self.chunks: Dict[str, Chunk] = {}

    def get_config(self) -> VectorStoreConfig:
        return VectorStoreConfig(name="fake")

    def load_document(self, chunks: List[Chunk]) -> List[str]:
        for chunk in chunks:
            self.chunks[chunk.chunk_id] = chunk
        return [chunk.chunk_id for chunk in chunks]

    def similar_search_with_scores(
        self,
        text: str,
        topk: int,
        score_threshold: float,
        filters: Optional[Any] = None,
    ) -> List[Chunk]:
        return list(self.chunks.values())[:topk]

    def delete_by_ids(self, ids: str) -> List[str]:
        id_list = ids.split(",")
        for chunk_id in id_list:
            self.chunks.pop(chunk_id, None)
        return id_list

    def vector_name_exists(self) -> bool:
        return True

    def delete_vector_name(self, index_name: str):
        self.chunks.clear()


@pytest.mark.asyncio
async def test_hybrid_memory_clear_removes_long_term_fragments():
    """Clearing a hybrid memory drops its fragments from every layer and the store."""
    now = datetime.now()
    store = _FakeVectorStore()
    with ThreadPoolExecutor() as executor:
        memory = HybridMemory(
            now,
            SensoryMemory(),
            ShortTermMemory(buffer_size=20),
            LongTermMemory(executor, store, now=now),
        )
        memory.initialize(name="test", real_memory_fragment_class=AgentMemoryFragment)
        await memory.write(
            AgentMemoryFragment(
                "Our art workshop is at Cedar Studio this Saturday.", importance=0.9
            )
        )
        assert await memory.read("workshop venue")

        cleared = await memory.clear()

        assert cleared
        assert await memory.read("workshop venue") == []
        assert store.chunks == {}
        assert memory._short_term_memory.short_term_memories == []
