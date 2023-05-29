#!/usr/bin/env python3
# -*- coding:utf-8 -*-

"""We need to design a base class.  That other connector can Write with this"""
from abc import ABC, abstractmethod
from pydantic import BaseModel, Extra, Field, root_validator
from typing import Any, Iterable, List, Optional


class BaseConnect(BaseModel, ABC):
    type
    driver: str


    def get_session(self, db_name: str):
        pass


    def get_table_names(self) -> Iterable[str]:
        pass

    def get_table_info(self, table_names: Optional[List[str]] = None) -> str:
        pass

    def get_table_info(self, table_names: Optional[List[str]] = None) -> str:
        pass

    def get_index_info(self, table_names: Optional[List[str]] = None) -> str:
        pass

    def get_database_list(self):
        pass

    def run(self, session, command: str, fetch: str = "all") -> List:
        pass