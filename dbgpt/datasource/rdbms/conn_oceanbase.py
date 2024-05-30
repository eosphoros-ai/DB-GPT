"""Ocean base connect."""

import logging

from dbgpt.datasource.rdbms.base import RDBMSConnector

logger = logging.getLogger(__name__)


class OceanBaseConnect(RDBMSConnector):
    """Connect Oceanbase Database fetch MetaData.

    Args:
    Usage:
    """

    db_type: str = "oceanbase"
    db_dialect: str = "mysql"
    driver: str = "mysql+ob"

    default_db = ["information_schema", "performance_schema", "sys", "mysql"]

    def get_users(self):
        """Get_users."""
        return []

    def get_grants(self):
        """Get_grants."""
        return []

    def get_collation(self):
        """Get collation."""
        return "UTF-8"

    def get_charset(self):
        """Get_charset."""
        return "UTF-8"
