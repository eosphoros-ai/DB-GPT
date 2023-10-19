#!/usr/bin/env python3
# -*- coding:utf-8 -*-

"""We need to design a base class.  That other connector can Write with this"""
from abc import ABC, abstractmethod
from typing import Any, Iterable, List, Optional


class BaseConnect(ABC):
    def get_connect(self, db_name: str):
        pass

    def get_table_names(self) -> Iterable[str]:
        pass

    def get_table_info(self, table_names: Optional[List[str]] = None) -> str:
        pass

    def get_index_info(self, table_names: Optional[List[str]] = None) -> str:
        pass

    def get_example_data(self, table: str, count: int = 3):
        pass

    def get_database_list(self):
        pass

    def get_database_names(self):
        pass

    def get_table_comments(self, db_name):
        pass

    def run(self, session, command: str, fetch: str = "all") -> List:
        pass

    def run_to_df(self, command: str, fetch: str = "all"):
        pass

    def get_users(self):
        pass

    def get_grants(self):
        pass

    def get_collation(self):
        pass

    def get_charset(self):
        pass

    def get_fields(self, table_name):
        pass

    def get_show_create_table(self, table_name):
        pass

    def get_indexes(self, table_name):
        pass
