"""Qdrant vector store."""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, List, Optional

if TYPE_CHECKING:
    from qdrant_client.models import Distance

from dbgpt.core import Chunk, Embeddings
from dbgpt.core.awel.flow import Parameter, ResourceCategory, register_resource
from dbgpt.storage.vector_store.base import (
    _COMMON_PARAMETERS,
    _VECTOR_STORE_COMMON_PARAMETERS,
    VectorStoreBase,
    VectorStoreConfig,
)
from dbgpt.storage.vector_store.filters import (
    FilterCondition,
    FilterOperator,
    MetadataFilters,
)
from dbgpt.util.i18n_utils import _

logger = logging.getLogger(__name__)


def _chunk_id_to_uuid(chunk_id: str) -> str:
    """
    Qdrant only allows UUIDs or +ve integers to be used as point IDs.
    Ref: https://qdrant.tech/documentation/manage-data/points/#point-ids
    """
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk_id))


@register_resource(
    _("Qdrant Config"),
    "qdrant_vector_config",
    category=ResourceCategory.VECTOR_STORE,
    description=_("Qdrant vector store config."),
    parameters=[
        *_COMMON_PARAMETERS,
        Parameter.build_from(
            _("Host"),
            "host",
            str,
            description=_("The host of the Qdrant instance."),
            optional=True,
            default="localhost",
        ),
        Parameter.build_from(
            _("Port"),
            "port",
            int,
            description=_("The REST port of the Qdrant instance."),
            optional=True,
            default=6333,
        ),
        Parameter.build_from(
            _("API Key"),
            "api_key",
            str,
            description=_("The API key for Qdrant Cloud or secured Qdrant instances."),
            optional=True,
            default=None,
        ),
        Parameter.build_from(
            _("Use HTTPS"),
            "https",
            bool,
            description=_("Whether to use HTTPS for the Qdrant connection."),
            optional=True,
            default=False,
        ),
        Parameter.build_from(
            _("Prefer gRPC"),
            "prefer_grpc",
            bool,
            description=_("Whether to prefer gRPC for data plane operations."),
            optional=True,
            default=False,
        ),
        Parameter.build_from(
            _("gRPC Port"),
            "grpc_port",
            int,
            description=_("The gRPC port of the Qdrant instance."),
            optional=True,
            default=6334,
        ),
        Parameter.build_from(
            _("Distance"),
            "distance",
            str,
            description=_(
                "Distance metric used to compare vectors. One of: "
                "Cosine, Euclid, Dot, Manhattan."
            ),
            optional=True,
            default="Cosine",
        ),
    ],
)
@dataclass
class QdrantVectorConfig(VectorStoreConfig):
    """Qdrant vector store config."""

    __type__ = "qdrant"

    host: str = field(
        default_factory=lambda: os.getenv("QDRANT_HOST", "localhost"),
        metadata={"help": _("The host of Qdrant store.")},
    )
    port: int = field(
        default_factory=lambda: int(os.getenv("QDRANT_PORT", "6333")),
        metadata={"help": _("The HTTP port of Qdrant store.")},
    )
    api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("QDRANT_API_KEY"),
        metadata={
            "help": _("The API key for Qdrant Cloud or secured Qdrant instances.")
        },
    )
    https: bool = field(
        default=False,
        metadata={"help": _("Whether to use HTTPS for the Qdrant connection.")},
    )
    prefer_grpc: bool = field(
        default=False,
        metadata={
            "help": _("Whether to prefer gRPC over HTTP for data plane operations.")
        },
    )
    grpc_port: int = field(
        default_factory=lambda: int(os.getenv("QDRANT_GRPC_PORT", "6334")),
        metadata={"help": _("The gRPC port of Qdrant store.")},
    )
    distance: str = field(
        default_factory=lambda: os.getenv("QDRANT_DISTANCE", "Cosine"),
        metadata={
            "help": _(
                "Distance metric used to compare vectors. One of: "
                "Cosine, Euclid, Dot, Manhattan."
            )
        },
    )

    def create_store(self, **kwargs) -> "QdrantStore":
        """Create QdrantStore."""
        return QdrantStore(vector_store_config=self, **kwargs)


