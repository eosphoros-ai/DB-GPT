"""Hybrid memory module.

This structure explicitly models the human short-term and long-term memories. The
short-term memory temporarily buffers recent perceptions, while long-term memory
consolidates important information over time.
"""

import os.path
from concurrent.futures import Executor, ThreadPoolExecutor
from datetime import datetime
from typing import Generic, List, Optional, Tuple, Type

from dbgpt.core import Embeddings, LLMClient
from dbgpt.storage.vector_store.base import VectorStoreBase
from dbgpt.util.annotations import immutable, mutable

from .base import (
    DiscardedMemoryFragments,
    ImportanceScorer,
    InsightExtractor,
    Memory,
    SensoryMemory,
    ShortTermMemory,
    T,
    WriteOperation,
)
from .long_term import LongTermMemory
from .short_term import EnhancedShortTermMemory


class HybridMemory(Memory, Generic[T]):
    """Hybrid memory for the agent."""

    importance_weight: float = 0.9

    def __init__(
        self,
        now: datetime,
        sensory_memory: SensoryMemory[T],
        short_term_memory: ShortTermMemory[T],
        long_term_memory: LongTermMemory[T],
        default_insight_extractor: Optional[InsightExtractor] = None,
        default_importance_scorer: Optional[ImportanceScorer] = None,
    ):
        """Create a hybrid memory."""
        self.now = now
        self._sensory_memory = sensory_memory
        self._short_term_memory = short_term_memory
        self._long_term_memory = long_term_memory
        self._default_insight_extractor = default_insight_extractor
        self._default_importance_scorer = default_importance_scorer

    def structure_clone(
        self: "HybridMemory[T]", now: Optional[datetime] = None
    ) -> "HybridMemory[T]":
        """Return a structure clone of the memory."""
        now = now or self.now
        m = HybridMemory(
            now=now,
            sensory_memory=self._sensory_memory.structure_clone(now),
            short_term_memory=self._short_term_memory.structure_clone(now),
            long_term_memory=self._long_term_memory.structure_clone(now),
            default_insight_extractor=self._default_insight_extractor,
            default_importance_scorer=self._default_importance_scorer,
        )
        m._copy_from(self)
        return m

    @classmethod
    def from_chroma(
        cls,
        vstore_name: Optional[str] = "_chroma_agent_memory_",
        vstore_path: Optional[str] = None,
        embeddings: Optional[Embeddings] = None,
        executor: Optional[Executor] = None,
        now: Optional[datetime] = None,
        sensory_memory: Optional[SensoryMemory[T]] = None,
        short_term_memory: Optional[ShortTermMemory[T]] = None,
        long_term_memory: Optional[LongTermMemory[T]] = None,
        **kwargs,
    ):
        """Create a hybrid memory from Chroma vector store."""
        from dbgpt.configs.model_config import DATA_DIR
        from dbgpt.storage.vector_store.chroma_store import (
            ChromaStore,
            ChromaVectorConfig,
        )

        if not embeddings:
            from dbgpt.rag.embedding import DefaultEmbeddingFactory

            embeddings = DefaultEmbeddingFactory.openai()

        vstore_path = vstore_path or os.path.join(DATA_DIR, "agent_memory")

        vector_store = ChromaStore(
            ChromaVectorConfig(
                name=vstore_name,
                persist_path=vstore_path,
                embedding_fn=embeddings,
            )
        )
        return cls.from_vstore(
            vector_store=vector_store,
            embeddings=embeddings,
            executor=executor,
            now=now,
            sensory_memory=sensory_memory,
            short_term_memory=short_term_memory,
            long_term_memory=long_term_memory,
            **kwargs,
        )

    @classmethod
    def from_vstore(
        cls,
        vector_store: "VectorStoreBase",
        embeddings: Optional[Embeddings] = None,
        executor: Optional[Executor] = None,
        now: Optional[datetime] = None,
        sensory_memory: Optional[SensoryMemory[T]] = None,
        short_term_memory: Optional[ShortTermMemory[T]] = None,
        long_term_memory: Optional[LongTermMemory[T]] = None,
        **kwargs,
    ):
        """Create a hybrid memory from vector store."""
        if not embeddings:
            raise ValueError("embeddings is required.")
        if not executor:
            executor = ThreadPoolExecutor()
        if not now:
            now = datetime.now()

        if not sensory_memory:
            sensory_memory = SensoryMemory()
        if not short_term_memory:
            if not embeddings:
                raise ValueError("embeddings is required.")
            short_term_memory = EnhancedShortTermMemory(embeddings, executor)
        if not long_term_memory:
            long_term_memory = LongTermMemory(
                executor,
                vector_store,
                now=now,
            )
        return cls(now, sensory_memory, short_term_memory, long_term_memory, **kwargs)

    def initialize(
        self,
        name: Optional[str] = None,
        llm_client: Optional[LLMClient] = None,
        importance_scorer: Optional[ImportanceScorer[T]] = None,
        insight_extractor: Optional[InsightExtractor[T]] = None,
        real_memory_fragment_class: Optional[Type[T]] = None,
    ) -> None:
        """Initialize the memory.

        It will initialize all the memories.
        """
        memories = [
            self._sensory_memory,
            self._short_term_memory,
            self._long_term_memory,
        ]
        kwargs = {
            "name": name,
            "llm_client": llm_client,
            "importance_scorer": importance_scorer,
            "insight_extractor": insight_extractor,
            "real_memory_fragment_class": real_memory_fragment_class,
        }
        for memory in memories:
            memory.initialize(**kwargs)
        super().initialize(**kwargs)

    @mutable
    async def write(
        self,
        memory_fragment: T,
        now: Optional[datetime] = None,
        op: WriteOperation = WriteOperation.ADD,
    ) -> Optional[DiscardedMemoryFragments[T]]:
        """Write a memory fragment to the memory."""
        # First write to sensory memory
        sen_discarded_memories = await self._sensory_memory.write(memory_fragment)
        if not sen_discarded_memories:
            return None
        short_term_discarded_memories = []
        discarded_memory_fragments = []
        discarded_insights = []
        for sen_memory in sen_discarded_memories.discarded_memory_fragments:
            # Write to short term memory
            short_discarded_memory = await self._short_term_memory.write(sen_memory)
            if short_discarded_memory:
                short_term_discarded_memories.append(short_discarded_memory)
                discarded_memory_fragments.extend(
                    short_discarded_memory.discarded_memory_fragments
                )
                for insight in short_discarded_memory.discarded_insights:
                    # Just keep the first insight
                    discarded_insights.append(insight.insights[0])
        # Obtain the importance of insights
        insight_scores = await self.score_memory_importance(discarded_insights)
        # Get the importance of insights
        for i, ins in enumerate(discarded_insights):
            ins.update_importance(insight_scores[i])
        all_memories = discarded_memory_fragments + discarded_insights
        if self._long_term_memory:
            # Write to long term memory
            await self._long_term_memory.write_batch(all_memories, self.now)
        return None

    @immutable
    async def read(
        self,
        observation: str,
        alpha: Optional[float] = None,
        beta: Optional[float] = None,
        gamma: Optional[float] = None,
    ) -> List[T]:
        """Read memories from the memory."""
        (
            retrieved_long_term_memories,
            short_term_discarded_memories,
        ) = await self.fetch_memories(observation, self._short_term_memory)

        await self.save_memories_after_retrieval(short_term_discarded_memories)
        return retrieved_long_term_memories

    @immutable
    async def fetch_memories(
        self,
        observation: str,
        short_term_memory: Optional[ShortTermMemory[T]] = None,
    ) -> Tuple[List[T], List[DiscardedMemoryFragments[T]]]:
        """Fetch memories from long term memory.

        If short_term_memory is provided, write the fetched memories to the short term
        memory.
        """
        retrieved_long_term_memories = await self._long_term_memory.fetch_memories(
            observation
        )
        if not short_term_memory:
            return retrieved_long_term_memories, []
        short_term_discarded_memories: List[DiscardedMemoryFragments[T]] = []
        discarded_memory_fragments: List[T] = []
        for ltm in retrieved_long_term_memories:
            short_discarded_memory = await short_term_memory.write(
                ltm, op=WriteOperation.RETRIEVAL
            )
            if short_discarded_memory:
                short_term_discarded_memories.append(short_discarded_memory)
                discarded_memory_fragments.extend(
                    short_discarded_memory.discarded_memory_fragments
                )
        for stm in short_term_memory.short_term_memories:
            retrieved_long_term_memories.append(
                stm.current_class.build_from(
                    observation=stm.raw_observation,
                    importance=stm.importance,
                )
            )
        return retrieved_long_term_memories, short_term_discarded_memories

    async def save_memories_after_retrieval(
        self, fragments: List[DiscardedMemoryFragments[T]]
    ):
        """Save memories after retrieval."""
        discarded_memory_fragments = []
        discarded_memory_insights: List[T] = []
        for f in fragments:
            discarded_memory_fragments.extend(f.discarded_memory_fragments)
            for fi in f.discarded_insights:
                discarded_memory_insights.append(fi.insights[0])
        insights_importance = await self.score_memory_importance(
            discarded_memory_insights
        )
        for i, ins in enumerate(discarded_memory_insights):
            ins.update_importance(insights_importance[i])
        all_memories = discarded_memory_fragments + discarded_memory_insights
        await self._long_term_memory.write_batch(all_memories, self.now)

    async def clear(self) -> List[T]:
        """Clear the memory.

        # TODO
        """
        return []
