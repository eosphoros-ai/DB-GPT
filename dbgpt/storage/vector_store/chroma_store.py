"""Chroma vector store."""
import logging
import os
from typing import Any, Dict, Iterable, List, Mapping, Optional, Union

from chromadb import PersistentClient
from chromadb.config import Settings

from dbgpt._private.pydantic import ConfigDict, Field
from dbgpt.configs.model_config import PILOT_PATH
from dbgpt.core import Chunk
from dbgpt.core.awel.flow import Parameter, ResourceCategory, register_resource
from dbgpt.util.i18n_utils import _

from .base import _COMMON_PARAMETERS, VectorStoreBase, VectorStoreConfig
from .filters import FilterOperator, MetadataFilters

logger = logging.getLogger(__name__)

CHROMA_COLLECTION_NAME = "langchain"


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
class ChromaVectorConfig(VectorStoreConfig):
    """Chroma vector store config."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    persist_path: Optional[str] = Field(
        default=os.getenv("CHROMA_PERSIST_PATH", None),
        description="the persist path of vector store.",
    )
    collection_metadata: Optional[dict] = Field(
        default=None,
        description="the index metadata of vector store, if not set, will use the "
        "default metadata.",
    )


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
    ],
)
class ChromaStore(VectorStoreBase):
    """Chroma vector store."""

    def __init__(self, vector_store_config: ChromaVectorConfig) -> None:
        """Create a ChromaStore instance.

        Args:
            vector_store_config(ChromaVectorConfig): vector store config.
        """
        super().__init__()
        self._vector_store_config = vector_store_config

        chroma_vector_config = vector_store_config.to_dict(exclude_none=True)
        chroma_path = chroma_vector_config.get(
            "persist_path", os.path.join(PILOT_PATH, "data")
        )
        self.persist_dir = os.path.join(
            chroma_path, vector_store_config.name + ".vectordb"
        )
        self.embeddings = vector_store_config.embedding_fn
        chroma_settings = Settings(
            # chroma_db_impl="duckdb+parquet", => deprecated configuration of Chroma
            persist_directory=self.persist_dir,
            anonymized_telemetry=False,
        )
        self._chroma_client = PersistentClient(
            path=self.persist_dir, settings=chroma_settings
        )

        collection_metadata = chroma_vector_config.get("collection_metadata") or {
            "hnsw:space": "cosine"
        }
        self._collection = self._chroma_client.get_or_create_collection(
            name=CHROMA_COLLECTION_NAME,
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
        logger.info(f"Check persist_dir: {self.persist_dir}")
        if not os.path.exists(self.persist_dir):
            return False
        files = os.listdir(self.persist_dir)
        # Skip default file: chroma.sqlite3
        files = list(filter(lambda f: f != "chroma.sqlite3", files))
        return len(files) > 0

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
        """Delete vector name."""
        logger.info(f"chroma vector_name:{vector_name} begin delete...")
        # self.vector_store_client.delete_collection()
        self._chroma_client.delete_collection(self._collection.name)
        self._clean_persist_folder()
        return True

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
    metadata: Dict[str, Any]
) -> Mapping[str, str | int | float | bool]:
    """Transform metadata to Chroma metadata."""
    transformed = {}
    for key, value in metadata.items():
        if isinstance(value, (str, int, float, bool)):
            transformed[key] = value
    return transformed
