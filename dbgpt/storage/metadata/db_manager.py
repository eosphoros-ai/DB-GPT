from __future__ import annotations

import abc
from contextlib import contextmanager
from typing import TypeVar, Generic, Union, Dict, Optional, Type, Iterator, List
import logging
from sqlalchemy import create_engine, URL, Engine
from sqlalchemy import orm, inspect, MetaData
from sqlalchemy.orm import (
    scoped_session,
    sessionmaker,
    Session,
    declarative_base,
    DeclarativeMeta,
)
from sqlalchemy.orm.session import _PKIdentityArgument
from sqlalchemy.orm.exc import UnmappedClassError

from sqlalchemy.pool import QueuePool
from dbgpt.util.string_utils import _to_str
from dbgpt.util.pagination_utils import PaginationResult

logger = logging.getLogger(__name__)
T = TypeVar("T", bound="BaseModel")


class _QueryObject:
    """The query object."""

    def __init__(self, db_manager: "DatabaseManager"):
        self._db_manager = db_manager

    def __get__(self, obj, type):
        try:
            mapper = orm.class_mapper(type)
            if mapper:
                return type.query_class(mapper, session=self._db_manager._session())
        except UnmappedClassError:
            return None


class BaseQuery(orm.Query):
    def paginate_query(
        self, page: Optional[int] = 1, per_page: Optional[int] = 20
    ) -> PaginationResult:
        """Paginate the query.

        Example:
            .. code-block:: python
                from dbgpt.storage.metadata import db, Model
                class User(Model):
                     __tablename__ = "user"
                     id = Column(Integer, primary_key=True)
                     name = Column(String(50))
                     fullname = Column(String(50))

                with db.session() as session:
                    pagination = session.query(User).paginate_query(page=1, page_size=10)
                    print(pagination)

                # Or you can use the query object
                with db.session() as session:
                    pagination = User.query.paginate_query(page=1, page_size=10)
                    print(pagination)

        Args:
            page (Optional[int], optional): The page number. Defaults to 1.
            per_page (Optional[int], optional): The number of items per page. Defaults to 20.
        Returns:
            PaginationResult: The pagination result.
        """
        if page < 1:
            raise ValueError("Page must be greater than 0")
        if per_page < 0:
            raise ValueError("Per page must be greater than 0")
        items = self.limit(per_page).offset((page - 1) * per_page).all()
        total = self.order_by(None).count()
        total_pages = (total - 1) // per_page + 1
        return PaginationResult(
            items=items,
            total_count=total,
            total_pages=total_pages,
            page=page,
            page_size=per_page,
        )


class _Model:
    """Base class for SQLAlchemy declarative base model.

    With this class, we can use the query object to query the database.

    Examples:
        .. code-block:: python
            from dbgpt.storage.metadata import db, Model
            class User(Model):
                __tablename__ = "user"
                id = Column(Integer, primary_key=True)
                name = Column(String(50))
                fullname = Column(String(50))

            with db.session() as session:
                # User is an instance of _Model, and we can use the query object to query the database.
                User.query.filter(User.name == "test").all()
    """

    query_class = None
    query: Optional[BaseQuery] = None

    def __repr__(self):
        identity = inspect(self).identity
        if identity is None:
            pk = "(transient {0})".format(id(self))
        else:
            pk = ", ".join(_to_str(value) for value in identity)
        return "<{0} {1}>".format(type(self).__name__, pk)


