from contextlib import contextmanager
from typing import TypeVar, Generic, Any, Optional
from sqlalchemy.orm.session import Session

T = TypeVar("T")

from .db_manager import db, DatabaseManager


class BaseDao(Generic[T]):
    """The base class for all DAOs.

    Examples:
        .. code-block:: python
            class UserDao(BaseDao[User]):
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
        return self._db_manager._session()

    @contextmanager
    def session(self) -> Session:
        """Provide a transactional scope around a series of operations.

        If raise an exception, the session will be roll back automatically, otherwise it will be committed.

        Example:
            .. code-block:: python
                with self.session() as session:
                    session.query(User).filter(User.name == 'Edward Snowden').first()

        Returns:
            Session: A session object.

        Raises:
            Exception: Any exception will be raised.
        """
        with self._db_manager.session() as session:
            yield session
