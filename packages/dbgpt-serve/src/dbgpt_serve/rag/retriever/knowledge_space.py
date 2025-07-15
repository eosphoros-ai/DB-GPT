import ast
import json
import logging
from typing import Any, List, Optional

from dbgpt.component import ComponentType, SystemApp
from dbgpt.core import Chunk, Document, LLMClient
from dbgpt.model import DefaultLLMClient
from dbgpt.model.cluster import WorkerManagerFactory
from dbgpt.rag.embedding.embedding_factory import EmbeddingFactory
from dbgpt.rag.retriever import EmbeddingRetriever, QueryRewrite, Ranker
from dbgpt.rag.retriever.base import BaseRetriever, RetrieverStrategy
from dbgpt.rag.transformer.keyword_extractor import KeywordExtractor
from dbgpt.storage.vector_store.filters import MetadataFilters
from dbgpt.util.executor_utils import ExecutorFactory
from dbgpt_ext.rag.retriever.doc_tree import TreeNode
from dbgpt_serve.rag.models.models import KnowledgeSpaceDao
from dbgpt_serve.rag.retriever.qa_retriever import QARetriever
from dbgpt_serve.rag.retriever.retriever_chain import RetrieverChain
from dbgpt_serve.rag.storage_manager import StorageManager

logger = logging.getLogger(__name__)


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
        retrieve_mode: Optional[str] = None,
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

        space_dao = KnowledgeSpaceDao()
        self._space = space_dao.get_one({"id": space_id})
        if self._space is None:
            self._space = space_dao.get_one({"name": space_id})
        if self._space is None:
            raise ValueError(f"Knowledge space {space_id} not found")
        self._storage_connector = self.storage_manager.get_storage_connector(
            self._space.name,
            self._space.vector_type,
            self._llm_model,
        )
        context_retrieve_mode = self._extract_space_retrieve_mode(self._space)
        self._retrieve_mode = (
            retrieve_mode or context_retrieve_mode or RetrieverStrategy.SEMANTIC.value
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
                    index_store=self._storage_connector,
                    top_k=self._top_k,
                    query_rewrite=self._query_rewrite,
                    rerank=self._rerank,
                ),
            ],
            executor=self._executor,
        )

    @property
    def storage_manager(self):
        return StorageManager.get_instance(self._system_app)

    @property
    def rag_service(self):
        from dbgpt_serve.rag.service.service import Service as RagService

        return RagService.get_instance(self._system_app)

    @property
    def llm_client(self) -> LLMClient:
        worker_manager = self._system_app.get_component(
            ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
        ).create()
        return DefaultLLMClient(worker_manager, True)

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
        candidates = await self._aretrieve_with_score(query, 0.0, filters)
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
        if self._retrieve_mode == RetrieverStrategy.SEMANTIC.value:
            logger.info("Starting Semantic retrieval")
            return await self.semantic_retrieve(query, score_threshold, filters)
        elif self._retrieve_mode == RetrieverStrategy.KEYWORD.value:
            logger.info("Starting Full Text retrieval")
            return await self.full_text_retrieve(query, self._top_k, filters)
        elif self._retrieve_mode == RetrieverStrategy.Tree.value:
            logger.info("Starting Doc Tree retrieval")
            return await self.tree_index_retrieve(query, self._top_k, filters)
        elif self._retrieve_mode == RetrieverStrategy.HYBRID.value:
            logger.info("Starting Hybrid retrieval")
            tasks = []
            import asyncio

            tasks.append(self.semantic_retrieve(query, score_threshold, filters))
            tasks.append(self.full_text_retrieve(query, self._top_k, filters))
            tasks.append(self.tree_index_retrieve(query, self._top_k, filters))
            results = await asyncio.gather(*tasks)
            semantic_candidates = results[0]
            full_text_candidates = results[1]
            tree_candidates = results[2]
            logger.info(
                f"Hybrid retrieval completed. "
                f"Found {len(semantic_candidates)} semantic candidates "
                f"and Found {len(full_text_candidates)} full text candidates."
                f"and Found {len(tree_candidates)} tree candidates."
            )
            candidates = semantic_candidates + full_text_candidates + tree_candidates
            # Remove duplicates
            unique_candidates = {chunk.content: chunk for chunk in candidates}
            return list(unique_candidates.values())

    async def semantic_retrieve(
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

    async def full_text_retrieve(
        self,
        query: str,
        top_k: int,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        """Full Text Retrieve knowledge chunks with score.
        refer https://www.elastic.co/guide/en/elasticsearch/reference/8.9/
        index-modules-similarity.html;
        TF/IDF or BM25 based similarity that has built-in tf normalization and is
        supposed to work better for short fields (like names).
        See Okapi_BM25 for more details.

        Args:
            query (str): query text.
            top_k (int): top k limit.
            filters: (Optional[MetadataFilters]) metadata filters.

        Return:
            List[Chunk]: list of chunks with score.
        """
        if self._storage_connector.is_support_full_text_search():
            return await self._storage_connector.afull_text_search(
                query, top_k, filters
            )
        else:
            logger.warning(
                "Full text search is not supported for this storage connector."
            )
            return []

    async def tree_index_retrieve(
        self, query: str, top_k: int, filters: Optional[MetadataFilters] = None
    ):
        """Search for keywords in the tree index."""
        # Check if the keyword is in the node title
        # If the node has children, recursively search in them
        # If the node is a leaf, check if it contains the keyword
        try:
            docs_res = self.rag_service.get_document_list(
                {
                    "space": self._space.name,
                }
            )
            docs = []
            for doc_res in docs_res:
                doc = Document(
                    content=doc_res.content,
                )
                chunks_res = self.rag_service.get_chunk_list(
                    {
                        "document_id": doc_res.id,
                    }
                )
                chunks = [
                    Chunk(
                        content=chunk_res.content,
                        metadata=ast.literal_eval(chunk_res.meta_info),
                    )
                    for chunk_res in chunks_res
                ]
                doc.chunks = chunks
                docs.append(doc)
            keyword_extractor = KeywordExtractor(
                llm_client=self.llm_client, model_name=self._llm_model
            )
            from dbgpt_ext.rag.retriever.doc_tree import DocTreeRetriever

            tree_retriever = DocTreeRetriever(
                docs=docs,
                keywords_extractor=keyword_extractor,
                top_k=self._top_k,
                query_rewrite=self._query_rewrite,
                with_content=True,
                rerank=self._rerank,
            )
            candidates = []
            tree_nodes = await tree_retriever.aretrieve_with_scores(
                query, top_k, filters
            )
            # Convert tree nodes to chunks
            for node in tree_nodes:
                chunks = self._traverse(node)
                candidates.extend(chunks)
            return candidates
        except Exception as e:
            logger.error(f"Error in tree index retrieval: {e}")
            return []

    def _traverse(self, node: TreeNode):
        """Traverse the tree and search for the keyword."""
        # Check if the node has children
        result = []
        if node.children:
            for child in node.children:
                result.extend(self._traverse(child))
        else:
            # If the node is a leaf, check if it contains the keyword
            if node:
                result.append(
                    Chunk(
                        content=node.content,
                        retriever=node.retriever,
                    )
                )
        return result

    def _extract_space_retrieve_mode(self, space: Any) -> str | None:
        """Extract space context and retrieve mode."""
        if space.context is not None:
            try:
                context = json.loads(space.context)
                if not isinstance(context, dict):
                    return None
                embedding_config = context.get("embedding", {})
                if not isinstance(embedding_config, dict):
                    return None
                retrieve_mode = embedding_config.get("retrieve_mode")
                if retrieve_mode is None:
                    return None
                for strategy in RetrieverStrategy:
                    if retrieve_mode == strategy.name:
                        return strategy.value
            except Exception as e:
                logger.warning(f"Failed to parse space context: {e}")
        return None
