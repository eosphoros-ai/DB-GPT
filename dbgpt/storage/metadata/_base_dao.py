from typing import TypeVar, Generic, Any
from sqlalchemy.orm import sessionmaker

T = TypeVar("T")


class BaseDao(Generic[T]):
    def __init__(
        self,
        orm_base=None,
        database: str = None,
        db_engine: Any = None,
        session: Any = None,
    ) -> None:
        """BaseDAO, If the current database is a file database and create_not_exist_table=True, we will automatically create a table that does not exist"""
        self._orm_base = orm_base
        self._database = database

        self._db_engine = db_engine
        self._session = session

    def get_session(self):
        Session = sessionmaker(autocommit=False, autoflush=False, bind=self._db_engine)
        session = Session()
        return session
