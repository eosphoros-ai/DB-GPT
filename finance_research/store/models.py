"""SQLAlchemy data models for provenance tracking and metrics storage."""

import datetime
import uuid

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def _uuid() -> str:
    return str(uuid.uuid4())


class Provenance(Base):
    """Source record: where a piece of data came from."""

    __tablename__ = "finance_provenance"

    id = Column(String, primary_key=True, default=_uuid)
    source_type = Column(String, nullable=False)  # html/pdf/table/csv/excel/upload
    source_url = Column(String, nullable=True)
    source_file = Column(String, nullable=True)
    title = Column(String, nullable=True)
    page = Column(Integer, nullable=True)
    table_name = Column(String, nullable=True)
    captured_at = Column(DateTime, default=datetime.datetime.utcnow)
    extracted_at = Column(DateTime, default=datetime.datetime.utcnow)
    raw_text = Column(Text, nullable=True)  # evidence snippet
    extra = Column(Text, nullable=True)  # JSON extra info

    metrics = relationship(
        "FinancialMetric", back_populates="provenance", cascade="all, delete-orphan"
    )


class FinancialMetric(Base):
    """A single structured financial metric, tied to a provenance record."""

    __tablename__ = "finance_metric"

    id = Column(String, primary_key=True, default=_uuid)
    provenance_id = Column(String, ForeignKey("finance_provenance.id"), nullable=False)
    company_name = Column(String, nullable=False)
    report_type = Column(String, nullable=True)
    fiscal_period = Column(String, nullable=True)
    metric_name = Column(String, nullable=False)
    metric_value = Column(Float, nullable=True)
    unit = Column(String, nullable=True)
    evidence = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    provenance = relationship("Provenance", back_populates="metrics")


class Report(Base):
    """Generated research report with citations."""

    __tablename__ = "finance_report"

    id = Column(String, primary_key=True, default=_uuid)
    title = Column(String, nullable=False)
    companies = Column(Text, nullable=True)  # JSON array
    content = Column(Text, nullable=True)  # markdown body with citations
    citations = Column(Text, nullable=True)  # JSON citation list
    charts = Column(Text, nullable=True)  # JSON chart paths
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
