"""Immutable domain values exposed by report persistence."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from dbgpt.core.interface.report import Artifact, EvidenceReference, ReportDocument


class ReportWriteConflictError(RuntimeError):
    """A bounded retry could not serialize a concurrent report save."""


@dataclass(frozen=True)
class ReportRunSummary:
    """Public metadata for one immutable report revision."""

    run_id: str
    report_id: str
    revision: int
    schema_version: int
    trigger_type: str
    parent_run_id: Optional[str]
    status: str
    created_at: datetime


@dataclass(frozen=True)
class ReportRunRecord(ReportRunSummary):
    """One report revision together with its lossless protocol document."""

    document: ReportDocument


@dataclass(frozen=True)
class ReportEvidenceDetail:
    """One ordered evidence binding and its referenced artifact."""

    section_id: str
    block_id: str
    ordinal: int
    evidence: EvidenceReference
    artifact: Artifact
