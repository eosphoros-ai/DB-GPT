"""Configuration for database connection."""
from dbgpt._private.pydantic import BaseModel, Field


class DBConfig(BaseModel):
    """Database connection configuration."""

    db_type: str = Field(..., description="Database type, e.g. sqlite, mysql, etc.")
    db_name: str = Field(..., description="Database name.")
    file_path: str = Field("", description="File path for file-based database.")
    db_host: str = Field("", description="Database host.")
    db_port: int = Field(0, description="Database port.")
    db_user: str = Field("", description="Database user.")
    db_pwd: str = Field("", description="Database password.")
    comment: str = Field("", description="Comment for the database.")


class DbTypeInfo(BaseModel):
    """Database type information."""

    db_type: str = Field(..., description="Database type.")
    is_file_db: bool = Field(False, description="Whether the database is file-based.")
