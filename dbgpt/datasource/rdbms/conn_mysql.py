"""MySQL connector."""

from .base import RDBMSConnector


class MySQLConnector(RDBMSConnector):
    """MySQL connector."""

    db_type: str = "mysql"
    db_dialect: str = "mysql"
    driver: str = "mysql+pymysql"

    default_db = ["information_schema", "performance_schema", "sys", "mysql"]
