"""SQLAlchemy model for session-scoped files."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects import mysql

from dbgpt.storage.metadata import Model


class SessionFileEntity(Model):
    """Private persistence record for an owner-bound session or task file."""

    __tablename__ = "dbgpt_session_file"
    __table_args__ = (
        CheckConstraint(
            "(session_id IS NULL) <> (task_id IS NULL)",
            name="ck_session_file_scope",
        ),
        Index("uk_session_file_file_id", "file_id", unique=True),
        Index(
            "idx_session_file_owner_session",
            "owner_id",
            "session_id",
            "ordinal",
        ),
        Index(
            "idx_session_file_owner_task",
            "owner_id",
            "task_id",
            "ordinal",
        ),
        Index("idx_session_file_sha256", "owner_id", "sha256"),
    )

    id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    file_id = Column(String(64), nullable=False)
    owner_id = Column(String(255), nullable=False)
    session_id = Column(String(255), nullable=True)
    task_id = Column(String(64), nullable=True)
    display_name = Column(String(256), nullable=False)
    storage_uri = Column(String(512), nullable=False)
    media_type = Column(String(255), nullable=False)
    file_kind = Column(String(32), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    sha256 = Column(String(64), nullable=False)
    ordinal = Column(Integer, nullable=False)
    status = Column(String(32), nullable=False)
    inspection_json = Column(
        Text().with_variant(mysql.LONGTEXT(), "mysql"), nullable=True
    )
    error_code = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)
    source_file_id = Column(String(64), nullable=True)
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.now,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now,
        server_default=func.now(),
    )
