import json
from abc import ABC, abstractmethod
from typing import Dict, Type

from dbgpt.core.awel.flow import ResourceCategory, register_resource
from dbgpt.core.interface.serialization import Serializable, Serializer

JSON_ENCODING = "utf-8"


class JsonSerializable(Serializable, ABC):
    @abstractmethod
    def to_dict(self) -> Dict:
        """Return the dict of current serializable object"""

    def serialize(self) -> bytes:
        """Convert the object into bytes for storage or transmission."""
        return json.dumps(self.to_dict(), ensure_ascii=False).encode(JSON_ENCODING)


@register_resource(
    label="Json Serializer",
    name="json_serializer",
    category=ResourceCategory.SERIALIZER,
    description="The serializer for serializing data with json format.",
)
class JsonSerializer(Serializer):
    """The serializer abstract class for serializing cache keys and values."""

    def serialize(self, obj: Serializable) -> bytes:
        """Serialize a cache object.

        Args:
            obj (Serializable): The object to serialize
        """
        return json.dumps(obj.to_dict(), ensure_ascii=False).encode(JSON_ENCODING)

    def deserialize(self, data: bytes, cls: Type[Serializable]) -> Serializable:
        """Deserialize data back into a cache object of the specified type.

        Args:
            data (bytes): The byte array to deserialize
            cls (Type[Serializable]): The type of current object

        Returns:
            Serializable: The serializable object
        """
        # Convert bytes back to JSON and then to the specified class
        json_data = json.loads(data.decode(JSON_ENCODING))
        # Assume that the cls has an __init__ that accepts a dictionary
        obj = cls(**json_data)
        obj.set_serializer(self)
        return obj
