#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Optional, Any, Iterable

from sqlalchemy import (
    MetaData,
    Table,
    create_engine,
    inspect,
    select,
    text,
)
from dbgpt.datasource.rdbms.base import RDBMSDatabase


class MSSQLConnect(RDBMSDatabase):
    """Connect MSSQL Database fetch MetaData
    Args:
    Usage:
    """

    db_type: str = "mssql"
    db_dialect: str = "mssql"
    driver: str = "mssql+pymssql"

    default_db = ["master", "model", "msdb", "tempdb", "modeldb", "resource", "sys"]

    def table_simple_info(self) -> Iterable[str]:
        _tables_sql = f"""
                SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE'
            """
        cursor = self.session.execute(text(_tables_sql))
        tables_results = cursor.fetchall()
        results = []
        for row in tables_results:
            table_name = row[0]
            _sql = f"""
                SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='{table_name}'
            """
            cursor_colums = self.session.execute(text(_sql))
            colum_results = cursor_colums.fetchall()
            table_colums = []
            for row_col in colum_results:
                field_info = list(row_col)
                table_colums.append(field_info[0])
            results.append(f"{table_name}({','.join(table_colums)});")
        return results
