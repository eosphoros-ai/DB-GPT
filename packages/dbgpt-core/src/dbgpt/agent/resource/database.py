"""Database resource module."""

import dataclasses
import logging
from concurrent.futures import Executor, ThreadPoolExecutor
from typing import Any, Dict, Generic, List, Optional, Tuple, Union

import cachetools

from dbgpt.datasource.rdbms.base import RDBMSConnector
from dbgpt.util.cache_utils import cached
from dbgpt.util.executor_utils import blocking_func_to_async

from .base import P, Resource, ResourceParameters, ResourceType

logger = logging.getLogger(__name__)

_DEFAULT_PROMPT_TEMPLATE = (
    "Database type: {db_type}, related table structure definition: {schemas}"
)
_DEFAULT_PROMPT_TEMPLATE_ZH = "数据库类型：{db_type}，相关表结构定义：{schemas}"


@dataclasses.dataclass
class DBParameters(ResourceParameters):
    """DB parameters class."""

    db_name: str = dataclasses.field(metadata={"help": "DB name"})


class DBResource(Resource[P], Generic[P]):
    """Database resource class."""

    def __init__(
        self,
        name: str,
        db_type: Optional[str] = None,
        db_name: Optional[str] = None,
        dialect: Optional[str] = None,
        executor: Optional[Executor] = None,
        prompt_template: str = _DEFAULT_PROMPT_TEMPLATE,
        **kwargs,
    ):
        """Initialize the DB resource."""
        self._name = name
        self._db_type = db_type
        self._db_name = db_name
        self._dialect = dialect or db_type
        # Executor for running async tasks
        self._executor = executor or ThreadPoolExecutor()
        self._prompt_template = prompt_template

    @classmethod
    def type(cls) -> ResourceType:
        """Return the resource type."""
        return ResourceType.DB

    @property
    def name(self) -> str:
        """Return the resource name."""
        return self._name

    @property
    def db_type(self) -> str:
        """Return the resource name."""
        if not self._db_type:
            raise ValueError("Database type is not set.")
        return self._db_type

    @property
    def dialect(self) -> str:
        """Return the resource name."""
        if not self._dialect:
            raise ValueError("Dialect is not set.")
        return self._dialect

    @cached(cachetools.TTLCache(maxsize=100, ttl=10))
    async def get_prompt(
        self,
        *,
        lang: str = "en",
        prompt_type: str = "default",
        question: Optional[str] = None,
        resource_name: Optional[str] = None,
        **kwargs,
    ) -> Tuple[str, Optional[List[Dict]]]:
        """Get the prompt."""
        if not self._db_name:
            return "No database name provided.", None
        schema_info = await blocking_func_to_async(
            self._executor, self.get_schema_link, db=self._db_name, question=question
        )
        return (
            self._prompt_template.format(db_type=self._db_type, schemas=schema_info),
            None,
        )

    def execute(self, *args, resource_name: Optional[str] = None, **kwargs) -> Any:
        """Execute the resource."""
        copy_kwargs = kwargs.copy()
        if "db" not in copy_kwargs:
            copy_kwargs["db"] = self._db_name
        return self._sync_query(*args, **copy_kwargs)

    async def async_execute(
        self, *args, resource_name: Optional[str] = None, **kwargs
    ) -> Any:
        """Execute the resource asynchronously."""
        copy_kwargs = kwargs.copy()
        if "db" not in copy_kwargs:
            copy_kwargs["db"] = self._db_name
        return await self.query(*args, **copy_kwargs)

    @property
    def is_async(self) -> bool:
        """Return whether the resource is asynchronous."""
        return True

    def get_schema_link(
        self, db: str, question: Optional[str] = None
    ) -> Union[str, List[str]]:
        """Return the schema link of the database."""
        raise NotImplementedError("The run method should be implemented in a subclass.")

    async def query_to_df(self, sql: str, db: Optional[str] = None):
        """Return the query result as a DataFrame."""
        import pandas as pd

        field_names, result = await self.query(sql, db=db)
        return pd.DataFrame(result, columns=field_names)

    async def query(self, sql: str, db: Optional[str] = None):
        """Return the query result."""
        db_name = db or self._db_name
        return await blocking_func_to_async(
            self._executor, self._sync_query, db=db_name, sql=sql
        )

    def _sync_query(self, db: str, sql: str):
        """Return the query result."""
        raise NotImplementedError("The run method should be implemented in a subclass.")


class RDBMSConnectorResource(DBResource[DBParameters]):
    """Connector resource class."""

    def __init__(
        self,
        name: str,
        connector: Optional[RDBMSConnector] = None,
        db_name: Optional[str] = None,
        db_type: Optional[str] = None,
        dialect: Optional[str] = None,
        executor: Optional[Executor] = None,
        **kwargs,
    ):
        """Initialize the connector resource."""
        if not db_type and connector:
            db_type = connector.db_type
        if not dialect and connector:
            dialect = connector.dialect
        if not db_name and connector:
            db_name = connector.get_current_db_name()
        self._connector = connector
        super().__init__(
            name,
            db_type=db_type,
            db_name=db_name,
            dialect=dialect,
            executor=executor,
            **kwargs,
        )

    @property
    def connector(self) -> RDBMSConnector:
        """Return the connector."""
        if not self._connector:
            raise ValueError("Connector is not set.")
        return self._connector

    def get_schema_link(
        self, db: str, question: Optional[str] = None
    ) -> Union[str, List[str]]:
        """Return the schema link of the database."""
        from dbgpt_ext.rag.summary.rdbms_db_summary import _parse_db_summary

        return _parse_db_summary(self.connector)

    def _sync_query(self, db: str, sql: str) -> Tuple[Tuple, List]:
        """Return the query result."""
        result_lst = self.connector.run(sql)
        columns = result_lst[0]
        values = result_lst[1:]
        return columns, values


class SQLiteDBResource(RDBMSConnectorResource):
    """SQLite database resource class."""

    def __init__(
        self, name: str, db_name: str, executor: Optional[Executor] = None, **kwargs
    ):
        """Initialize the SQLite database resource."""
        from dbgpt.datasource.rdbms.conn_sqlite import SQLiteConnector

        conn = SQLiteConnector.from_file_path(db_name)
        super().__init__(name, conn, executor=executor, **kwargs)
