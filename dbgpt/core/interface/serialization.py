"""The interface for serializing."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Optional, Type


class Serializable(ABC):
    """The serializable abstract class."""

    serializer: Optional["Serializer"] = None

    @abstractmethod
    def to_dict(self) -> Dict:
        """Convert the object's state to a dictionary."""

    def serialize(self) -> bytes:
        """Convert the object into bytes for storage or transmission.

        Returns:
            bytes: The byte array after serialization
        """
        if self.serializer is None:
            raise ValueError(
                "Serializer is not set. Please set the serializer before serialization."
            )
        return self.serializer.serialize(self)

    def set_serializer(self, serializer: "Serializer") -> None:
        """Set the serializer for current serializable object.

        Args:
            serializer (Serializer): The serializer to set
        """
        self.serializer = serializer


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
