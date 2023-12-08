from abc import ABC, abstractmethod
from typing import Type, Dict


class Serializable(ABC):
    @abstractmethod
    def serialize(self) -> bytes:
        """Convert the object into bytes for storage or transmission.

        Returns:
            bytes: The byte array after serialization
        """

    @abstractmethod
    def to_dict(self) -> Dict:
        """Convert the object's state to a dictionary."""


class Serializer(ABC):
    """The serializer abstract class for serializing cache keys and values."""

    @abstractmethod
    def serialize(self, obj: Serializable) -> bytes:
        """Serialize a cache object.

        Args:
            obj (Serializable): The object to serialize
        """

    @abstractmethod
    def deserialize(self, data: bytes, cls: Type[Serializable]) -> Serializable:
        """Deserialize data back into a cache object of the specified type.

        Args:
            data (bytes): The byte array to deserialize
            cls (Type[Serializable]): The type of current object

        Returns:
            Serializable: The serializable object
        """