@register_resource(
    _("Qdrant Vector Store"),
    "qdrant_vector_store",
    category=ResourceCategory.VECTOR_STORE,
    description=_("Qdrant vector store."),
    parameters=[
        Parameter.build_from(
            _("Qdrant Config"),
            "vector_store_config",
            QdrantVectorConfig,
            description=_("the qdrant config of vector store."),
            optional=True,
            default=None,
        ),
        *_VECTOR_STORE_COMMON_PARAMETERS,
    ],
)
class QdrantStore(VectorStoreBase):
    """Qdrant vector store."""

    def __init__(
        self,
        vector_store_config: QdrantVectorConfig,
        name: Optional[str],
        embedding_fn: Optional[Embeddings] = None,
        max_chunks_once_load: Optional[int] = None,
        max_threads: Optional[int] = None,
    ) -> None:
        try:
            from qdrant_client import QdrantClient
        except ImportError:
            raise ImportError("Please install qdrant-client: pip install qdrant-client")
        super().__init__(
            max_chunks_once_load=max_chunks_once_load, max_threads=max_threads
        )
        if embedding_fn is None:
            raise ValueError("embedding_fn is required for QdrantStore")

        self._vector_store_config = vector_store_config
        self.embeddings = embedding_fn
        self.collection_name = name

        self._client = QdrantClient(
            host=vector_store_config.host,
            port=vector_store_config.port,
            grpc_port=vector_store_config.grpc_port,
            api_key=vector_store_config.api_key,
            https=vector_store_config.https,
            prefer_grpc=vector_store_config.prefer_grpc,
        )
        self.create_collection(self.collection_name)

    def get_config(self) -> QdrantVectorConfig:
        """Get the vector store config."""
        return self._vector_store_config

    def create_collection(self, collection_name: str, **kwargs) -> None:
        """Create a Qdrant collection."""
        from qdrant_client.models import VectorParams

        if self._client.collection_exists(collection_name):
            return

        dim = len(self.embeddings.embed_query("probe"))
        self._client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=dim,
                distance=self._resolve_distance(self._vector_store_config.distance),
            ),
        )

    @staticmethod
    def _resolve_distance(name: str) -> "Distance":
        from qdrant_client.models import Distance

        mapping = {
            "cosine": Distance.COSINE,
            "euclid": Distance.EUCLID,
            "dot": Distance.DOT,
            "manhattan": Distance.MANHATTAN,
        }
        try:
            return mapping[name.strip().lower()]
        except (AttributeError, KeyError):
            raise ValueError(
                f"Unsupported Qdrant distance metric: {name!r}. "
                f"Expected one of: {sorted(mapping)}"
            )

    def load_document(self, chunks: List[Chunk]) -> List[str]:
        """Load document in vector database."""
        from qdrant_client.models import PointStruct

        texts = [chunk.content for chunk in chunks]
        vectors = self.embeddings.embed_documents(texts)
        points = [
            PointStruct(
                id=_chunk_id_to_uuid(chunk.chunk_id),
                vector=vector,
                payload={
                    "content": chunk.content,
                    "metadata": chunk.metadata,
                    "chunk_id": chunk.chunk_id,
                },
            )
            for chunk, vector in zip(chunks, vectors)
        ]
        self._client.upsert(collection_name=self.collection_name, points=points)
        return [chunk.chunk_id for chunk in chunks]

    def _query(
        self,
        text: str,
        topk: int,
        filters: Optional[MetadataFilters] = None,
        score_threshold: Optional[float] = None,
    ) -> List[Chunk]:
        query_vector = self.embeddings.embed_query(text)
        qdrant_filter = self.convert_metadata_filters(filters) if filters else None
        response = self._client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=topk,
            query_filter=qdrant_filter,
            with_payload=True,
            score_threshold=score_threshold,
        )
        return [
            Chunk(
                content=r.payload.get("content", ""),
                metadata=r.payload.get("metadata", {}),
                score=r.score,
                chunk_id=r.payload.get("chunk_id", ""),
            )
            for r in response.points
        ]

    def similar_search(
        self, text: str, topk: int, filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        """Search similar documents."""
        return self._query(text, topk, filters)

    def similar_search_with_scores(
        self,
        text: str,
        topk: int,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        """Search similar documents with scores."""
        chunks = self._query(text, topk, filters, score_threshold)
        return self.filter_by_score_threshold(chunks, score_threshold)

    def vector_name_exists(self) -> bool:
        """Whether vector name exists."""
        try:
            if not self._client.collection_exists(self.collection_name):
                return False

            return self._client.count(self.collection_name).count > 0
        except Exception as e:
            logger.error(f"vector_name_exists error, {str(e)}")
            return False

    def delete_vector_name(self, vector_name: str):
        """Delete vector name."""
        logger.info(f"qdrant vector_name:{vector_name} begin delete...")
        self._client.delete_collection(self.collection_name)
        return True

    def delete_by_ids(self, ids: str, batch_size: int = 1000) -> List[str]:
        """Delete vector by ids."""
        from qdrant_client.models import PointIdsList

        id_list = [i.strip() for i in ids.split(",") if i.strip()]
        point_ids = [_chunk_id_to_uuid(cid) for cid in id_list]
        for i in range(0, len(point_ids), batch_size):
            batch = point_ids[i : i + batch_size]
            self._client.delete(
                collection_name=self.collection_name,
                points_selector=PointIdsList(points=batch),
            )
        return id_list

    def truncate(self) -> List[str]:
        """Truncate data."""
        logger.info(f"begin truncate qdrant collection:{self.collection_name}")
        all_ids = []
        next_offset = None
        while True:
            records, next_offset = self._client.scroll(
                collection_name=self.collection_name,
                limit=1000,
                offset=next_offset,
                with_payload=False,
                with_vectors=False,
            )
            all_ids.extend(str(r.id) for r in records)
            if next_offset is None:
                break

        if all_ids:
            self._client.delete(
                collection_name=self.collection_name,
                points_selector=all_ids,
            )
        return all_ids

    def convert_metadata_filters(self, filters: MetadataFilters) -> Any:
        """Convert metadata filters to Qdrant filters."""
        from qdrant_client.models import (
            FieldCondition,
            Filter,
            MatchAny,
            MatchValue,
            Range,
        )

        positive = []
        negative = []

        for f in filters.filters:
            key = f"metadata.{f.key}"
            op = f.operator
            val = f.value

            if op == FilterOperator.EQ:
                positive.append(FieldCondition(key=key, match=MatchValue(value=val)))
            elif op == FilterOperator.GT:
                positive.append(FieldCondition(key=key, range=Range(gt=val)))
            elif op == FilterOperator.GTE:
                positive.append(FieldCondition(key=key, range=Range(gte=val)))
            elif op == FilterOperator.LT:
                positive.append(FieldCondition(key=key, range=Range(lt=val)))
            elif op == FilterOperator.LTE:
                positive.append(FieldCondition(key=key, range=Range(lte=val)))
            elif op == FilterOperator.NE:
                negative.append(FieldCondition(key=key, match=MatchValue(value=val)))
            elif op == FilterOperator.IN:
                positive.append(FieldCondition(key=key, match=MatchAny(any=val)))
            elif op == FilterOperator.NIN:
                negative.append(FieldCondition(key=key, match=MatchAny(any=val)))
            else:
                raise ValueError(f"Qdrant Where operator {op} not supported")

        if filters.condition == FilterCondition.AND:
            return Filter(must=positive or None, must_not=negative or None)
        else:
            return Filter(should=positive or None, must_not=negative or None)
