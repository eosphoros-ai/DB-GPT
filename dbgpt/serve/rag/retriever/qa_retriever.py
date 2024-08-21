import ast
import json
import logging
from typing import Any, List, Optional

from dbgpt._private.config import Config
from dbgpt.app.knowledge.chunk_db import DocumentChunkDao, DocumentChunkEntity
from dbgpt.app.knowledge.document_db import KnowledgeDocumentDao
from dbgpt.component import ComponentType
from dbgpt.core import Chunk
from dbgpt.rag.retriever.base import BaseRetriever
from dbgpt.serve.rag.models.models import KnowledgeSpaceDao, KnowledgeSpaceEntity
from dbgpt.storage.vector_store.filters import MetadataFilters
from dbgpt.util.executor_utils import ExecutorFactory, blocking_func_to_async
from dbgpt.util.similarity_util import calculate_cosine_similarity
from dbgpt.util.string_utils import remove_trailing_punctuation

CFG = Config()
CHUNK_PAGE_SIZE = 1000
logger = logging.getLogger(__name__)


class QARetriever(BaseRetriever):
    """Document QA retriever."""

    def __init__(
        self,
        space_id: str = None,
        top_k: Optional[int] = 4,
        embedding_fn: Optional[Any] = 4,
        lambda_value: Optional[float] = 1e-5,
    ):
        """
        Args:
            space_id (str): knowledge space name
            top_k (Optional[int]): top k
        """
        if space_id is None:
            raise ValueError("space_id is required")
        self._top_k = top_k
        self._lambda_value = lambda_value
        self._space_dao = KnowledgeSpaceDao()
        self._document_dao = KnowledgeDocumentDao()
        self._chunk_dao = DocumentChunkDao()
        self._embedding_fn = embedding_fn

        space = self._space_dao.get_one({"id": space_id})
        if not space:
            raise ValueError("space not found")
        self.documents = self._document_dao.get_list({"space": space.name})
        self._executor = CFG.SYSTEM_APP.get_component(
            ComponentType.EXECUTOR_DEFAULT, ExecutorFactory
        ).create()

    def _retrieve(
        self, query: str, filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        """Retrieve knowledge chunks.
        Args:
            query (str): query text
            filters: (Optional[MetadataFilters]) metadata filters.
        Return:
            List[Chunk]: list of chunks
        """
        query = remove_trailing_punctuation(query)
        candidate_results = []
        for doc in self.documents:
            if doc.questions:
                questions = json.loads(doc.questions)
                if query in questions:
                    chunks = self._chunk_dao.get_document_chunks(
                        DocumentChunkEntity(document_id=doc.id),
                        page_size=CHUNK_PAGE_SIZE,
                    )
                    candidates = [
                        Chunk(
                            content=chunk.content,
                            metadata=ast.literal_eval(chunk.meta_info),
                            retriever=self.name(),
                            score=0.0,
                        )
                        for chunk in chunks
                    ]
                    candidate_results.extend(
                        self._cosine_similarity_rerank(candidates, query)
                    )
        return candidate_results

    def _retrieve_with_score(
        self,
        query: str,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
        lambda_value: Optional[float] = None,
    ) -> List[Chunk]:
        """Retrieve knowledge chunks with score.
        Args:
            query (str): query text
            score_threshold (float): score threshold
            filters: (Optional[MetadataFilters]) metadata filters.
        Return:
            List[Chunk]: list of chunks with score
        """
        query = remove_trailing_punctuation(query)
        candidate_results = []
        doc_ids = [doc.id for doc in self.documents]
        query_param = DocumentChunkEntity()
        chunks = self._chunk_dao.get_chunks_with_questions(
            query=query_param, document_ids=doc_ids
        )
        for chunk in chunks:
            if chunk.questions:
                questions = json.loads(chunk.questions)
                if query in questions:
                    logger.info(f"qa chunk hit:{chunk}, question:{query}")
                    candidate_results.append(
                        Chunk(
                            content=chunk.content,
                            chunk_id=str(chunk.id),
                            metadata={"prop_field": ast.literal_eval(chunk.meta_info)},
                            retriever=self.name(),
                            score=1.0,
                        )
                    )
        if len(candidate_results) > 0:
            return self._cosine_similarity_rerank(candidate_results, query)

        for doc in self.documents:
            if doc.questions:
                questions = json.loads(doc.questions)
                if query in questions:
                    logger.info(f"qa document hit:{doc}, question:{query}")
                    chunks = self._chunk_dao.get_document_chunks(
                        DocumentChunkEntity(document_id=doc.id),
                        page_size=CHUNK_PAGE_SIZE,
                    )
                    candidates_with_scores = [
                        Chunk(
                            content=chunk.content,
                            chunk_id=str(chunk.id),
                            metadata={"prop_field": ast.literal_eval(chunk.meta_info)},
                            retriever=self.name(),
                            score=1.0,
                        )
                        for chunk in chunks
                    ]
                    candidate_results.extend(
                        self._cosine_similarity_rerank(candidates_with_scores, query)
                    )
        return candidate_results

    async def _aretrieve(
        self, query: str, filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        """Retrieve knowledge chunks.
        Args:
            query (str): query text
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
            query (str): query text
            score_threshold (float): score threshold
            filters: (Optional[MetadataFilters]) metadata filters.
        Return:
            List[Chunk]: list of chunks with score
        """
        candidates_with_score = await blocking_func_to_async(
            self._executor, self._retrieve_with_score, query, score_threshold, filters
        )
        return candidates_with_score

    def _cosine_similarity_rerank(
        self, candidates_with_scores: List[Chunk], query: str
    ) -> List[Chunk]:
        """Rerank candidates using cosine similarity."""
        if len(candidates_with_scores) > self._top_k:
            for candidate in candidates_with_scores:
                similarity = calculate_cosine_similarity(
                    embeddings=self._embedding_fn,
                    prediction=query,
                    contexts=[candidate.content],
                )
                score = float(similarity.mean())
                candidate.score = score
            candidates_with_scores.sort(key=lambda x: x.score, reverse=True)
            candidates_with_scores = candidates_with_scores[: self._top_k]
            candidates_with_scores = [
                Chunk(
                    content=candidate.content,
                    chunk_id=candidate.chunk_id,
                    metadata=candidate.metadata,
                    retriever=self.name(),
                    score=1.0,
                )
                for candidate in candidates_with_scores
            ]
        return candidates_with_scores

    @classmethod
    def name(cls):
        """Return retriever name."""
        return "qa_retriever"
