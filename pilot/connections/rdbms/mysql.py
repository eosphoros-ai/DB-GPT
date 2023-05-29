#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pymysql
from pilot.connections.rdbms.rdbms_connect import RDBMSDatabase


class MySQLConnect(RDBMSDatabase):
    """Connect MySQL Database fetch MetaData For LLM Prompt
    Args:
    Usage:
    """

    type:str = "MySQL"
    connect_url = "mysql+pymysql://"

    default_db = ["information_schema", "performance_schema", "sys", "mysql"]

