from typing import List

from dbgpt.core import Embeddings, RerankEmbeddings
from dbgpt.model.cluster.manager_base import WorkerManager
from dbgpt.model.parameter import WorkerType


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
        result = await self.aembed_documents([text])
        return result[0]


class RemoteRerankEmbeddings(RerankEmbeddings):
    def __init__(self, model_name: str, worker_manager: WorkerManager) -> None:
        self.model_name = model_name
        self.worker_manager = worker_manager

    def predict(self, query: str, candidates: List[str]) -> List[float]:
        """Predict the scores of the candidates."""
        params = {
            "model": self.model_name,
            "input": candidates,
            "query": query,
            "worker_type": WorkerType.RERANKER.value,
        }
        return self.worker_manager.sync_embeddings(params)[0]

    async def apredict(self, query: str, candidates: List[str]) -> List[float]:
        """Asynchronously predict the scores of the candidates."""
        params = {
            "model": self.model_name,
            "input": candidates,
            "query": query,
            "worker_type": WorkerType.RERANKER.value,
        }
        # Use embeddings interface to get scores of ranker
        scores = await self.worker_manager.embeddings(params)
        # The first element is the scores of the query
        return scores[0]
