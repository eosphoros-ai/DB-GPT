import os
import json
import weaviate
from langchain.vectorstores import Weaviate
from pilot.configs.model_config import KNOWLEDGE_UPLOAD_ROOT_PATH
from pilot.logs import logger
from pilot.vector_store.vector_store_base import VectorStoreBase


class WeaviateStore(VectorStoreBase):
    """Weaviate database"""

    def __init__(self, ctx: dict, weaviate_url: str) -> None:
        """Initialize with Weaviate client."""
        try:
            import weaviate
        except ImportError:
            raise ValueError(
                "Could not import weaviate python package. "
                "Please install it with `pip install weaviate-client`."
            )

        self.ctx = ctx
        self.weaviate_url = weaviate_url
        self.persist_dir = os.path.join(
            KNOWLEDGE_UPLOAD_ROOT_PATH, ctx["vector_store_name"] + ".vectordb"
        )

        self.vector_store_client = weaviate.Client(self.weaviate_url)

    def similar_search(self, text: str, topk: int) -> None:
        """Perform similar search in Weaviate"""
        logger.info("Weaviate similar search")
        nearText = {
            "concepts": [text],
            "distance": 0.75,  # prior to v1.14 use "certainty" instead of "distance"
        }
        response = (
            self.vector_store_client.query.get("Document", ["metadata", "text"])
            .with_near_vector({"vector": nearText})
            .with_limit(topk)
            .with_additional(["distance"])
            .do()
        )

        return json.dumps(response, indent=2)

    def vector_name_exists(self) -> bool:
        """Check if a vector name exists for a given class in Weaviate.
        Returns:
            bool: True if the vector name exists, False otherwise.
        """
        if self.vector_store_client.schema.get("Document"):
            return True
        return False

    def _default_schema(self) -> None:
        """
        Create the schema for Weaviate with a Document class containing metadata and text properties.
        """

        schema = {
            "classes": [
                {
                    "class": "Document",
                    "description": "A document with metadata and text",
                    "moduleConfig": {
                        "text2vec-transformers": {
                            "poolingStrategy": "masked_mean",
                            "vectorizeClassName": False,
                        }
                    },
                    "properties": [
                        {
                            "dataType": ["text"],
                            "moduleConfig": {
                                "text2vec-transformers": {
                                    "skip": False,
                                    "vectorizePropertyName": False,
                                }
                            },
                            "description": "Metadata of the document",
                            "name": "metadata",
                        },
                        {
                            "dataType": ["text"],
                            "moduleConfig": {
                                "text2vec-transformers": {
                                    "skip": False,
                                    "vectorizePropertyName": False,
                                }
                            },
                            "description": "Text content of the document",
                            "name": "text",
                        },
                    ],
                    "vectorizer": "text2vec-transformers",
                }
            ]
        }

        # Create the schema in Weaviate
        self.vector_store_client.schema.create(schema)

    def load_document(self, documents: list) -> None:
        """Load documents into Weaviate"""
        logger.info("Weaviate load document")
        texts = [doc.page_content for doc in documents]
        metadatas = [doc.metadata for doc in documents]

        # Import data
        with self.vector_store_client.batch as batch:
            batch.batch_size = 100

            # Batch import all documents
            for i in range(len(texts)):
                properties = {"metadata": metadatas[i], "text": texts[i]}

                self.vector_store_client.batch.add_data_object(properties, "Document")
