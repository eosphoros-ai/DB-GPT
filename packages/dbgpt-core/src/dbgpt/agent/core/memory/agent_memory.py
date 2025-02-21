"""Agent memory module."""

from datetime import datetime
from typing import Callable, List, Optional, Type, cast

from dbgpt.core import LLMClient
from dbgpt.util.annotations import immutable, mutable
from dbgpt.util.id_generator import new_id

from .base import (
    DiscardedMemoryFragments,
    ImportanceScorer,
    InsightExtractor,
    Memory,
    MemoryFragment,
    ShortTermMemory,
    WriteOperation,
)
from .gpts import GptsMemory, GptsMessageMemory, GptsPlansMemory


class AgentMemoryFragment(MemoryFragment):
    """Default memory fragment for agent memory."""

    def __init__(
        self,
        observation: str,
        embeddings: Optional[List[float]] = None,
        memory_id: Optional[int] = None,
        importance: Optional[float] = None,
        last_accessed_time: Optional[datetime] = None,
        is_insight: bool = False,
    ):
        """Create a memory fragment."""
        if not memory_id:
            # Generate a new memory id, we use snowflake id generator here.
            memory_id = new_id()
        self.observation = observation
        self._embeddings = embeddings
        self.memory_id: int = cast(int, memory_id)
        self._importance: Optional[float] = importance
        self._last_accessed_time: Optional[datetime] = last_accessed_time
        self._is_insight = is_insight

    @property
    def id(self) -> int:
        """Return the memory id."""
        return self.memory_id

    @property
    def raw_observation(self) -> str:
        """Return the raw observation."""
        return self.observation

    @property
    def embeddings(self) -> Optional[List[float]]:
        """Return the embeddings of the memory fragment."""
        return self._embeddings

    def update_embeddings(self, embeddings: List[float]) -> None:
        """Update the embeddings of the memory fragment.

        Args:
            embeddings(List[float]): embeddings
        """
        self._embeddings = embeddings

    def calculate_current_embeddings(
        self, embedding_func: Callable[[List[str]], List[List[float]]]
    ) -> List[float]:
        """Calculate the embeddings of the memory fragment.

        Args:
            embedding_func(Callable[[List[str]], List[List[float]]]): Function to
                compute embeddings

        Returns:
            List[float]: Embeddings of the memory fragment
        """
        embeddings = embedding_func([self.observation])
        return embeddings[0]

    @property
    def is_insight(self) -> bool:
        """Return whether the memory fragment is an insight.

        Returns:
            bool: Whether the memory fragment is an insight
        """
        return self._is_insight

    @property
    def importance(self) -> Optional[float]:
        """Return the importance of the memory fragment.

        Returns:
            Optional[float]: Importance of the memory fragment
        """
        return self._importance

    def update_importance(self, importance: float) -> Optional[float]:
        """Update the importance of the memory fragment.

        Args:
            importance(float): Importance of the memory fragment

        Returns:
            Optional[float]: Old importance
        """
        old_importance = self._importance
        self._importance = importance
        return old_importance

    @property
    def last_accessed_time(self) -> Optional[datetime]:
        """Return the last accessed time of the memory fragment.

        Used to determine the least recently used memory fragment.

        Returns:
            Optional[datetime]: Last accessed time
        """
        return self._last_accessed_time

    def update_accessed_time(self, now: datetime) -> Optional[datetime]:
        """Update the last accessed time of the memory fragment.

        Args:
            now(datetime): Current time

        Returns:
            Optional[datetime]: Old last accessed time
        """
        old_time = self._last_accessed_time
        self._last_accessed_time = now
        return old_time

    @classmethod
    def build_from(
        cls: Type["AgentMemoryFragment"],
        observation: str,
        embeddings: Optional[List[float]] = None,
        memory_id: Optional[int] = None,
        importance: Optional[float] = None,
        is_insight: bool = False,
        last_accessed_time: Optional[datetime] = None,
        **kwargs,
    ) -> "AgentMemoryFragment":
        """Build a memory fragment from the given parameters."""
        return cls(
            observation=observation,
            embeddings=embeddings,
            memory_id=memory_id,
            importance=importance,
            last_accessed_time=last_accessed_time,
            is_insight=is_insight,
        )

    def copy(self: "AgentMemoryFragment") -> "AgentMemoryFragment":
        """Return a copy of the memory fragment."""
        return AgentMemoryFragment.build_from(
            observation=self.observation,
            embeddings=self._embeddings,
            memory_id=self.memory_id,
            importance=self.importance,
            last_accessed_time=self.last_accessed_time,
            is_insight=self.is_insight,
        )


