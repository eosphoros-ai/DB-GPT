"""SQLAlchemy entities for report snapshots and execution evidence."""

from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects import mysql

from dbgpt.core.interface.report import (
    MAX_ARTIFACT_ID_LENGTH,
    MAX_BLOCK_ID_LENGTH,
    MAX_CONV_UID_LENGTH,
    MAX_MESSAGE_ID_LENGTH,
    MAX_REPORT_ID_LENGTH,
    MAX_REPORT_TITLE_LENGTH,
    MAX_RUN_ID_LENGTH,
    MAX_SECTION_ID_LENGTH,
    MAX_STEP_ID_LENGTH,
    MAX_TASK_ID_LENGTH,
)
from dbgpt.storage.metadata import Model

_LONG_TEXT = Text().with_variant(mysql.LONGTEXT(), "mysql")
_PRIMARY_KEY = BigInteger().with_variant(Integer, "sqlite")
MAX_OWNER_ID_LENGTH = 255


class ReportEntity(Model):
    """Stable owner-scoped report identity and latest-run pointer."""

    __tablename__ = "dbgpt_report"
    __table_args__ = (
        Index("uk_report_owner_report", "owner_id", "report_id", unique=True),
        Index("idx_report_owner_updated", "owner_id", "updated_at"),
    )

    id = Column(_PRIMARY_KEY, primary_key=True, autoincrement=True)
    report_id = Column(String(MAX_REPORT_ID_LENGTH), nullable=False)
    owner_id = Column(String(MAX_OWNER_ID_LENGTH), nullable=False)
    title = Column(String(MAX_REPORT_TITLE_LENGTH), nullable=False)
    conv_uid = Column(String(MAX_CONV_UID_LENGTH), nullable=False)
    latest_run_id = Column(String(MAX_RUN_ID_LENGTH), nullable=False)
    latest_revision = Column(Integer, nullable=False)
    created_at = Column(
        DateTime, nullable=False, default=datetime.now, server_default=func.now()
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now,
        server_default=func.now(),
    )


class ReportRunEntity(Model):
    """One immutable, lossless report snapshot."""

    __tablename__ = "dbgpt_report_run"
    __table_args__ = (
        Index("uk_report_run_id", "run_id", unique=True),
        Index(
            "uk_report_run_owner_report_revision",
            "owner_id",
            "report_id",
            "revision",
            unique=True,
        ),
        Index("idx_report_run_owner_report_created", "owner_id", "report_id", "id"),
    )

    id = Column(_PRIMARY_KEY, primary_key=True, autoincrement=True)
    run_id = Column(String(MAX_RUN_ID_LENGTH), nullable=False)
    report_id = Column(String(MAX_REPORT_ID_LENGTH), nullable=False)
    owner_id = Column(String(MAX_OWNER_ID_LENGTH), nullable=False)
    revision = Column(Integer, nullable=False)
    schema_version = Column(Integer, nullable=False)
    trigger_type = Column(String(32), nullable=False, default="interactive")
    parent_run_id = Column(String(MAX_RUN_ID_LENGTH), nullable=True)
    status = Column(String(32), nullable=False, default="completed")
    document_json = Column(_LONG_TEXT, nullable=False)
    created_at = Column(
        DateTime, nullable=False, default=datetime.now, server_default=func.now()
    )


class ReportArtifactEntity(Model):
    """Queryable artifact index for one immutable run."""

    __tablename__ = "dbgpt_report_artifact"
    __table_args__ = (
        Index(
            "uk_report_artifact_run_artifact",
            "run_id",
            "artifact_id",
            unique=True,
        ),
        Index("idx_report_artifact_execution", "conv_uid", "step_id"),
    )

    id = Column(_PRIMARY_KEY, primary_key=True, autoincrement=True)
    run_id = Column(String(MAX_RUN_ID_LENGTH), nullable=False)
    artifact_id = Column(String(MAX_ARTIFACT_ID_LENGTH), nullable=False)
    artifact_type = Column(String(32), nullable=False)
    conv_uid = Column(String(MAX_CONV_UID_LENGTH), nullable=False)
    step_id = Column(String(MAX_STEP_ID_LENGTH), nullable=False)
    message_id = Column(String(MAX_MESSAGE_ID_LENGTH), nullable=True)
    task_id = Column(String(MAX_TASK_ID_LENGTH), nullable=True)
    execution_run_id = Column(String(MAX_RUN_ID_LENGTH), nullable=True)
    artifact_json = Column(_LONG_TEXT, nullable=False)


class ReportArtifactDependencyEntity(Model):
    """Directed execution/product lineage edge between two artifacts."""

    __tablename__ = "dbgpt_report_artifact_dependency"
    __table_args__ = (
        Index(
            "uk_report_artifact_dependency",
            "run_id",
            "artifact_id",
            "input_artifact_id",
            unique=True,
        ),
        Index(
            "idx_report_artifact_dependency_input",
            "run_id",
            "input_artifact_id",
        ),
    )

    id = Column(_PRIMARY_KEY, primary_key=True, autoincrement=True)
    run_id = Column(String(MAX_RUN_ID_LENGTH), nullable=False)
    artifact_id = Column(String(MAX_ARTIFACT_ID_LENGTH), nullable=False)
    input_artifact_id = Column(String(MAX_ARTIFACT_ID_LENGTH), nullable=False)


class ReportEvidenceEntity(Model):
    """Queryable report-block to artifact evidence binding."""

    __tablename__ = "dbgpt_report_evidence"
    __table_args__ = (
        Index(
            "uk_report_evidence_ordinal",
            "run_id",
            "block_id",
            "ordinal",
            unique=True,
        ),
        Index("idx_report_evidence_artifact", "run_id", "artifact_id"),
    )

    id = Column(_PRIMARY_KEY, primary_key=True, autoincrement=True)
    run_id = Column(String(MAX_RUN_ID_LENGTH), nullable=False)
    section_id = Column(String(MAX_SECTION_ID_LENGTH), nullable=False)
    block_id = Column(String(MAX_BLOCK_ID_LENGTH), nullable=False)
    ordinal = Column(Integer, nullable=False)
    artifact_id = Column(String(MAX_ARTIFACT_ID_LENGTH), nullable=False)
    role = Column(String(32), nullable=False)
    selector_json = Column(_LONG_TEXT, nullable=False)
    target_selector_json = Column(_LONG_TEXT, nullable=False)
