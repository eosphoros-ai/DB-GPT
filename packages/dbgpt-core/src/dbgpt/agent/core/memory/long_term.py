"""Long-term memory module."""

from concurrent.futures import Executor
from datetime import datetime
from typing import Any, Dict, Generic, List, Optional

from dbgpt.core import Chunk
from dbgpt.rag.retriever.time_weighted import TimeWeightedEmbeddingRetriever
from dbgpt.storage.vector_store.base import VectorStoreBase
from dbgpt.storage.vector_store.filters import MetadataFilter, MetadataFilters
from dbgpt.util.annotations import immutable, mutable
from dbgpt.util.executor_utils import blocking_func_to_async

from .base import DiscardedMemoryFragments, Memory, T, WriteOperation

_FORGET_PLACEHOLDER = "[FORGET]"
_MERGE_PLACEHOLDER = "[MERGE]"
_METADATA_BUFFER_IDX = "buffer_idx"
_METADATA_LAST_ACCESSED_AT = "last_accessed_at"
_METADATA_SESSION_ID = "session_id"
_METADAT_IMPORTANCE = "importance"


class LongTermRetriever(TimeWeightedEmbeddingRetriever):
    """Long-term retriever with persistence support."""

    def __init__(self, now: datetime, **kwargs):
        """Create a long-term retriever.

        Args:
            now: Current datetime to use for time-based calculations
            **kwargs: Additional arguments passed to TimeWeightedEmbeddingRetriever
        """
        self.now = now
        super().__init__(**kwargs)

    @mutable
    def _retrieve(
        self, query: str, filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        """Retrieve memories based on query and time weights.

        Args:
            query: The query string
            filters: Optional metadata filters

        Returns:
            List of relevant document chunks
        """
        # Use the current time from self.now instead of generating a new one
        current_time = self.now

        if self._use_vector_store_only:
            # If operating in vector store only mode, use parent class implementation
            # with custom adjustments for long-term memory
            return self._retrieve_vector_store_only(query, filters, current_time)

        # Process all memories in memory_stream
        docs_and_scores = {}
        for doc in self.memory_stream:
            if _METADATA_BUFFER_IDX in doc.metadata:
                buffer_idx = doc.metadata[_METADATA_BUFFER_IDX]
                docs_and_scores[buffer_idx] = (doc, self.default_salience)

        # If a doc is considered salient, update the salience score
        docs_and_scores.update(self.get_salient_docs(query, filters))

        # If no documents found and we're in vector store only mode, fall back
        if not docs_and_scores and self._use_vector_store_only:
            return self._retrieve_vector_store_only(query, filters, current_time)

        # Calculate combined scores for all documents
        rescored_docs = [
            (doc, self._get_combined_score(doc, relevance, current_time))
            for doc, relevance in docs_and_scores.values()
        ]

        # Sort by score
        rescored_docs.sort(key=lambda x: x[1], reverse=True)

        result = []
        retrieved_num = 0

        # Process documents in order of score
        for doc, _ in rescored_docs:
            # Skip documents that are marked for forgetting or merging
            if (
                retrieved_num < self._k
                and doc.content.find(_FORGET_PLACEHOLDER) == -1
                and doc.content.find(_MERGE_PLACEHOLDER) == -1
            ):
                retrieved_num += 1

                # Get the document from memory stream
                if _METADATA_BUFFER_IDX in doc.metadata and 0 <= doc.metadata[
                    _METADATA_BUFFER_IDX
                ] < len(self.memory_stream):
                    buffered_doc = self.memory_stream[
                        doc.metadata[_METADATA_BUFFER_IDX]
                    ]
                    buffered_doc.metadata[_METADATA_LAST_ACCESSED_AT] = current_time
                    result.append(buffered_doc)
                else:
                    # Handle case where buffer_idx is invalid
                    doc.metadata[_METADATA_LAST_ACCESSED_AT] = current_time
                    result.append(doc)

        # Save memory stream after updating access times
        self._save_memory_stream()

        return result

    def _retrieve_vector_store_only(
        self,
        query: str,
        filters: Optional[MetadataFilters] = None,
        current_time: Optional[datetime] = None,
    ) -> List[Chunk]:
        """Retrieve documents using only vector store when memory_stream is unavailable.

        Args:
            query: The query string
            filters: Optional metadata filters

        Returns:
            List of relevant document chunks
        """
        # Get documents from vector store
        docs = self._index_store.similar_search_with_scores(
            query, topk=self._top_k * 2, score_threshold=0, filters=filters
        )

        # Filter out documents that are marked for forgetting or merging
        filtered_docs = [
            doc
            for doc in docs
            if (
                doc.content.find(_FORGET_PLACEHOLDER) == -1
                and doc.content.find(_MERGE_PLACEHOLDER) == -1
            )
        ]

        # Apply time weighting
        rescored_docs = []
        for doc in filtered_docs:
            if _METADATA_LAST_ACCESSED_AT in doc.metadata:
                last_accessed_time = datetime.fromtimestamp(
                    float(doc.metadata[_METADATA_LAST_ACCESSED_AT])
                )
                hours_passed = self._get_hours_passed(current_time, last_accessed_time)
                time_score = (1.0 - self.decay_rate) ** hours_passed

                # Add importance score if available
                importance_score = 0
                if _METADAT_IMPORTANCE in doc.metadata:
                    importance_score = float(doc.metadata[_METADAT_IMPORTANCE])

                # Combine scores
                combined_score = doc.score + time_score + importance_score
                rescored_docs.append((doc, combined_score))
            else:
                # Just use vector similarity if no time data
                rescored_docs.append((doc, doc.score))

        # Sort by combined score
        rescored_docs.sort(key=lambda x: x[1], reverse=True)

        # Return top results, updating last_accessed_at
        result = []
        for doc, _ in rescored_docs[: self._k]:
            doc.metadata[_METADATA_LAST_ACCESSED_AT] = current_time
            result.append(doc)

        return result

    def _get_hours_passed(self, time: datetime, ref_time: datetime) -> float:
        """Get the hours passed between two datetime objects."""
        return (time - ref_time).total_seconds() / 3600


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
        metadata: Optional[Dict[str, Any]] = None,
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
        self._metadata: Dict[str, Any] = metadata or {"memory_type": "long_term"}

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
        metadata = self._metadata
        metadata[_METADAT_IMPORTANCE] = importance
        metadata[_METADATA_LAST_ACCESSED_AT] = last_accessed_time.timestamp()
        if self.session_id:
            metadata[_METADATA_SESSION_ID] = self.session_id

        document = Chunk(
            content="[{}] ".format(memory_idx) + str(memory_fragment.raw_observation),
            metadata=metadata,
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
        filters = []
        for key, value in self._metadata.items():
            # Just handle str, int, float
            if isinstance(value, (str, int, float)):
                filters.append(MetadataFilter(key=key, value=value))
        if self.session_id:
            filters.append(
                MetadataFilter(key=_METADATA_SESSION_ID, value=self.session_id)
            )
        filters = MetadataFilters(filters=filters)
        retrieved_list = await blocking_func_to_async(
            self.executor,
            self.memory_retriever.retrieve,
            observation,
            filters=filters,
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
