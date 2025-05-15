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
        buffer_size: int = 10,
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

        async with self._lock:
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
        discarded_memories = []
        if len(self._fragments) > self._buffer_size:
            id2fragments: Dict[int, Dict] = {}
            for idx in range(len(self._fragments) - 1):
                memory = self._fragments[idx]
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
            # Get the ID of the memory fragment to be popped
            pop_id = sorted_ids[0]
            pop_memory = self._fragments[pop_id]
            pop_raw_observation = pop_memory.raw_observation
            # Save the discarded memory
            discarded_memory = self._fragments.pop(pop_id)
            discarded_memories.append(discarded_memory)
            # Remove the corresponding embedding vector
            self.short_embeddings.pop(pop_id)

            # Reorganize enhance count and enhance memories
            new_enhance_memories = [[] for _ in range(self._buffer_size)]
            new_enhance_cnt = [0 for _ in range(self._buffer_size)]
            # Copy and adjust enhanced memory and count
            current_idx = 0
            for idx in range(len(self._fragments)):
                if idx == pop_id:
                    continue  # Skip the popped memory

                # Copy the enhanced memory list but remove any items matching the
                # popped memory
                current_memories = []
                removed_count = 0

                for ehf in self.enhance_memories[idx]:
                    if ehf.raw_observation != pop_raw_observation:
                        current_memories.append(ehf)
                    else:
                        removed_count += 1

                # Update to new array
                new_enhance_memories[current_idx] = current_memories
                new_enhance_cnt[current_idx] = self.enhance_cnt[idx] - removed_count
                current_idx += 1
            # Update enhanced memories and counts
            self.enhance_memories = new_enhance_memories
            self.enhance_cnt = new_enhance_cnt

        return memory_fragments, discarded_memories
