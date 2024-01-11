from typing import Dict, Type

import pytest
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import Session, declarative_base

from dbgpt.core.interface.storage import (
    QuerySpec,
    ResourceIdentifier,
    StorageItem,
    StorageItemAdapter,
)
from dbgpt.core.interface.tests.test_storage import MockResourceIdentifier
from dbgpt.storage.metadata.db_storage import SQLAlchemyStorage
from dbgpt.util.serialization.json_serialization import JsonSerializer

Base = declarative_base()


class MockModel(Base):
    """The SQLAlchemy model for the mock data."""

    __tablename__ = "mock_data"
    id = Column(Integer, primary_key=True)
    data = Column(String)


class MockStorageItem(StorageItem):
    """The mock storage item."""

    def merge(self, other: "StorageItem") -> None:
        if not isinstance(other, MockStorageItem):
            raise ValueError("other must be a MockStorageItem")
        self.data = other.data

    def __init__(self, identifier: ResourceIdentifier, data: str):
        self._identifier = identifier
        self.data = data

    @property
    def identifier(self) -> ResourceIdentifier:
        return self._identifier

    def to_dict(self) -> Dict:
        return {"identifier": self._identifier, "data": self.data}

    def serialize(self) -> bytes:
        return str(self.data).encode()


class MockStorageItemAdapter(StorageItemAdapter[MockStorageItem, MockModel]):
    """The adapter for the mock storage item."""

    def to_storage_format(self, item: MockStorageItem) -> MockModel:
        return MockModel(id=int(item.identifier.str_identifier), data=item.data)

    def from_storage_format(self, model: MockModel) -> MockStorageItem:
        return MockStorageItem(MockResourceIdentifier(str(model.id)), model.data)

    def get_query_for_identifier(
        self,
        storage_format: Type[MockModel],
        resource_id: ResourceIdentifier,
        **kwargs,
    ):
        session: Session = kwargs.get("session")
        if session is None:
            raise ValueError("session is required for this adapter")
        return session.query(storage_format).filter(
            storage_format.id == int(resource_id.str_identifier)
        )


@pytest.fixture
def serializer():
    return JsonSerializer()


@pytest.fixture
def db_url():
    """Use in-memory SQLite database for testing"""
    return "sqlite:///:memory:"


@pytest.fixture
def sqlalchemy_storage(db_url, serializer):
    adapter = MockStorageItemAdapter()
    storage = SQLAlchemyStorage(db_url, MockModel, adapter, serializer, base=Base)
    Base.metadata.create_all(storage.db_manager.engine)
    return storage


def test_save_and_load(sqlalchemy_storage):
    item = MockStorageItem(MockResourceIdentifier("1"), "test_data")

    sqlalchemy_storage.save(item)

    loaded_item = sqlalchemy_storage.load(MockResourceIdentifier("1"), MockStorageItem)
    assert loaded_item.data == "test_data"


def test_delete(sqlalchemy_storage):
    resource_id = MockResourceIdentifier("1")

    sqlalchemy_storage.delete(resource_id)
    # Make sure the item is deleted
    assert sqlalchemy_storage.load(resource_id, MockStorageItem) is None


def test_query_with_various_conditions(sqlalchemy_storage):
    # Add multiple items for testing
    for i in range(5):
        item = MockStorageItem(MockResourceIdentifier(str(i)), f"test_data_{i}")
        sqlalchemy_storage.save(item)

    # Test query with single condition
    query_spec = QuerySpec(conditions={"data": "test_data_2"})
    results = sqlalchemy_storage.query(query_spec, MockStorageItem)
    assert len(results) == 1
    assert results[0].data == "test_data_2"

    # Test not existing condition
    query_spec = QuerySpec(conditions={"data": "nonexistent"})
    results = sqlalchemy_storage.query(query_spec, MockStorageItem)
    assert len(results) == 0

    # Test query with multiple conditions
    query_spec = QuerySpec(conditions={"data": "test_data_2", "id": "2"})
    results = sqlalchemy_storage.query(query_spec, MockStorageItem)
    assert len(results) == 1


def test_query_nonexistent_item(sqlalchemy_storage):
    query_spec = QuerySpec(conditions={"data": "nonexistent"})
    results = sqlalchemy_storage.query(query_spec, MockStorageItem)
    assert len(results) == 0


def test_count_items(sqlalchemy_storage):
    for i in range(5):
        item = MockStorageItem(MockResourceIdentifier(str(i)), f"test_data_{i}")
        sqlalchemy_storage.save(item)

    # Test count without conditions
    query_spec = QuerySpec(conditions={})
    total_count = sqlalchemy_storage.count(query_spec, MockStorageItem)
    assert total_count == 5

    # Test count with conditions
    query_spec = QuerySpec(conditions={"data": "test_data_2"})
    total_count = sqlalchemy_storage.count(query_spec, MockStorageItem)
    assert total_count == 1


def test_paginate_query(sqlalchemy_storage):
    for i in range(10):
        item = MockStorageItem(MockResourceIdentifier(str(i)), f"test_data_{i}")
        sqlalchemy_storage.save(item)

    page_size = 3
    page_number = 2

    query_spec = QuerySpec(conditions={})
    page_result = sqlalchemy_storage.paginate_query(
        page_number, page_size, MockStorageItem, query_spec
    )

    assert len(page_result.items) == page_size
    assert page_result.page == page_number
    assert page_result.total_pages == 4
    assert page_result.total_count == 10
