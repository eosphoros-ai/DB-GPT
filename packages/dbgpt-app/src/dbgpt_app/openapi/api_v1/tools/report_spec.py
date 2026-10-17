"""The input contract of the shipped business report template."""

import json
from typing import Any, List, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from dbgpt.core.interface.report import normalize_result_path


class _SpecNode(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ReportReference(_SpecNode):
    artifact_id: str = Field(min_length=1)
    field: str | None = None
    path: list[str | int] | None = None
    kind: str | None = None
    quote: str | None = None
    format: str | None = None
    suffix: str | None = None
    proposal: str | None = Field(default=None, min_length=1)

    @field_validator("path", mode="before")
    @classmethod
    def normalize_path(cls, value):
        return normalize_result_path(value) if value is not None else None


ReportPart = str | ReportReference


class ReportKPI(_SpecNode):
    label: str
    ref: ReportReference
    unit: str | None = None
    hint: str | None = None


class ReportTableColumn(_SpecNode):
    field: str
    label: str | None = None
    format: str | None = None


class ReportTable(_SpecNode):
    artifact_id: str = Field(min_length=1)
    field: str | None = None
    path: list[str | int] | None = None
    columns: list[str | ReportTableColumn] = Field(min_length=1)
    rows: list[list[ReportPart]] | None = None
    limit: int | None = Field(default=None, ge=0)
    offset: int | None = Field(default=None, ge=0)
    label: str | None = None

    @field_validator("path", mode="before")
    @classmethod
    def normalize_path(cls, value):
        return normalize_result_path(value) if value is not None else None


class ReportChart(_SpecNode):
    refs: list[str] = Field(default_factory=list)
    img: str | None = None
    renderer: Literal["echarts"] | None = None
    host_id: str | None = None
    chart_id: str | None = None
    producer: ReportReference | None = None
    caption: str | None = None
    option: dict[str, Any] | None = None
    height: int | None = Field(default=None, ge=200, le=10000)
    maps: dict[str, ReportReference] | None = None


class ReportRecommendationLine(_SpecNode):
    label: str | None = None
    parts: list[ReportPart] = Field(default_factory=list)


class ReportRecommendation(_SpecNode):
    title: str = Field(min_length=1)
    badge: str | None = None
    cls: str | None = None
    lines: list[ReportRecommendationLine] = Field(default_factory=list)


class ReportNote(_SpecNode):
    label: str | None = None
    parts: list[ReportPart] = Field(default_factory=list)
    ref: ReportReference | None = None


class ReportSection(_SpecNode):
    heading: str | None = None
    kpis: List[ReportKPI] = Field(default_factory=list)
    intro: List[List[ReportPart]] = Field(default_factory=list)
    bullets: List[List[ReportPart]] = Field(default_factory=list)
    list: List[List[ReportPart]] = Field(default_factory=list)
    recommendations: List[ReportRecommendation] = Field(default_factory=lambda: [])
    table: ReportTable | None = None
    chart: ReportChart | None = None
    note: ReportNote | None = None


class BusinessReportSpec(_SpecNode):
    title: str | None = None
    subtitle: str | None = None
    scope: str | None = None
    kpis: list[ReportKPI] = Field(default_factory=list)
    sections: list[ReportSection] = Field(default_factory=list)


def validate_report_spec(value: Any) -> dict:
    """Reject ignored keys and missing references before generating any HTML."""
    try:
        return BusinessReportSpec.model_validate(value).model_dump(
            exclude_none=True, exclude_unset=True
        )
    except ValidationError as error:
        issues = []
        for item in error.errors(include_url=False, include_input=False):
            location = "$.data.REPORT_SPEC"
            for key in item["loc"]:
                if key in {"str", "ReportReference", "ReportTableColumn"}:
                    continue
                location += f"[{key}]" if isinstance(key, int) else f".{key}"
            issues.append(f"{location}: {item['msg']}")
        raise ValueError(
            "REPORT_TEMPLATE_SPEC_INVALID: attribute=data; "
            + "; ".join(issues)
            + '. Use kpis[{"label": ..., "ref": {"artifact_id": ..., '
            '"field"/"path": ...}}], sections[].intro as lists of parts, and '
            "sections[].recommendations as objects with title and lines[].parts. "
            "Do not use KPI value, section parts, placeholders, or top-level "
            "recommendations; these are not rendered by this template. Preserve "
            "the contract in skills/business-report/SKILL.md and "
            "the completed artifacts and repair only the named spec fields. In a "
            "REPORT_SPEC repair, remove unsupported root keys by setting them to "
            "null; replace the affected sections/kpis lists with their corrected lists."
        ) from error


def report_data_schema() -> dict:
    """Publish the existing spec contract, including its root patch semantics."""
    schema = BusinessReportSpec.model_json_schema()
    definitions = schema.pop("$defs", {})
    # Root null deletes a key before validating the merged spec.
    schema["additionalProperties"] = {"type": "null"}
    for key, value in schema["properties"].items():
        schema["properties"][key] = {"anyOf": [value, {"type": "null"}]}
    definitions["BusinessReportSpec"] = schema
    return {
        "type": ["object", "null"],
        "$defs": definitions,
        "properties": {
            key: {"$ref": "#/$defs/BusinessReportSpec"}
            for key in ("REPORT_SPEC", "REPORT_SPEC_APPEND")
        },
        "additionalProperties": False,
        "description": (
            "REPORT_SPEC patches root fields; sections/kpis replace lists. "
            "REPORT_SPEC_APPEND appends sections/kpis. Values select "
            "captured artifacts. chart.option accepts full JSON ECharts "
            "options without a series-type whitelist; "
            "data/source/nodes/links use captured artifact_id + field/path "
            "references. producer supplies default dataset/encode; maps "
            "binds captured GeoJSON. proposal is an explicitly labelled "
            "recommendation target, never an observed "
            "result."
        ),
    }


def merge_report_data(previous: dict, updates: dict) -> dict:
    """A spec update replaces named root fields, retaining the other fields."""
    merged = {**previous, **updates}
    old_spec, new_spec = previous.get("REPORT_SPEC"), updates.get("REPORT_SPEC")
    if isinstance(old_spec, str):
        try:
            old_spec = json.loads(old_spec)
        except ValueError:
            old_spec = None
    if isinstance(new_spec, dict) and isinstance(old_spec, dict):
        spec = dict(old_spec)
        for key, value in new_spec.items():
            if value is None:
                spec.pop(key, None)
            else:
                spec[key] = value
        merged["REPORT_SPEC"] = spec
    return merged
