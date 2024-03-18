"""Weaviate vector store."""
import logging
import os
from typing import List

from dbgpt._private.config import Config
from dbgpt._private.pydantic import Field
from dbgpt.core import Chunk

from .base import VectorStoreBase, VectorStoreConfig

logger = logging.getLogger(__name__)
CFG = Config()


class WeaviateVectorConfig(VectorStoreConfig):
    """Weaviate vector store config."""

    class Config:
        """Config for BaseModel."""

        arbitrary_types_allowed = True

    weaviate_url: str = Field(
        default=os.getenv("WEAVIATE_URL", None),
        description="weaviate url address, if not set, will use the default url.",
    )
    persist_path: str = Field(
        default=os.getenv("WEAVIATE_PERSIST_PATH", None),
        description="weaviate persist path.",
    )


class WeaviateStore(VectorStoreBase):
    """Weaviate database."""

    def __init__(self, vector_store_config: WeaviateVectorConfig) -> None:
        """Initialize with Weaviate client."""
        try:
            import weaviate
        except ImportError:
            raise ValueError(
                "Could not import weaviate python package. "
                "Please install it with `pip install weaviate-client`."
            )

        self.weaviate_url = vector_store_config.weaviate_url
        self.embedding = vector_store_config.embedding_fn
        self.vector_name = vector_store_config.name
        self.persist_dir = os.path.join(
            vector_store_config.persist_path, vector_store_config.name + ".vectordb"
        )

        self.vector_store_client = weaviate.Client(self.weaviate_url)

    def similar_search(self, text: str, topk: int) -> List[Chunk]:
        """Perform similar search in Weaviate."""
        logger.info("Weaviate similar search")
        # nearText = {
        #     "concepts": [text],
        #     "distance": 0.75,  # prior to v1.14 use "certainty" instead of "distance"
        # }
        # vector = self.embedding.embed_query(text)
        response = (
            self.vector_store_client.query.get(
                self.vector_name, ["metadata", "page_content"]
            )
            # .with_near_vector({"vector": vector})
            .with_limit(topk).do()
        )
        res = response["data"]["Get"][list(response["data"]["Get"].keys())[0]]
        docs = []
        for r in res:
            docs.append(
                Chunk(
                    content=r["page_content"],
                    metadata={"metadata": r["metadata"]},
                )
            )
        return docs

    def vector_name_exists(self) -> bool:
        """Whether the vector name exists in Weaviate.

        Returns:
            bool: True if the vector name exists, False otherwise.
        """
        try:
            if self.vector_store_client.schema.get(self.vector_name):
                return True
            return False
        except Exception as e:
            logger.error(f"vector_name_exists error, {str(e)}")
            return False

    def _default_schema(self) -> None:
        """Create default schema in Weaviate.

        Create the schema for Weaviate with a Document class containing metadata and
        text properties.
        """
        schema = {
            "classes": [
                {
                    "class": self.vector_name,
                    "description": "A document with metadata and text",
                    # "moduleConfig": {
                    #     "text2vec-transformers": {
                    #         "poolingStrategy": "masked_mean",
                    #         "vectorizeClassName": False,
                    #     }
                    # },
                    "properties": [
                        {
                            "dataType": ["text"],
                            # "moduleConfig": {
                            #     "text2vec-transformers": {
                            #         "skip": False,
                            #         "vectorizePropertyName": False,
                            #     }
                            # },
                            "description": "Metadata of the document",
                            "name": "metadata",
                        },
                        {
                            "dataType": ["text"],
                            # "moduleConfig": {
                            #     "text2vec-transformers": {
                            #         "skip": False,
                            #         "vectorizePropertyName": False,
                            #     }
                            # },
                            "description": "Text content of the document",
                            "name": "page_content",
                        },
                    ],
                    # "vectorizer": "text2vec-transformers",
                }
            ]
        }

        # Create the schema in Weaviate
        self.vector_store_client.schema.create(schema)

    def load_document(self, chunks: List[Chunk]) -> List[str]:
        """Load document to Weaviate."""
        logger.info("Weaviate load document")
        texts = [doc.content for doc in chunks]
        metadatas = [doc.metadata for doc in chunks]

        # Import data
        with self.vector_store_client.batch as batch:
            batch.batch_size = 100

            # Batch import all documents
            for i in range(len(texts)):
                properties = {
                    "metadata": metadatas[i]["source"],
                    "content": texts[i],
                }

                self.vector_store_client.batch.add_data_object(
                    data_object=properties, class_name=self.vector_name
                )
            self.vector_store_client.batch.flush()
        # TODO: return ids
        return []
