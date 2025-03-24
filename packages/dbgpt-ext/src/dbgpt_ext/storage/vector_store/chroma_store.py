"""Chroma vector store."""

import hashlib
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Union

from dbgpt.configs.model_config import PILOT_PATH, resolve_root_path
from dbgpt.core import Chunk, Embeddings
from dbgpt.core.awel.flow import Parameter, ResourceCategory, register_resource
from dbgpt.storage.vector_store.base import (
    _COMMON_PARAMETERS,
    _VECTOR_STORE_COMMON_PARAMETERS,
    VectorStoreBase,
    VectorStoreConfig,
)
from dbgpt.storage.vector_store.filters import FilterOperator, MetadataFilters
from dbgpt.util import string_utils
from dbgpt.util.i18n_utils import _

logger = logging.getLogger(__name__)


@register_resource(
    _("Chroma Config"),
    "chroma_vector_config",
    category=ResourceCategory.VECTOR_STORE,
    description=_("Chroma vector store config."),
    parameters=[
        *_COMMON_PARAMETERS,
        Parameter.build_from(
            _("Persist Path"),
            "persist_path",
            str,
            description=_("the persist path of vector store."),
            optional=True,
            default=None,
        ),
    ],
)
@dataclass
class ChromaVectorConfig(VectorStoreConfig):
    """Chroma vector store config."""

    __type__ = "chroma"

    persist_path: Optional[str] = field(
        default=os.getenv("CHROMA_PERSIST_PATH", None),
        metadata={
            "help": _("The persist path of vector store."),
        },
    )
    collection_metadata: Optional[dict] = field(
        default=None,
        metadata={
            "help": _("The metadata of collection."),
        },
    )

    def create_store(self, **kwargs) -> "ChromaStore":
        """Create index store."""
        return ChromaStore(vector_store_config=self, **kwargs)


