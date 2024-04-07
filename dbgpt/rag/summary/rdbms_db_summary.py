"""Summary for rdbms database."""

from typing import TYPE_CHECKING, List, Optional

from dbgpt._private.config import Config
from dbgpt.datasource import BaseConnector
from dbgpt.rag.summary.db_summary import DBSummary

if TYPE_CHECKING:
    from dbgpt.datasource.manages import ConnectorManager

CFG = Config()


class RdbmsSummary(DBSummary):
    """Get rdbms db table summary template.

    Summary example:
        table_name(column1(column1 comment),column2(column2 comment),
        column3(column3 comment) and index keys, and table comment is {table_comment})
    """

    def __init__(
        self, name: str, type: str, manager: Optional["ConnectorManager"] = None
    ):
        """Create a new RdbmsSummary."""
        self.name = name
        self.type = type
        self.summary_template = "{table_name}({columns})"
        self.tables = {}
        # self.tables_info = []
        # self.vector_tables_info = []

        # TODO: Don't use the global variable.
        db_manager = manager or CFG.local_db_manager
        if not db_manager:
            raise ValueError("Local db manage is not initialized.")
        self.db = db_manager.get_connector(name)

        self.metadata = """user info :{users}, grant info:{grant}, charset:{charset},
        collation:{collation}""".format(
            users=self.db.get_users(),
            grant=self.db.get_grants(),
            charset=self.db.get_charset(),
            collation=self.db.get_collation(),
        )
        tables = self.db.get_table_names()
        self.table_info_summaries = [
            self.get_table_summary(table_name) for table_name in tables
        ]

    def get_table_summary(self, table_name):
        """Get table summary for table.

        example:
            table_name(column1(column1 comment),column2(column2 comment),
            column3(column3 comment) and index keys, and table comment: {table_comment})
        """
        return _parse_table_summary(self.db, self.summary_template, table_name)

    def table_summaries(self):
        """Get table summaries."""
        return self.table_info_summaries


def _parse_db_summary(
    conn: BaseConnector, summary_template: str = "{table_name}({columns})"
) -> List[str]:
    """Get db summary for database.

    Args:
        conn (BaseConnector): database connection
        summary_template (str): summary template
    """
    tables = conn.get_table_names()
    table_info_summaries = [
        _parse_table_summary(conn, summary_template, table_name)
        for table_name in tables
    ]
    return table_info_summaries


def _parse_table_summary(
    conn: BaseConnector, summary_template: str, table_name: str
) -> str:
    """Get table summary for table.

    Args:
        conn (BaseConnector): database connection
        summary_template (str): summary template
        table_name (str): table name

    Examples:
        table_name(column1(column1 comment),column2(column2 comment),
        column3(column3 comment) and index keys, and table comment: {table_comment})
    """
    columns = []
    for column in conn.get_columns(table_name):
        if column.get("comment"):
            columns.append(f"{column['name']} ({column.get('comment')})")
        else:
            columns.append(f"{column['name']}")

    column_str = ", ".join(columns)
    index_keys = []
    for index_key in conn.get_indexes(table_name):
        key_str = ", ".join(index_key["column_names"])
        index_keys.append(f"{index_key['name']}(`{key_str}`) ")  # noqa
    table_str = summary_template.format(table_name=table_name, columns=column_str)
    if len(index_keys) > 0:
        index_key_str = ", ".join(index_keys)
        table_str += f", and index keys: {index_key_str}"
    try:
        comment = conn.get_table_comment(table_name)
    except Exception:
        comment = dict(text=None)
    if comment.get("text"):
        table_str += f", and table comment: {comment.get('text')}"
    return table_str
