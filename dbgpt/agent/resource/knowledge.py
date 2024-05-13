"""Knowledge resource."""

import dataclasses
from typing import TYPE_CHECKING, Any, List, Optional, Type

import cachetools

from dbgpt.util.cache_utils import cached

from .base import Resource, ResourceParameters, ResourceType

if TYPE_CHECKING:
    from dbgpt.core import Chunk
    from dbgpt.rag.retriever.base import BaseRetriever
    from dbgpt.storage.vector_store.filters import MetadataFilters


@dataclasses.dataclass
class RetrieverResourceParameters(ResourceParameters):
    """Retriever resource parameters."""

    pass


class RetrieverResource(Resource[ResourceParameters]):
    """Retriever resource.

    Retrieve knowledge chunks from a retriever.
    """

    def __init__(self, name: str, retriever: "BaseRetriever"):
        """Create a new RetrieverResource."""
        self._name = name
        self._retriever = retriever

    @property
    def name(self) -> str:
        """Return the resource name."""
        return self._name

    @property
    def retriever(self) -> "BaseRetriever":
        """Return the retriever."""
        return self._retriever

    @classmethod
    def type(cls) -> ResourceType:
        """Return the resource type."""
        return ResourceType.Knowledge

    @classmethod
    def resource_parameters_class(cls) -> Type[ResourceParameters]:
        """Return the resource parameters class."""
        return RetrieverResourceParameters

    @cached(cachetools.TTLCache(maxsize=100, ttl=10))
    async def get_prompt(
        self,
        *,
        lang: str = "en",
        prompt_type: str = "default",
        question: Optional[str] = None,
        resource_name: Optional[str] = None,
        **kwargs
    ) -> str:
        """Get the prompt for the resource."""
        if not question:
            raise ValueError("Question is required for knowledge resource.")
        chunks = await self.retrieve(question)
        content = "\n".join([chunk.content for chunk in chunks])
        prompt_template = "known information: {content}"
        prompt_template_zh = "已知信息: {content}"
        if lang == "en":
            return prompt_template.format(content=content)
        return prompt_template_zh.format(content=content)

    async def async_execute(
        self, *args, resource_name: Optional[str] = None, **kwargs
    ) -> Any:
        """Execute the resource asynchronously."""
        return await self.retrieve(*args, **kwargs)

    async def retrieve(
        self, query: str, filters: Optional["MetadataFilters"] = None
    ) -> List["Chunk"]:
        """Retrieve knowledge chunks.

        Args:
            query (str): query text.
            filters: (Optional[MetadataFilters]) metadata filters.

        Returns:
            List[Chunk]: list of chunks
        """
        return await self.retriever.aretrieve(query, filters)
