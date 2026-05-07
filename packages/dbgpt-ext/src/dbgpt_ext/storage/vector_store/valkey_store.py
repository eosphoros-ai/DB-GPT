"""Valkey vector store.

Requires a Valkey server with the valkey-search module loaded for vector
similarity search. Uses the valkey-glide client library.

To run Valkey with the search module::

    docker run -d --name valkey -p 6379:6379 valkey/valkey:latest \\
        --loadmodule /usr/lib/valkey/modules/valkey-search.so
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

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

_VALKEY_DEFAULT_INDEX_TYPE = "HNSW"
_VALKEY_DEFAULT_DISTANCE_METRIC = "COSINE"
_VALKEY_DEFAULT_KEY_PREFIX = "dbgpt_vec:"
_VALKEY_VECTOR_FIELD = "vector"
_VALKEY_CONTENT_FIELD = "content"
_VALKEY_METADATA_FIELD = "metadata"
_VALKEY_CHUNK_ID_FIELD = "chunk_id"
_VALKEY_METADATA_PREFIX = "meta_"


@register_resource(
    _("Valkey Config"),
    "valkey_vector_config",
    category=ResourceCategory.VECTOR_STORE,
    description=_("Valkey vector store config."),
    parameters=[
        *_COMMON_PARAMETERS,
        Parameter.build_from(
            _("Host"),
            "host",
            str,
            description=_("The host of the Valkey instance."),
            optional=True,
            default="localhost",
        ),
        Parameter.build_from(
            _("Port"),
            "port",
            int,
            description=_("The port of the Valkey instance."),
            optional=True,
            default=6379,
        ),
        Parameter.build_from(
            _("Password"),
            "password",
            str,
            description=_("The password for the Valkey instance."),
            optional=True,
            default=None,
        ),
        Parameter.build_from(
            _("Use SSL"),
            "use_ssl",
            bool,
            description=_("Whether to use SSL for the Valkey connection."),
            optional=True,
            default=False,
        ),
        Parameter.build_from(
            _("Index Type"),
            "index_type",
            str,
            description=_(
                "The vector index type: 'HNSW' (approximate, fast) or "
                "'FLAT' (exact, slower)."
            ),
            optional=True,
            default="HNSW",
        ),
        Parameter.build_from(
            _("Distance Metric"),
            "distance_metric",
            str,
            description=_(
                "The distance metric: 'COSINE', 'L2' (Euclidean), or "
                "'IP' (Inner Product)."
            ),
            optional=True,
            default="COSINE",
        ),
    ],
)
@dataclass
class ValkeyVectorConfig(VectorStoreConfig):
    """Valkey vector store config."""

    __type__ = "valkey"

    host: str = field(
        default_factory=lambda: os.getenv("VALKEY_HOST", "localhost"),
        metadata={"help": _("The host of Valkey store.")},
    )
    port: int = field(
        default_factory=lambda: int(os.getenv("VALKEY_PORT", "6379")),
        metadata={"help": _("The port of Valkey store.")},
    )
    password: Optional[str] = field(
        default_factory=lambda: os.getenv("VALKEY_PASSWORD"),
        metadata={"help": _("The password for Valkey store.")},
    )
    use_ssl: bool = field(
        default=False,
        metadata={"help": _("Whether to use SSL for the Valkey connection.")},
    )
    index_type: str = field(
        default_factory=lambda: os.getenv(
            "VALKEY_INDEX_TYPE", _VALKEY_DEFAULT_INDEX_TYPE
        ),
        metadata={
            "help": _(
                "The vector index type: 'HNSW' (approximate, fast) or "
                "'FLAT' (exact, slower)."
            )
        },
    )
    distance_metric: str = field(
        default_factory=lambda: os.getenv(
            "VALKEY_DISTANCE_METRIC", _VALKEY_DEFAULT_DISTANCE_METRIC
        ),
        metadata={
            "help": _(
                "The distance metric: 'COSINE', 'L2' (Euclidean), or "
                "'IP' (Inner Product)."
            )
        },
    )
    key_prefix: str = field(
        default_factory=lambda: os.getenv(
            "VALKEY_KEY_PREFIX", _VALKEY_DEFAULT_KEY_PREFIX
        ),
        metadata={"help": _("The key prefix for all vector store keys.")},
    )
    hnsw_m: int = field(
        default=16,
        metadata={"help": _("HNSW: number of connections per node.")},
    )
    hnsw_ef_construction: int = field(
        default=200,
        metadata={"help": _("HNSW: construction time quality factor.")},
    )
    hnsw_ef_runtime: int = field(
        default=10,
        metadata={"help": _("HNSW: runtime search quality factor.")},
    )
    request_timeout: int = field(
        default_factory=lambda: int(os.getenv("VALKEY_REQUEST_TIMEOUT", "5000")),
        metadata={
            "help": _(
                "Request timeout in milliseconds for Valkey operations. "
                "Prevents indefinite hangs on network issues."
            )
        },
    )
    metadata_schema: Optional[Dict[str, str]] = field(
        default=None,
        metadata={
            "help": _(
                "Metadata fields to index for filtering. Dict mapping field name "
                "to type: 'tag' (string) or 'numeric'. "
                "E.g. {'source': 'tag', 'page': 'numeric'}. "
                "Must be defined at store creation time."
            )
        },
    )

    def create_store(self, **kwargs) -> "ValkeyStore":
        """Create ValkeyStore."""
        return ValkeyStore(vector_store_config=self, **kwargs)


@register_resource(
    _("Valkey Vector Store"),
    "valkey_vector_store",
    category=ResourceCategory.VECTOR_STORE,
    description=_("Valkey vector store."),
    parameters=[
        Parameter.build_from(
            _("Valkey Config"),
            "vector_store_config",
            ValkeyVectorConfig,
            description=_("the valkey config of vector store."),
            optional=True,
            default=None,
        ),
        *_VECTOR_STORE_COMMON_PARAMETERS,
    ],
)
class ValkeyStore(VectorStoreBase):
    """Valkey vector store using valkey-glide client.

    Requires a Valkey server with the valkey-search module loaded.
    """

    def __init__(
        self,
        vector_store_config: ValkeyVectorConfig,
        name: Optional[str] = None,
        embedding_fn: Optional[Embeddings] = None,
        max_chunks_once_load: Optional[int] = None,
        max_threads: Optional[int] = None,
    ) -> None:
        """Initialize ValkeyStore.

        Args:
            vector_store_config: Valkey connection and index configuration.
            name: Collection/index name.
            embedding_fn: Embedding function for vectorizing text.
            max_chunks_once_load: Max chunks per load batch.
            max_threads: Max threads for parallel loading.
        """
        try:
            import glide  # noqa: F401
        except ImportError:
            raise ImportError(
                "Please install valkey-glide: pip install 'valkey-glide>=2.3.0'"
            )

        super().__init__(
            max_chunks_once_load=max_chunks_once_load, max_threads=max_threads
        )

        if embedding_fn is None:
            raise ValueError("embedding_fn is required for ValkeyStore")

        self._vector_store_config = vector_store_config
        self._embedding_fn = embedding_fn
        self._collection_name = name or "dbgpt_collection"
        self._key_prefix = vector_store_config.key_prefix + self._collection_name + ":"
        self._index_name = f"idx:{self._collection_name}"
        self._client: Optional[Any] = None
        self._dim: Optional[int] = None

        # Dedicated event loop for async glide operations
        import asyncio

        self._loop = asyncio.new_event_loop()

    def close(self):
        """Close the client connection and event loop."""
        if self._client:
            try:
                self._loop.run_until_complete(self._client.close())
            except Exception:
                pass
            self._client = None
        if self._loop and not self._loop.is_closed():
            self._loop.close()

    def __del__(self):
        """Clean up resources if close() was not called explicitly."""
        if hasattr(self, "_loop"):
            self.close()

    @property
    def client(self) -> Any:
        """Get or create the Valkey client (lazy initialization)."""
        if self._client is None:
            self._client = self._create_client()
        return self._client

    def _create_client(self) -> Any:
        """Create a Valkey-glide client."""
        from glide import GlideClient, GlideClientConfiguration, NodeAddress

        config = self._vector_store_config
        node = NodeAddress(host=config.host, port=config.port)

        if config.password:
            from glide import ServerCredentials

            client_config = GlideClientConfiguration(
                addresses=[node],
                use_tls=config.use_ssl,
                request_timeout=config.request_timeout,
                credentials=ServerCredentials(password=config.password),
            )
        else:
            client_config = GlideClientConfiguration(
                addresses=[node],
                use_tls=config.use_ssl,
                request_timeout=config.request_timeout,
            )

        # GlideClient.create() is async — run it in our dedicated loop
        return self._loop.run_until_complete(GlideClient.create(client_config))

    def _get_dimension(self) -> int:
        """Get embedding dimension by running a probe embedding."""
        if self._dim is None:
            self._dim = len(self._embedding_fn.embed_query("probe"))
        return self._dim

    def _run_async(self, coro):
        """Run an async coroutine synchronously using the dedicated event loop."""
        if self._loop.is_closed():
            raise RuntimeError("ValkeyStore has been closed")
        return self._loop.run_until_complete(coro)

    def get_config(self) -> ValkeyVectorConfig:
        """Get the vector store config."""
        return self._vector_store_config

    def create_collection(self, collection_name: str, **kwargs) -> None:
        """Create a vector index in Valkey.

        Args:
            collection_name: The name for the collection/index.
        """
        from glide import DataType, ft

        # Check if index already exists
        if self._index_exists():
            return

        dim = self._get_dimension()
        config = self._vector_store_config

        # Build the schema fields
        schema = self._build_index_schema(dim, config)

        # Create the index
        prefix = self._key_prefix
        options = ft.FtCreateOptions(
            data_type=DataType.HASH,
            prefixes=[prefix],
        )

        self._run_async(
            ft.create(self.client, self._index_name, schema=schema, options=options)
        )
        logger.info(
            f"Created Valkey index '{self._index_name}' with {config.index_type} "
            f"algorithm, {config.distance_metric} metric, dim={dim}"
        )

    def _build_index_schema(self, dim: int, config: ValkeyVectorConfig) -> List:
        """Build the FT.CREATE schema fields."""
        from glide import (
            DistanceMetricType,
            NumericField,
            TagField,
            TextField,
            VectorAlgorithm,
            VectorField,
            VectorFieldAttributesFlat,
            VectorFieldAttributesHnsw,
            VectorType,
        )

        # Map string config to enum values
        distance_map = {
            "COSINE": DistanceMetricType.COSINE,
            "L2": DistanceMetricType.L2,
            "IP": DistanceMetricType.IP,
        }
        distance_metric = distance_map.get(
            config.distance_metric.upper(), DistanceMetricType.COSINE
        )

        fields = [
            TextField(_VALKEY_CONTENT_FIELD),
            TextField(_VALKEY_METADATA_FIELD),
            TagField(_VALKEY_CHUNK_ID_FIELD),
        ]

        # Add user-defined metadata fields to schema
        if config.metadata_schema:
            for field_name, field_type in config.metadata_schema.items():
                prefixed = _VALKEY_METADATA_PREFIX + field_name
                if field_type.lower() == "numeric":
                    fields.append(NumericField(prefixed))
                else:
                    # Default to TAG for string fields
                    fields.append(TagField(prefixed))

        # Vector field with algorithm-specific parameters
        if config.index_type.upper() == "FLAT":
            attributes = VectorFieldAttributesFlat(
                dimensions=dim,
                distance_metric=distance_metric,
                type=VectorType.FLOAT32,
            )
            vector_field = VectorField(
                _VALKEY_VECTOR_FIELD,
                algorithm=VectorAlgorithm.FLAT,
                attributes=attributes,
            )
        else:
            # Default to HNSW
            attributes = VectorFieldAttributesHnsw(
                dimensions=dim,
                distance_metric=distance_metric,
                type=VectorType.FLOAT32,
                number_of_edges=config.hnsw_m,
                vectors_examined_on_construction=config.hnsw_ef_construction,
                vectors_examined_on_runtime=config.hnsw_ef_runtime,
            )
            vector_field = VectorField(
                _VALKEY_VECTOR_FIELD,
                algorithm=VectorAlgorithm.HNSW,
                attributes=attributes,
            )

        fields.append(vector_field)
        return fields

    def _index_exists(self) -> bool:
        """Check if the index already exists."""
        from glide import ft

        existing = self._run_async(ft.list(self.client))
        names = {
            i.decode() if isinstance(i, bytes) else str(i) for i in (existing or [])
        }
        return self._index_name in names

    def load_document(self, chunks: List[Chunk]) -> List[str]:
        """Load document chunks into Valkey.

        Args:
            chunks: Document chunks to store.

        Returns:
            List of chunk IDs that were stored.
        """
        import struct

        # Ensure index exists
        self.create_collection(self._collection_name)

        texts = [chunk.content for chunk in chunks]
        vectors = self._embedding_fn.embed_documents(texts)

        for chunk, vector in zip(chunks, vectors):
            key = self._key_prefix + chunk.chunk_id

            # Pack vector as binary float32
            vector_bytes = struct.pack(f"{len(vector)}f", *vector)

            # Store as hash fields
            field_map = {
                _VALKEY_CONTENT_FIELD: chunk.content,
                _VALKEY_METADATA_FIELD: json.dumps(
                    chunk.metadata if chunk.metadata else {}
                ),
                _VALKEY_CHUNK_ID_FIELD: chunk.chunk_id,
                _VALKEY_VECTOR_FIELD: vector_bytes,
            }

            # Store indexed metadata fields as top-level hash fields
            metadata_schema = self._vector_store_config.metadata_schema
            if metadata_schema and chunk.metadata:
                for field_name in metadata_schema:
                    if field_name in chunk.metadata:
                        prefixed = _VALKEY_METADATA_PREFIX + field_name
                        field_map[prefixed] = str(chunk.metadata[field_name])

            self._run_async(self.client.hset(key, field_map))

        return [chunk.chunk_id for chunk in chunks]

    def similar_search(
        self, text: str, topk: int, filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        """Search for similar documents.

        Args:
            text: Query text.
            topk: Number of results to return.
            filters: Optional metadata filters.

        Returns:
            List of similar chunks.
        """
        return self._search(text, topk, filters=filters)

    def similar_search_with_scores(
        self,
        text: str,
        topk: int,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        """Search for similar documents with score filtering.

        Args:
            text: Query text.
            topk: Number of results to return.
            score_threshold: Minimum score threshold.
            filters: Optional metadata filters.

        Returns:
            List of similar chunks with scores above threshold.
        """
        chunks = self._search(text, topk, filters=filters)
        return self.filter_by_score_threshold(chunks, score_threshold)

    def _search(
        self,
        text: str,
        topk: int,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        """Execute a vector similarity search.

        Args:
            text: Query text to embed and search.
            topk: Number of results.
            filters: Optional metadata filters.

        Returns:
            List of matching chunks with scores.
        """
        import struct

        from glide import FtSearchLimit, FtSearchOptions, ReturnField, ft

        query_vector = self._embedding_fn.embed_query(text)
        vector_bytes = struct.pack(f"{len(query_vector)}f", *query_vector)

        # Build the KNN query
        filter_expr = self._build_filter_expression(filters)
        query_str = f"{filter_expr}=>[KNN {topk} @{_VALKEY_VECTOR_FIELD} $vec AS score]"

        # Execute search
        options = FtSearchOptions(
            params={"vec": vector_bytes},
            return_fields=[
                ReturnField(_VALKEY_CONTENT_FIELD),
                ReturnField(_VALKEY_METADATA_FIELD),
                ReturnField(_VALKEY_CHUNK_ID_FIELD),
                ReturnField("score"),
            ],
            limit=FtSearchLimit(0, topk),
        )

        result = self._run_async(
            ft.search(self.client, self._index_name, query_str, options)
        )

        return self._parse_search_results(result)

    def _parse_search_results(self, result) -> List[Chunk]:
        """Parse FT.SEARCH results into Chunk objects.

        The result format from valkey-glide ft.search is:
        [total_count, {key1: {field: value, ...}, key2: {field: value, ...}}]
        """
        chunks: List[Chunk] = []

        if not result:
            return chunks

        # Handle structured results (newer glide versions)
        if hasattr(result, "results"):
            for doc in result.results:
                chunk = self._doc_to_chunk(doc)
                if chunk:
                    chunks.append(chunk)
            return chunks

        # Handle list-based results: [total_count, {key: {fields}, ...}]
        if not isinstance(result, (list, tuple)) or len(result) < 2:
            return chunks

        docs = result[1]
        if isinstance(docs, dict):
            # Format: {b'key1': {b'field': b'value', ...}, ...}
            for key, fields in docs.items():
                if isinstance(fields, dict):
                    chunk = self._doc_to_chunk(fields)
                    if chunk:
                        chunks.append(chunk)
        elif isinstance(docs, list):
            for entry in docs:
                chunk = self._doc_to_chunk(entry)
                if chunk:
                    chunks.append(chunk)

        return chunks

    def _doc_to_chunk(self, doc) -> Optional[Chunk]:
        """Convert a search result document to a Chunk."""
        try:
            if hasattr(doc, "fields"):
                fields = doc.fields
            elif isinstance(doc, dict):
                # Normalize bytes keys to strings
                fields = {}
                for k, v in doc.items():
                    key = k.decode() if isinstance(k, bytes) else k
                    fields[key] = v
            elif isinstance(doc, (list, tuple)):
                # Convert flat list [field, value, field, value, ...] to dict
                fields = {}
                for j in range(0, len(doc), 2):
                    key = doc[j] if isinstance(doc[j], str) else doc[j].decode()
                    fields[key] = doc[j + 1]
            else:
                return None

            content = fields.get(_VALKEY_CONTENT_FIELD, "")
            if isinstance(content, bytes):
                content = content.decode()

            metadata_raw = fields.get(_VALKEY_METADATA_FIELD, "{}")
            if isinstance(metadata_raw, bytes):
                metadata_raw = metadata_raw.decode()
            metadata = json.loads(metadata_raw) if metadata_raw else {}

            chunk_id = fields.get(_VALKEY_CHUNK_ID_FIELD, "")
            if isinstance(chunk_id, bytes):
                chunk_id = chunk_id.decode()

            score_raw = fields.get("score", 0.0)
            if isinstance(score_raw, bytes):
                score_raw = score_raw.decode()
            # Convert distance to similarity score based on metric
            distance = float(score_raw)
            metric = self._vector_store_config.distance_metric.upper()
            if metric == "COSINE":
                # COSINE distance range: 0 (identical) to 2 (opposite)
                score = 1.0 - distance
            elif metric == "IP":
                # Inner Product: assumes normalized vectors; clamp for safety
                score = max(0.0, min(1.0, 1.0 + distance))
            else:
                # L2 (Euclidean): distance >= 0, convert via 1/(1+d)
                score = 1.0 / (1.0 + distance)

            return Chunk(
                content=content,
                metadata=metadata,
                chunk_id=chunk_id,
                score=score,
            )
        except Exception as e:
            logger.warning(f"Failed to parse search result document: {e}")
            return None

    def _build_filter_expression(self, filters: Optional[MetadataFilters]) -> str:
        """Build a Valkey search filter expression.

        Args:
            filters: Metadata filters to convert.

        Returns:
            Filter expression string for FT.SEARCH query.
        """
        if not filters or not filters.filters:
            return "*"

        if not self._vector_store_config.metadata_schema:
            raise ValueError(
                "Metadata filters provided but no metadata_schema configured. "
                "Configure metadata_schema in ValkeyVectorConfig to enable filtering."
            )

        expressions = []
        for f in filters.filters:
            expr = self._single_filter_to_expr(f)
            if expr:
                expressions.append(expr)

        if not expressions:
            return "*"

        if filters.condition == FilterCondition.OR:
            return " | ".join(expressions)
        else:
            # AND condition
            return " ".join(expressions)

    def _single_filter_to_expr(self, f) -> Optional[str]:
        """Convert a single MetadataFilter to a Valkey search expression."""
        key = _VALKEY_METADATA_PREFIX + f.key
        op = f.operator
        val = f.value

        if op == FilterOperator.EQ:
            if isinstance(val, (int, float)):
                return f"@{key}:[{val} {val}]"
            else:
                # Tag field exact match
                return f"@{key}:{{{_escape_tag_value(str(val))}}}"
        elif op == FilterOperator.GT:
            return f"@{key}:[({val} +inf]"
        elif op == FilterOperator.GTE:
            return f"@{key}:[{val} +inf]"
        elif op == FilterOperator.LT:
            return f"@{key}:[-inf ({val}]"
        elif op == FilterOperator.LTE:
            return f"@{key}:[-inf {val}]"
        elif op == FilterOperator.NE:
            if isinstance(val, (int, float)):
                return f"-@{key}:[{val} {val}]"
            else:
                return f"-@{key}:{{{_escape_tag_value(str(val))}}}"
        elif op == FilterOperator.IN:
            if isinstance(val, list):
                escaped = "|".join(_escape_tag_value(str(v)) for v in val)
                return f"@{key}:{{{escaped}}}"
            return None
        elif op == FilterOperator.NIN:
            if isinstance(val, list):
                escaped = "|".join(_escape_tag_value(str(v)) for v in val)
                return f"-@{key}:{{{escaped}}}"
            return None
        else:
            logger.warning(f"Unsupported filter operator for Valkey: {op}")
            return None

    def vector_name_exists(self) -> bool:
        """Check whether the vector index exists and has data."""
        try:
            if not self._index_exists():
                return False
            # Use FT.INFO to get the number of documents in the index
            from glide import ft

            info = self._run_async(ft.info(self.client, self._index_name))
            # info is a dict with index stats
            if isinstance(info, dict):
                num_docs = info.get(b"num_docs", info.get("num_docs", 0))
                if isinstance(num_docs, bytes):
                    num_docs = num_docs.decode()
                return int(num_docs) > 0
            return False
        except Exception as e:
            logger.error(f"vector_name_exists error: {e}")
            return False

    def delete_vector_name(self, vector_name: str) -> bool:
        """Delete the vector index and all associated keys.

        Args:
            vector_name: The name of the vector index to delete.

        Returns:
            True if deletion was successful.
        """
        from glide import ft

        logger.info(f"Deleting Valkey vector index: {self._index_name}")
        try:
            # Drop the index (does not delete the underlying hash keys)
            self._run_async(ft.dropindex(self.client, self._index_name))
        except Exception as e:
            logger.warning(f"Error dropping index: {e}")

        # Also delete any remaining keys with the prefix
        self._delete_keys_with_prefix(self._key_prefix)
        return True

    def delete_by_ids(self, ids: str) -> List[str]:
        """Delete vectors by their IDs.

        Args:
            ids: Comma-separated string of chunk IDs to delete.

        Returns:
            List of deleted chunk IDs.
        """
        id_list = [i.strip() for i in ids.split(",") if i.strip()]
        for chunk_id in id_list:
            key = self._key_prefix + chunk_id
            self._run_async(self.client.delete([key]))
        return id_list

    def truncate(self) -> List[str]:
        """Truncate all data in the collection.

        Returns:
            List of deleted key names.
        """
        logger.info(f"Truncating Valkey collection: {self._collection_name}")
        deleted = self._delete_keys_with_prefix(self._key_prefix)
        return deleted

    def _delete_keys_with_prefix(self, prefix: str) -> List[str]:
        """Delete all keys matching a prefix using SCAN.

        Args:
            prefix: Key prefix to match.

        Returns:
            List of deleted key names.
        """
        deleted_keys = []
        cursor = "0"
        while True:
            # Use SCAN to find keys with prefix
            result = self._run_async(
                self.client.custom_command(
                    ["SCAN", cursor, "MATCH", f"{prefix}*", "COUNT", "100"]
                )
            )
            if isinstance(result, (list, tuple)) and len(result) == 2:
                cursor = result[0]
                if isinstance(cursor, bytes):
                    cursor = cursor.decode()
                keys = result[1]
                if keys:
                    key_list = [k.decode() if isinstance(k, bytes) else k for k in keys]
                    self._run_async(self.client.delete(key_list))
                    deleted_keys.extend(key_list)
            else:
                break
            if str(cursor) == "0":
                break
        return deleted_keys

    def convert_metadata_filters(self, filters: MetadataFilters) -> str:
        """Convert metadata filters to Valkey search filter expression.

        Args:
            filters: Metadata filters.

        Returns:
            Filter expression string.
        """
        return self._build_filter_expression(filters)


def _escape_tag_value(value: str) -> str:
    """Escape special characters in tag values for Valkey search.

    Args:
        value: The tag value to escape.

    Returns:
        Escaped tag value safe for use in FT.SEARCH queries.
    """
    special_chars = r".,<>{}[]\"':;!@#$%^&*()-+=~/ |"
    escaped = ""
    for char in value:
        if char in special_chars:
            escaped += f"\\{char}"
        else:
            escaped += char
    return escaped
