from typing import Optional

from dbgpt.datasource.rdbms.base import RDBMSDatabase


class SqlExec:
    """Sql execution"""

    def __init__(self, connection: Optional[RDBMSDatabase] = None, **kwargs):
        """ "
        Args:
            connection (Optional[RDBMSDatabase]): RDBMSDatabase connection
        """
        super().__init__(**kwargs)
        self._connection = connection

    def sql_exec(self, sql: str) -> str:
        """sql execution in database
        Args:
            sql (str): query text
        Return:
            str: sql result in database
        """
        res = self._connection._query(query=sql, fetch="all")
        return str(res)
