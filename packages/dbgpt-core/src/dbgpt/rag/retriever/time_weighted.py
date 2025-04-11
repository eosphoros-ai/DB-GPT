"""Time weighted retriever with external storage support."""

import datetime
import logging
from copy import deepcopy
from typing import Any, Dict, List, Optional, Protocol, Tuple

from dbgpt.core import Chunk
from dbgpt.rag.retriever.rerank import Ranker
from dbgpt.rag.retriever.rewrite import QueryRewrite
from dbgpt.storage.base import IndexStoreBase
from dbgpt.storage.vector_store.filters import MetadataFilters

from .embedding import EmbeddingRetriever

logger = logging.getLogger(__name__)


class DocumentStorage(Protocol):
    """Protocol for external document storage."""

    def get_all_documents(self) -> List[Chunk]:
        """Get all documents from storage.

        Returns:
            List of document chunks
        """
        ...

    def save_documents(self, documents: List[Chunk]) -> bool:
        """Save documents to storage.

        Args:
            documents: List of document chunks to save

        Returns:
            Boolean indicating success
        """
        ...


def _get_hours_passed(time: datetime.datetime, ref_time: datetime.datetime) -> float:
    """Get the hours passed between two datetime objects."""
    return (time - ref_time).total_seconds() / 3600


