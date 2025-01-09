"""The database manager."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import ClassVar, Dict, Generic, Iterator, Optional, Type, TypeVar, Union

from sqlalchemy import URL, Engine, MetaData, create_engine, inspect, orm
from sqlalchemy.orm import (
    DeclarativeMeta,
    Session,
    declarative_base,
    scoped_session,
    sessionmaker,
)
from sqlalchemy.pool import QueuePool

from dbgpt.util.pagination_utils import PaginationResult
from dbgpt.util.string_utils import _to_str

logger = logging.getLogger(__name__)
T = TypeVar("T", bound="BaseModel")


# class _QueryObject:
#     """The query object."""
#
#     def __get__(self, obj: Union[_Model, None], model_cls: type[_Model]):
#         return model_cls.query_class(
#             model_cls, session=model_cls.__db_manager__._session()
#         )
#


class BaseQuery(orm.Query):
    """Base query class."""

    def paginate_query(self, page: int = 1, per_page: int = 20) -> PaginationResult:
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
                    pagination = session.query(User).paginate_query(
                        page=1, page_size=10
                    )
                    print(pagination)

        Args:
            page (Optional[int], optional): The page number. Defaults to 1.
            per_page (Optional[int], optional): The number of items per page. Defaults
                to 20.
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
    """Base class for SQLAlchemy declarative base model."""

    __db_manager__: ClassVar[DatabaseManager]
    query_class = BaseQuery

    # query: Optional[BaseQuery] = _QueryObject()

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
            engine_args = {
                "pool_size": 10,
                "max_overflow": 20,
                "pool_timeout": 30,
                "pool_recycle": 3600,
                "pool_pre_ping": True,
            }
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
                assert (
                    session.query(User).filter(User.name == "test").first().name
                    == "test"
                )


            # More usage:

            with db.session() as session:
                session.add(User(name="test1", fullname="test1"))
                session.add(User(name="test2", fullname="test1"))
                users = session.query(User).all()
                print(users)
                user = users[0]
                user.name = "test1_1111"
                session.merge(user)

                user2 = users[1]
                # Update user2 by save
                user2.name = "test2_1111"
                session.merge(user2)
                session.commit()
                # Delete user2
                user2.delete()
    """

    Query = BaseQuery

    def __init__(self):
        """Create a DatabaseManager."""
        self._db_url = None
        self._base: DeclarativeMeta = self._make_declarative_base(_Model)
        self._engine: Optional[Engine] = None
        self._session: Optional[scoped_session] = None

    @property
    def Model(self) -> _Model:
        """Get the declarative base."""
        return self._base  # type: ignore

    @property
    def metadata(self) -> MetaData:
        """Get the metadata."""
        return self.Model.metadata  # type: ignore

    @property
    def engine(self):
        """Get the engine.""" ""
        return self._engine

    @property
    def is_initialized(self) -> bool:
        """Whether the database manager is initialized."""
        return self._engine is not None and self._session is not None

    @contextmanager
    def session(self, commit: Optional[bool] = True) -> Iterator[Session]:
        """Get the session with context manager.

        This context manager handles the lifecycle of a SQLAlchemy session.
        It automatically commits or rolls back transactions based on
        the execution and handles session closure.

        The `commit` parameter controls whether the session should commit
        changes at the end of the block. This is useful for separating
        read and write operations.

        Examples:
            .. code-block:: python

                # For write operations (insert, update, delete):
                with db.session() as session:
                    user = User(name="John Doe")
                    session.add(user)
                    # session.commit() is called automatically

                # For read-only operations:
                with db.session(commit=False) as session:
                    user = session.query(User).filter_by(name="John Doe").first()
                    # session.commit() is NOT called, as it's unnecessary for read
                    # operations

        Args:
            commit (Optional[bool], optional): Whether to commit the session.
                If True (default), the session will commit changes at the end
                of the block. Use False for read-only operations or when manual
                control over commit is needed. Defaults to True.

        Yields:
            Session: The SQLAlchemy session object.

        Raises:
            RuntimeError: Raised if the database manager is not initialized.
            Exception: Propagates any exception that occurred within the block.

        Important Notes:
            - DetachedInstanceError: This error occurs when trying to access or
              modify an instance that has been detached from its session.
              DetachedInstanceError can occur in scenarios where the session is
              closed, and further interaction with the ORM object is attempted,
              especially when accessing lazy-loaded attributes. To avoid this:
                a. Ensure required attributes are loaded before session closure.
                b. Avoid closing the session before all necessary interactions
                   with the ORM object are complete.
                c. Re-bind the instance to a new session if further interaction
                   is required after the session is closed.
        """
        if not self.is_initialized:
            raise RuntimeError("The database manager is not initialized.")
        session = self._session()  # type: ignore
        try:
            yield session
            if commit:
                session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _make_declarative_base(
        self, model: Union[Type[DeclarativeMeta], Type[_Model]]
    ) -> DeclarativeMeta:
        """Make the declarative base.

        Args:
            model (DeclarativeMeta): The base class.

        Returns:
            DeclarativeMeta: The declarative base.
        """
        if not isinstance(model, DeclarativeMeta):
            model = declarative_base(cls=model, name="Model")
        if not getattr(model, "query_class", None):
            model.query_class = self.Query  # type: ignore
        # model.query = _QueryObject()
        model.__db_manager__ = self  # type: ignore
        return model  # type: ignore

    def init_db(
        self,
        db_url: Union[str, URL],
        engine_args: Optional[Dict] = None,
        base: Optional[DeclarativeMeta] = None,
        query_class=BaseQuery,
        override_query_class: Optional[bool] = False,
        session_options: Optional[Dict] = None,
    ):
        """Initialize the database manager.

        Args:
            db_url (Union[str, URL]): The database url.
            engine_args (Optional[Dict], optional): The engine arguments. Defaults to
                None.
            base (Optional[DeclarativeMeta]): The base class. Defaults to None.
            query_class (BaseQuery, optional): The query class. Defaults to BaseQuery.
            override_query_class (Optional[bool], optional): Whether to override the
                query class. Defaults to False.
            session_options (Optional[Dict], optional): The session options. Defaults
                to None.
        """
        if session_options is None:
            session_options = {}
        self._db_url = db_url
        if query_class is not None:
            self.Query = query_class
        if base is not None:
            self._base = base
            # if not hasattr(base, "query") or override_query_class:
            #     base.query = _QueryObject()
            if not getattr(base, "query_class", None) or override_query_class:
                base.query_class = self.Query
            if not hasattr(base, "__db_manager__") or override_query_class:
                base.__db_manager__ = self
        self._engine = create_engine(db_url, **(engine_args or {}))

        session_options.setdefault("class_", Session)
        session_options.setdefault("query_cls", self.Query)
        session_factory = sessionmaker(bind=self._engine, **session_options)
        # self._session = scoped_session(session_factory)
        self._session = session_factory  # type: ignore
        self._base.metadata.bind = self._engine  # type: ignore

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
            ...     session.query(...)
            ...

        Args:
            sqlite_path (str): The sqlite path.
            engine_args (Optional[Dict], optional): The engine arguments.
                Defaults to None, if None, we will use connection pool.
            base (Optional[DeclarativeMeta]): The base class. Defaults to None.
        """
        if not engine_args:
            engine_args = {
                # Pool class
                "poolclass": QueuePool,
                # The number of connections to keep open inside the connection pool.
                "pool_size": 10,
                # The maximum overflow size of the pool when the number of connections
                # be used in the pool is exceeded(pool_size).
                "max_overflow": 20,
                # The number of seconds to wait before giving up on getting a connection
                # from the pool.
                "pool_timeout": 30,
                # Recycle the connection if it has been idle for this many seconds.
                "pool_recycle": 3600,
                # Enable the connection pool “pre-ping” feature that tests connections
                # for liveness upon each checkout.
                "pool_pre_ping": True,
            }

        self.init_db(f"sqlite:///{sqlite_path}", engine_args, base)

    def create_all(self):
        """Create all tables."""
        self.Model.metadata.create_all(self._engine)

    @staticmethod
    def build_from(
        db_url_or_db: Union[str, URL, DatabaseManager],
        engine_args: Optional[Dict] = None,
        base: Optional[DeclarativeMeta] = None,
        query_class=BaseQuery,
        override_query_class: Optional[bool] = False,
    ) -> DatabaseManager:
        """Build the database manager from the db_url_or_db.

        Examples:
            Build from the database url.
            .. code-block:: python

                from dbgpt.storage.metadata import DatabaseManager
                from sqlalchemy import Column, Integer, String

                db = DatabaseManager.build_from("sqlite:///:memory:")


                class User(db.Model):
                    __tablename__ = "user"
                    id = Column(Integer, primary_key=True)
                    name = Column(String(50))
                    fullname = Column(String(50))


                db.create_all()
                with db.session() as session:
                    session.add(User(name="test", fullname="test"))
                    session.commit()
                    print(User.query.filter(User.name == "test").all())

        Args:
            db_url_or_db (Union[str, URL, DatabaseManager]): The database url or the
                database manager.
            engine_args (Optional[Dict], optional): The engine arguments. Defaults to
                None.
            base (Optional[DeclarativeMeta]): The base class. Defaults to None.
            query_class (BaseQuery, optional): The query class. Defaults to BaseQuery.
            override_query_class (Optional[bool], optional): Whether to override the
                query class. Defaults to False.

        Returns:
            DatabaseManager: The database manager.
        """
        if isinstance(db_url_or_db, (str, URL)):
            db_manager = DatabaseManager()
            db_manager.init_db(
                db_url_or_db, engine_args, base, query_class, override_query_class
            )
            return db_manager
        elif isinstance(db_url_or_db, DatabaseManager):
            return db_url_or_db
        else:
            raise ValueError(
                f"db_url_or_db should be either url or a DatabaseManager, got "
                f"{type(db_url_or_db)}"
            )


db = DatabaseManager()
"""The global database manager.

