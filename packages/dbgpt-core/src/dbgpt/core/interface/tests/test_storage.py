from typing import Dict, Union

import pytest

from dbgpt.core.interface.storage import (
    InMemoryStorage,
    QuerySpec,
    ResourceIdentifier,
    StorageError,
    StorageItem,
)
from dbgpt.util.serialization.json_serialization import JsonSerializer


class MockResourceIdentifier(ResourceIdentifier):
    def __init__(self, identifier: str):
        self._identifier = identifier

    @property
    def str_identifier(self) -> str:
        return self._identifier

    def to_dict(self) -> Dict:
        return {"identifier": self._identifier}


class MockStorageItem(StorageItem):
    def merge(self, other: "StorageItem") -> None:
        if not isinstance(other, MockStorageItem):
            raise ValueError("other must be a MockStorageItem")
        self.data = other.data

    def __init__(self, identifier: Union[str, MockResourceIdentifier], data):
        self._identifier_str = (
            identifier if isinstance(identifier, str) else identifier.str_identifier
        )
        self.data = data

    def to_dict(self) -> Dict:
        return {"identifier": self._identifier_str, "data": self.data}

    @property
    def identifier(self) -> ResourceIdentifier:
        return MockResourceIdentifier(self._identifier_str)


@pytest.fixture
def serializer():
    return JsonSerializer()


@pytest.fixture
def in_memory_storage(serializer):
    return InMemoryStorage(serializer)


def test_save_and_load(in_memory_storage):
    resource_id = MockResourceIdentifier("1")
    item = MockStorageItem(resource_id, "test_data")

    in_memory_storage.save(item)

    loaded_item = in_memory_storage.load(resource_id, MockStorageItem)
    assert loaded_item.data == "test_data"


def test_duplicate_save(in_memory_storage):
    item = MockStorageItem("1", "test_data")

    in_memory_storage.save(item)

    # Should raise StorageError when saving the same data
    with pytest.raises(StorageError):
        in_memory_storage.save(item)


def test_delete(in_memory_storage):
    resource_id = MockResourceIdentifier("1")
    item = MockStorageItem(resource_id, "test_data")

    in_memory_storage.save(item)
    in_memory_storage.delete(resource_id)
    # Storage should not contain the data after deletion
    assert in_memory_storage.load(resource_id, MockStorageItem) is None


def test_query(in_memory_storage):
    resource_id1 = MockResourceIdentifier("1")
    item1 = MockStorageItem(resource_id1, "test_data1")

    resource_id2 = MockResourceIdentifier("2")
    item2 = MockStorageItem(resource_id2, "test_data2")

    in_memory_storage.save(item1)
    in_memory_storage.save(item2)

    query_spec = QuerySpec(conditions={"data": "test_data1"})
    results = in_memory_storage.query(query_spec, MockStorageItem)
    assert len(results) == 1
    assert results[0].data == "test_data1"


def test_count(in_memory_storage):
    item1 = MockStorageItem("1", "test_data1")

    item2 = MockStorageItem("2", "test_data2")

    in_memory_storage.save(item1)
    in_memory_storage.save(item2)

    query_spec = QuerySpec(conditions={})
    count = in_memory_storage.count(query_spec, MockStorageItem)
    assert count == 2


def test_paginate_query(in_memory_storage):
    for i in range(10):
        resource_id = MockResourceIdentifier(str(i))
        item = MockStorageItem(resource_id, f"test_data{i}")
        in_memory_storage.save(item)

    page_size = 3
    query_spec = QuerySpec(conditions={})
    page_result = in_memory_storage.paginate_query(
        2, page_size, MockStorageItem, query_spec
    )

    assert len(page_result.items) == page_size
    assert page_result.total_count == 10
    assert page_result.total_pages == 4
    assert page_result.page == 2