@register_resource(
    _("Chroma Vector Store"),
    "chroma_vector_store",
    category=ResourceCategory.VECTOR_STORE,
    description=_("Chroma vector store."),
    parameters=[
        Parameter.build_from(
            _("Chroma Config"),
            "vector_store_config",
            ChromaVectorConfig,
            description=_("the chroma config of vector store."),
            optional=True,
            default=None,
        ),
        *_VECTOR_STORE_COMMON_PARAMETERS,
    ],
)
class ChromaStore(VectorStoreBase):
    """Chroma vector store."""

    def __init__(
        self,
        vector_store_config: ChromaVectorConfig,
        name: Optional[str],
        embedding_fn: Optional[Embeddings] = None,
        chroma_client: Optional["PersistentClient"] = None,  # type: ignore # noqa
        collection_metadata: Optional[dict] = None,
    ) -> None:
        """Create a ChromaStore instance.

        Args:
            vector_store_config(ChromaVectorConfig): vector store config.
            name(str): collection name.
            embedding_fn(Embeddings): embedding function.
            chroma_client(PersistentClient): chroma client.
            collection_metadata(dict): collection metadata.
        """
        super().__init__()
        self._vector_store_config = vector_store_config
        try:
            from chromadb import PersistentClient, Settings
        except ImportError:
            raise ImportError("Please install chroma package first.")
        chroma_vector_config = vector_store_config.to_dict()
        chroma_path = chroma_vector_config.get(
            "persist_path", os.path.join(PILOT_PATH, "data")
        )
        self.persist_dir = os.path.join(resolve_root_path(chroma_path) + "/chromadb")
        self.embeddings = embedding_fn
        if not self.embeddings:
            raise ValueError("Embeddings is None")
        self._collection_name = name
        if not _valid_chroma_collection_name(name):
            hash_object = hashlib.sha256(name.encode("utf-8"))
            hex_hash = hash_object.hexdigest()
            # ensure the collection name is less than 64 characters
            self._collection_name = hex_hash[:63] if len(hex_hash) > 63 else hex_hash
        chroma_settings = Settings(
            # chroma_db_impl="duckdb+parquet", => deprecated configuration of Chroma
            persist_directory=self.persist_dir,
            anonymized_telemetry=False,
        )
        self._chroma_client = chroma_client
        if not self._chroma_client:
            self._chroma_client = PersistentClient(
                path=self.persist_dir, settings=chroma_settings
            )
        collection_metadata = collection_metadata or {"hnsw:space": "cosine"}

        self._collection = self._chroma_client.get_or_create_collection(
            name=self._collection_name,
            embedding_function=None,
            metadata=collection_metadata,
        )

    def get_config(self) -> ChromaVectorConfig:
        """Get the vector store config."""
        return self._vector_store_config

    def similar_search(
        self, text, topk, filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        """Search similar documents."""
        logger.info("ChromaStore similar search")
        chroma_results = self._query(
            text=text,
            topk=topk,
            filters=filters,
        )
        return [
            Chunk(
                content=chroma_result[0],
                metadata=chroma_result[1] or {},
                score=0.0,
                chunk_id=chroma_result[2],
            )
            for chroma_result in zip(
                chroma_results["documents"][0],
                chroma_results["metadatas"][0],
                chroma_results["ids"][0],
            )
        ]

    def similar_search_with_scores(
        self, text, topk, score_threshold, filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        """Search similar documents with scores.

        Chroma similar_search_with_score.
        Return docs and relevance scores in the range [0, 1].
        Args:
            text(str): query text
            topk(int): return docs nums. Defaults to 4.
            score_threshold(float): score_threshold: Optional, a floating point value
                between 0 to 1 to filter the resulting set of retrieved docs,0 is
                dissimilar, 1 is most similar.
            filters(MetadataFilters): metadata filters, defaults to None
        """
        logger.info("ChromaStore similar search with scores")
        chroma_results = self._query(
            text=text,
            topk=topk,
            filters=filters,
        )
        chunks = [
            (
                Chunk(
                    content=chroma_result[0],
                    metadata=chroma_result[1] or {},
                    score=(1 - chroma_result[2]),
                    chunk_id=chroma_result[3],
                )
            )
            for chroma_result in zip(
                chroma_results["documents"][0],
                chroma_results["metadatas"][0],
                chroma_results["distances"][0],
                chroma_results["ids"][0],
            )
        ]
        return self.filter_by_score_threshold(chunks, score_threshold)

    def vector_name_exists(self) -> bool:
        """Whether vector name exists."""
        try:
            collection = self._chroma_client.get_collection(self._collection_name)
            return collection.count() > 0
        except Exception as _e:
            logger.info(f"Collection {self._collection_name} does not exist")
            return False

    def load_document(self, chunks: List[Chunk]) -> List[str]:
        """Load document to vector store."""
        logger.info("ChromaStore load document")
        texts = [chunk.content for chunk in chunks]
        metadatas = [chunk.metadata for chunk in chunks]
        ids = [chunk.chunk_id for chunk in chunks]
        chroma_metadatas = [
            _transform_chroma_metadata(metadata) for metadata in metadatas
        ]
        self._add_texts(texts=texts, metadatas=chroma_metadatas, ids=ids)
        return ids

    def delete_vector_name(self, vector_name: str):
        """Delete vector name and clean up resources.

        Args:
            vector_name (str): Name of the vector to delete

        Returns:
            bool: True if deletion was successful, False otherwise

        Raises:
            Exception: If any error occurs during deletion
        """
        try:
            from chromadb.api.client import SharedSystemClient
        except ImportError:
            raise ImportError("Please install chroma package first.")

        logger.info(f"chroma vector_name:{vector_name} begin delete...")

        try:
            # Check if collection exists first
            collections = self._chroma_client.list_collections()
            collection_exists = self._collection.name in collections

            if not collection_exists:
                logger.warning(
                    f"Collection {self._collection.name} does not exist, skip delete"
                )
                return True

            # Delete collection if it exists
            self._chroma_client.delete_collection(self._collection.name)
            SharedSystemClient.clear_system_cache()
            return True

        except Exception as e:
            logger.error(f"Error during vector store deletion: {e}")
            raise

    def delete_by_ids(self, ids):
        """Delete vector by ids."""
        logger.info(f"begin delete chroma ids: {ids}")
        ids = ids.split(",")
        if len(ids) > 0:
            self._collection.delete(ids=ids)

    def truncate(self) -> List[str]:
        """Truncate data index_name."""
        logger.info(f"begin truncate chroma collection:{self._collection.name}")
        results = self._collection.get()
        ids = results.get("ids")
        if ids:
            self._collection.delete(ids=ids)
            logger.info(
                f"truncate chroma collection {self._collection.name} "
                f"{len(ids)} chunks success"
            )
            return ids
        return []

    def convert_metadata_filters(
        self,
        filters: MetadataFilters,
    ) -> dict:
        """Convert metadata filters to Chroma filters.

        Args:
            filters(MetadataFilters): metadata filters.
        Returns:
            dict: Chroma filters.
        """
        where_filters = {}
        filters_list = []
        condition = filters.condition
        chroma_condition = f"${condition.value}"
        if filters.filters:
            for filter in filters.filters:
                if filter.operator:
                    filters_list.append(
                        {
                            filter.key: {
                                _convert_chroma_filter_operator(
                                    filter.operator
                                ): filter.value
                            }
                        }
                    )
                else:
                    filters_list.append({filter.key: filter.value})  # type: ignore

        if len(filters_list) == 1:
            return filters_list[0]
        elif len(filters_list) > 1:
            where_filters[chroma_condition] = filters_list
        return where_filters

    def _add_texts(
        self,
        texts: Iterable[str],
        ids: List[str],
        metadatas: Optional[List[Mapping[str, Union[str, int, float, bool]]]] = None,
    ) -> List[str]:
        """Add texts to Chroma collection.

        Args:
            texts(Iterable[str]): texts.
            metadatas(Optional[List[dict]]): metadatas.
            ids(Optional[List[str]]): ids.
        Returns:
            List[str]: ids.
        """
        embeddings = None
        texts = list(texts)
        if self.embeddings is not None:
            embeddings = self.embeddings.embed_documents(texts)
        if metadatas:
            try:
                self._collection.upsert(
                    metadatas=metadatas,
                    embeddings=embeddings,  # type: ignore
                    documents=texts,
                    ids=ids,
                )
            except ValueError as e:
                logger.error(f"Error upsert chromadb with metadata: {e}")
        else:
            self._collection.upsert(
                embeddings=embeddings,  # type: ignore
                documents=texts,
                ids=ids,
            )
        return ids

    def _query(self, text: str, topk: int, filters: Optional[MetadataFilters] = None):
        """Query Chroma collection.

        Args:
            text(str): query text.
            topk(int): topk.
            filters(MetadataFilters): metadata filters.
        Returns:
            dict: query result.
        """
        if not text:
            return {}
        where_filters = self.convert_metadata_filters(filters) if filters else None
        if self.embeddings is None:
            raise ValueError("Chroma Embeddings is None")
        query_embedding = self.embeddings.embed_query(text)
        return self._collection.query(
            query_embeddings=query_embedding,
            n_results=topk,
            where=where_filters,
        )

    def _clean_persist_folder(self):
        """Clean persist folder."""
        for root, dirs, files in os.walk(self.persist_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(self.persist_dir)


def _convert_chroma_filter_operator(operator: str) -> str:
    """Convert operator to Chroma where operator.

    Args:
        operator(str): operator.
    Returns:
        str: Chroma where operator.
    """
    if operator == FilterOperator.EQ:
        return "$eq"
    elif operator == FilterOperator.NE:
        return "$ne"
    elif operator == FilterOperator.GT:
        return "$gt"
    elif operator == FilterOperator.LT:
        return "$lt"
    elif operator == FilterOperator.GTE:
        return "$gte"
    elif operator == FilterOperator.LTE:
        return "$lte"
    else:
        raise ValueError(f"Chroma Where operator {operator} not supported")


def _transform_chroma_metadata(
    metadata: Dict[str, Any],
) -> Mapping[str, str | int | float | bool]:
    """Transform metadata to Chroma metadata."""
    transformed = {}
    for key, value in metadata.items():
        if isinstance(value, (str, int, float, bool)):
            transformed[key] = value
    return transformed


def _valid_chroma_collection_name(name):
    """Check if the collection name is valid."""
    # ensure the collection name is less than 64 characters
    if not (3 <= len(name) <= 63):
        return False

    # ensure the collection name starts and ends with an alphanumeric character
    if not re.match(r"^[a-zA-Z0-9].*[a-zA-Z0-9]$", name):
        return False

    # ensure the collection name contains only alphanumeric characters,
    # hyphens, underscores, and dots
    if not re.match(r"^[a-zA-Z0-9_][-a-zA-Z0-9_.]*$", name):
        return False

    # ensure the collection name does not contain the '..' substring
    if ".." in name:
        return False

    if string_utils.is_valid_ipv4(name):
        return False

    if string_utils.contains_chinese(name):
        return False

    return True
