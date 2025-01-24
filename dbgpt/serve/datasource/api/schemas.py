from typing import Optional

from dbgpt._private.pydantic import BaseModel, Field


class DatasourceServeRequest(BaseModel):
    """DatasourceServeRequest."""

    id: Optional[int] = Field(None, description="The datasource id")
    db_type: str = Field(..., description="Database type, e.g. sqlite, mysql, etc.")
    db_name: str = Field(..., description="Database name.")
    db_path: str = Field("", description="File path for file-based database.")
    db_host: str = Field("", description="Database host.")
    db_port: int = Field(0, description="Database port.")
    db_user: str = Field("", description="Database user.")
    db_pwd: str = Field("", description="Database password.")
    comment: str = Field("", description="Comment for the database.")


class DatasourceServeResponse(BaseModel):
    """Datasource response model"""

    id: Optional[int] = Field(None, description="The datasource id")
    db_type: Optional[str] = Field(
        None, description="Database type, e.g. sqlite, mysql, etc."
    )
    db_name: Optional[str] = Field(None, description="Database name.")
    db_path: Optional[str] = Field("", description="File path for file-based database.")
    db_host: Optional[str] = Field("", description="Database host.")
    db_port: Optional[int] = Field(0, description="Database port.")
    db_user: Optional[str] = Field("", description="Database user.")
    db_pwd: Optional[str] = Field("", description="Database password.")
    comment: Optional[str] = Field("", description="Comment for the database.")
