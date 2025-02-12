"""Knowledge resource."""

import dataclasses
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Type

import cachetools

from dbgpt.core import Chunk
from dbgpt.util.cache_utils import cached

from .base import Resource, ResourceParameters, ResourceType

if TYPE_CHECKING:
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
    def retriever_name(self) -> str:
        """Return the resource name."""
        return ""

    @property
    def retriever_desc(self) -> str:
        """Return the retriever desc."""
        return ""

    @property
    def retriever(self) -> "BaseRetriever":
        """Return the retriever."""
        return self._retriever

    @classmethod
    def type(cls) -> ResourceType:
        """Return the resource type."""
        return ResourceType.Knowledge

    @classmethod
    def resource_parameters_class(cls, **kwargs) -> Type[ResourceParameters]:
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
        **kwargs,
    ) -> Tuple[str, Optional[Dict]]:
        """Get the prompt for the resource."""
        if not question:
            raise ValueError("Question is required for knowledge resource.")
        chunks = await self.retrieve(question)
        content = "\n".join(
            [f"--{i}--:" + chunk.content for i, chunk in enumerate(chunks)]
        )
        prompt_template = f"\nResources-{self.name}:\n {content}"
        prompt_template_zh = f"\n资源-{self.name}:\n {content}"
        if lang == "en":
            return prompt_template, self._get_references(chunks)
        return prompt_template_zh, self._get_references(chunks)

    async def get_resources(
        self,
        lang: str = "en",
        prompt_type: str = "default",
        question: Optional[str] = None,
        resource_name: Optional[str] = None,
    ) -> Tuple[Optional[List[Chunk]], str, Optional[Dict]]:
        """Get the chunks for the resource."""
        if not question:
            raise ValueError("Question is required for knowledge resource.")
        chunks = await self.retrieve(question)
        prompt_template = """Resources-{name}:\n {content}"""
        prompt_template_zh = """资源-{name}:\n {content}"""
        if lang == "en":
            return chunks, prompt_template, self._get_references(chunks)
        else:
            return chunks, prompt_template_zh, self._get_references(chunks)

    def _get_references(self, docs: List[Chunk]) -> Optional[Dict]:
        references_dict = {}
        for chunk in docs:
            doc_name = None
            prop_field = chunk.metadata.get("prop_field", None)
            if prop_field:
                doc_name = prop_field.get("source", None)
            if not doc_name:
                doc_name = chunk.metadata.get("metadata", "-")
            if doc_name not in references_dict:
                references_dict[doc_name] = {
                    "name": doc_name,
                    "chunks": [
                        {
                            "id": chunk.chunk_id,
                            "content": chunk.content,
                            "meta_info": doc_name,
                            "recall_score": chunk.score,
                            "retriever": chunk.retriever,
                        }
                    ],
                }
            else:
                references_dict[doc_name]["chunks"].append(
                    {
                        "id": chunk.chunk_id,
                        "content": chunk.content,
                        "meta_info": doc_name,
                        "recall_score": chunk.score,
                        "retriever": chunk.retriever,
                    }
                )
        return {self.type().value: list(references_dict.values())}

    async def async_execute(
        self, *args, resource_name: Optional[str] = None, **kwargs
    ) -> Any:
        """Execute the resource asynchronously."""
        return await self.retrieve(*args, **kwargs)

    async def retrieve(
        self,
        query: str,
        filters: Optional["MetadataFilters"] = None,
        score: float = 0.0,
    ) -> List["Chunk"]:
        """Retrieve knowledge chunks.

        Args:
            query (str): query text.
            filters: (Optional[MetadataFilters]) metadata filters.
            score: (float) similarity score.

        Returns:
            List[Chunk]: list of chunks
        """
        return await self.retriever.aretrieve_with_scores(query, score, filters)
