"""The storage interface for storing and loading data."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, cast

from dbgpt.core.interface.serialization import Serializable, Serializer
from dbgpt.util.annotations import PublicAPI
from dbgpt.util.i18n_utils import _
from dbgpt.util.pagination_utils import PaginationResult
from dbgpt.util.serialization.json_serialization import JsonSerializer

from ..awel.flow import Parameter, ResourceCategory, register_resource


@PublicAPI(stability="beta")
class ResourceIdentifier(Serializable, ABC):
    """The resource identifier interface for resource identifiers."""

    @property
    @abstractmethod
    def str_identifier(self) -> str:
        """Get the string identifier of the resource.

        The string identifier is used to uniquely identify the resource.

        Returns:
            str: The string identifier of the resource
        """

    def __hash__(self) -> int:
        """Return the hash value of the key."""
        return hash(self.str_identifier)

    def __eq__(self, other: Any) -> bool:
        """Check equality with another key."""
        if not isinstance(other, ResourceIdentifier):
            return False
        return self.str_identifier == other.str_identifier


@PublicAPI(stability="beta")
class StorageItem(Serializable, ABC):
    """The storage item interface for storage items."""

    @property
    @abstractmethod
    def identifier(self) -> ResourceIdentifier:
        """Get the resource identifier of the storage item.

        Returns:
            ResourceIdentifier: The resource identifier of the storage item
        """

    @abstractmethod
    def merge(self, other: "StorageItem") -> None:
        """Merge the other storage item into the current storage item.

        Args:
            other (StorageItem): The other storage item
        """


ID = TypeVar("ID", bound=ResourceIdentifier)
T = TypeVar("T", bound=StorageItem)
TDataRepresentation = TypeVar("TDataRepresentation")


class StorageItemAdapter(Generic[T, TDataRepresentation]):
    """Storage item adapter.

    The storage item adapter for converting storage items to and from the storage
    format.

    Sometimes, the storage item is not the same as the storage format,
    so we need to convert the storage item to the storage format and vice versa.

    In database storage, the storage format is database model, but the StorageItem is
    the user-defined object.
    """

    @abstractmethod
    def to_storage_format(self, item: T) -> TDataRepresentation:
        """Convert the storage item to the storage format.

        Args:
            item (T): The storage item

        Returns:
            TDataRepresentation: The data in the storage format
        """

    @abstractmethod
    def from_storage_format(self, data: TDataRepresentation) -> T:
        """Convert the storage format to the storage item.

        Args:
            data (TDataRepresentation): The data in the storage format

        Returns:
            T: The storage item
        """

    @abstractmethod
    def get_query_for_identifier(
        self,
        storage_format: Type[TDataRepresentation],
        resource_id: ResourceIdentifier,
        **kwargs,
    ) -> Any:
        """Get the query for the resource identifier.

        Args:
            storage_format (Type[TDataRepresentation]): The storage format
            resource_id (ResourceIdentifier): The resource identifier
            kwargs: The additional arguments

        Returns:
            Any: The query for the resource identifier
        """


class DefaultStorageItemAdapter(StorageItemAdapter[T, T]):
    """Default storage item adapter.

    The default storage item adapter for converting storage items to and from the
    storage format.

    The storage item is the same as the storage format, so no conversion is required.
    """

    def to_storage_format(self, item: T) -> T:
        """Convert the storage item to the storage format.

        Returns the storage item itself.

        Args:
            item (T): The storage item

        Returns:
            T: The data in the storage format
        """
        return item

    def from_storage_format(self, data: T) -> T:
        """Convert the storage format to the storage item.

        Returns the storage format itself.

        Args:
            data (T): The data in the storage format

        Returns:
            T: The storage item
        """
        return data

    def get_query_for_identifier(
        self, storage_format: Type[T], resource_id: ID, **kwargs
    ) -> bool:
        """Return the query for the resource identifier."""
        return True


@PublicAPI(stability="beta")
class StorageError(Exception):
    """The base exception class for storage errors."""

    def __init__(self, message: str):
        """Create a new StorageError."""
        super().__init__(message)


@PublicAPI(stability="beta")
class QuerySpec:
    """The query specification for querying data from the storage.

    Attributes:
        conditions (Dict[str, Any]): The conditions for querying data
        limit (int): The maximum number of data to return
        offset (int): The offset of the data to return
    """

    def __init__(
        self, conditions: Dict[str, Any], limit: Optional[int] = None, offset: int = 0
    ) -> None:
        """Create a new QuerySpec."""
        self.conditions = conditions
        self.limit = limit
        self.offset = offset


@PublicAPI(stability="beta")
class StorageInterface(Generic[T, TDataRepresentation], ABC):
    """The storage interface for storing and loading data."""

    def __init__(
        self,
        serializer: Optional[Serializer] = None,
        adapter: Optional[StorageItemAdapter[T, TDataRepresentation]] = None,
    ):
        """Create a new StorageInterface."""
        self._serializer = serializer or JsonSerializer()
        self._storage_item_adapter = adapter or DefaultStorageItemAdapter()

    @property
    def serializer(self) -> Serializer:
        """Get the serializer of the storage.

        Returns:
            Serializer: The serializer of the storage
        """
        return self._serializer

    @property
    def adapter(self) -> StorageItemAdapter[T, TDataRepresentation]:
        """Get the adapter of the storage.

        Returns:
            StorageItemAdapter[T, TDataRepresentation]: The adapter of the storage
        """
        return self._storage_item_adapter

    @abstractmethod
    def save(self, data: T) -> None:
        """Save the data to the storage.

        Args:
            data (T): The data to save

        Raises:
            StorageError: If the data already exists in the storage or data is None
        """

    @abstractmethod
    def update(self, data: T) -> None:
        """Update the data to the storage.

        Args:
            data (T): The data to save

        Raises:
            StorageError: If data is None
        """

    @abstractmethod
    def save_or_update(self, data: T) -> None:
        """Save or update the data to the storage.

        Args:
            data (T): The data to save

        Raises:
            StorageError: If data is None
        """

    def save_list(self, data: List[T]) -> None:
        """Save the data to the storage.

        Args:
            data (T): The data to save

        Raises:
            StorageError: If the data already exists in the storage or data is None
        """
        for d in data:
            self.save(d)

    def save_or_update_list(self, data: List[T]) -> None:
        """Save or update the data to the storage.

        Args:
            data (T): The data to save
        """
        for d in data:
            self.save_or_update(d)

    @abstractmethod
    def load(self, resource_id: ID, cls: Type[T]) -> Optional[T]:
        """Load the data from the storage.

        None will be returned if the data does not exist in the storage.

        Load data with resource_id will be faster than query data with conditions,
        so we suggest to use load if possible.

        Args:
            resource_id (ID): The resource identifier of the data
            cls (Type[T]): The type of the data

        Returns:
            Optional[T]: The loaded data
        """

    def load_list(self, resource_id: List[ID], cls: Type[T]) -> List[T]:
        """Load the data from the storage.

        None will be returned if the data does not exist in the storage.

        Load data with resource_id will be faster than query data with conditions,
        so we suggest to use load if possible.

        Args:
            resource_id (ID): The resource identifier of the data
            cls (Type[T]): The type of the data

        Returns:
            Optional[T]: The loaded data
        """
        result = []
        for r in resource_id:
            item = self.load(r, cls)
            if item is not None:
                result.append(item)
        return result

    @abstractmethod
    def delete(self, resource_id: ID) -> None:
        """Delete the data from the storage.

        Args:
            resource_id (ID): The resource identifier of the data
        """

    def delete_list(self, resource_id: List[ID]) -> None:
        """Delete the data from the storage.

        Args:
            resource_id (ID): The resource identifier of the data
        """
        for r in resource_id:
            self.delete(r)

    @abstractmethod
    def query(self, spec: QuerySpec, cls: Type[T]) -> List[T]:
        """Query data from the storage.

        Query data with resource_id will be faster than query data with conditions,
        so please use load if possible.

        Args:
            spec (QuerySpec): The query specification
            cls (Type[T]): The type of the data

        Returns:
            List[T]: The queried data
        """

    @abstractmethod
    def count(self, spec: QuerySpec, cls: Type[T]) -> int:
        """Count the number of data from the storage.

        Args:
            spec (QuerySpec): The query specification
            cls (Type[T]): The type of the data

        Returns:
            int: The number of data
        """

    def paginate_query(
        self, page: int, page_size: int, cls: Type[T], spec: Optional[QuerySpec] = None
    ) -> PaginationResult[T]:
        """Paginate the query result.

        Args:
            page (int): The page number
            page_size (int): The number of items per page
            cls (Type[T]): The type of the data
            spec (Optional[QuerySpec], optional): The query specification.
                Defaults to None.

        Returns:
            PaginationResult[T]: The pagination result
        """
        if spec is None:
            spec = QuerySpec(conditions={})
        spec.limit = page_size
        spec.offset = (page - 1) * page_size
        items = self.query(spec, cls)
        total = self.count(spec, cls)
        return PaginationResult(
            items=items,
            total_count=total,
            total_pages=(total + page_size - 1) // page_size,
            page=page,
            page_size=page_size,
        )


@register_resource(
    label=_("Memory Storage"),
    name="in_memory_storage",
    category=ResourceCategory.STORAGE,
    description=_("Save your data in memory."),
    parameters=[
        Parameter.build_from(
            _("Serializer"),
            "serializer",
            Serializer,
            optional=True,
            default=None,
            description=_(
                "The serializer for serializing the data. If not set, the "
                "default JSON serializer will be used."
            ),
        )
    ],
)
@PublicAPI(stability="alpha")
class InMemoryStorage(StorageInterface[T, T]):
    """The in-memory storage for storing and loading data."""

    def __init__(
        self,
        serializer: Optional[Serializer] = None,
    ):
        """Create a new InMemoryStorage."""
        super().__init__(serializer)
        # Key: ResourceIdentifier, Value: Serialized data
        self._data: Dict[str, bytes] = {}

    def save(self, data: T) -> None:
        """Save the data to the storage.

        Args:
            data (T): The data to save
        """
        if not data:
            raise StorageError("Data cannot be None")
        if not data._serializer:
            data.set_serializer(self.serializer)

        if data.identifier.str_identifier in self._data:
            raise StorageError(
                f"Data with identifier {data.identifier.str_identifier} already exists"
            )
        self._data[data.identifier.str_identifier] = data.serialize()

    def update(self, data: T) -> None:
        """Update the data to the storage."""
        if not data:
            raise StorageError("Data cannot be None")
        if not data._serializer:
            data.set_serializer(self.serializer)
        self._data[data.identifier.str_identifier] = data.serialize()

    def save_or_update(self, data: T) -> None:
        """Save or update the data to the storage."""
        self.update(data)

    def load(self, resource_id: ID, cls: Type[T]) -> Optional[T]:
        """Load the data from the storage."""
        serialized_data = self._data.get(resource_id.str_identifier)
        if serialized_data is None:
            return None
        return cast(T, self.serializer.deserialize(serialized_data, cls))

    def delete(self, resource_id: ID) -> None:
        """Delete the data from the storage."""
        if resource_id.str_identifier in self._data:
            del self._data[resource_id.str_identifier]

    def query(self, spec: QuerySpec, cls: Type[T]) -> List[T]:
        """Query data from the storage.

        Args:
            spec (QuerySpec): The query specification
            cls (Type[T]): The type of the data

        Returns:
            List[T]: The queried data
        """
        result = []
        for serialized_data in self._data.values():
            data = cast(T, self._serializer.deserialize(serialized_data, cls))
            if all(
                getattr(data, key) == value for key, value in spec.conditions.items()
            ):
                result.append(data)

        # Apply limit and offset
        if spec.limit is not None:
            result = result[spec.offset : spec.offset + spec.limit]
        else:
            result = result[spec.offset :]
        return result

    def count(self, spec: QuerySpec, cls: Type[T]) -> int:
        """Count the number of data from the storage.

        Args:
            spec (QuerySpec): The query specification
            cls (Type[T]): The type of the data

        Returns:
            int: The number of data
        """
        count = 0
        for serialized_data in self._data.values():
            data = self._serializer.deserialize(serialized_data, cls)
            if all(
                getattr(data, key) == value for key, value in spec.conditions.items()
            ):
                count += 1
        return count
