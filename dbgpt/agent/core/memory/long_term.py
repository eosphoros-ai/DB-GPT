"""Long-term memory module."""

from concurrent.futures import Executor
from datetime import datetime
from typing import Generic, List, Optional

from dbgpt.core import Chunk
from dbgpt.rag.retriever.time_weighted import TimeWeightedEmbeddingRetriever
from dbgpt.storage.vector_store.base import VectorStoreBase
from dbgpt.storage.vector_store.filters import MetadataFilters
from dbgpt.util.annotations import immutable, mutable
from dbgpt.util.executor_utils import blocking_func_to_async

from .base import DiscardedMemoryFragments, Memory, T, WriteOperation

_FORGET_PLACEHOLDER = "[FORGET]"
_MERGE_PLACEHOLDER = "[MERGE]"
_METADATA_BUFFER_IDX = "buffer_idx"
_METADATA_LAST_ACCESSED_AT = "last_accessed_at"
_METADAT_IMPORTANCE = "importance"


class LongTermRetriever(TimeWeightedEmbeddingRetriever):
    """Long-term retriever."""

    def __init__(self, now: datetime, **kwargs):
        """Create a long-term retriever."""
        self.now = now
        super().__init__(**kwargs)

    @mutable
    def _retrieve(
        self, query: str, filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        """Retrieve memories."""
        current_time = self.now
        docs_and_scores = {
            doc.metadata[_METADATA_BUFFER_IDX]: (doc, self.default_salience)
            # Calculate for all memories.
            for doc in self.memory_stream
        }
        # If a doc is considered salient, update the salience score
        docs_and_scores.update(self.get_salient_docs(query))
        rescored_docs = [
            (doc, self._get_combined_score(doc, relevance, current_time))
            for doc, relevance in docs_and_scores.values()
        ]
        rescored_docs.sort(key=lambda x: x[1], reverse=True)
        result = []
        # Ensure frequently accessed memories aren't forgotten
        retrieved_num = 0
        for doc, _ in rescored_docs:
            if (
                retrieved_num < self._k
                and doc.content.find(_FORGET_PLACEHOLDER) == -1
                and doc.content.find(_MERGE_PLACEHOLDER) == -1
            ):
                retrieved_num += 1
                buffered_doc = self.memory_stream[doc.metadata[_METADATA_BUFFER_IDX]]
                buffered_doc.metadata[_METADATA_LAST_ACCESSED_AT] = current_time
                result.append(buffered_doc)
        return result


class LongTermMemory(Memory, Generic[T]):
    """Long-term memory."""

    importance_weight: float = 0.15

    def __init__(
        self,
        executor: Executor,
        vector_store: VectorStoreBase,
        now: Optional[datetime] = None,
        reflection_threshold: Optional[float] = None,
        _default_importance: Optional[float] = None,
    ):
        """Create a long-term memory."""
        self.now = now or datetime.now()
        self.executor = executor
        self.reflecting: bool = False
        self.forgetting: bool = False
        self.reflection_threshold: Optional[float] = reflection_threshold
        self.aggregate_importance: float = 0.0
        self._vector_store = vector_store
        self.memory_retriever = LongTermRetriever(
            now=self.now, index_store=vector_store
        )
        self._default_importance = _default_importance

    @immutable
    def structure_clone(
        self: "LongTermMemory[T]", now: Optional[datetime] = None
    ) -> "LongTermMemory[T]":
        """Create a structure clone of the long-term memory."""
        new_name = self.name
        if not new_name:
            raise ValueError("name is required.")
        m: LongTermMemory[T] = LongTermMemory(
            now=now,
            executor=self.executor,
            vector_store=self._vector_store,
            reflection_threshold=self.reflection_threshold,
            _default_importance=self._default_importance,
        )
        m._copy_from(self)
        return m

    @mutable
    async def write(
        self,
        memory_fragment: T,
        now: Optional[datetime] = None,
        op: WriteOperation = WriteOperation.ADD,
    ) -> Optional[DiscardedMemoryFragments[T]]:
        """Write a memory fragment to the memory."""
        importance = memory_fragment.importance
        if importance is None:
            importance = self._default_importance
        last_accessed_time = memory_fragment.last_accessed_time
        if importance is None:
            raise ValueError("importance is required.")
        if not self.reflecting:
            self.aggregate_importance += importance

        memory_idx = len(self.memory_retriever.memory_stream)
        document = Chunk(
            page_content="[{}] ".format(memory_idx)
            + str(memory_fragment.raw_observation),
            metadata={
                _METADAT_IMPORTANCE: importance,
                _METADATA_LAST_ACCESSED_AT: last_accessed_time,
            },
        )
        await blocking_func_to_async(
            self.executor,
            self.memory_retriever.load_document,
            [document],
            current_time=now,
        )

        return None

    @mutable
    async def write_batch(
        self, memory_fragments: List[T], now: Optional[datetime] = None
    ) -> Optional[DiscardedMemoryFragments[T]]:
        """Write a batch of memory fragments to the memory."""
        current_datetime = self.now
        if not now:
            raise ValueError("Now time is required.")
        for short_term_memory in memory_fragments:
            short_term_memory.update_accessed_time(now=now)
            await self.write(short_term_memory, now=current_datetime)
        # TODO(fangyinc): Reflect on the memories and get high-level insights.
        # TODO(fangyinc): Forget memories that are not important.
        return None

    @immutable
    async def read(
        self,
        observation: str,
        alpha: Optional[float] = None,
        beta: Optional[float] = None,
        gamma: Optional[float] = None,
    ) -> List[T]:
        """Read memory fragments related to the observation."""
        return await self.fetch_memories(observation=observation, now=self.now)

    @immutable
    async def fetch_memories(
        self, observation: str, now: Optional[datetime] = None
    ) -> List[T]:
        """Fetch memories related to the observation."""
        # TODO: Mock now?
        retrieved_memories = []
        retrieved_list = await blocking_func_to_async(
            self.executor,
            self.memory_retriever.retrieve,
            observation,
        )
        for retrieved_chunk in retrieved_list:
            retrieved_memories.append(
                self.real_memory_fragment_class.build_from(
                    observation=retrieved_chunk.content,
                    importance=retrieved_chunk.metadata[_METADAT_IMPORTANCE],
                )
            )
        return retrieved_memories

    @mutable
    async def clear(self) -> List[T]:
        """Clear the memory.

        TODO: Implement this method.
        """
        return []