class DatabaseManager:
    """The database manager.

    Examples:
        .. code-block:: python
            from urllib.parse import quote_plus as urlquote, quote
            from dbgpt.storage.metadata import DatabaseManager, create_model
            db = DatabaseManager()
            # Use sqlite with memory storage.
            url = f"sqlite:///:memory:"
            engine_args = {"pool_size": 10, "max_overflow": 20, "pool_timeout": 30, "pool_recycle": 3600, "pool_pre_ping": True}
            db.init_db(url, engine_args=engine_args)

            Model = create_model(db)

            class User(Model):
                __tablename__ = "user"
                id = Column(Integer, primary_key=True)
                name = Column(String(50))
                fullname = Column(String(50))

            with db.session() as session:
                session.add(User(name="test", fullname="test"))
                # db will commit the session automatically default.
                # session.commit()
                print(User.query.filter(User.name == "test").all())


            # Use CURDMixin APIs to create, update, delete, query the database.
            with db.session() as session:
                User.create(**{"name": "test1", "fullname": "test1"})
                User.create(**{"name": "test2", "fullname": "test1"})
                users = User.all()
                print(users)
                user = users[0]
                user.update(**{"name": "test1_1111"})
                user2 = users[1]
                # Update user2 by save
                user2.name = "test2_1111"
                user2.save()
                # Delete user2
                user2.delete()
    """

    Query = BaseQuery

    def __init__(self):
        self._db_url = None
        self._base: DeclarativeMeta = self._make_declarative_base(_Model)
        self._engine: Optional[Engine] = None
        self._session: Optional[scoped_session] = None

    @property
    def Model(self) -> _Model:
        """Get the declarative base."""
        return self._base

    @property
    def metadata(self) -> MetaData:
        """Get the metadata."""
        return self.Model.metadata

    @property
    def engine(self):
        """Get the engine.""" ""
        return self._engine

    @contextmanager
    def session(self) -> Session:
        """Get the session with context manager.

        If raise any exception, the session will roll back automatically, otherwise, the session will commit automatically.

        Example:
            >>> with db.session() as session:
            >>>     session.query(...)

        Returns:
            Session: The session.

        Raises:
            RuntimeError: The database manager is not initialized.
            Exception: Any exception.
        """
        if not self._session:
            raise RuntimeError("The database manager is not initialized.")
        session = self._session()
        try:
            yield session
            session.commit()
        except:
            session.rollback()
            raise
        finally:
            session.close()

    def _make_declarative_base(
        self, model: Union[Type[DeclarativeMeta], Type[_Model]]
    ) -> DeclarativeMeta:
        """Make the declarative base.

        Args:
            base (DeclarativeMeta): The base class.

        Returns:
            DeclarativeMeta: The declarative base.
        """
        if not isinstance(model, DeclarativeMeta):
            model = declarative_base(cls=model, name="Model")
        if not getattr(model, "query_class", None):
            model.query_class = self.Query
        model.query = _QueryObject(self)
        return model

    def init_db(
        self,
        db_url: Union[str, URL],
        engine_args: Optional[Dict] = None,
        base: Optional[DeclarativeMeta] = None,
        query_class=BaseQuery,
    ):
        """Initialize the database manager.

        Args:
            db_url (Union[str, URL]): The database url.
            engine_args (Optional[Dict], optional): The engine arguments. Defaults to None.
            base (Optional[DeclarativeMeta]): The base class. Defaults to None.
            query_class (BaseQuery, optional): The query class. Defaults to BaseQuery.
        """
        self._db_url = db_url
        if query_class is not None:
            self.Query = query_class
        if base is not None:
            self._base = base
            if not hasattr(base, "query"):
                base.query = _QueryObject(self)
            if not getattr(base, "query_class", None):
                base.query_class = self.Query
        self._engine = create_engine(db_url, **(engine_args or {}))
        session_factory = sessionmaker(bind=self._engine)
        self._session = scoped_session(session_factory)
        self._base.metadata.bind = self._engine

    def init_default_db(
        self,
        sqlite_path: str,
        engine_args: Optional[Dict] = None,
        base: Optional[DeclarativeMeta] = None,
    ):
        """Initialize the database manager with default config.

        Examples:
            >>> db.init_default_db(sqlite_path)
            >>> with db.session() as session:
            >>>     session.query(...)

        Args:
            sqlite_path (str): The sqlite path.
            engine_args (Optional[Dict], optional): The engine arguments.
                Defaults to None, if None, we will use connection pool.
            base (Optional[DeclarativeMeta]): The base class. Defaults to None.
        """
        if not engine_args:
            engine_args = {}
            # Pool class
            engine_args["poolclass"] = QueuePool
            # The number of connections to keep open inside the connection pool.
            engine_args["pool_size"] = 10
            # The maximum overflow size of the pool when the number of connections be used in the pool is exceeded(
            # pool_size).
            engine_args["max_overflow"] = 20
            # The number of seconds to wait before giving up on getting a connection from the pool.
            engine_args["pool_timeout"] = 30
            # Recycle the connection if it has been idle for this many seconds.
            engine_args["pool_recycle"] = 3600
            # Enable the connection pool “pre-ping” feature that tests connections for liveness upon each checkout.
            engine_args["pool_pre_ping"] = True

        self.init_db(f"sqlite:///{sqlite_path}", engine_args, base)

    def create_all(self):
        self.Model.metadata.create_all(self._engine)


