MYSQL Connection
==================================
MYSQL can connect mysql server.

inheriting the RDBMSDatabase
```
class MySQLConnect(RDBMSDatabase):
    """Connect MySQL Database fetch MetaData
    Args:
    Usage:
    """

    type: str = "MySQL"
    dialect: str = "mysql"
    driver: str = "pymysql"

    default_db = ["information_schema", "performance_schema", "sys", "mysql"]
```