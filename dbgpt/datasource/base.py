#!/usr/bin/env python3
# -*- coding:utf-8 -*-

"""We need to design a base class.  That other connector can Write with this"""
from abc import ABC
from typing import Iterable, List, Optional


class BaseConnect(ABC):
    def get_table_names(self) -> Iterable[str]:
        """Get all table names"""
        pass

    def get_table_info(self, table_names: Optional[List[str]] = None) -> str:
        """Get table info about specified table.

        Returns:
            str: Table information joined by '\n\n'
        """
        pass

    def get_index_info(self, table_names: Optional[List[str]] = None) -> str:
        """Get index info about specified table.

        Args:
             table_names (Optional[List[str]]): table names
        """
        pass

    def get_example_data(self, table: str, count: int = 3):
        """Get example data about specified table.

        Not used now.

        Args:
            table (str): table name
            count (int): example data count
        """
        pass

    def get_database_list(self) -> List[str]:
        """Get database list.

        Returns:
            List[str]: database list
        """
        pass

    def get_database_names(self):
        """Get database names."""
        pass

    def get_table_comments(self, db_name):
        """Get table comments.

        Args:
            db_name (str): database name
        """
        pass

    def run(self, command: str, fetch: str = "all") -> List:
        """Execute sql command.

        Args:
            command (str): sql command
            fetch (str): fetch type
        """
        pass

    def run_to_df(self, command: str, fetch: str = "all"):
        """Execute sql command and return dataframe."""
        pass

    def get_users(self):
        """Get user info."""
        return []

    def get_grants(self):
        """Get grant info."""
        return []

    def get_collation(self):
        """Get collation."""
        return None

    def get_charset(self) -> str:
        """Get character_set of current database."""
        return "utf-8"

    def get_fields(self, table_name):
        """Get column fields about specified table."""
        pass

    def get_simple_fields(self, table_name):
        """Get column fields about specified table."""
        return self.get_fields(table_name)

    def get_show_create_table(self, table_name):
        """Get the creation table sql about specified table."""
        pass

    def get_indexes(self, table_name):
        """Get table indexes about specified table."""
        pass

    @classmethod
    def is_normal_type(cls) -> bool:
        """Return whether the connector is a normal type."""
        return True
