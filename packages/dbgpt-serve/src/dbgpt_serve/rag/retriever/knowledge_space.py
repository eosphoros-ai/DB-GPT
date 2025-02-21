from typing import List, Optional

from dbgpt.component import ComponentType, SystemApp
from dbgpt.core import Chunk
from dbgpt.model import DefaultLLMClient
from dbgpt.model.cluster import WorkerManagerFactory
from dbgpt.rag.embedding.embedding_factory import EmbeddingFactory
from dbgpt.rag.retriever import EmbeddingRetriever, QueryRewrite, Ranker
from dbgpt.rag.retriever.base import BaseRetriever
from dbgpt.storage.vector_store.filters import MetadataFilters
from dbgpt.util.executor_utils import ExecutorFactory, blocking_func_to_async
from dbgpt_serve.rag.connector import VectorStoreConnector
from dbgpt_serve.rag.models.models import KnowledgeSpaceDao
from dbgpt_serve.rag.retriever.qa_retriever import QARetriever
from dbgpt_serve.rag.retriever.retriever_chain import RetrieverChain


class KnowledgeSpaceRetriever(BaseRetriever):
    """Knowledge Space retriever."""

    def __init__(
        self,
        space_id: str = None,
        top_k: Optional[int] = 4,
        query_rewrite: Optional[QueryRewrite] = None,
        rerank: Optional[Ranker] = None,
        llm_model: Optional[str] = None,
        embedding_model: Optional[str] = None,
        system_app: SystemApp = None,
    ):
        """
        Args:
            space_id (str): knowledge space name
            top_k (Optional[int]): top k
            query_rewrite: (Optional[QueryRewrite]) query rewrite
            rerank: (Optional[Ranker]) rerank
        """
        if space_id is None:
            raise ValueError("space_id is required")
        self._space_id = space_id
        self._query_rewrite = query_rewrite
        self._rerank = rerank
        self._llm_model = llm_model
        app_config = system_app.config.configs.get("app_config")
        self._top_k = top_k or app_config.rag.similarity_top_k
        self._embedding_model = embedding_model or app_config.models.default_embedding
        self._system_app = system_app
        embedding_factory = self._system_app.get_component(
            "embedding_factory", EmbeddingFactory
        )
        embedding_fn = embedding_factory.create()
        from dbgpt.storage.vector_store.base import VectorStoreConfig

        space_dao = KnowledgeSpaceDao()
        space = space_dao.get_one({"id": space_id})
        if space is None:
            space = space_dao.get_one({"name": space_id})
        if space is None:
            raise ValueError(f"Knowledge space {space_id} not found")
        worker_manager = self._system_app.get_component(
            ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
        ).create()
        llm_client = DefaultLLMClient(worker_manager=worker_manager)
        config = VectorStoreConfig(
            name=space.name,
            embedding_fn=embedding_fn,
            llm_client=llm_client,
            llm_model=self._llm_model,
        )

        self._vector_store_connector = VectorStoreConnector(
            vector_store_type=space.vector_type,
            vector_store_config=config,
            system_app=self._system_app,
        )
        self._executor = self._system_app.get_component(
            ComponentType.EXECUTOR_DEFAULT, ExecutorFactory
        ).create()

        self._retriever_chain = RetrieverChain(
            retrievers=[
                QARetriever(
                    space_id=space_id,
                    top_k=self._top_k,
                    embedding_fn=embedding_fn,
                    system_app=system_app,
                ),
                EmbeddingRetriever(
                    index_store=self._vector_store_connector.index_client,
                    top_k=self._top_k,
                    query_rewrite=self._query_rewrite,
                    rerank=self._rerank,
                ),
            ],
            executor=self._executor,
        )

    def _retrieve(
        self, query: str, filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        """Retrieve knowledge chunks.

        Args:
            query (str): query text.
            filters: (Optional[MetadataFilters]) metadata filters.

        Return:
            List[Chunk]: list of chunks
        """
        candidates = self._retriever_chain.retrieve(query=query, filters=filters)
        return candidates

    def _retrieve_with_score(
        self,
        query: str,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        """Retrieve knowledge chunks with score.

        Args:
            query (str): query text
            score_threshold (float): score threshold
            filters: (Optional[MetadataFilters]) metadata filters.

        Return:
            List[Chunk]: list of chunks with score
        """
        candidates_with_scores = self._retriever_chain.retrieve_with_scores(
            query, score_threshold, filters
        )
        return candidates_with_scores

    async def _aretrieve(
        self, query: str, filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        """Retrieve knowledge chunks.

        Args:
            query (str): query text.
            filters: (Optional[MetadataFilters]) metadata filters.

        Return:
            List[Chunk]: list of chunks
        """
        candidates = await blocking_func_to_async(
            self._executor, self._retrieve, query, filters
        )
        return candidates

    async def _aretrieve_with_score(
        self,
        query: str,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        """Retrieve knowledge chunks with score.

        Args:
            query (str): query text.
            score_threshold (float): score threshold.
            filters: (Optional[MetadataFilters]) metadata filters.

        Return:
            List[Chunk]: list of chunks with score.
        """
        return await self._retriever_chain.aretrieve_with_scores(
            query, score_threshold, filters
        )
