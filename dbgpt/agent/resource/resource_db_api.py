import logging
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple, Union

from dbgpt.agent.resource.resource_api import AgentResource

from .resource_api import ResourceClient, ResourceType

logger = logging.getLogger(__name__)


class ResourceDbClient(ResourceClient):
    @property
    def type(self):
        return ResourceType.DB

    def get_data_type(self, resource: AgentResource) -> str:
        return super().get_data_type(resource)

    async def get_data_introduce(
        self, resource: AgentResource, question: Optional[str] = None
    ) -> str:
        return await self.a_get_schema_link(resource.value, question)

    async def a_get_schema_link(self, db: str, question: Optional[str] = None) -> str:
        raise NotImplementedError("The run method should be implemented in a subclass.")

    async def a_query_to_df(self, dbe: str, sql: str):
        raise NotImplementedError("The run method should be implemented in a subclass.")

    async def a_query(self, db: str, sql: str):
        raise NotImplementedError("The run method should be implemented in a subclass.")

    async def a_run_sql(self, db: str, sql: str):
        raise NotImplementedError("The run method should be implemented in a subclass.")


class SqliteLoadClient(ResourceDbClient):
    from sqlalchemy.orm.session import Session

    def __init__(self):
        super(SqliteLoadClient, self).__init__()

    def get_data_type(self, resource: AgentResource) -> str:
        return "sqlite"

    @contextmanager
    def connect(self, db) -> Session:
        from sqlalchemy import create_engine, text
        from sqlalchemy.orm import sessionmaker

        engine = create_engine("sqlite:///" + db, echo=True)
        Session = sessionmaker(bind=engine)
        session = Session()
        try:
            yield session
            session.commit()
        except:
            session.rollback()
            raise
        finally:
            session.close()

    async def a_get_schema_link(self, db: str, question: Optional[str] = None) -> str:
        from sqlalchemy import text

        with self.connect(db) as connect:
            _tables_sql = f"""
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

    async def a_query_to_df(self, db: str, sql: str):
        import pandas as pd

        field_names, result = await self.a_query(db, sql)
        return pd.DataFrame(result, columns=field_names)

    async def a_query(self, db: str, sql: str):
        from sqlalchemy import text

        with self.connect(db) as connect:
            logger.info(f"Query[{sql}]")
            if not sql:
                return []
            cursor = connect.execute(text(sql))
            if cursor.returns_rows:
                result = cursor.fetchall()
                field_names = tuple(i[0:] for i in cursor.keys())
                return field_names, result

    async def a_run_sql(self, db: str, sql: str):
        pass
