import logging
from contextlib import contextmanager
from typing import (
    Any,
    Dict,
    Generic,
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
)

from sqlalchemy import Column, desc, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.session import Session

from dbgpt._private.pydantic import model_to_dict
from dbgpt.util.pagination_utils import PaginationResult

from .db_manager import BaseQuery, DatabaseManager, db

logger = logging.getLogger(__name__)

# The entity type
T = TypeVar("T")
# The request schema type
REQ = TypeVar("REQ")
# The response schema type
RES = TypeVar("RES")

QUERY_SPEC = Union[REQ, Dict[str, Any]]

# Tracks (db_manager identity, table, column) tuples already ensured this process,
# so the migration probe runs at most once per column even across hot sleeves.
_ensured_columns: Set[Tuple[int, str, str]] = set()


def ensure_column(db_manager: DatabaseManager, table_name: str, column: Column) -> None:
    """Ensure ``column`` exists on ``table_name`` (lightweight additive migration).

    ``metadata.create_all`` only creates tables that don't yet exist; it never
    adds columns to already-existing tables. This helper is the pragmatic
    migration path for *additive, nullable, no-default* columns (e.g. the
    observability ``trace_id`` linkage columns): probe via the inspector and,
    if missing, ``ALTER TABLE ... ADD COLUMN``. The ALTER form for nullable
    columns is portable across SQLite / MySQL / PostgreSQL.

    Idempotent and run-once per (db, table, column): subsequent calls return
    immediately. Failure is non-fatal (logged at warning level) — callers
    should also carry a defensive fallback at the write site.
    """
    key = (id(db_manager), table_name, column.name)
    if key in _ensured_columns:
        return
    try:
        engine = db_manager.engine
        if engine is None:
            # DB not initialised yet; do NOT mark done so a later call retries.
            return
        insp = inspect(engine)
        if table_name not in insp.get_table_names():
            # Table not created yet -> create_all will bring it up with the column.
            # Mark done since there's nothing else to do for this table/column pair.
            _ensured_columns.add(key)
            return
        existing = {c["name"] for c in insp.get_columns(table_name)}
        if column.name in existing:
            _ensured_columns.add(key)
            return
        col_type = column.type.compile(dialect=engine.dialect)
        with engine.begin() as conn:
            conn.execute(
                text(f"ALTER TABLE {table_name} ADD COLUMN {column.name} {col_type}")
            )
        _ensured_columns.add(key)
        logger.info(
            "ensure_column: added column %s to table %s", column.name, table_name
        )
    except SQLAlchemyError as e:
        # Mark done to avoid hot-loop logs on a persistent failure; write-site
        # OperationalError fallback still covers correctness.
        _ensured_columns.add(key)
        logger.warning(
            "ensure_column: failed to add %s.%s (%s); deferring to write-site fallback",
            table_name,
            column.name,
            e,
        )


