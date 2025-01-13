"""Short term memory module."""

import random
from concurrent.futures import Executor
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from dbgpt.core import Embeddings
from dbgpt.util.annotations import immutable, mutable
from dbgpt.util.executor_utils import blocking_func_to_async
from dbgpt.util.similarity_util import cosine_similarity, sigmoid_function

from .base import (
    DiscardedMemoryFragments,
    InsightMemoryFragment,
    ShortTermMemory,
    T,
    WriteOperation,
)


class EnhancedShortTermMemory(ShortTermMemory[T]):
    """Enhanced short term memory."""

    def __init__(
        self,
        embeddings: Embeddings,
        executor: Executor,
        buffer_size: int = 2,
        enhance_similarity_threshold: float = 0.7,
        enhance_threshold: int = 3,
    ):
        """Initialize enhanced short term memory."""
        super().__init__(buffer_size=buffer_size)
        self._executor = executor
        self._embeddings = embeddings
        self.short_embeddings: List[List[float]] = []
        self.enhance_cnt: List[int] = [0 for _ in range(self._buffer_size)]
        self.enhance_memories: List[List[T]] = [[] for _ in range(self._buffer_size)]
        self.enhance_similarity_threshold = enhance_similarity_threshold
        self.enhance_threshold = enhance_threshold

    @immutable
    def structure_clone(
        self: "EnhancedShortTermMemory[T]", now: Optional[datetime] = None
    ) -> "EnhancedShortTermMemory[T]":
        """Return a structure clone of the memory."""
        m: EnhancedShortTermMemory[T] = EnhancedShortTermMemory(
            embeddings=self._embeddings,
            executor=self._executor,
            buffer_size=self._buffer_size,
            enhance_similarity_threshold=self.enhance_similarity_threshold,
            enhance_threshold=self.enhance_threshold,
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
        """Write memory fragment to short term memory.

        Reference:
        https://github.com/RUC-GSAI/YuLan-Rec/blob/main/agents/recagent_memory.py#L336
        """
        # Calculate current embeddings of current memory fragment
        memory_fragment_embeddings = await blocking_func_to_async(
            self._executor,
            memory_fragment.calculate_current_embeddings,
            self._embeddings.embed_documents,
        )
        memory_fragment.update_embeddings(memory_fragment_embeddings)
        for idx, memory_embedding in enumerate(self.short_embeddings):
            similarity = await blocking_func_to_async(
                self._executor,
                cosine_similarity,
                memory_embedding,
                memory_fragment_embeddings,
            )
            # Sigmoid probability, transform similarity to [0, 1]
            sigmoid_prob: float = await blocking_func_to_async(
                self._executor, sigmoid_function, similarity
            )
            if (
                sigmoid_prob >= self.enhance_similarity_threshold
                and random.random() < sigmoid_prob
            ):
                self.enhance_cnt[idx] += 1
                self.enhance_memories[idx].append(memory_fragment)
        discard_memories = await self.transfer_to_long_term(memory_fragment)
        if op == WriteOperation.ADD:
            self._fragments.append(memory_fragment)
            self.short_embeddings.append(memory_fragment_embeddings)
            await self.handle_overflow(self._fragments)
        return discard_memories

    @mutable
    async def transfer_to_long_term(
        self, memory_fragment: T
    ) -> Optional[DiscardedMemoryFragments[T]]:
        """Transfer memory fragment to long term memory."""
        transfer_flag = False
        existing_memory = [True for _ in range(len(self.short_term_memories))]

        enhance_memories: List[T] = []
        to_get_insight_memories: List[T] = []
        for idx, memory in enumerate(self.short_term_memories):
            # if exceed the enhancement threshold
            if (
                self.enhance_cnt[idx] >= self.enhance_threshold
                and existing_memory[idx] is True
            ):
                existing_memory[idx] = False
                transfer_flag = True
                #
                # short-term memories
                content = [memory]
                # do not repeatedly add observation memory to summary, so use [:-1].
                for enhance_memory in self.enhance_memories[idx][:-1]:
                    content.append(enhance_memory)
                # Append the current observation memory
                content.append(memory_fragment)
                # Merge the enhanced memories to single memory
                merged_enhance_memory: T = memory.reduce(
                    content, importance=memory.importance
                )
                to_get_insight_memories.append(merged_enhance_memory)
                enhance_memories.append(merged_enhance_memory)
        # Get insights for the every enhanced memory
        enhance_insights: List[InsightMemoryFragment] = await self.get_insights(
            to_get_insight_memories
        )

        if transfer_flag:
            # re-construct the indexes of short-term memories after removing summarized
            # memories
            new_memories: List[T] = []
            new_embeddings: List[List[float]] = []
            new_enhance_memories: List[List[T]] = [[] for _ in range(self._buffer_size)]
            new_enhance_cnt: List[int] = [0 for _ in range(self._buffer_size)]
            for idx, memory in enumerate(self.short_term_memories):
                if existing_memory[idx]:
                    # Remove not enhanced memories to new memories
                    new_enhance_memories[len(new_memories)] = self.enhance_memories[idx]
                    new_enhance_cnt[len(new_memories)] = self.enhance_cnt[idx]
                    new_memories.append(memory)
                    new_embeddings.append(self.short_embeddings[idx])
            self._fragments = new_memories
            self.short_embeddings = new_embeddings
            self.enhance_memories = new_enhance_memories
            self.enhance_cnt = new_enhance_cnt
        return DiscardedMemoryFragments(enhance_memories, enhance_insights)

    @mutable
    async def handle_overflow(
        self, memory_fragments: List[T]
    ) -> Tuple[List[T], List[T]]:
        """Handle overflow of short term memory.

        Discard the least important memory fragment if the buffer size exceeds.
        """
        if len(self.short_term_memories) > self._buffer_size:
            id2fragments: Dict[int, Dict] = {}
            for idx in range(len(self.short_term_memories) - 1):
                # Not discard the last one
                memory = self.short_term_memories[idx]
                id2fragments[idx] = {
                    "enhance_count": self.enhance_cnt[idx],
                    "importance": memory.importance,
                }
            # Sort by importance and enhance count, first discard the least important
            sorted_ids = sorted(
                id2fragments.keys(),
                key=lambda x: (
                    id2fragments[x]["importance"],
                    id2fragments[x]["enhance_count"],
                ),
            )
            pop_id = sorted_ids[0]
            pop_raw_observation = self.short_term_memories[pop_id].raw_observation
            self.enhance_cnt.pop(pop_id)
            self.enhance_cnt.append(0)
            self.enhance_memories.pop(pop_id)
            self.enhance_memories.append([])

            discard_memory = self._fragments.pop(pop_id)
            self.short_embeddings.pop(pop_id)

            # remove the discard_memory from other short-term memory's enhanced list
            for idx in range(len(self.short_term_memories)):
                current_enhance_memories: List[T] = self.enhance_memories[idx]
                to_remove_idx = []
                for i, ehf in enumerate(current_enhance_memories):
                    if ehf.raw_observation == pop_raw_observation:
                        to_remove_idx.append(i)
                for i in to_remove_idx:
                    current_enhance_memories.pop(i)
                self.enhance_cnt[idx] -= len(to_remove_idx)

            return memory_fragments, [discard_memory]
        return memory_fragments, []
