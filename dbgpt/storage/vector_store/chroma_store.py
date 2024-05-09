"""Chroma vector store."""
import logging
import os
from typing import List, Optional

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


@register_resource(
    _("Chroma Vector Store"),
    "chroma_vector_store",
    category=ResourceCategory.VECTOR_STORE,
    description=_("Chroma vector store."),
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


class ChromaStore(VectorStoreBase):
    """Chroma vector store."""

    def __init__(self, vector_store_config: ChromaVectorConfig) -> None:
        """Create a ChromaStore instance."""
        from langchain.vectorstores import Chroma

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
        client = PersistentClient(path=self.persist_dir, settings=chroma_settings)

        collection_metadata = chroma_vector_config.get("collection_metadata") or {
            "hnsw:space": "cosine"
        }
        self.vector_store_client = Chroma(
            persist_directory=self.persist_dir,
            embedding_function=self.embeddings,
            # client_settings=chroma_settings,
            client=client,
            collection_metadata=collection_metadata,
        )   # type: ignore

    def similar_search(
        self, text, topk, filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        """Search similar documents."""
        logger.info("ChromaStore similar search")
        where_filters = self.convert_metadata_filters(filters) if filters else None
        lc_documents = self.vector_store_client.similarity_search(
            text, topk, filter=where_filters
        )
        return [
            Chunk(content=doc.page_content, metadata=doc.metadata)
            for doc in lc_documents
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
        where_filters = self.convert_metadata_filters(filters) if filters else None
        docs_and_scores = (
            self.vector_store_client.similarity_search_with_relevance_scores(
                query=text,
                k=topk,
                score_threshold=score_threshold,
                filter=where_filters,
            )
        )
        return [
            Chunk(content=doc.page_content, metadata=doc.metadata, score=score)
            for doc, score in docs_and_scores
        ]

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
        self.vector_store_client.add_texts(texts=texts, metadatas=metadatas, ids=ids)
        return ids

    def delete_vector_name(self, vector_name: str):
        """Delete vector name."""
        logger.info(f"chroma vector_name:{vector_name} begin delete...")
        self.vector_store_client.delete_collection()
        self._clean_persist_folder()
        return True

    def delete_by_ids(self, ids):
        """Delete vector by ids."""
        logger.info(f"begin delete chroma ids: {ids}")
        ids = ids.split(",")
        if len(ids) > 0:
            collection = self.vector_store_client._collection
            collection.delete(ids=ids)

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
        chroma_condition = f"${condition}"
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