db = DatabaseManager()
"""The global database manager.

Examples:
    >>> from dbgpt.storage.metadata import db
    >>> sqlite_path = "/tmp/dbgpt.db"
    >>> db.init_default_db(sqlite_path)
    >>> with db.session() as session:
    >>>     session.query(...)
    
    >>> from dbgpt.storage.metadata import db, Model
    >>> from urllib.parse import quote_plus as urlquote, quote
    >>> db_name = "dbgpt"
    >>> db_host = "localhost"
    >>> db_port = 3306
    >>> user = "root"
    >>> password = "123456"
    >>> url = f"mysql+pymysql://{quote(user)}:{urlquote(password)}@{db_host}:{str(db_port)}/{db_name}"
    >>> engine_args = {"pool_size": 10, "max_overflow": 20, "pool_timeout": 30, "pool_recycle": 3600, "pool_pre_ping": True}
    >>> db.init_db(url, engine_args=engine_args)
    >>> class User(Model):
    >>>     __tablename__ = "user"
    >>>     id = Column(Integer, primary_key=True)
    >>>     name = Column(String(50))
    >>>     fullname = Column(String(50))
    >>> with db.session() as session:
    >>>     session.add(User(name="test", fullname="test"))
    >>>     session.commit()
"""


class BaseCRUDMixin(Generic[T]):
    """The base CRUD mixin."""

    __abstract__ = True

    @classmethod
    def create(cls: Type[T], **kwargs) -> T:
        instance = cls(**kwargs)
        return instance.save()

    @classmethod
    def all(cls: Type[T]) -> List[T]:
        return cls.query.all()

    @classmethod
    def get(cls: Type[T], ident: _PKIdentityArgument) -> Optional[T]:
        """Get a record by its primary key identifier."""

    def update(self: T, commit: Optional[bool] = True, **kwargs) -> T:
        """Update specific fields of a record."""
        for attr, value in kwargs.items():
            setattr(self, attr, value)
        return commit and self.save() or self

    @abc.abstractmethod
    def save(self: T, commit: Optional[bool] = True) -> T:
        """Save the record."""

    @abc.abstractmethod
    def delete(self: T, commit: Optional[bool] = True) -> None:
        """Remove the record from the database."""


class BaseModel(BaseCRUDMixin[T], _Model, Generic[T]):

    """The base model class that includes CRUD convenience methods."""

    __abstract__ = True


def create_model(db_manager: DatabaseManager) -> Type[BaseModel[T]]:
    class CRUDMixin(BaseCRUDMixin[T], Generic[T]):
        """Mixin that adds convenience methods for CRUD (create, read, update, delete)"""

        @classmethod
        def get(cls: Type[T], ident: _PKIdentityArgument) -> Optional[T]:
            """Get a record by its primary key identifier."""
            return db_manager._session().get(cls, ident)

        def save(self: T, commit: Optional[bool] = True) -> T:
            """Save the record."""
            session = db_manager._session()
            session.add(self)
            if commit:
                session.commit()
            return self

        def delete(self: T, commit: Optional[bool] = True) -> None:
            """Remove the record from the database."""
            session = db_manager._session()
            session.delete(self)
            return commit and session.commit()

    class _NewModel(CRUDMixin[T], db_manager.Model, Generic[T]):
        """Base model class that includes CRUD convenience methods."""

        __abstract__ = True

    return _NewModel


Model = create_model(db)


def initialize_db(
    db_url: Union[str, URL],
    db_name: str,
    engine_args: Optional[Dict] = None,
    base: Optional[DeclarativeMeta] = None,
    try_to_create_db: Optional[bool] = False,
) -> DatabaseManager:
    """Initialize the database manager.

    Args:
        db_url (Union[str, URL]): The database url.
        db_name (str): The database name.
        engine_args (Optional[Dict], optional): The engine arguments. Defaults to None.
        base (Optional[DeclarativeMeta]): The base class. Defaults to None.
        try_to_create_db (Optional[bool], optional): Whether to try to create the database. Defaults to False.
    Returns:
        DatabaseManager: The database manager.
    """
    db.init_db(db_url, engine_args, base)
    if try_to_create_db:
        try:
            db.create_all()
        except Exception as e:
            logger.error(f"Failed to create database {db_name}: {e}")
    return db
