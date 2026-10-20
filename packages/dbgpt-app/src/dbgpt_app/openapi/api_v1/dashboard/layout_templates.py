"""Deterministic template layouts shared by planning and the browser editor."""

import json
from pathlib import Path
from typing import List

from .schemas import DashboardLayouts, DashboardVisualTheme, DashboardWidget, LayoutItem

LAYOUT_TEMPLATES = {
    item["id"]: item
    for item in json.loads(
        (
            Path(__file__).parent / "schema" / "dashboard-layout-templates.json"
        ).read_text(encoding="utf-8")
    )
}


def template_theme(template_id: str) -> DashboardVisualTheme:
    return DashboardVisualTheme(**LAYOUT_TEMPLATES[template_id]["theme"])


def template_layout(
    widgets: List[DashboardWidget], template_id: str
) -> DashboardLayouts:
    """Mirror dashboard-layout-templates.ts without changing widgets or queries."""
    template = LAYOUT_TEMPLATES[template_id]

    def kind(widget):
        return widget.presentation.visualization or widget.type

    metrics = [widget for widget in widgets if kind(widget) == "kpi"]
    tables = [widget for widget in widgets if kind(widget) == "table"]
    charts = [widget for widget in widgets if kind(widget) not in ("kpi", "table")]
    items = []
    y = 0

    def row(entries, widths, height):
        nonlocal y
        x = 0
        for widget, width in zip(entries, widths):
            items.append(
                LayoutItem(
                    widget_id=widget.id,
                    x=x,
                    y=y,
                    w=width,
                    h=height,
                    min_w=3
                    if kind(widget) == "kpi"
                    else 6
                    if kind(widget) == "table"
                    else 4,
                    min_h=3 if kind(widget) == "kpi" else 4,
                )
            )
            x += width
        y += height

    def balanced_rows(entries, columns, height):
        offset = 0
        remaining_rows = (len(entries) + columns - 1) // columns
        while offset < len(entries):
            count = (len(entries) - offset + remaining_rows - 1) // remaining_rows
            row(entries[offset : offset + count], [12 // count] * count, height)
            offset += count
            remaining_rows -= 1

    balanced_rows(metrics, template["metric_columns"], template["metric_height"])
    if template["focus"] == "trend" and charts:
        index = next(
            (
                i
                for i, widget in enumerate(charts)
                if kind(widget) in ("line", "area", "dual_axis")
            ),
            0,
        )
        primary = charts.pop(index)
        secondary = charts.pop(0) if charts else None
        row(
            [primary, secondary] if secondary else [primary],
            [8, 4] if secondary else [12],
            template["detail_height"],
        )
    elif template["focus"] == "table" and tables:
        primary = tables.pop(0)
        secondary = charts.pop(0) if charts else None
        row(
            [primary, secondary] if secondary else [primary],
            [8, 4] if secondary else [12],
            template["detail_height"],
        )
    balanced_rows(charts, template["chart_columns"], template["chart_height"])
    for widget in tables:
        row([widget], [12], template["detail_height"])
    return DashboardLayouts(desktop=items)
