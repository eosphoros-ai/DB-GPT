from typing import Any, Optional

from dbgpt.core.awel import MapOperator
from dbgpt.core.awel.task.base import IN
from dbgpt.datasource.rdbms.base import RDBMSDatabase
from dbgpt.rag.schemalinker.sql_exec import SqlExec


class SqlExecOperator(MapOperator[Any, Any]):
    """The Sql Execution Operator."""

    def __init__(self, connection: Optional[RDBMSDatabase] = None, **kwargs):
        """
        Args:
            connection (Optional[RDBMSDatabase]): RDBMSDatabase connection
        """
        super().__init__(**kwargs)
        self._sql_exec = SqlExec(connection=connection)

    def map(self, sql: str) -> str:
        """retrieve table schemas.
        Args:
            sql (str): query.
        Return:
            str: sql execution
        """
        return self._sql_exec.sql_exec(sql=sql)
