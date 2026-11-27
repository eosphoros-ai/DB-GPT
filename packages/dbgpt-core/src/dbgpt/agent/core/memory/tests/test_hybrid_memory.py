import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, List, Optional

import pytest

from dbgpt.agent.core.memory.agent_memory import (
    AgentMemory,
    AgentMemoryFragment,
    StructuredAgentMemoryFragment,
)
from dbgpt.agent.core.memory.base import SensoryMemory, ShortTermMemory
from dbgpt.agent.core.memory.hybrid import HybridMemory
from dbgpt.agent.core.memory.long_term import LongTermMemory
from dbgpt.agent.core.memory.short_term import EnhancedShortTermMemory
from dbgpt.core import Chunk, Embeddings
from dbgpt.storage.vector_store.base import VectorStoreBase
from dbgpt.storage.vector_store.filters import MetadataFilters


class InMemoryVectorStore(VectorStoreBase):
    """A vector store that keeps chunks in a dict and matches every query."""

    def __init__(self):
        super().__init__()
        self.chunks: Dict[str, Chunk] = {}

    def get_config(self):
        raise NotImplementedError

    def load_document(self, chunks: List[Chunk]) -> List[str]:
        for chunk in chunks:
            self.chunks[chunk.chunk_id] = chunk
        return [chunk.chunk_id for chunk in chunks]

    def similar_search_with_scores(
        self,
        text,
        topk,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        return [
            Chunk(
                content=c.content, metadata=c.metadata, score=1.0, chunk_id=c.chunk_id
            )
            for c in self.chunks.values()
        ][:topk]

    def delete_by_ids(self, ids: str) -> List[str]:
        id_list = ids.split(",")
        for chunk_id in id_list:
            self.chunks.pop(chunk_id, None)
        return id_list

    def vector_name_exists(self) -> bool:
        return True

    def delete_vector_name(self, vector_name: str):
        self.chunks.clear()


class FakeEmbeddings(Embeddings):
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [[float(len(text)), 1.0] for text in texts]

    def embed_query(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]


def _fragment(observation: str) -> AgentMemoryFragment:
    return AgentMemoryFragment(
        observation, importance=0.5, last_accessed_time=datetime.now()
    )


@pytest.mark.asyncio
async def test_clear_removes_fragments_from_all_hybrid_memories():
    store = InMemoryVectorStore()
    with ThreadPoolExecutor() as executor:
        memory = AgentMemory(
            memory=HybridMemory(
                datetime.now(),
                SensoryMemory(),
                ShortTermMemory(buffer_size=1),
                LongTermMemory(executor, store),
            )
        )
        memory.initialize(name="assistant", session_id="draft")
        for observation in [
            "Our art workshop is at Cedar Studio this Saturday.",
            "The workshop starts at 10am.",
            "Bring your own brushes.",
        ]:
            await memory.write(_fragment(observation))
        short_term_memory = memory.memory._short_term_memory
        # Fragments are kept in both the short-term and the long-term memories.
        assert store.chunks and short_term_memory.short_term_memories
        # Long-term fragments come back without the "[idx] " storage prefix.
        expected = [c.content.split("] ", 1)[1] for c in store.chunks.values()] + [
            f.raw_observation for f in short_term_memory.short_term_memories
        ]

        cleared = await memory.clear()

        assert sorted(f.raw_observation for f in cleared) == sorted(expected)
        assert store.chunks == {}
        assert short_term_memory.short_term_memories == []
        assert await memory.read("workshop venue") == []


@pytest.mark.asyncio
async def test_clear_resets_enhanced_short_term_memory():
    with ThreadPoolExecutor() as executor:
        memory = AgentMemory(
            memory=HybridMemory.from_vstore(
                InMemoryVectorStore(), embeddings=FakeEmbeddings(), executor=executor
            )
        )
        memory.initialize(name="assistant", session_id="draft")
        await memory.write(_fragment("Our art workshop is at Cedar Studio."))
        short_term_memory = memory.memory._short_term_memory
        assert isinstance(short_term_memory, EnhancedShortTermMemory)
        assert short_term_memory.short_embeddings

        cleared = await memory.clear()

        assert [f.raw_observation for f in cleared] == [
            "Our art workshop is at Cedar Studio."
        ]
        assert short_term_memory.short_embeddings == []
        assert await memory.read("workshop venue") == []
        # The memory is still usable after being cleared.
        await memory.write(_fragment("Next week's workshop needs a venue."))
        assert len(await memory.read("workshop venue")) == 1


class FailingDeleteVectorStore(InMemoryVectorStore):
    """A vector store whose deletion fails until ``fail`` is reset."""

    def __init__(self):
        super().__init__()
        self.fail = True

    def delete_by_ids(self, ids: str) -> List[str]:
        if self.fail:
            raise RuntimeError("delete failed")
        return super().delete_by_ids(ids)


@pytest.mark.asyncio
async def test_long_term_clear_returns_structured_fragments():
    store = InMemoryVectorStore()
    with ThreadPoolExecutor() as executor:
        memory = LongTermMemory(executor, store)
        memory.initialize(
            name="assistant",
            session_id="draft",
            real_memory_fragment_class=StructuredAgentMemoryFragment,
        )
        observation = {"observation": "Cedar Studio"}
        await memory.write(
            StructuredAgentMemoryFragment(
                observation, importance=0.5, last_accessed_time=datetime.now()
            )
        )

        cleared = await memory.clear()

        assert [f.raw_observation for f in cleared] == [
            StructuredAgentMemoryFragment(observation).raw_observation
        ]
        assert store.chunks == {}


@pytest.mark.asyncio
async def test_long_term_clear_can_be_retried_after_failed_delete():
    store = FailingDeleteVectorStore()
    with ThreadPoolExecutor() as executor:
        memory = LongTermMemory(executor, store)
        memory.initialize(
            name="assistant",
            session_id="draft",
            real_memory_fragment_class=AgentMemoryFragment,
        )
        await memory.write(_fragment("Our art workshop is at Cedar Studio."))

        with pytest.raises(RuntimeError):
            await memory.clear()
        assert store.chunks

        store.fail = False
        cleared = await memory.clear()

        assert [f.raw_observation for f in cleared] == [
            "Our art workshop is at Cedar Studio."
        ]
        assert store.chunks == {}


class BlockingDeleteVectorStore(InMemoryVectorStore):
    """A vector store whose deletion waits until ``release`` is set."""

    def __init__(self):
        super().__init__()
        self.deleting = threading.Event()
        self.release = threading.Event()

    def delete_by_ids(self, ids: str) -> List[str]:
        self.deleting.set()
        self.release.wait(timeout=5)
        return super().delete_by_ids(ids)


@pytest.mark.asyncio
async def test_long_term_clear_keeps_fragments_written_during_delete():
    store = BlockingDeleteVectorStore()
    with ThreadPoolExecutor() as executor:
        memory = LongTermMemory(executor, store)
        memory.initialize(
            name="assistant",
            session_id="draft",
            real_memory_fragment_class=AgentMemoryFragment,
        )
        await memory.write(_fragment("Our art workshop is at Cedar Studio."))

        clear_task = asyncio.create_task(memory.clear())
        await asyncio.get_running_loop().run_in_executor(None, store.deleting.wait, 5)
        await memory.write(_fragment("The workshop moved to Oak Hall."))
        store.release.set()
        cleared = await clear_task

        assert [f.raw_observation for f in cleared] == [
            "Our art workshop is at Cedar Studio."
        ]
        (remaining,) = store.chunks.values()
        assert remaining.content.endswith("The workshop moved to Oak Hall.")
        # The fragment written during the first clear is still tracked.
        cleared = await memory.clear()
        assert [f.raw_observation for f in cleared] == [
            "The workshop moved to Oak Hall."
        ]
        assert store.chunks == {}