class AgentMemory(Memory[AgentMemoryFragment]):
    """Agent memory."""

    def __init__(
        self,
        memory: Optional[Memory[AgentMemoryFragment]] = None,
        importance_scorer: Optional[ImportanceScorer[AgentMemoryFragment]] = None,
        insight_extractor: Optional[InsightExtractor[AgentMemoryFragment]] = None,
        gpts_memory: Optional[GptsMemory] = None,
    ):
        """Create an agent memory.

        Args:
            memory(Memory[AgentMemoryFragment]): Memory to store fragments
            importance_scorer(ImportanceScorer[AgentMemoryFragment]): Scorer to
                calculate the importance of memory fragments
            insight_extractor(InsightExtractor[AgentMemoryFragment]): Extractor to
                extract insights from memory fragments
            gpts_memory(GptsMemory): Memory to store GPTs related information
        """
        if not memory:
            memory = ShortTermMemory(buffer_size=5)
        if not gpts_memory:
            gpts_memory = GptsMemory()
        self.memory: Memory[AgentMemoryFragment] = cast(
            Memory[AgentMemoryFragment], memory
        )
        self.importance_scorer = importance_scorer
        self.insight_extractor = insight_extractor
        self.gpts_memory = gpts_memory

    @immutable
    def structure_clone(
        self: "AgentMemory", now: Optional[datetime] = None
    ) -> "AgentMemory":
        """Return a structure clone of the memory.

        The gpst_memory is not cloned, it will be shared in whole agent memory.
        """
        m = AgentMemory(
            memory=self.memory.structure_clone(now),
            importance_scorer=self.importance_scorer,
            insight_extractor=self.insight_extractor,
            gpts_memory=self.gpts_memory,
        )
        m._copy_from(self)
        return m

    @mutable
    def initialize(
        self,
        name: Optional[str] = None,
        llm_client: Optional[LLMClient] = None,
        importance_scorer: Optional[ImportanceScorer[AgentMemoryFragment]] = None,
        insight_extractor: Optional[InsightExtractor[AgentMemoryFragment]] = None,
        real_memory_fragment_class: Optional[Type[AgentMemoryFragment]] = None,
    ) -> None:
        """Initialize the memory."""
        self.memory.initialize(
            name=name,
            llm_client=llm_client,
            importance_scorer=importance_scorer or self.importance_scorer,
            insight_extractor=insight_extractor or self.insight_extractor,
            real_memory_fragment_class=real_memory_fragment_class
            or AgentMemoryFragment,
        )

    @mutable
    async def write(
        self,
        memory_fragment: AgentMemoryFragment,
        now: Optional[datetime] = None,
        op: WriteOperation = WriteOperation.ADD,
    ) -> Optional[DiscardedMemoryFragments[AgentMemoryFragment]]:
        """Write a memory fragment to the memory."""
        return await self.memory.write(memory_fragment, now)

    @immutable
    async def read(
        self,
        observation: str,
        alpha: Optional[float] = None,
        beta: Optional[float] = None,
        gamma: Optional[float] = None,
    ) -> List[AgentMemoryFragment]:
        """Read memory fragments related to the observation.

        Args:
            observation(str): Observation
            alpha(float): Importance weight
            beta(float): Time weight
            gamma(float): Randomness weight

        Returns:
            List[AgentMemoryFragment]: List of memory fragments
        """
        return await self.memory.read(observation, alpha, beta, gamma)

    @mutable
    async def clear(self) -> List[AgentMemoryFragment]:
        """Clear the memory."""
        return await self.memory.clear()

    @property
    def plans_memory(self) -> GptsPlansMemory:
        """Return the plan memory."""
        return self.gpts_memory.plans_memory

    @property
    def message_memory(self) -> GptsMessageMemory:
        """Return the message memory."""
        return self.gpts_memory.message_memory
