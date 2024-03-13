#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from dbgpt.datasource.rdbms.base import RDBMSDatabase


class MySQLConnect(RDBMSDatabase):
    """Connect MySQL Database fetch MetaData
    Args:
    Usage:
    """

    db_type: str = "mysql"
    db_dialect: str = "mysql"
    driver: str = "mysql+pymysql"

    default_db = ["information_schema", "performance_schema", "sys", "mysql"]