class BaseDao(Generic[T, REQ, RES]):
    """The base class for all DAOs.

    Examples:
        .. code-block:: python

            class UserDao(BaseDao):
                def get_user_by_name(self, name: str) -> User:
                    with self.session() as session:
                        return session.query(User).filter(User.name == name).first()

                def get_user_by_id(self, id: int) -> User:
                    with self.session() as session:
                        return User.get(id)

                def create_user(self, name: str) -> User:
                    return User.create(**{"name": name})
    Args:
        db_manager (DatabaseManager, optional): The database manager. Defaults to None.
            If None, the default database manager(db) will be used.
    """

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
    ) -> None:
        """Create a BaseDao instance."""
        self._db_manager = db_manager or db

    def get_raw_session(self) -> Session:
        """Get a raw session object.

        Your should commit or rollback the session manually.
        We suggest you use :meth:`session` instead.

        Example:
            .. code-block:: python

                user = User(name="Edward Snowden")
                session = self.get_raw_session()
                session.add(user)
                session.commit()
                session.close()
        """
        return self._db_manager._session()  # type: ignore

    @contextmanager
    def session(self, commit: Optional[bool] = True) -> Iterator[Session]:
        """Provide a transactional scope around a series of operations.

        If raise an exception, the session will be roll back automatically, otherwise
        it will be committed.

        Example:
            .. code-block:: python

                with self.session() as session:
                    session.query(User).filter(User.name == "Edward Snowden").first()

        Args:
            commit (Optional[bool], optional): Whether to commit the session. Defaults
                to True.

        Returns:
            Session: A session object.

        Raises:
            Exception: Any exception will be raised.
        """
        with self._db_manager.session(commit=commit) as session:
            yield session

    def from_request(self, request: QUERY_SPEC) -> T:
        """Convert a request schema object to an entity object.

        Args:
            request (REQ): The request schema object or dict for query.

        Returns:
            T: The entity object.
        """
        raise NotImplementedError

    def to_request(self, entity: T) -> REQ:
        """Convert an entity object to a request schema object.

        Args:
            entity (T): The entity object.

        Returns:
            REQ: The request schema object.
        """
        raise NotImplementedError

    def from_response(self, response: RES) -> T:
        """Convert a response schema object to an entity object.

        Args:
            response (RES): The response schema object.

        Returns:
            T: The entity object.
        """
        raise NotImplementedError

    def to_response(self, entity: T) -> RES:
        """Convert an entity object to a response schema object.

        Args:
            entity (T): The entity object.

        Returns:
            RES: The response schema object.
        """
        raise NotImplementedError

    def create(self, request: REQ) -> RES:
        """Create an entity object.

        Args:
            request (REQ): The request schema object.

        Returns:
            RES: The response schema object.
        """
        entry = self.from_request(request)
        with self.session(commit=False) as session:
            session.add(entry)
            req = self.to_request(entry)
            session.commit()
            res = self.get_one(req)
            return res  # type: ignore

    def update(self, query_request: QUERY_SPEC, update_request: REQ) -> RES:
        """Update an entity object.

        Args:
            query_request (REQ): The request schema object or dict for query.
            update_request (REQ): The request schema object for update.
        Returns:
            RES: The response schema object.
        """
        with self.session() as session:
            query = self._create_query_object(session, query_request)
            entry = query.first()
            if entry is None:
                raise Exception("Invalid request")
            update_request = (
                update_request
                if isinstance(update_request, dict)
                else model_to_dict(update_request)
            )
            for key, value in update_request.items():  # type: ignore
                if value is not None:
                    setattr(entry, key, value)
            session.merge(entry)
            # res = self.get_one(self.to_request(entry))
            # if not res:
            #     raise Exception("Update failed")
            return self.to_response(entry)

    def delete(self, query_request: QUERY_SPEC) -> None:
        """Delete an entity object.

        Args:
            query_request (REQ): The request schema object or dict for query.
        """
        with self.session() as session:
            result_list = self._get_entity_list(session, query_request)
            if len(result_list) != 1:
                raise ValueError(
                    f"Delete request should return one result, but got "
                    f"{len(result_list)}"
                )
            session.delete(result_list[0])

    def get_one(self, query_request: QUERY_SPEC) -> Optional[RES]:
        """Get an entity object.

        Args:
            query_request (REQ): The request schema object or dict for query.

        Returns:
            Optional[RES]: The response schema object.
        """
        with self.session() as session:
            query = self._create_query_object(session, query_request)
            result = query.first()
            if result is None:
                return None
            return self.to_response(result)

    def get_list(self, query_request: QUERY_SPEC) -> List[RES]:
        """Get a list of entity objects.

        Args:
            query_request (REQ): The request schema object or dict for query.
        Returns:
            List[RES]: The response schema object.
        """
        with self.session() as session:
            result_list = self._get_entity_list(session, query_request)
            return [self.to_response(item) for item in result_list]

    def _get_entity_list(self, session: Session, query_request: QUERY_SPEC) -> List[T]:
        """Get a list of entity objects.

        Args:
            session (Session): The session object.
            query_request (REQ): The request schema object or dict for query.
        Returns:
            List[RES]: The response schema object.
        """
        query = self._create_query_object(session, query_request)
        result_list = query.all()
        return result_list

    def get_list_page(
        self,
        query_request: QUERY_SPEC,
        page: int,
        page_size: int,
        desc_order_column: Optional[str] = None,
    ) -> PaginationResult[RES]:
        """Get a page of entity objects.

        Args:
            query_request (REQ): The request schema object or dict for query.
            page (int): The page number.
            page_size (int): The page size.

        Returns:
            PaginationResult: The pagination result.
        """
        with self.session() as session:
            query = self._create_query_object(session, query_request, desc_order_column)
            total_count = query.count()
            items = query.offset((page - 1) * page_size).limit(page_size)
            res_items = [self.to_response(item) for item in items]
            total_pages = (total_count + page_size - 1) // page_size

            return PaginationResult(
                items=res_items,
                total_count=total_count,
                total_pages=total_pages,
                page=page,
                page_size=page_size,
            )

    def _create_query_object(
        self,
        session: Session,
        query_request: QUERY_SPEC,
        desc_order_column: Optional[str] = None,
    ) -> BaseQuery:
        """Create a query object.

        Args:
            session (Session): The session object.
            query_request (QUERY_SPEC): The request schema object or dict for query.
        Returns:
            BaseQuery: The query object.
        """
        model_cls = type(self.from_request(query_request))
        query = session.query(model_cls)
        query_dict = (
            query_request
            if isinstance(query_request, dict)
            else model_to_dict(query_request)
        )
        for key, value in query_dict.items():
            if value and isinstance(value, (list, tuple, dict, set)):
                # Skip the list, tuple, dict, set
                continue
            if value is not None and hasattr(model_cls, key):
                if isinstance(value, list):
                    if len(value) > 0:
                        query = query.filter(getattr(model_cls, key).in_(value))
                    else:
                        continue
                elif isinstance(value, (tuple, dict, set)):
                    continue
                else:
                    query = query.filter(getattr(model_cls, key) == value)

        if desc_order_column:
            query = query.order_by(desc(getattr(model_cls, desc_order_column)))
        return query  # type: ignore
