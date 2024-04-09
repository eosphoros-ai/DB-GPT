import logging
from typing import Any, List, Optional, Union

from dbgpt._private.config import Config
from dbgpt.agent.resource.resource_api import AgentResource
from dbgpt.agent.resource.resource_knowledge_api import ResourceKnowledgeClient
from dbgpt.core import Chunk
from dbgpt.serve.rag.retriever.knowledge_space import KnowledgeSpaceRetriever

CFG = Config()

logger = logging.getLogger(__name__)


class KnowledgeSpaceLoadClient(ResourceKnowledgeClient):
    async def get_space_desc(self, space_name) -> str:
        pass

    async def get_kn(
        self, space_name: str, question: Optional[str] = None
    ) -> List[Chunk]:
        kn_retriver = KnowledgeSpaceRetriever(space_name=space_name)
        chunks: List[Chunk] = kn_retriver.retrieve(question)
        return chunks

    async def add_kn(
        self, space_name: str, kn_name: str, type: str, content: Optional[Any]
    ):
        kn_retriver = KnowledgeSpaceRetriever(space_name=space_name)

    async def get_data_introduce(
        self, resource: AgentResource, question: Optional[str] = None
    ) -> Union[str, List[str]]:
        docs = await self.get_kn(resource.value, question)
        return "\n".join([doc.content for doc in docs])
