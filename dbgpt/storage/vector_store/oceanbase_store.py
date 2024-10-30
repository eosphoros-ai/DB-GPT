"""OceanBase vector store."""
import json
import logging
import math
import os
import uuid
from typing import Any, List, Optional, Tuple

import numpy as np
from pydantic import Field
from sqlalchemy import JSON, Column, String, Table, func, text
from sqlalchemy.dialects.mysql import LONGTEXT

from dbgpt.core import Chunk
from dbgpt.core.awel.flow import Parameter, ResourceCategory, register_resource
from dbgpt.storage.vector_store.base import (
    _COMMON_PARAMETERS,
    VectorStoreBase,
    VectorStoreConfig,
)
from dbgpt.storage.vector_store.filters import FilterOperator, MetadataFilters
from dbgpt.util.i18n_utils import _

logger = logging.getLogger(__name__)

DEFAULT_OCEANBASE_BATCH_SIZE = 100
DEFAULT_OCEANBASE_VECTOR_TABLE_NAME = "dbgpt_vector"
DEFAULT_OCEANBASE_HNSW_BUILD_PARAM = {"M": 16, "efConstruction": 256}
DEFAULT_OCEANBASE_HNSW_SEARCH_PARAM = {"efSearch": 64}
OCEANBASE_SUPPORTED_VECTOR_INDEX_TYPE = "HNSW"
DEFAULT_OCEANBASE_VECTOR_METRIC_TYPE = "l2"

DEFAULT_OCEANBASE_PFIELD = "id"
DEFAULT_OCEANBASE_DOCID_FIELD = "doc_id"
DEFAULT_OCEANBASE_VEC_FIELD = "embedding"
DEFAULT_OCEANBASE_DOC_FIELD = "document"
DEFAULT_OCEANBASE_METADATA_FIELD = "metadata"

DEFAULT_OCEANBASE_VEC_INDEX_NAME = "vidx"


def _parse_filter_value(filter_value: Any, is_text_match: bool = False):
    if filter_value is None:
        return filter_value

    if is_text_match:
        return f"'{filter_value!s}%'"

    if isinstance(filter_value, str):
        return f"'{filter_value!s}'"

    if isinstance(filter_value, list):
        if all(isinstance(item, str) for item in filter_value):
            return "(" + ",".join([f"'{str(v)}'" for v in filter_value]) + ")"
        return "(" + ",".join([str(v) for v in filter_value]) + ")"

    return str(filter_value)


def _euclidean_similarity(distance: float) -> float:
    return 1.0 - distance / math.sqrt(2)


def _neg_inner_product_similarity(distance: float) -> float:
    return -distance


def _normalize(vector: List[float]) -> List[float]:
    arr = np.array(vector)
    norm = np.linalg.norm(arr)
    arr = arr / norm
    return arr.tolist()


@register_resource(
    _("OceanBase Vector Store"),
    "oceanbase_vector_store",
    category=ResourceCategory.VECTOR_STORE,
    parameters=[
        *_COMMON_PARAMETERS,
        Parameter.build_from(
            _("OceanBase Host"),
            "ob_host",
            str,
            description=_("oceanbase host"),
            optional=True,
            default=None,
        ),
        Parameter.build_from(
            _("OceanBase Port"),
            "ob_port",
            int,
            description=_("oceanbase port"),
            optional=True,
            default=None,
        ),
        Parameter.build_from(
            _("OceanBase User"),
            "ob_user",
            str,
            description=_("user to login"),
            optional=True,
            default=None,
        ),
        Parameter.build_from(
            _("OceanBase Password"),
            "ob_password",
            str,
            description=_("password to login"),
            optional=True,
            default=None,
        ),
        Parameter.build_from(
            _("OceanBase Database"),
            "ob_database",
            str,
            description=_("database for vector tables"),
            optional=True,
            default=None,
        ),
    ],
    description="OceanBase vector store.",
)
class OceanBaseConfig(VectorStoreConfig):
    """OceanBase vector store config."""

    class Config:
        """Config for BaseModel."""

        arbitrary_types_allowed = True

    """OceanBase config"""
    ob_host: Optional[str] = Field(
        default=None,
        description="oceanbase host",
    )
    ob_port: Optional[int] = Field(
        default=None,
        description="oceanbase port",
    )
    ob_user: Optional[str] = Field(
        default=None,
        description="user to login",
    )
    ob_password: Optional[str] = Field(
        default=None,
        description="password to login",
    )
    ob_database: Optional[str] = Field(
        default=None,
        description="database for vector tables",
    )


