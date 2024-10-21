"""Summary for rdbms database."""

from typing import TYPE_CHECKING, Dict, List, Optional

from dbgpt._private.config import Config
from dbgpt.datasource import BaseConnector
from dbgpt.datasource.conn_tugraph import TuGraphConnector
from dbgpt.rag.summary.db_summary import DBSummary

if TYPE_CHECKING:
    from dbgpt.datasource.manages import ConnectorManager

CFG = Config()


class GdbmsSummary(DBSummary):
    """Get graph db table summary template."""

    def __init__(
        self, name: str, type: str, manager: Optional["ConnectorManager"] = None
    ):
        """Create a new RdbmsSummary."""
        self.name = name
        self.type = type
        self.summary_template = "{table_name}({columns})"
        # self.v_summary_template = "{table_name}({columns})"
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
        self.table_info_summaries = {
            "vertex_tables": [
                self.get_table_summary(table_name, "vertex")
                for table_name in tables["vertex_tables"]
            ],
            "edge_tables": [
                self.get_table_summary(table_name, "edge")
                for table_name in tables["edge_tables"]
            ],
        }

    def get_table_summary(self, table_name, table_type):
        """Get table summary for table.

        example:
            table_name(column1(column1 comment),column2(column2 comment),
            column3(column3 comment) and index keys, and table comment: {table_comment})
        """
        return _parse_table_summary(
            self.db, self.summary_template, table_name, table_type
        )

    def table_summaries(self):
        """Get table summaries."""
        return self.table_info_summaries


def _parse_db_summary(
    conn: BaseConnector, summary_template: str = "{table_name}({columns})"
) -> List[str]:
    """Get db summary for database."""
    table_info_summaries = None
    if isinstance(conn, TuGraphConnector):
        table_names = conn.get_table_names()
        v_tables = table_names.get("vertex_tables", [])  # type: ignore
        e_tables = table_names.get("edge_tables", [])  # type: ignore
        table_info_summaries = [
            _parse_table_summary(conn, summary_template, table_name, "vertex")
            for table_name in v_tables
        ] + [
            _parse_table_summary(conn, summary_template, table_name, "edge")
            for table_name in e_tables
        ]
    else:
        table_info_summaries = []

    return table_info_summaries


def _format_column(column: Dict) -> str:
    """Format a single column's summary."""
    comment = column.get("comment", "")
    if column.get("is_in_primary_key"):
        comment += " Primary Key" if comment else "Primary Key"
    return f"{column['name']} ({comment})" if comment else column["name"]


def _format_indexes(indexes: List[Dict]) -> str:
    """Format index keys for table summary."""
    return ", ".join(
        f"{index['name']}(`{', '.join(index['column_names'])}`)" for index in indexes
    )


def _parse_table_summary(
    conn: TuGraphConnector, summary_template: str, table_name: str, table_type: str
) -> str:
    """Enhanced table summary function."""
    columns = [
        _format_column(column) for column in conn.get_columns(table_name, table_type)
    ]
    column_str = ", ".join(columns)

    indexes = conn.get_indexes(table_name, table_type)
    index_str = _format_indexes(indexes) if indexes else ""

    table_str = summary_template.format(table_name=table_name, columns=column_str)
    if index_str:
        table_str += f", and index keys: {index_str}"
    try:
        comment = conn.get_table_comment(table_name)
    except Exception:
        comment = dict(text=None)
    if comment.get("text"):
        table_str += (
            f", and table comment: {comment.get('text')}, this is a {table_type} table"
        )
    else:
        table_str += f", and table comment: this is a {table_type} table"
    return table_str
