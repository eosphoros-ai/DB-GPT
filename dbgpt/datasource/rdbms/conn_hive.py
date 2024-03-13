from typing import Any, Optional
from urllib.parse import quote
from urllib.parse import quote_plus as urlquote

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from dbgpt.datasource.rdbms.base import RDBMSDatabase


class HiveConnect(RDBMSDatabase):
    """db type"""

    db_type: str = "hive"
    """db driver"""
    driver: str = "hive"
    """db dialect"""
    dialect: str = "hive"

    @classmethod
    def from_uri_db(
        cls,
        host: str,
        port: int,
        user: str,
        pwd: str,
        db_name: str,
        engine_args: Optional[dict] = None,
        **kwargs: Any,
    ) -> RDBMSDatabase:
        """Construct a SQLAlchemy engine from uri database.
        Args:
            host (str): database host.
            port (int): database port.
            user (str): database user.
            pwd (str): database password.
            db_name (str): database name.
            engine_args (Optional[dict]):other engine_args.
        """
        db_url: str = f"{cls.driver}://{host}:{str(port)}/{db_name}"
        if user and pwd:
            db_url: str = f"{cls.driver}://{quote(user)}:{urlquote(pwd)}@{host}:{str(port)}/{db_name}"
        return cls.from_uri(db_url, engine_args, **kwargs)

    def table_simple_info(self):
        return []

    def get_users(self):
        return []

    def get_grants(self):
        return []

    def get_collation(self):
        """Get collation."""
        return "UTF-8"

    def get_charset(self):
        return "UTF-8"
