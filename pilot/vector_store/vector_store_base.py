from abc import ABC, abstractmethod


class VectorStoreBase(ABC):

    @abstractmethod
    def init_schema(self) -> None:
        """Initialize schema in vector database."""
        pass