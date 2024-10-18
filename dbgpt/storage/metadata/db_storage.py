"""Database storage implementation using SQLAlchemy."""
from contextlib import contextmanager
from typing import Dict, Iterator, List, Optional, Type, Union

from sqlalchemy import URL
from sqlalchemy.orm import DeclarativeMeta, Session

from dbgpt.core import Serializer
from dbgpt.core.interface.storage import (
    QuerySpec,
    ResourceIdentifier,
    StorageInterface,
    StorageItemAdapter,
    T,
)

from .db_manager import BaseModel, BaseQuery, DatabaseManager


def _copy_public_properties(src: BaseModel, dest: BaseModel):
    """Copy public properties from src to dest."""
    for column in src.__table__.columns:  # type: ignore
        if column.name != "id":
            value = getattr(src, column.name)
            if value is not None:
                setattr(dest, column.name, value)


class SQLAlchemyStorage(StorageInterface[T, BaseModel]):
    """Database storage implementation using SQLAlchemy."""

    def __init__(
        self,
        db_url_or_db: Union[str, URL, DatabaseManager],
        model_class: Type[BaseModel],
        adapter: StorageItemAdapter[T, BaseModel],
        serializer: Optional[Serializer] = None,
        engine_args: Optional[Dict] = None,
        base: Optional[DeclarativeMeta] = None,
        query_class=BaseQuery,
    ):
        """Create a SQLAlchemyStorage instance."""
        super().__init__(serializer=serializer, adapter=adapter)
        self.db_manager = DatabaseManager.build_from(
            db_url_or_db, engine_args, base, query_class
        )
        self._model_class = model_class

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Return a session."""
        with self.db_manager.session() as session:
            yield session

    def save(self, data: T) -> None:
        """Save data to the storage."""
        with self.session() as session:
            model_instance = self.adapter.to_storage_format(data)
            session.add(model_instance)

    def update(self, data: T) -> None:
        """Update data in the storage."""
        with self.session() as session:
            query = self.adapter.get_query_for_identifier(
                self._model_class, data.identifier, session=session
            )
            exist_model_instance = query.with_session(session).first()
            if exist_model_instance:
                _copy_public_properties(
                    self.adapter.to_storage_format(data), exist_model_instance
                )
                session.merge(exist_model_instance)
                return

    def save_or_update(self, data: T) -> None:
        """Save or update data in the storage."""
        with self.session() as session:
            query = self.adapter.get_query_for_identifier(
                self._model_class, data.identifier, session=session
            )
            model_instance = query.with_session(session).first()
            if model_instance:
                new_instance = self.adapter.to_storage_format(data)
                _copy_public_properties(new_instance, model_instance)
                session.merge(model_instance)
                return
        self.save(data)

    def load(self, resource_id: ResourceIdentifier, cls: Type[T]) -> Optional[T]:
        """Load data by identifier from the storage."""
        with self.session() as session:
            query = self.adapter.get_query_for_identifier(
                self._model_class, resource_id, session=session
            )
            model_instance = query.with_session(session).first()
            if model_instance:
                return self.adapter.from_storage_format(model_instance)
            return None

    def delete(self, resource_id: ResourceIdentifier) -> None:
        """Delete data by identifier from the storage."""
        with self.session() as session:
            query = self.adapter.get_query_for_identifier(
                self._model_class, resource_id, session=session
            )
            model_instance = query.with_session(session).first()
            if model_instance:
                session.delete(model_instance)

    def query(self, spec: QuerySpec, cls: Type[T]) -> List[T]:
        """Query data from the storage.

        Args:
            spec (QuerySpec): The query specification
            cls (Type[T]): The type of the data
        """
        with self.session() as session:
            query = session.query(self._model_class)
            for key, value in spec.conditions.items():
                if value is not None:
                    query = query.filter(getattr(self._model_class, key) == value)
            if spec.limit is not None:
                query = query.limit(spec.limit)
            if spec.offset is not None:
                query = query.offset(spec.offset)
            model_instances = query.all()
            return [
                self.adapter.from_storage_format(instance)
                for instance in model_instances
            ]

    def count(self, spec: QuerySpec, cls: Type[T]) -> int:
        """Count the number of data in the storage.

        Args:
            spec (QuerySpec): The query specification
            cls (Type[T]): The type of the data
        """
        with self.session() as session:
            query = session.query(self._model_class)
            for key, value in spec.conditions.items():
                if value is not None:
                    query = query.filter(getattr(self._model_class, key) == value)
            return query.count()
