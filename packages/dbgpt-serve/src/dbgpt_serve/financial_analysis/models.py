"""Financial run and immutable report snapshot in the existing metadata DB."""

from sqlalchemy import Column, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import declarative_base

from dbgpt.storage.metadata import Model


class _FinancialRunColumns:
    id = Column(String(36), primary_key=True)
    owner_id = Column(String(255), nullable=False)
    session_id = Column(String(255), nullable=False)
    file_id = Column(String(64), nullable=False)
    status = Column(String(16), nullable=False)
    stage = Column(String(32), nullable=False)
    created_at = Column(String(40), nullable=False)
    updated_at = Column(String(40), nullable=False)
    completed_at = Column(String(40), nullable=True)
    error = Column(Text, nullable=True)
    report_json = Column(Text().with_variant(LONGTEXT(), "mysql"), nullable=True)


class FinancialRunEntity(_FinancialRunColumns, Model):
    __tablename__ = "dbgpt_financial_analysis_run"
    __table_args__ = (Index("idx_financial_run_scope", "owner_id", "session_id"),)
    supports_revisions = True

    mode = Column(String(16), nullable=False, default="report", server_default="report")
    config_json = Column(Text().with_variant(LONGTEXT(), "mysql"), nullable=True)
    request_fingerprint = Column(String(64), nullable=True)


class LegacyFinancialRunEntity(_FinancialRunColumns, declarative_base()):
    """Separate metadata keeps legacy queries and inserts free of v2 columns."""

    __tablename__ = "dbgpt_financial_analysis_run"
    supports_revisions = False
    mode = "report"


class FinancialRunDocumentEntity(Model):
    __tablename__ = "dbgpt_financial_run_document"
    __table_args__ = (
        UniqueConstraint("run_id", "file_id", name="uq_financial_run_document"),
        Index("idx_financial_document_run", "run_id"),
    )
    id = Column(String(64), primary_key=True)
    run_id = Column(String(36), nullable=False)
    file_id = Column(String(64), nullable=False)
    position = Column(Integer, nullable=False)
    file_name = Column(String(255), nullable=False)
    status = Column(String(16), nullable=False)
    document_id = Column(String(96), nullable=True)
    sha256 = Column(String(64), nullable=False)
    extractor_version = Column(String(64), nullable=False)
    extracted_json = Column(Text().with_variant(LONGTEXT(), "mysql"), nullable=True)
    error = Column(Text, nullable=True)
    started_at = Column(String(40), nullable=True)
    completed_at = Column(String(40), nullable=True)


class FinancialReportRevisionEntity(Model):
    __tablename__ = "dbgpt_financial_report_revision"
    __table_args__ = (
        UniqueConstraint("run_id", "revision", name="uq_financial_report_revision"),
        Index("idx_financial_revision_run", "run_id"),
    )
    id = Column(String(64), primary_key=True)
    run_id = Column(String(36), nullable=False)
    revision = Column(String(255), nullable=False)
    report_json = Column(Text().with_variant(LONGTEXT(), "mysql"), nullable=False)
    published_at = Column(String(40), nullable=False)
    sha256 = Column(String(64), nullable=False)


class FinancialExportEntity(Model):
    """Immutable generated files; ownership is inherited from the parent run."""

    __tablename__ = "dbgpt_financial_analysis_export"
    __table_args__ = (Index("idx_financial_export_run", "run_id", "revision"),)
    id = Column(String(64), primary_key=True)
    run_id = Column(String(36), nullable=False)
    revision = Column(String(255), nullable=False)
    format = Column(String(8), nullable=False)
    file_name = Column(String(255), nullable=False)
    created_at = Column(String(40), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    sha256 = Column(String(64), nullable=False)
    content = Column(Text().with_variant(LONGTEXT(), "mysql"), nullable=False)