class TimeWeightedEmbeddingRetriever(EmbeddingRetriever):
    """Time weighted embedding retriever with external storage support."""

    def __init__(
        self,
        index_store: IndexStoreBase,
        top_k: int = 100,
        query_rewrite: Optional[QueryRewrite] = None,
        rerank: Optional[Ranker] = None,
        decay_rate: float = 0.01,
        external_storage: Optional[DocumentStorage] = None,
    ):
        """Initialize TimeWeightedEmbeddingRetriever.

        Args:
            index_store (IndexStoreBase): vector store connector
            top_k (int): top k results to retrieve
            query_rewrite (Optional[QueryRewrite]): query rewrite component
            rerank (Ranker): reranking component
            decay_rate (float): rate at which relevance decays over time
            external_storage (Optional[DocumentStorage]): external storage for
                persistence
        """
        super().__init__(
            index_store=index_store,
            top_k=top_k,
            query_rewrite=query_rewrite,
            rerank=rerank,
        )
        self.memory_stream: List[Chunk] = []
        self.other_score_keys: List[str] = []
        self.decay_rate: float = decay_rate
        self.default_salience: Optional[float] = None
        self._top_k = top_k
        self._k = 4
        self._external_storage = external_storage
        self._use_vector_store_only = False

        # Initialize memory stream
        self._initialize_memory_stream()

    def _initialize_memory_stream(self) -> None:
        """Initialize memory stream from external storage."""
        if self._external_storage:
            try:
                self.memory_stream = self._external_storage.get_all_documents()
                logger.info(
                    "Loaded memory stream from external storage with "
                    f"{len(self.memory_stream)} documents"
                )
                return
            except Exception as e:
                logger.error(f"Failed to load memory stream from external storage: {e}")

        # If external storage is not available or loading failed, operate in vector
        # store only mode
        self._use_vector_store_only = True
        logger.info("No memory stream available. Operating in vector store only mode.")

    def _save_memory_stream(self) -> None:
        """Save memory stream to external storage."""
        if self._external_storage and self.memory_stream:
            try:
                success = self._external_storage.save_documents(self.memory_stream)
                if success:
                    logger.debug(
                        f"Saved {len(self.memory_stream)} documents to external storage"
                    )
                else:
                    logger.warning("Failed to save documents to external storage")
            except Exception as e:
                logger.error(f"Error saving documents to external storage: {e}")

    def load_document(self, chunks: List[Chunk], **kwargs: Dict[str, Any]) -> List[str]:
        """Load document chunks into vector database.

        Args:
            chunks: document chunks to be loaded
            **kwargs: additional parameters including current_time

        Returns:
            List of chunk IDs
        """
        current_time: Optional[datetime.datetime] = kwargs.get("current_time")  # type: ignore # noqa
        if current_time is None:
            current_time = datetime.datetime.now()

        # Avoid mutating input documents
        dup_docs = [deepcopy(d) for d in chunks]

        # Generate buffer indices for new documents
        for i, doc in enumerate(dup_docs):
            if doc.metadata.get("last_accessed_at") is None:
                doc.metadata["last_accessed_at"] = current_time
            if "created_at" not in doc.metadata:
                doc.metadata["created_at"] = current_time
            doc.metadata["buffer_idx"] = len(self.memory_stream) + i

        # Add to memory stream
        self.memory_stream.extend(dup_docs)

        # Save memory stream after adding new documents
        self._save_memory_stream()

        # Add to vector store
        return self._index_store.load_document_with_limit(dup_docs)

    def _retrieve(
        self, query: str, filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        """Retrieve knowledge chunks based on query.

        Args:
            query (str): query text
            filters: metadata filters

        Returns:
            List[Chunk]: list of relevant chunks
        """
        current_time = datetime.datetime.now()

        if self._use_vector_store_only:
            # If operating in vector store only mode, perform similar search
            # and apply time weighting directly on the results
            docs_and_scores = self._index_store.similar_search_with_scores(
                query, topk=self._top_k, score_threshold=0, filters=filters
            )

            # Apply time weighting to vector store results
            rescored_docs = []
            for doc in docs_and_scores:
                # Extract time information from metadata
                if "last_accessed_at" in doc.metadata and "created_at" in doc.metadata:
                    rescored_docs.append(
                        (doc, self._get_combined_score(doc, doc.score, current_time))
                    )
                else:
                    # If time info not available, just use vector similarity
                    rescored_docs.append((doc, doc.score))

            # Sort by combined score
            rescored_docs.sort(key=lambda x: x[1], reverse=True)

            # Return top k results
            return [doc for doc, _ in rescored_docs[: self._k]]

        # Normal operation with memory stream
        # Get the most recent documents
        docs_and_scores = {}
        if self.memory_stream:
            docs_and_scores = {
                doc.metadata["buffer_idx"]: (doc, self.default_salience)
                for doc in self.memory_stream[-self._k :]
                if "buffer_idx" in doc.metadata
            }

        # If a doc is considered salient, update the salience score
        docs_and_scores.update(self.get_salient_docs(query, filters))

        # If no documents found, fall back to vector store query with time weighting
        if not docs_and_scores:
            return self._retrieve_vector_store_only(query, filters, current_time)

        rescored_docs = [
            (doc, self._get_combined_score(doc, relevance, current_time))
            for doc, relevance in docs_and_scores.values()
        ]

        rescored_docs.sort(key=lambda x: x[1], reverse=True)
        result = []

        # Ensure frequently accessed memories aren't forgotten
        for doc, _ in rescored_docs[: self._k]:
            if "buffer_idx" in doc.metadata:
                buffer_idx = doc.metadata["buffer_idx"]
                if 0 <= buffer_idx < len(self.memory_stream):
                    buffered_doc = self.memory_stream[buffer_idx]
                    buffered_doc.metadata["last_accessed_at"] = current_time
                    result.append(buffered_doc)
                else:
                    # If buffer_idx is invalid, still return the document from vector
                    # store
                    result.append(doc)
            else:
                result.append(doc)

        # Save memory stream after updating access times
        self._save_memory_stream()

        return result

    def _retrieve_vector_store_only(
        self,
        query: str,
        filters: Optional[MetadataFilters],
        current_time: datetime.datetime,
    ) -> List[Chunk]:
        """Retrieve and apply time weighting using only vector store.

        Args:
            query: User query text
            filters: Optional metadata filters
            current_time: Current time for calculating decay

        Returns:
            List of relevant chunks
        """
        # Get documents from vector store
        docs = self._index_store.similar_search_with_scores(
            query, topk=self._top_k, score_threshold=0, filters=filters
        )

        # Apply time weighting
        rescored_docs = []
        for doc in docs:
            # Update last_accessed_at time if it exists
            if "last_accessed_at" in doc.metadata:
                last_accessed_time = doc.metadata["last_accessed_at"]
                hours_passed = _get_hours_passed(current_time, last_accessed_time)
                time_score = (1.0 - self.decay_rate) ** hours_passed
                # Combine with vector similarity score
                combined_score = doc.score + time_score
                rescored_docs.append((doc, combined_score))
            else:
                # Just use vector similarity if no time data
                rescored_docs.append((doc, doc.score))

        # Sort by combined score
        rescored_docs.sort(key=lambda x: x[1], reverse=True)

        # Return top results
        return [doc for doc, _ in rescored_docs[: self._k]]

    def _get_combined_score(
        self,
        chunk: Chunk,
        vector_relevance: Optional[float],
        current_time: datetime.datetime,
    ) -> float:
        """Calculate combined score for a document based on time decay and relevance.

        Args:
            chunk: The document chunk
            vector_relevance: Vector similarity score
            current_time: Current time for calculating decay

        Returns:
            Combined score value
        """
        # Default last_accessed_at to creation time if not present
        last_accessed_at = chunk.metadata.get("last_accessed_at")
        if last_accessed_at is None:
            last_accessed_at = chunk.metadata.get("created_at", current_time)

        hours_passed = _get_hours_passed(current_time, last_accessed_at)
        score = (1.0 - self.decay_rate) ** hours_passed

        for key in self.other_score_keys:
            if key in chunk.metadata:
                score += chunk.metadata[key]

        if vector_relevance is not None:
            score += vector_relevance

        return score

    def get_salient_docs(
        self, query: str, filters: Optional[MetadataFilters] = None
    ) -> Dict[int, Tuple[Chunk, float]]:
        """Find documents that are relevant to the query.

        Args:
            query: User query text
            filters: Optional metadata filters

        Returns:
            Dictionary mapping buffer indices to (document, score) tuples
        """
        docs_and_scores: List[Chunk]
        docs_and_scores = self._index_store.similar_search_with_scores(
            query, topk=self._top_k, score_threshold=0, filters=filters
        )

        results = {}
        for ck in docs_and_scores:
            if "buffer_idx" in ck.metadata:
                buffer_idx = ck.metadata["buffer_idx"]
                # Add error handling to prevent IndexError
                if 0 <= buffer_idx < len(self.memory_stream):
                    doc = self.memory_stream[buffer_idx]
                    results[buffer_idx] = (doc, ck.score)
                else:
                    # If buffer_idx is out of range, still include document but with
                    # original
                    results[buffer_idx] = (ck, ck.score)

        return results

    def set_external_storage(self, storage: DocumentStorage) -> None:
        """Set external storage and reload memory stream.

        Args:
            storage: External document storage
        """
        self._external_storage = storage
        self._use_vector_store_only = False
        self._initialize_memory_stream()

    def sync_with_external_storage(self) -> None:
        """Sync memory stream with external storage."""
        if self._external_storage:
            try:
                self.memory_stream = self._external_storage.get_all_documents()
                self._use_vector_store_only = False
                logger.info(
                    "Synced memory stream from external storage with "
                    f"{len(self.memory_stream)} documents"
                )
            except Exception as e:
                logger.error(f"Failed to sync memory stream from external storage: {e}")
