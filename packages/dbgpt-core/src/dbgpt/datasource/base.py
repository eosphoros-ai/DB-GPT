"""Base class for all connectors."""

from abc import ABC, abstractmethod
from typing import Dict, Iterable, List, Optional, Tuple, Type, TypeVar

from .parameter import BaseDatasourceParameters  # noqa: F401

C = TypeVar("C", bound="BaseDatasourceParameters")
T = TypeVar("T", bound="BaseConnector")


class BaseConnector(ABC):
    """Base class for all connectors."""

    db_type: str = "__abstract__db_type__"
    driver: str = ""

    @classmethod
    def param_class(cls) -> Type[C]:
        """Return parameter class.

        You should implement this method in your subclass.

        Returns:
            Type[C]: parameter class
        """

    @classmethod
    def from_parameters(cls, parameters: C) -> T:
        """Create a new connector from parameters.

        Args:
            parameters (C): parameters to create a new connector

        Returns:
            T: connector instance
        """
        raise NotImplementedError("Current connector does not support from_parameters")

    @property
    def db_url(self) -> str:
        """Return database engine url."""
        raise NotImplementedError("Current connector does not support db_url")

    def get_table_names(self) -> Iterable[str]:
        """Get all table names."""
        raise NotImplementedError("Current connector does not support get_table_names")

    def get_table_info(self, table_names: Optional[List[str]] = None) -> str:
        r"""Get table info about specified table.

        Returns:
            str: Table information joined by "\n\n"
        """
        raise NotImplementedError("Current connector does not support get_table_info")

    def get_index_info(self, table_names: Optional[List[str]] = None) -> str:
        """Get index info about specified table.

        Args:
             table_names (Optional[List[str]]): table names
        """
        raise NotImplementedError("Current connector does not support get_index_info")

    def get_example_data(self, table: str, count: int = 3):
        """Get example data about specified table.

        Not used now.

        Args:
            table (str): table name
            count (int): example data count
        """
        raise NotImplementedError("Current connector does not support get_example_data")

    def get_database_names(self) -> List[str]:
        """Return database names.

        Examples:
            .. code-block:: python

                print(conn.get_database_names())
                # ['db1', 'db2']

        Returns:
            List[str]: database list
        """
        raise NotImplementedError(
            "Current connector does not support get_database_names"
        )

    def get_table_comments(self, db_name: str) -> List[Tuple[str, str]]:
        """Get table comments.

        Args:
            db_name (str): database name

        Returns:
            List[Tuple[str, str]]: Table comments, first element is table name, second
                element is comment
        """
        raise NotImplementedError(
            "Current connector does not support get_table_comments"
        )

    def get_table_comment(self, table_name: str) -> Dict:
        """Return table comment with table name.

        Args:
            table_name (str): table name

        Returns:
            comment: Dict, which contains text: Optional[str], eg:["text": "comment"]
        """
        raise NotImplementedError(
            "Current connector does not support get_table_comment"
        )

    def get_columns(self, table_name: str) -> List[Dict]:
        """Return columns with table name.

        Args:
            table_name (str): table name

        Returns:
            List[Dict]: columns of table, which contains name: str, type: str,
                default_expression: str, is_in_primary_key: bool, comment: str
                eg: [{'name': 'id', 'type': 'int', 'default_expression': '',
                'is_in_primary_key': True, 'comment': 'id'}, ...]
        """
        raise NotImplementedError("Current connector does not support get_columns")

    def get_column_comments(self, db_name: str, table_name: str):
        """Return column comments with db name and table name.

        Args:
            db_name (str): database name
            table_name (_type_): _description_
        """
        raise NotImplementedError(
            "Current connector does not support get_column_comments"
        )

    @abstractmethod
    def run(self, command: str, fetch: str = "all") -> List:
        """Execute sql command.

        Args:
            command (str): sql command
            fetch (str): fetch type

        Returns:
            List: result list
        """

    def run_to_df(self, command: str, fetch: str = "all"):
        """Execute sql command and return result as dataframe.

        Args:
            command (str): sql command
            fetch (str): fetch type

        Returns:
            DataFrame: result dataframe
        """
        raise NotImplementedError("Current connector does not support run_to_df")

    def get_users(self) -> List[Tuple[str, str]]:
        """Return user information.

        Returns:
            List[Tuple[str, str]]: user list, which contains username and host
        """
        return []

    def get_grants(self) -> List[Tuple]:
        """Return grant information.

        Examples:
            .. code-block:: python

                print(conn.get_grants())
                # [(('GRANT SELECT, INSERT, UPDATE, DROP ROLE ON *.* TO `root`@`%`
                # WITH GRANT OPTION',)]

        Returns:
            List[Tuple]: grant list, which contains grant information
        """
        return []

    def get_collation(self) -> Optional[str]:
        """Return collation.

        Returns:
            Optional[str]: collation
        """
        return None

    def get_charset(self) -> str:
        """Get character_set of current database."""
        return "utf-8"

    def get_fields(self, table_name: str) -> List[Tuple]:
        """Get column fields about specified table.

        Args:
            table_name (str): table name

        Returns:
            List[Tuple]: column fields, which contains column name, column type,
                column default, is nullable, column comment
        """
        raise NotImplementedError("Current connector does not support get_fields")

    def get_simple_fields(self, table_name: str) -> List[Tuple]:
        """Return simple fields about specified table.

        Args:
            table_name (str): table name

        Returns:
            List[Tuple]: simple fields, which contains column name, column type,
                is nullable, column key, default value, extra.
        """
        return self.get_fields(table_name)

    def get_show_create_table(self, table_name: str) -> str:
        """Return show create table about specified table.

        Returns:
            str: show create table
        """
        raise NotImplementedError(
            "Current connector does not support get_show_create_table"
        )

    def get_indexes(self, table_name: str) -> List[Dict]:
        """Return indexes about specified table.

        Args:
            table_name (str): table name

        Returns:
            List[Dict], eg:[{'name': 'idx_key', 'column_names': ['id']}]
        """
        raise NotImplementedError("Current connector does not support get_indexes")

    @classmethod
    def is_normal_type(cls) -> bool:
        """Return whether the connector is a normal type."""
        return True

    @classmethod
    def is_graph_type(cls) -> bool:
        """Return whether the connector is a graph database connector."""
        return False

    def close(self):
        """Close the connector.

        Make sure it can be called multiple times.
        """

    def __enter__(self):
        """Return self when entering the context."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close the connection when exiting the context."""
        self.close()

    def __del__(self):
        """Close the connection when the object is deleted."""
        self.close()
