from abc import ABC, abstractmethod


class VectorStoreBase(ABC):
    """base class for vector store database"""

    @abstractmethod
    def load_document(self, documents) -> None:
        """load document in vector database."""
        pass

    @abstractmethod
    def similar_search(self, text, topk) -> None:
        """Initialize schema in vector database."""
        pass