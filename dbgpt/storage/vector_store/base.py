"""Vector store base class."""
import logging
import math
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field, model_to_dict
from dbgpt.core import Chunk, Embeddings
from dbgpt.core.awel.flow import Parameter
from dbgpt.storage.vector_store.filters import MetadataFilters
from dbgpt.util.i18n_utils import _

logger = logging.getLogger(__name__)


_COMMON_PARAMETERS = [
    Parameter.build_from(
        _("Collection Name"),
        "name",
        str,
        description=_(
            "The name of vector store, if not set, will use the default " "name."
        ),
        optional=True,
        default="dbgpt_collection",
    ),
    Parameter.build_from(
        _("User"),
        "user",
        str,
        description=_(
            "The user of vector store, if not set, will use the default " "user."
        ),
        optional=True,
        default=None,
    ),
    Parameter.build_from(
        _("Password"),
        "password",
        str,
        description=_(
            "The password of vector store, if not set, will use the "
            "default password."
        ),
        optional=True,
        default=None,
    ),
    Parameter.build_from(
        _("Embedding Function"),
        "embedding_fn",
        Embeddings,
        description=_(
            "The embedding function of vector store, if not set, will use "
            "the default embedding function."
        ),
        optional=True,
        default=None,
    ),
    Parameter.build_from(
        _("Max Chunks Once Load"),
        "max_chunks_once_load",
        int,
        description=_(
            "The max number of chunks to load at once. If your document is "
            "large, you can set this value to a larger number to speed up the loading "
            "process. Default is 10."
        ),
        optional=True,
        default=10,
    ),
    Parameter.build_from(
        _("Max Threads"),
        "max_threads",
        int,
        description=_(
            "The max number of threads to use. Default is 1. If you set "
            "this bigger than 1, please make sure your vector store is thread-safe."
        ),
        optional=True,
        default=1,
    ),
]


class VectorStoreConfig(BaseModel):
    """Vector store config."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = Field(
        default="dbgpt_collection",
        description="The name of vector store, if not set, will use the default name.",
    )
    user: Optional[str] = Field(
        default=None,
        description="The user of vector store, if not set, will use the default user.",
    )
    password: Optional[str] = Field(
        default=None,
        description="The password of vector store, if not set, will use the default "
        "password.",
    )
    embedding_fn: Optional[Embeddings] = Field(
        default=None,
        description="The embedding function of vector store, if not set, will use the "
        "default embedding function.",
    )
    max_chunks_once_load: int = Field(
        default=10,
        description="The max number of chunks to load at once. If your document is "
        "large, you can set this value to a larger number to speed up the loading "
        "process. Default is 10.",
    )
    max_threads: int = Field(
        default=1,
        description="The max number of threads to use. Default is 1. If you set this "
        "bigger than 1, please make sure your vector store is thread-safe.",
    )

    def to_dict(self, **kwargs) -> Dict[str, Any]:
        """Convert to dict."""
        return model_to_dict(self, **kwargs)


class VectorStoreBase(ABC):
    """Vector store base class."""

    @abstractmethod
    def load_document(self, chunks: List[Chunk]) -> List[str]:
        """Load document in vector database.

        Args:
            chunks(List[Chunk]): document chunks.

        Return:
            List[str]: chunk ids.
        """

    def load_document_with_limit(
        self, chunks: List[Chunk], max_chunks_once_load: int = 10, max_threads: int = 1
    ) -> List[str]:
        """Load document in vector database with specified limit.

        Args:
            chunks(List[Chunk]): Document chunks.
            max_chunks_once_load(int): Max number of chunks to load at once.
            max_threads(int): Max number of threads to use.

        Return:
            List[str]: Chunk ids.
        """
        # Group the chunks into chunks of size max_chunks
        chunk_groups = [
            chunks[i : i + max_chunks_once_load]
            for i in range(0, len(chunks), max_chunks_once_load)
        ]
        logger.info(
            f"Loading {len(chunks)} chunks in {len(chunk_groups)} groups with "
            f"{max_threads} threads."
        )
        ids = []
        loaded_cnt = 0
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            tasks = []
            for chunk_group in chunk_groups:
                tasks.append(executor.submit(self.load_document, chunk_group))
            for future in tasks:
                success_ids = future.result()
                ids.extend(success_ids)
                loaded_cnt += len(success_ids)
                logger.info(f"Loaded {loaded_cnt} chunks, total {len(chunks)} chunks.")
        logger.info(
            f"Loaded {len(chunks)} chunks in {time.time() - start_time} seconds"
        )
        return ids

    @abstractmethod
    def similar_search(
        self, text: str, topk: int, filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        """Similar search in vector database.

        Args:
            text(str): The query text.
            topk(int): The number of similar documents to return.
            filters(Optional[MetadataFilters]): metadata filters.
        Return:
            List[Chunk]: The similar documents.
        """
        pass

    @abstractmethod
    def similar_search_with_scores(
        self,
        text,
        topk,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        """Similar search with scores in vector database.

        Args:
            text(str): The query text.
            topk(int): The number of similar documents to return.
            score_threshold(int): score_threshold: Optional, a floating point value
                between 0 to 1
            filters(Optional[MetadataFilters]): metadata filters.
        Return:
            List[Chunk]: The similar documents.
        """

    @abstractmethod
    def vector_name_exists(self) -> bool:
        """Whether vector name exists."""
        return False

    @abstractmethod
    def delete_by_ids(self, ids: str):
        """Delete vectors by ids.

        Args:
            ids(str): The ids of vectors to delete, separated by comma.
        """

    @abstractmethod
    def delete_vector_name(self, vector_name: str):
        """Delete vector by name.

        Args:
            vector_name(str): The name of vector to delete.
        """
        pass

    def convert_metadata_filters(self, filters: MetadataFilters) -> Any:
        """Convert metadata filters to vector store filters.

        Args:
            filters: (Optional[MetadataFilters]) metadata filters.
        """
        raise NotImplementedError

    def _normalization_vectors(self, vectors):
        """Return L2-normalization vectors to scale[0,1].

        Normalization vectors to scale[0,1].
        """
        import numpy as np

        norm = np.linalg.norm(vectors)
        return vectors / norm

    def _default_relevance_score_fn(self, distance: float) -> float:
        """Return a similarity score on a scale [0, 1]."""
        return 1.0 - distance / math.sqrt(2)
