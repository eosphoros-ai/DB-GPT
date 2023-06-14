from typing import Optional, Any

from pilot.connections.rdbms.rdbms_connect import RDBMSDatabase

from pilot.configs.config import Config

CFG = Config()


class DuckDbConnect(RDBMSDatabase):
    """Connect Duckdb Database fetch MetaData
    Args:
    Usage:
    """

    type: str = "DUCKDB"

    driver: str = "duckdb"

    file_path: str

    default_db = ["information_schema", "performance_schema", "sys", "mysql"]

    @classmethod
    def from_config(cls) -> RDBMSDatabase:
        """
        Todo password encryption
        Returns:
        """
        return cls.from_uri_db(
            cls,
            CFG.LOCAL_DB_PATH,
            engine_args={"pool_size": 10, "pool_recycle": 3600, "echo": True},
        )

    @classmethod
    def from_uri_db(
        cls, db_path: str, engine_args: Optional[dict] = None, **kwargs: Any
    ) -> RDBMSDatabase:
        db_url: str = cls.connect_driver + "://" + db_path
        return cls.from_uri(db_url, engine_args, **kwargs)
