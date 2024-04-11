"""Database resource client API."""
import logging
from contextlib import contextmanager
from typing import TYPE_CHECKING, Iterator, List, Optional, Union

from .resource_api import AgentResource, ResourceClient, ResourceType

logger = logging.getLogger(__name__)


class ResourceDbClient(ResourceClient):
    """Database resource client API."""

    @property
    def type(self):
        """Return the resource type."""
        return ResourceType.DB

    def get_data_type(self, resource: AgentResource) -> str:
        """Return the data type of the resource."""
        return super().get_data_type(resource)

    async def get_data_introduce(
        self, resource: AgentResource, question: Optional[str] = None
    ) -> Union[str, List[str]]:
        """Return the data introduce of the resource."""
        return await self.get_schema_link(resource.value, question)

    async def get_schema_link(
        self, db: str, question: Optional[str] = None
    ) -> Union[str, List[str]]:
        """Return the schema link of the database."""
        raise NotImplementedError("The run method should be implemented in a subclass.")

    async def query_to_df(self, dbe: str, sql: str):
        """Return the query result as a DataFrame."""
        raise NotImplementedError("The run method should be implemented in a subclass.")

    async def query(self, db: str, sql: str):
        """Return the query result."""
        raise NotImplementedError("The run method should be implemented in a subclass.")

    async def run_sql(self, db: str, sql: str):
        """Run the SQL."""
        raise NotImplementedError("The run method should be implemented in a subclass.")


class SqliteLoadClient(ResourceDbClient):
    """SQLite resource client."""

    if TYPE_CHECKING:
        from sqlalchemy.orm.session import Session

    def __init__(self):
        """Create a SQLite resource client."""
        super(SqliteLoadClient, self).__init__()

    def get_data_type(self, resource: AgentResource) -> str:
        """Return the data type of the resource."""
        return "sqlite"

    @contextmanager
    def connect(self, db) -> Iterator["Session"]:
        """Connect to the database."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_engine("sqlite:///" + db, echo=True)
        Session = sessionmaker(bind=engine)
        session = Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    async def get_schema_link(
        self, db: str, question: Optional[str] = None
    ) -> Union[str, List[str]]:
        """Return the schema link of the database."""
        from sqlalchemy import text

        with self.connect(db) as connect:
            _tables_sql = """
                    SELECT name FROM sqlite_master WHERE type='table'
                """
            cursor = connect.execute(text(_tables_sql))
            tables_results = cursor.fetchall()
            results = []
            for row in tables_results:
                table_name = row[0]
                _sql = f"""
                    PRAGMA  table_info({table_name})
                """
                cursor_colums = connect.execute(text(_sql))
                colum_results = cursor_colums.fetchall()
                table_colums = []
                for row_col in colum_results:
                    field_info = list(row_col)
                    table_colums.append(field_info[1])

                results.append(f"{table_name}({','.join(table_colums)});")
            return results

    async def query_to_df(self, db: str, sql: str):
        """Return the query result as a DataFrame."""
        import pandas as pd

        field_names, result = await self.query(db, sql)
        return pd.DataFrame(result, columns=field_names)

    async def query(self, db: str, sql: str):
        """Return the query result."""
        from sqlalchemy import text

        with self.connect(db) as connect:
            logger.info(f"Query[{sql}]")
            if not sql:
                return []
            cursor = connect.execute(text(sql))
            if cursor.returns_rows:  # type: ignore
                result = cursor.fetchall()
                field_names = tuple(i[0:] for i in cursor.keys())
                return field_names, result