Examples:
    >>> from dbgpt.storage.metadata import db
    >>> sqlite_path = "/tmp/dbgpt.db"
    >>> db.init_default_db(sqlite_path)
    >>> with db.session() as session:
    ...     session.query(...)
    ...
    >>> from dbgpt.storage.metadata import db, Model
    >>> from urllib.parse import quote_plus as urlquote, quote
    >>> db_name = "dbgpt"
    >>> db_host = "localhost"
    >>> db_port = 3306
    >>> user = "root"
    >>> password = "123456"
    >>> url = (
    ...     f"mysql+pymysql://{quote(user)}:{urlquote(password)}@{db_host}"
    ...     f":{str(db_port)}/{db_name}"
    ... )
    >>> engine_args = {
    ...     "pool_size": 10,
    ...     "max_overflow": 20,
    ...     "pool_timeout": 30,
    ...     "pool_recycle": 3600,
    ...     "pool_pre_ping": True,
    ... }
    >>> db.init_db(url, engine_args=engine_args)
    >>> class User(Model):
    ...     __tablename__ = "user"
    ...     id = Column(Integer, primary_key=True)
    ...     name = Column(String(50))
    ...     fullname = Column(String(50))
    ...
    >>> with db.session() as session:
    ...     session.add(User(name="test", fullname="test"))
    ...     session.commit()
    ...