class OceanBaseStore(VectorStoreBase):
    """OceanBase vector store."""

    def __init__(self, vector_store_config: OceanBaseConfig) -> None:
        """Create a OceanBaseStore instance."""
        try:
            from pyobvector import ObVecClient  # type: ignore
        except ImportError:
            raise ImportError(
                "Could not import pyobvector package. "
                "Please install it with `pip install pyobvector`."
            )

        if vector_store_config.embedding_fn is None:
            raise ValueError("embedding_fn is required for OceanBaseStore")

        super().__init__()

        self._vector_store_config = vector_store_config
        self.embedding_function = vector_store_config.embedding_fn
        self.table_name = vector_store_config.name

        vector_store_config_map = vector_store_config.to_dict()
        OB_HOST = str(
            vector_store_config_map.get("ob_host") or os.getenv("OB_HOST", "127.0.0.1")
        )
        OB_PORT = int(
            vector_store_config_map.get("ob_port") or int(os.getenv("OB_PORT", "2881"))
        )
        OB_USER = str(
            vector_store_config_map.get("ob_user") or os.getenv("OB_USER", "root@test")
        )
        OB_PASSWORD = str(
            vector_store_config_map.get("ob_password") or os.getenv("OB_PASSWORD", "")
        )
        OB_DATABASE = str(
            vector_store_config_map.get("ob_database")
            or os.getenv("OB_DATABASE", "test")
        )

        self.normalize = bool(os.getenv("OB_ENABLE_NORMALIZE_VECTOR", ""))
        self.vidx_metric_type = DEFAULT_OCEANBASE_VECTOR_METRIC_TYPE
        self.vidx_algo_params = DEFAULT_OCEANBASE_HNSW_BUILD_PARAM
        self.primary_field = DEFAULT_OCEANBASE_PFIELD
        self.vector_field = DEFAULT_OCEANBASE_VEC_FIELD
        self.text_field = DEFAULT_OCEANBASE_DOC_FIELD
        self.metadata_field = DEFAULT_OCEANBASE_METADATA_FIELD
        self.vidx_name = DEFAULT_OCEANBASE_VEC_INDEX_NAME
        self.hnsw_ef_search = -1

        self.vector_store_client = ObVecClient(
            uri=OB_HOST + ":" + str(OB_PORT),
            user=OB_USER,
            password=OB_PASSWORD,
            db_name=OB_DATABASE,
            echo=True,
        )

    def get_config(self) -> OceanBaseConfig:
        """Get the vector store config."""
        return self._vector_store_config

    def vector_name_exists(self) -> bool:
        """Whether vector name exists."""
        return self.vector_store_client.check_table_exists(table_name=self.table_name)

    def _load_table(self) -> None:
        table = Table(
            self.table_name,
            self.vector_store_client.metadata_obj,
            autoload_with=self.vector_store_client.engine,
        )
        column_names = [column.name for column in table.columns]
        assert len(column_names) == 4

        self.primary_field = column_names[0]
        self.vector_field = column_names[1]
        self.text_field = column_names[2]
        self.metadata_field = column_names[3]

    def _create_table_with_index(self, embeddings: list) -> None:
        try:
            from pyobvector import VECTOR
        except ImportError:
            raise ImportError(
                "Could not import pyobvector package. "
                "Please install it with `pip install pyobvector`."
            )

        if self.vector_store_client.check_table_exists(self.table_name):
            self._load_table()
            return

        dim = len(embeddings[0])
        cols = [
            Column(
                self.primary_field, String(4096), primary_key=True, autoincrement=False
            ),
            Column(self.vector_field, VECTOR(dim)),
            Column(self.text_field, LONGTEXT),
            Column(self.metadata_field, JSON),
        ]

        vidx_params = self.vector_store_client.prepare_index_params()
        vidx_params.add_index(
            field_name=self.vector_field,
            index_type=OCEANBASE_SUPPORTED_VECTOR_INDEX_TYPE,
            index_name=self.vidx_name,
            metric_type=self.vidx_metric_type,
            params=self.vidx_algo_params,
        )

        self.vector_store_client.create_table_with_index_params(
            table_name=self.table_name,
            columns=cols,
            indexes=None,
            vidxs=vidx_params,
        )

    def load_document(self, chunks: List[Chunk]) -> List[str]:
        """Load document in vector database."""
        batch_size = 100
        texts = [d.content for d in chunks]
        metadatas = [d.metadata for d in chunks]
        embeddings = self.embedding_function.embed_documents(texts)

        self._create_table_with_index(embeddings)

        ids = [str(uuid.uuid4()) for _ in texts]
        pks: list[str] = []
        for i in range(0, len(embeddings), batch_size):
            data = [
                {
                    self.primary_field: id,
                    self.vector_field: (
                        embedding if not self.normalize else _normalize(embedding)
                    ),
                    self.text_field: text,
                    self.metadata_field: metadata,
                }
                for id, embedding, text, metadata in zip(
                    ids[i : i + batch_size],
                    embeddings[i : i + batch_size],
                    texts[i : i + batch_size],
                    metadatas[i : i + batch_size],
                )
            ]
            self.vector_store_client.insert(
                table_name=self.table_name,
                data=data,
            )
            pks.extend(ids[i : i + batch_size])
        return pks

    def _parse_metric_type_str_to_dist_func(self) -> Any:
        if self.vidx_metric_type == "l2":
            return func.l2_distance
        if self.vidx_metric_type == "cosine":
            return func.cosine_distance
        if self.vidx_metric_type == "inner_product":
            return func.negative_inner_product
        raise ValueError(f"Invalid vector index metric type: {self.vidx_metric_type}")

    def similar_search(
        self,
        text: str,
        topk: int,
        filters: Optional[MetadataFilters] = None,
        param: Optional[dict] = None,
    ) -> List[Chunk]:
        """Perform a search on a query string and return results."""
        query_vector = self.embedding_function.embed_query(text)
        return self._similarity_search_by_vector(
            embedding=query_vector, k=topk, param=param, filters=filters
        )

    def similar_search_with_scores(
        self,
        text: str,
        topk: int,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
        param: Optional[dict] = None,
    ) -> List[Chunk]:
        """Perform a search on a query string and return results with score."""
        query_vector = self.embedding_function.embed_query(text)
        docs_with_id_and_scores = self._similarity_search_with_score_by_vector(
            embedding=query_vector, k=topk, param=param, filters=filters
        )
        return [
            Chunk(
                metadata=doc.metadata,
                content=doc.content,
                score=score,
                chunk_id=str(id),
            )
            for doc, id, score in docs_with_id_and_scores
            if score >= score_threshold
        ]

    def _similarity_search_by_vector(
        self,
        embedding: List[float],
        k: int = 4,
        param: Optional[dict] = None,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        if filters is not None:
            filter = self._convert_metadata_filters(filters)
        else:
            filter = None

        search_param = (
            param if param is not None else DEFAULT_OCEANBASE_HNSW_SEARCH_PARAM
        )
        ef_search = search_param.get(
            "efSearch", DEFAULT_OCEANBASE_HNSW_SEARCH_PARAM["efSearch"]
        )
        if ef_search != self.hnsw_ef_search:
            self.vector_store_client.set_ob_hnsw_ef_search(ef_search)
            self.hnsw_ef_search = ef_search

        res = self.vector_store_client.ann_search(
            table_name=self.table_name,
            vec_data=(embedding if not self.normalize else _normalize(embedding)),
            vec_column_name=self.vector_field,
            distance_func=self._parse_metric_type_str_to_dist_func(),
            topk=k,
            output_column_names=[self.text_field, self.metadata_field],
            where_clause=([text(filter)] if filter is not None else None),
        )
        return [
            Chunk(
                content=r[0],
                metadata=json.loads(r[1]),
            )
            for r in res.fetchall()
        ]

    def _similarity_search_with_score_by_vector(
        self,
        embedding: List[float],
        k: int = 10,
        param: Optional[dict] = None,
        filters: Optional[MetadataFilters] = None,
        **kwargs: Any,
    ) -> List[Tuple[Chunk, str, float]]:
        if filters is not None:
            filter = self._convert_metadata_filters(filters)
        else:
            filter = None

        search_param = (
            param if param is not None else DEFAULT_OCEANBASE_HNSW_SEARCH_PARAM
        )
        ef_search = search_param.get(
            "efSearch", DEFAULT_OCEANBASE_HNSW_SEARCH_PARAM["efSearch"]
        )
        if ef_search != self.hnsw_ef_search:
            self.vector_store_client.set_ob_hnsw_ef_search(ef_search)
            self.hnsw_ef_search = ef_search

        res = self.vector_store_client.ann_search(
            table_name=self.table_name,
            vec_data=(embedding if not self.normalize else _normalize(embedding)),
            vec_column_name=self.vector_field,
            distance_func=self._parse_metric_type_str_to_dist_func(),
            with_dist=True,
            topk=k,
            output_column_names=[
                self.text_field,
                self.metadata_field,
                self.primary_field,
            ],
            where_clause=([text(filter)] if filter is not None else None),
            **kwargs,
        )
        return [
            (
                Chunk(content=r[0], metadata=json.loads(r[1])),
                r[2],
                r[3],
            )
            for r in res.fetchall()
        ]

    def delete_vector_name(self, vector_name: str):
        """Delete vector name."""
        self.vector_store_client.drop_table_if_exist(table_name=self.table_name)

    def delete_by_ids(self, ids: str):
        """Delete vector by ids."""
        split_ids = ids.split(",")
        self.vector_store_client.delete(table_name=self.table_name, ids=split_ids)

    def _enhance_filter_key(self, filter_key: str) -> str:
        return f"{self.metadata_field}->'$.{filter_key}'"

    def _convert_metadata_filters(self, metafilters: MetadataFilters) -> str:
        filters = []
        for filter in metafilters.filters:
            filter_value = _parse_filter_value(filter.value)

            if filter.operator == FilterOperator.EQ:
                filters.append(f"{self._enhance_filter_key(filter.key)}={filter_value}")
            elif filter.operator == FilterOperator.GT:
                filters.append(f"{self._enhance_filter_key(filter.key)}>{filter_value}")
            elif filter.operator == FilterOperator.LT:
                filters.append(f"{self._enhance_filter_key(filter.key)}<{filter_value}")
            elif filter.operator == FilterOperator.NE:
                filters.append(
                    f"{self._enhance_filter_key(filter.key)}!={filter_value}"
                )
            elif filter.operator == FilterOperator.GTE:
                filters.append(
                    f"{self._enhance_filter_key(filter.key)}>={filter_value}"
                )
            elif filter.operator == FilterOperator.LTE:
                filters.append(
                    f"{self._enhance_filter_key(filter.key)}<={filter_value}"
                )
            elif filter.operator == FilterOperator.IN:
                filters.append(
                    f"{self._enhance_filter_key(filter.key)} in {filter_value}"
                )
            elif filter.operator == FilterOperator.NIN:
                filters.append(
                    f"{self._enhance_filter_key(filter.key)} not in {filter_value}"
                )
            else:
                raise ValueError(
                    f"Operator {filter.operator} ('{filter.operator.value}') "
                    f"is not supported by OceanBase."
                )
        return f" {metafilters.condition.value} ".join(filters)
