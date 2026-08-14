"""Financial metric schemas used for structured extraction."""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class SegmentRevenue(BaseModel):
    """Revenue by business segment or region."""

    segment: str = Field(..., description="Business segment or region name.")
    amount: Optional[float] = Field(None, description="Revenue amount.")


class FinancialMetrics(BaseModel):
    """Structured financial metrics extracted from a report."""

    company_name: str = Field(..., description="Company name.")
    report_type: str = Field("annual", description="annual / quarterly / announcement")
    fiscal_period: str = Field(..., description="e.g. 2024FY, 2025Q1.")

    revenue: Optional[float] = Field(None, description="Operating revenue.")
    gross_profit: Optional[float] = Field(None, description="Gross profit.")
    net_profit: Optional[float] = Field(None, description="Net profit.")
    gross_margin: Optional[float] = Field(None, description="Gross margin (%).")
    net_margin: Optional[float] = Field(None, description="Net margin (%).")
    operating_cash_flow: Optional[float] = Field(
        None, description="Net operating cash flow."
    )

    segment_revenue: Optional[List[SegmentRevenue]] = Field(
        None, description="Revenue by business segment."
    )
    region_revenue: Optional[List[SegmentRevenue]] = Field(
        None, description="Revenue by region."
    )

    evidence: Optional[str] = Field(
        None, description="Original text snippet the values were extracted from."
    )
    evidence_by_metric: Optional[Dict[str, str]] = Field(
        None,
        description="Per-metric evidence snippets (populated by the rule extractor).",
        exclude=True,
    )

    def as_flat_rows(self) -> List[dict]:
        """Flatten the metrics into a list of (metric_name, value) rows.

        Each row carries ``metric_name`` and ``metric_value``; scalar rows also
        carry their per-metric ``evidence`` when available. Segment/region
        revenue is serialized under a stable ``<collection>:<segment>`` key.
        """
        rows = []
        scalar_fields = {
            "revenue": self.revenue,
            "gross_profit": self.gross_profit,
            "net_profit": self.net_profit,
            "gross_margin": self.gross_margin,
            "net_margin": self.net_margin,
            "operating_cash_flow": self.operating_cash_flow,
        }
        evidence_by_metric = self.evidence_by_metric or {}
        for name, value in scalar_fields.items():
            if value is not None:
                row = {"metric_name": name, "metric_value": value}
                if name in evidence_by_metric:
                    row["evidence"] = evidence_by_metric[name]
                rows.append(row)

        for prefix, collection in (
            ("segment_revenue", self.segment_revenue),
            ("region_revenue", self.region_revenue),
        ):
            for item in collection or []:
                if item.amount is not None:
                    rows.append(
                        {
                            "metric_name": f"{prefix}:{item.segment}",
                            "metric_value": item.amount,
                        }
                    )
        return rows
