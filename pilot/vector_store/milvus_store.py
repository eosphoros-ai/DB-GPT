
from pymilvus import DataType, FieldSchema, CollectionSchema, connections, Collection

from pilot.vector_store.vector_store_base import VectorStoreBase


class MilvusStore(VectorStoreBase):
    def __init__(self, cfg: {}) -> None:
        """Construct a milvus memory storage connection.

        Args:
            cfg (Config): Auto-GPT global config.
        """
        # self.configure(cfg)

        connect_kwargs = {}
        self.uri = None
        self.uri = cfg["url"]
        self.port = cfg["port"]
        self.username = cfg.get("username", None)
        self.password = cfg.get("password", None)
        self.collection_name = cfg["table_name"]
        self.password = cfg.get("secure", None)

        # use HNSW by default.
        self.index_params = {
            "metric_type": "IP",
            "index_type": "HNSW",
            "params": {"M": 8, "efConstruction": 64},
        }

        if (self.username is None) != (self.password is None):
            raise ValueError(
                "Both username and password must be set to use authentication for Milvus"
            )
        if self.username:
            connect_kwargs["user"] = self.username
            connect_kwargs["password"] = self.password

        connections.connect(
            **connect_kwargs,
            host=self.uri or "127.0.0.1",
            port=self.port or "19530",
            alias="default"
            # secure=self.secure,
        )

        self.init_schema()

    def init_schema(self) -> None:
        """Initialize collection in milvus database."""
        fields = [
            FieldSchema(name="pk", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=384),
            FieldSchema(name="raw_text", dtype=DataType.VARCHAR, max_length=65535),
        ]

        # create collection if not exist and load it.
        self.schema = CollectionSchema(fields, "db-gpt memory storage")
        self.collection = Collection(self.collection_name, self.schema)
        self.index_params = {
            "metric_type": "IP",
            "index_type": "HNSW",
            "params": {"M": 8, "efConstruction": 64},
        }
        # create index if not exist.
        if not self.collection.has_index():
            self.collection.release()
            self.collection.create_index(
                "vector",
                self.index_params,
                index_name="vector",
            )
        self.collection.load()

    # def add(self, data) -> str:
    #     """Add an embedding of data into milvus.
    #
    #     Args:
    #         data (str): The raw text to construct embedding index.
    #
    #     Returns:
    #         str: log.
    #     """
    #     embedding = get_ada_embedding(data)
    #     result = self.collection.insert([[embedding], [data]])
    #     _text = (
    #         "Inserting data into memory at primary key: "
    #         f"{result.primary_keys[0]}:\n data: {data}"
    #     )
    #     return _text