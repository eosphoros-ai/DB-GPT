from typing import Optional, Any, Iterable
from sqlalchemy import (
    MetaData,
    Table,
    create_engine,
    inspect,
    select,
    text,
)

from pilot.connections.rdbms.rdbms_connect import RDBMSDatabase
from pilot.configs.config import Config

CFG = Config()


class DuckDbConnect(RDBMSDatabase):
    """Connect Duckdb Database fetch MetaData
    Args:
    Usage:
    """

    def table_simple_info(self) -> Iterable[str]:
        return super().get_table_names()

    db_type: str = "duckdb"

    @classmethod
    def from_file_path(
        cls, file_path: str, engine_args: Optional[dict] = None, **kwargs: Any
    ) -> RDBMSDatabase:
        """Construct a SQLAlchemy engine from URI."""
        _engine_args = engine_args or {}
        return cls(create_engine("duckdb://" + file_path, **_engine_args), **kwargs)
