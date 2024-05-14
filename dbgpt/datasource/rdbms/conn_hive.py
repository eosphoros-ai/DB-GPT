"""Hive Connector."""
from typing import Any, Optional, cast
from urllib.parse import quote
from urllib.parse import quote_plus as urlquote

from .base import RDBMSConnector


class HiveConnector(RDBMSConnector):
    """Hive connector."""

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
    ) -> "HiveConnector":
        """Create a new HiveConnector from host, port, user, pwd, db_name."""
        db_url: str = f"{cls.driver}://{host}:{str(port)}/{db_name}"
        if user and pwd:
            db_url = (
                f"{cls.driver}://{quote(user)}:{urlquote(pwd)}@{host}:{str(port)}/"
                f"{db_name}"
            )
        return cast(HiveConnector, cls.from_uri(db_url, engine_args, **kwargs))

    def table_simple_info(self):
        """Get table simple info."""
        return []

    def get_users(self):
        """Get users."""
        return []

    def get_grants(self):
        """Get grants."""
        return []

    def get_collation(self):
        """Get collation."""
        return "UTF-8"

    def get_charset(self):
        """Get character_set of current database."""
        return "UTF-8"
