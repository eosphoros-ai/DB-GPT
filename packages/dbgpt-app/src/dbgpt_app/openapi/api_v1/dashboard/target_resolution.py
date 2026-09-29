"""Deterministic target resolution for natural dashboard references.

The resolver deliberately does not use a language model.  A dashboard edit may
only proceed when the referenced widget is uniquely identified from a stable
title/id, layout position, or the editor's explicit current selection.
"""

import re
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .schemas import (
    DashboardSchemaV1,
    DashboardSelectionKind,
    DashboardSelectionTarget,
    DashboardTargetCandidate,
    DashboardTargetResolution,
    DashboardTargetResolutionStatus,
)

_PUNCTUATION = re.compile(r"[\s\-_—–·,，。.!！?？:：;；'\"“”‘’()（）\[\]【】]+")

_SPATIAL_TERMS: Sequence[Tuple[str, Tuple[str, ...]]] = (
    ("right", ("最右", "右边", "右侧", "rightmost", "ontheright", "rightside")),
    ("left", ("最左", "左边", "左侧", "leftmost", "ontheleft", "leftside")),
    ("top", ("最上面", "顶部", "上边", "上面", "topmost", "atthetop", "above")),
    (
        "bottom",
        ("最下面", "底部", "下边", "下面", "bottommost", "atthebottom", "below"),
    ),
)

_DEICTIC_TERMS = (
    "这个图",
    "这张图",
    "这个组件",
    "当前图",
    "当前组件",
    "选中的图",
    "选中组件",
    "thischart",
    "thiswidget",
    "selectedchart",
    "selectedwidget",
)


def _normalize(value: str) -> str:
    return _PUNCTUATION.sub("", value).casefold()


def _candidate(widget_id: str, title: str) -> DashboardTargetCandidate:
    return DashboardTargetCandidate(widget_id=widget_id, label=title)


def _target(widget_id: str, title: str) -> DashboardSelectionTarget:
    return DashboardSelectionTarget(
        kind=DashboardSelectionKind.WIDGET,
        widget_id=widget_id,
        label=f"组件：{title}",
        datum_key={},
        row_key={},
    )


def _clarification(
    candidates: Iterable[DashboardTargetCandidate],
    *,
    reason: str,
) -> DashboardTargetResolution:
    items = list(candidates)
    labels = "、".join(f"“{item.label}”" for item in items)
    if labels:
        question = f"我还不能唯一确定目标。你指的是 {labels} 中的哪一个？"
    else:
        question = (
            "我还不能确定你指的是哪一个图表。请点选目标图表，或直接说出图表标题。"
        )
    return DashboardTargetResolution(
        status=DashboardTargetResolutionStatus.NEEDS_CLARIFICATION,
        candidates=items,
        question=question,
        matched_by=reason,
    )


def _resolved(widget_id: str, title: str, matched_by: str) -> DashboardTargetResolution:
    return DashboardTargetResolution(
        status=DashboardTargetResolutionStatus.RESOLVED,
        target=_target(widget_id, title),
        candidates=[_candidate(widget_id, title)],
        matched_by=matched_by,
    )


def _unique_spatial_widget(
    schema: DashboardSchemaV1, direction: str
) -> Tuple[List[str], str]:
    widget_ids = {widget.id for widget in schema.widgets}
    layouts = [item for item in schema.layouts.desktop if item.widget_id in widget_ids]
    if not layouts:
        return [], f"position_{direction}"

    def score(item):
        if direction == "right":
            return item.x + item.w
        if direction == "left":
            return item.x
        if direction == "top":
            return item.y
        return item.y + item.h

    scores = [score(item) for item in layouts]
    best = min(scores) if direction in {"left", "top"} else max(scores)
    return (
        [item.widget_id for item in layouts if score(item) == best],
        f"position_{direction}",
    )


def resolve_dashboard_target(
    schema: DashboardSchemaV1,
    reference: str,
    *,
    selected_widget_id: Optional[str] = None,
) -> DashboardTargetResolution:
    """Resolve one natural reference without guessing between multiple widgets."""

    widgets = list(schema.widgets)
    candidates_by_id: Dict[str, DashboardTargetCandidate] = {
        widget.id: _candidate(widget.id, widget.title) for widget in widgets
    }
    normalized = _normalize(reference)

    # Stable ids and visible titles are the strongest evidence.  Prefer the
    # longest explicit match so "销售趋势" wins over a shorter title "销售".
    explicit_matches: List[Tuple[int, str, str]] = []
    for widget in widgets:
        for value, matched_by in ((widget.id, "widget_id"), (widget.title, "title")):
            token = _normalize(value)
            if token and token in normalized:
                explicit_matches.append((len(token), widget.id, matched_by))
    if explicit_matches:
        longest = max(length for length, _, _ in explicit_matches)
        strongest = [item for item in explicit_matches if item[0] == longest]
        ids = list(dict.fromkeys(widget_id for _, widget_id, _ in strongest))
        if len(ids) == 1:
            widget_id = ids[0]
            widget = candidates_by_id[widget_id]
            matched_by = next(item[2] for item in strongest if item[1] == widget_id)
            return _resolved(widget_id, widget.label, matched_by)
        return _clarification(
            (candidates_by_id[item] for item in ids), reason="ambiguous_explicit"
        )

    for direction, terms in _SPATIAL_TERMS:
        if any(term in normalized for term in terms):
            ids, matched_by = _unique_spatial_widget(schema, direction)
            ids = list(dict.fromkeys(ids))
            if len(ids) == 1:
                widget = candidates_by_id[ids[0]]
                return _resolved(widget.widget_id, widget.label, matched_by)
            return _clarification(
                (candidates_by_id[item] for item in ids), reason=matched_by
            )

    if any(term in normalized for term in _DEICTIC_TERMS):
        selected = candidates_by_id.get(selected_widget_id or "")
        if selected is not None:
            return _resolved(selected.widget_id, selected.label, "current_selection")
        return _clarification(candidates_by_id.values(), reason="missing_selection")

    if len(widgets) == 1:
        widget = widgets[0]
        return _resolved(widget.id, widget.title, "single_widget")

    return _clarification(candidates_by_id.values(), reason="no_unique_match")
