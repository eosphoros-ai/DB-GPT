"""Strict public wire schemas for report persistence APIs."""

from datetime import datetime
from typing import Any, Literal, Optional

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field
from dbgpt.core.interface.report import (
    Artifact,
    EvidenceReference,
    ReportDocument,
)

from ..domain import ReportEvidenceDetail, ReportRunRecord, ReportRunSummary


class _ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SaveReportRequest(_ApiModel):
    """Save request; owner and run identity are always server-owned."""

    document: ReportDocument
    trigger_type: Literal["interactive", "refresh", "replay", "scheduled"] = (
        "interactive"
    )
    parent_run_id: Optional[str] = None


class RenderObservationRequest(_ApiModel):
    """Browser observations are separate from immutable execution evidence."""

    observation_id: str = Field(min_length=1, max_length=100)
    artifact_id: str = Field(min_length=1, max_length=200)
    renderer: Literal["echarts", "g2", "image", "table"]
    state: Literal["rendered", "failed", "not_rendered"]
    duration_ms: Optional[int] = Field(default=None, ge=0, le=86400000)
    options: Optional[dict[str, Any]] = None
    error: Optional[str] = Field(default=None, max_length=2000)


class ReportRunSummaryResponse(_ApiModel):
    """Wire representation of immutable report-run metadata."""

    run_id: str
    report_id: str
    revision: int
    schema_version: int
    trigger_type: str
    parent_run_id: Optional[str]
    status: str
    created_at: datetime

    @classmethod
    def from_domain(cls, run: ReportRunSummary) -> "ReportRunSummaryResponse":
        return cls(
            run_id=run.run_id,
            report_id=run.report_id,
            revision=run.revision,
            schema_version=run.schema_version,
            trigger_type=run.trigger_type,
            parent_run_id=run.parent_run_id,
            status=run.status,
            created_at=run.created_at,
        )


class ReportRunResponse(ReportRunSummaryResponse):
    """Wire representation of a report run and its complete document."""

    document: ReportDocument

    @classmethod
    def from_record(cls, run: ReportRunRecord) -> "ReportRunResponse":
        return cls(
            run_id=run.run_id,
            report_id=run.report_id,
            revision=run.revision,
            schema_version=run.schema_version,
            trigger_type=run.trigger_type,
            parent_run_id=run.parent_run_id,
            status=run.status,
            created_at=run.created_at,
            document=run.document,
        )


class ReportEvidenceResponse(_ApiModel):
    """Evidence binding paired with the artifact needed to inspect it."""

    section_id: str
    block_id: str
    ordinal: int
    evidence: EvidenceReference
    artifact: Artifact

    @classmethod
    def from_domain(cls, detail: ReportEvidenceDetail) -> "ReportEvidenceResponse":
        return cls(
            section_id=detail.section_id,
            block_id=detail.block_id,
            ordinal=detail.ordinal,
            evidence=detail.evidence,
            artifact=detail.artifact,
        )