"""


class BaseCRUDMixin(Generic[T]):
    """The base CRUD mixin."""

    __abstract__ = True

    @classmethod
    def db(cls) -> DatabaseManager:
        """Get the database manager."""
        return cls.__db_manager__  # type: ignore


class BaseModel(BaseCRUDMixin[T], _Model, Generic[T]):
    """The base model class that includes CRUD convenience methods."""

    __abstract__ = True
    """Whether the model is abstract."""


def create_model(db_manager: DatabaseManager) -> Type[BaseModel[T]]:
    """Create a model."""

    class CRUDMixin(BaseCRUDMixin[T], Generic[T]):  # type: ignore
        """Mixin that adds convenience methods for CRUD."""

        _db_manager: DatabaseManager = db_manager

        @classmethod
        def set_db(cls, db_manager: DatabaseManager):
            # TODO: It is hard to replace to user DB Connection
            cls._db_manager = db_manager

        @classmethod
        def db(cls) -> DatabaseManager:
            """Get the database manager."""
            return cls._db_manager

    class _NewModel(CRUDMixin[T], db_manager.Model, Generic[T]):  # type: ignore
        """Base model class that includes CRUD convenience methods."""

        __abstract__ = True

    return _NewModel


Model: Type = create_model(db)


def initialize_db(
    db_url: Union[str, URL],
    db_name: str,
    engine_args: Optional[Dict] = None,
    base: Optional[DeclarativeMeta] = None,
    try_to_create_db: Optional[bool] = False,
    session_options: Optional[Dict] = None,
) -> DatabaseManager:
    """Initialize the database manager.

    Args:
        db_url (Union[str, URL]): The database url.
        db_name (str): The database name.
        engine_args (Optional[Dict], optional): The engine arguments. Defaults to None.
        base (Optional[DeclarativeMeta]): The base class. Defaults to None.
        try_to_create_db (Optional[bool], optional): Whether to try to create the
            database. Defaults to False.
        session_options (Optional[Dict], optional): The session options. Defaults to
            None.
    Returns:
        DatabaseManager: The database manager.
    """
    db.init_db(db_url, engine_args, base, session_options=session_options)
    if try_to_create_db:
        try:
            db.create_all()
        except Exception as e:
            logger.error(f"Failed to create database {db_name}: {e}")
    return db
