"""Summary for rdbms database."""

import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from dbgpt._private.config import Config
from dbgpt.datasource import BaseConnector
from dbgpt.rag.summary.db_summary import DBSummary

if TYPE_CHECKING:
    from dbgpt.datasource.manages import ConnectorManager

CFG = Config()


_DEFAULT_SUMMARY_TEMPLATE = """\
table_name: {table_name}\r\n\
table_comment: {table_comment}\r\n\
index_keys: {index_keys}\r\n\
"""
_DEFAULT_SUMMARY_TEMPLATE_PATTEN = (
    r"table_name:\s*(?P<table_name>.*)\s*"
    r"table_comment:\s*(?P<table_comment>.*)\s*"
    r"index_keys:\s*(?P<index_keys>.*)\s*"
)
_DEFAULT_COLUMN_SEPARATOR = ",\r\n    "


def _parse_table_detail(table_desc_str: str) -> Dict[str, Any]:
    """Parse table detail string.

    Args:
        table_desc_str (str): table detail string

    Returns:
        Dict[str, Any]: A dictionary containing table_name, table_comment, and
            index_keys.
    """
    matched = re.match(_DEFAULT_SUMMARY_TEMPLATE_PATTEN, table_desc_str)
    if matched:
        return matched.groupdict()
    return {}


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


def _parse_db_summary_with_metadata(
    conn: BaseConnector,
    summary_template: str = _DEFAULT_SUMMARY_TEMPLATE,
    separator: str = "--table-field-separator--",
    column_separator: str = _DEFAULT_COLUMN_SEPARATOR,
    model_dimension: int = 512,
) -> List[Tuple[str, Dict[str, Any]]]:
    """Get db summary for database.

    Args:
        conn (BaseConnector): database connection
        summary_template (str): summary template
        separator(str, optional): separator used to separate table's
            basic info and fields. defaults to `-- table-field-separator--`
        model_dimension(int, optional): The threshold for splitting field string
    """
    tables = conn.get_table_names()
    table_info_summaries = [
        _parse_table_summary_with_metadata(
            conn,
            summary_template,
            separator,
            table_name,
            model_dimension,
            column_separator=column_separator,
        )
        for table_name in tables
    ]
    return table_info_summaries


def _split_columns_str(
    columns: List[str], model_dimension: int, column_separator: str = ",\r\n    "
):
    """Split columns str.

    Args:
    columns (List[str]): fields string
    model_dimension (int, optional): The threshold for splitting field string.
    """
    result = []
    current_string = ""
    current_length = 0

    for element_str in columns:
        element_length = len(element_str)

        # If adding the current element's length would exceed the threshold,
        # add the current string to results and reset
        if current_length + element_length > model_dimension:
            result.append(current_string.strip())  # Remove trailing spaces
            current_string = element_str
            current_length = element_length
        else:
            # If current string is empty, add element directly
            if current_string:
                current_string += column_separator + element_str
            else:
                current_string = element_str
            current_length += element_length + 1  # Add length of space

    # Handle the last string segment
    if current_string:
        result.append(current_string.strip())

    return result


def _parse_table_summary_with_metadata(
    conn: BaseConnector,
    summary_template: str,
    separator,
    table_name: str,
    model_dimension=512,
    column_separator: str = _DEFAULT_COLUMN_SEPARATOR,
    db_summary_version: str = "v1.0",
) -> Tuple[str, Dict[str, Any]]:
    """Get table summary for table.

    Args:
        conn (BaseConnector): database connection
        summary_template (str): summary template
        separator(str, optional): separator used to separate table's
            basic info and fields. defaults to `-- table-field-separator--`
        model_dimension(int, optional): The threshold for splitting field string

    Examples:
        metadata: {'table_name': 'asd', 'separated': 0/1}

        table_name: table1
        table_comment: comment
        index_keys: keys
        --table-field-separator--
        (column1,comment), (column2, comment), (column3, comment)
        (column4,comment), (column5, comment), (column6, comment)
    """
    columns = []
    metadata = {
        "table_name": table_name,
        "separated": 0,
        "db_summary_version": db_summary_version,
    }
    for column in conn.get_columns(table_name):
        col_name = column["name"]
        col_type = str(column["type"]) if "type" in column else None
        col_comment = column.get("comment")
        column_def = f'"{col_name}" {col_type.upper()}'
        if col_comment:
            column_def += f' COMMENT "{col_comment}"'
        columns.append(column_def)
    metadata.update({"field_num": len(columns)})
    separated_columns = _split_columns_str(
        columns, model_dimension=model_dimension, column_separator=column_separator
    )
    if len(separated_columns) > 1:
        metadata["separated"] = 1
    column_str = column_separator.join(separated_columns)
    # Obtain index information
    index_keys = []
    raw_indexes = conn.get_indexes(table_name)
    for index in raw_indexes:
        if isinstance(index, tuple):  # Process tuple type index information
            index_name, index_creation_command = index
            # Extract column names using re
            matched_columns = re.findall(r"\(([^)]+)\)", index_creation_command)
            if matched_columns:
                key_str = ", ".join(matched_columns)
                index_keys.append(f"{index_name}(`{key_str}`) ")
        else:
            key_str = ", ".join(index["column_names"])
            index_keys.append(f"{index['name']}(`{key_str}`) ")

    table_comment = ""

    try:
        comment = conn.get_table_comment(table_name)
        table_comment = comment.get("text")
    except Exception:
        pass

    index_key_str = ", ".join(index_keys)
    table_str = summary_template.format(
        table_name=table_name, table_comment=table_comment, index_keys=index_key_str
    )
    table_str += f"\n{separator}\n{column_str}"
    return table_str, metadata


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
    # Obtain index information
    index_keys = []
    raw_indexes = conn.get_indexes(table_name)
    for index in raw_indexes:
        if isinstance(index, tuple):  # Process tuple type index information
            index_name, index_creation_command = index
            # Extract column names using re
            matched_columns = re.findall(r"\(([^)]+)\)", index_creation_command)
            if matched_columns:
                key_str = ", ".join(matched_columns)
                index_keys.append(f"{index_name}(`{key_str}`) ")
        else:
            key_str = ", ".join(index["column_names"])
            index_keys.append(f"{index['name']}(`{key_str}`) ")
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
