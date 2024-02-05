from typing import Any, Dict, List, Optional, Tuple, Union

from dbgpt.rag.retriever.base import BaseRetriever

from .resource_api import ResourceClient, ResourceType


class ResourceKnowledgeClient(ResourceClient):
    @property
    def type(self):
        return ResourceType.Knowledge

    async def a_get_kn(self, space_name: str, question: Optional[str] = None) -> str:
        raise NotImplementedError("The run method should be implemented in a subclass.")

    async def add_kn(
        self, space_name: str, kn_name: str, type: str, content: Optional[Any]
    ):
        raise NotImplementedError("The run method should be implemented in a subclass.")
