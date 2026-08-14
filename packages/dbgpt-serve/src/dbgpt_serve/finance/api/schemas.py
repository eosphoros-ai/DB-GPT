"""API schemas for the finance research module."""

from typing import Dict, List, Optional

from dbgpt._private.pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    """Request to analyze a company's public financial reports."""

    company: str = Field(..., description="Company name to analyze.")
    query: Optional[str] = Field(
        None, description="Optional search query; defaults to '<company> 年报 财报'."
    )


class CompareRequest(BaseModel):
    """Request to compare multiple companies."""

    companies: List[str] = Field(..., description="Company names to compare.")
    queries: Optional[List[str]] = Field(
        None, description="Optional per-company search queries."
    )


class Citation(BaseModel):
    """A single data citation for traceability."""

    metric: Optional[str] = None
    fiscal_period: Optional[str] = None
    report_type: Optional[str] = None
    metric_value: Optional[float] = None
    source_type: Optional[str] = None
    source_url: Optional[str] = None
    source_file: Optional[str] = None
    page: Optional[int] = None
    table_name: Optional[str] = None
    evidence: Optional[str] = None
    extracted_at: Optional[str] = None


class MetricPoint(BaseModel):
    """One data point of a metric with its full provenance."""

    fiscal_period: Optional[str] = None
    value: Optional[float] = None
    source_type: Optional[str] = None
    source_url: Optional[str] = None
    source_file: Optional[str] = None
    page: Optional[int] = None
    table_name: Optional[str] = None
    evidence: Optional[str] = None
    extracted_at: Optional[str] = None


class MetricItem(BaseModel):
    """A metric grouped across periods with provenance per point."""

    name: str = Field(..., description="Metric key, e.g. revenue / net_profit.")
    report_type: Optional[str] = Field(
        None, description="annual / quarterly / announcement."
    )
    latest_yoy: Optional[float] = Field(
        None, description="Latest year-over-year growth in percent."
    )
    latest_qoq: Optional[float] = Field(
        None, description="Latest quarter-over-quarter growth in percent."
    )
    points: List[MetricPoint] = Field(default_factory=list)


class BreakdownItem(BaseModel):
    """One business-segment or regional revenue item."""

    name: Optional[str] = None
    amount: Optional[float] = None
    ratio: Optional[float] = None


class BreakdownRecord(BaseModel):
    """A revenue breakdown for one fiscal period."""

    fiscal_period: Optional[str] = None
    report_type: Optional[str] = None
    source_type: Optional[str] = None
    source_url: Optional[str] = None
    extracted_at: Optional[str] = None
    items: List[BreakdownItem] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    """Response containing the generated report, structured metrics, citations."""

    company: str = Field(..., description="Analyzed company.")
    report: str = Field(..., description="Markdown report with citations.")
    metrics: List[MetricItem] = Field(default_factory=list)
    segments: List[BreakdownRecord] = Field(default_factory=list)
    regions: List[BreakdownRecord] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)


class CompareResponse(BaseModel):
    """Response for a multi-company comparison."""

    companies: List[str] = Field(default_factory=list)
    report: str = Field(..., description="Markdown comparison report.")
    comparison: List[Dict] = Field(
        default_factory=list, description="Comparison table rows."
    )
    metrics: Dict[str, List[MetricItem]] = Field(
        default_factory=dict, description="Per-company metric series."
    )
