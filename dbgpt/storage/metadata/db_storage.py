from contextlib import contextmanager

from typing import Type, List, Optional, Union, Dict
from dbgpt.core import Serializer
from dbgpt.core.interface.storage import (
    StorageInterface,
    QuerySpec,
    ResourceIdentifier,
    StorageItemAdapter,
    T,
)
from sqlalchemy import URL
from sqlalchemy.orm import Session, DeclarativeMeta

from .db_manager import BaseModel, DatabaseManager, BaseQuery


def _copy_public_properties(src: BaseModel, dest: BaseModel):
    """Simple copy public properties from src to dest"""
    for column in src.__table__.columns:
        if column.name != "id":
            setattr(dest, column.name, getattr(src, column.name))


class SQLAlchemyStorage(StorageInterface[T, BaseModel]):
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
        super().__init__(serializer=serializer, adapter=adapter)
        if isinstance(db_url_or_db, str) or isinstance(db_url_or_db, URL):
            db_manager = DatabaseManager()
            db_manager.init_db(db_url_or_db, engine_args, base, query_class)
            self.db_manager = db_manager
        elif isinstance(db_url_or_db, DatabaseManager):
            self.db_manager = db_url_or_db
        else:
            raise ValueError(
                f"db_url_or_db should be either url or a DatabaseManager, got {type(db_url_or_db)}"
            )
        self._model_class = model_class

    @contextmanager
    def session(self) -> Session:
        with self.db_manager.session() as session:
            yield session

    def save(self, data: T) -> None:
        with self.session() as session:
            model_instance = self.adapter.to_storage_format(data)
            session.add(model_instance)

    def update(self, data: T) -> None:
        with self.session() as session:
            model_instance = self.adapter.to_storage_format(data)
            session.merge(model_instance)

    def save_or_update(self, data: T) -> None:
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
        with self.session() as session:
            query = self.adapter.get_query_for_identifier(
                self._model_class, resource_id, session=session
            )
            model_instance = query.with_session(session).first()
            if model_instance:
                return self.adapter.from_storage_format(model_instance)
            return None

    def delete(self, resource_id: ResourceIdentifier) -> None:
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
                query = query.filter(getattr(self._model_class, key) == value)
            return query.count()
