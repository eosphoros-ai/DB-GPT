"""One-way adapter from the existing chat-dashboard report to Schema v1.

The old scene stays intact.  Importing creates a new editable draft and never
mutates the historical conversation payload.
"""

import re
from typing import Any, Dict, List

from .schemas import (
    ChartEncoding,
    DashboardDescriptor,
    DashboardLayouts,
    DashboardMetadata,
    DashboardSchemaV1,
    DashboardWidget,
    DataFieldType,
    LayoutItem,
    MetricContext,
    QueryOutputField,
    WidgetQueryBinding,
    WidgetType,
)

_TYPE_MAP = {
    "indicatorvalue": WidgetType.KPI,
    "kpi": WidgetType.KPI,
    "linechart": WidgetType.LINE,
    "line": WidgetType.LINE,
    "barchart": WidgetType.BAR,
    "bar": WidgetType.BAR,
    "piechart": WidgetType.PIE,
    "pie": WidgetType.PIE,
    "table": WidgetType.TABLE,
}


def _widget_id(value: Any, index: int, used: set[str]) -> str:
    candidate = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(value or "")).strip("-")
    candidate = (candidate or f"legacy-widget-{index + 1}")[:128]
    base = candidate
    suffix = 2
    while candidate in used:
        candidate = f"{base[:120]}-{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def _encoding(widget_type: WidgetType, columns: List[str]) -> ChartEncoding:
    first = columns[0] if columns else None
    second = columns[1] if len(columns) > 1 else first
    if widget_type == WidgetType.KPI:
        return ChartEncoding(value=first)
    if widget_type in (WidgetType.LINE, WidgetType.BAR):
        return ChartEncoding(x=first, y=second)
    if widget_type == WidgetType.PIE:
        return ChartEncoding(category=first, angle=second)
    return ChartEncoding(columns=columns)


def _output_fields(
    widget_type: WidgetType, columns: List[str]
) -> List[QueryOutputField]:
    fields: List[QueryOutputField] = []
    for index, name in enumerate(columns):
        inferred = (
            DataFieldType.NUMBER
            if widget_type == WidgetType.KPI or index > 0
            else DataFieldType.STRING
        )
        fields.append(QueryOutputField(name=name, type=inferred, label=name))
    return fields


def adapt_legacy_report(
    report: Dict[str, Any], data_source_id: str, conversation_id: str | None = None
) -> DashboardSchemaV1:
    """Convert one legacy ``ReportData.prepare_dict()`` result into Schema v1."""

    charts = report.get("charts")
    if not isinstance(charts, list) or not charts:
        raise ValueError("Legacy report must contain at least one chart.")

    used_ids: set[str] = set()
    widgets: List[DashboardWidget] = []
    layouts: List[LayoutItem] = []
    for index, chart in enumerate(charts):
        if not isinstance(chart, dict):
            raise ValueError(f"Legacy chart {index + 1} must be an object.")
        sql = str(chart.get("chart_sql") or "").strip()
        columns = [str(item) for item in (chart.get("column_name") or []) if str(item)]
        if not sql or not columns:
            raise ValueError(
                f"Legacy chart {index + 1} requires chart_sql and column_name."
            )

        widget_type = _TYPE_MAP.get(
            str(chart.get("chart_type") or "").replace("_", "").lower(),
            WidgetType.TABLE,
        )
        widget_id = _widget_id(chart.get("chart_uid"), index, used_ids)
        widgets.append(
            DashboardWidget(
                id=widget_id,
                type=widget_type,
                title=str(chart.get("chart_name") or f"Chart {index + 1}"),
                description=str(chart.get("chart_desc") or ""),
                query=WidgetQueryBinding(
                    data_source_id=data_source_id,
                    sql=sql,
                    output_fields=_output_fields(widget_type, columns),
                ),
                encoding=_encoding(widget_type, columns),
            )
        )
        layouts.append(
            LayoutItem(
                widget_id=widget_id,
                x=0 if index % 2 == 0 else 6,
                y=(index // 2) * 5,
                w=6,
                h=4 if widget_type == WidgetType.KPI else 5,
            )
        )

    legacy_conversation = conversation_id or report.get("conv_uid")
    return DashboardSchemaV1(
        dashboard=DashboardDescriptor(
            title=str(report.get("template_name") or "Imported dashboard"),
            description=str(report.get("template_introduce") or ""),
            data_source_id=data_source_id,
        ),
        metric_context=MetricContext(
            source_notes=["Imported from the existing DB-GPT chat_dashboard scene."]
        ),
        widgets=widgets,
        layouts=DashboardLayouts(desktop=layouts),
        metadata=DashboardMetadata(
            conversation_id=str(legacy_conversation) if legacy_conversation else None,
            compatibility={
                "source": "chat_dashboard.ReportData",
                "legacy_template": report.get("template_name"),
                "import_mode": "one_way_copy",
            },
        ),
    )
