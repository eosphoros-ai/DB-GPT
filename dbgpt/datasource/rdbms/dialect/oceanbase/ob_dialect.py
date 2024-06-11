"""OB Dialect support."""

from sqlalchemy.dialects import registry
from sqlalchemy.dialects.mysql import pymysql


class OBDialect(pymysql.MySQLDialect_pymysql):
    """OBDialect expend."""

    def initialize(self, connection):
        """Ob dialect initialize."""
        super(OBDialect, self).initialize(connection)
        self._server_version_info = (5, 7, 19)
        self.server_version_info = (5, 7, 19)

    def _server_version_info(self, connection):
        """Ob set fixed version ending compatibility issue."""
        return (5, 7, 19)

    def get_isolation_level(self, dbapi_connection):
        """Ob set fixed version ending compatibility issue."""
        self.server_version_info = (5, 7, 19)
        return super(OBDialect, self).get_isolation_level(dbapi_connection)


registry.register("mysql.ob", __name__, "OBDialect")
