from typing import List
from langchain.embeddings.base import Embeddings

from dbgpt.model.cluster.manager_base import WorkerManager


class RemoteEmbeddings(Embeddings):
    def __init__(self, model_name: str, worker_manager: WorkerManager) -> None:
        self.model_name = model_name
        self.worker_manager = worker_manager

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed search docs."""
        params = {"model": self.model_name, "input": texts}
        return self.worker_manager.sync_embeddings(params)

    def embed_query(self, text: str) -> List[float]:
        """Embed query text."""
        return self.embed_documents([text])[0]

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        """Asynchronous Embed search docs."""
        params = {"model": self.model_name, "input": texts}
        return await self.worker_manager.embeddings(params)

    async def aembed_query(self, text: str) -> List[float]:
        """Asynchronous Embed query text."""
        return await self.aembed_documents([text])[0]
