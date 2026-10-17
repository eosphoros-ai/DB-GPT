"""Render selected captured results as charts without querying or recalculating.

Chart choice uses the result's structural types and the report's selected columns,
never business names, metric aliases or conversation-specific rules.
"""

import json
import math
import re
from time import perf_counter
from typing import Any

from dbgpt.core.interface.report_capture import (
    normalize_artifact_result_selector,
    select_artifact_result,
)


def _number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _grouped_columns(artifact, header):
    """A numeric SQL GROUP BY key is a category, not a continuous measure."""
    if artifact.type != "sql":
        return []
    import sqlparse
    from sqlparse.sql import IdentifierList

    fields = {field.casefold(): field for field in header}
    result = []
    for statement in sqlparse.parse(artifact.sql):
        after_group = False
        for token in statement.tokens:
            if token.is_whitespace:
                continue
            if after_group:
                items = (
                    token.get_identifiers()
                    if isinstance(token, IdentifierList)
                    else [token]
                )
                for item in items:
                    name = (
                        item.get_real_name()
                        if hasattr(item, "get_real_name")
                        else str(item).strip('`"')
                    )
                    if name and name.casefold() in fields:
                        result.append(fields[name.casefold()])
                break
            after_group = token.normalized == "GROUP BY"
    return result


def result_table(artifact, selector=None, columns=None, limit=None, offset=0):
    """Read a tabular selection, preserving its real headers and row order."""
    if artifact.status != "succeeded" or artifact.type not in {"sql", "python"}:
        return None
    selector = normalize_artifact_result_selector(artifact, selector or {"path": []})
    data = select_artifact_result(artifact, selector)
    if isinstance(data, str):
        data = json.loads(data)
    header = []
    rows = data
    if isinstance(data, dict):
        header, rows = data.get("columns", data.get("headers", [])), data.get("rows")
    if not isinstance(rows, list) or len(rows) < 2:
        return None
    if not header and all(isinstance(row, dict) for row in rows):
        header = list(dict.fromkeys(key for row in rows for key in row))
    elif not header:
        # A selected rows array still uses its actual parent's captured header.
        path = selector.get("path", [])
        if path and path[-1] == "rows":
            parent = select_artifact_result(artifact, {**selector, "path": path[:-1]})
            header = (
                parent.get("columns", parent.get("headers", []))
                if isinstance(parent, dict)
                else []
            )
    if not header or any(not isinstance(key, str) for key in header):
        return None
    records = []
    for row in rows:
        if isinstance(row, dict):
            records.append(row)
        elif isinstance(row, list) and len(row) == len(header):
            records.append(dict(zip(header, row)))
        else:
            return None
    selected = columns or header
    fields = [
        column if isinstance(column, str) else column["field"] for column in selected
    ]
    if any(field not in header for field in fields):
        return None
    labels = {
        column["field"]: column.get("label") or column["field"]
        for column in selected
        if isinstance(column, dict)
    }
    # Only display a projection of captured rows; do not aggregate or fill gaps.
    records = records[offset : offset + limit if limit is not None else None]
    if len(records) < 2:
        return None
    return {
        "data": data,
        "rows": records,
        "fields": fields,
        "labels": labels,
        "selector": selector,
        "offset": offset,
        "limit": limit,
        "grouped_fields": _grouped_columns(artifact, header),
    }


def table_option(table):
    """Build independent axes for numeric measures with different units."""
    rows, fields = table["rows"], table["fields"]
    numeric = [
        key
        for key in fields
        if any(_number(row.get(key)) for row in rows)
        and all(row.get(key) is None or _number(row.get(key)) for row in rows)
    ]
    dimensions = [
        key
        for key in fields
        if key not in numeric
        and any(isinstance(row.get(key), (str, bool)) for row in rows)
        and all(
            row.get(key) is None or isinstance(row.get(key), (str, bool))
            for row in rows
        )
    ]
    dimensions = list(
        dict.fromkeys(
            [*dimensions, *(key for key in table["grouped_fields"] if key in fields)]
        )
    )
    numeric = [key for key in numeric if key not in dimensions]
    if not numeric:
        return None
    scatter = not dimensions and len(numeric) >= 2
    if not dimensions and not scatter:
        return None  # No meaningful horizontal dimension; don't invent labels.
    temporal = len(dimensions) == 1 and all(
        isinstance(row.get(dimensions[0]), str)
        and re.fullmatch(r"\d{4}-\d{2}(?:-\d{2}(?:[ T].*)?)?", row[dimensions[0]])
        for row in rows
    )
    measures = numeric[1:] if scatter else numeric
    labels = [
        " / ".join("" if row.get(key) is None else str(row[key]) for key in dimensions)
        for row in rows
    ]
    option = {
        "animation": False,
        "tooltip": {"trigger": "item" if scatter else "axis"},
        "grid": [],
        "xAxis": [],
        "yAxis": [],
        "series": [],
        "title": [],
    }
    for index, measure in enumerate(measures):
        label = table["labels"].get(measure, measure)
        top = 40 + index * 245
        option["grid"].append(
            {"top": top, "height": 170, "left": 85, "right": 30, "containLabel": True}
        )
        option["title"].append(
            {"text": label, "top": top - 30, "left": 85, "textStyle": {"fontSize": 13}}
        )
        option["xAxis"].append(
            {
                "type": "value" if scatter else "category",
                "gridIndex": index,
                **(
                    {"name": numeric[0]}
                    if scatter
                    else {
                        "data": labels,
                        "axisLabel": {"rotate": 25, "hideOverlap": True},
                    }
                ),
            }
        )
        option["yAxis"].append({"type": "value", "gridIndex": index})
        values = (
            [[row.get(numeric[0]), row.get(measure)] for row in rows]
            if scatter
            else [row.get(measure) for row in rows]
        )
        option["series"].append(
            {
                "name": label,
                "type": "scatter" if scatter else "line" if temporal else "bar",
                "xAxisIndex": index,
                "yAxisIndex": index,
                "data": values,
            }
        )
    return option


def chart_sources(spec):
    """The report author selects relevant producers; exploration stays excluded."""
    found = {}

    def visit(node, section=None):
        if isinstance(node, dict):
            if node.get("artifact_id"):
                found.setdefault(node["artifact_id"], section)
            for item in (
                node.get("refs", []) if isinstance(node.get("refs"), list) else []
            ):
                found.setdefault(item, section)
            for value in node.values():
                visit(value, section)
        elif isinstance(node, list):
            for value in node:
                visit(value, section)

    visit(spec.get("kpis", []))
    for section in spec.get("sections", []):
        visit(section, section)
    return found


def _has_tabular_result(artifact):
    """Include captured nested Python tables the report can actually select."""
    paths = [[]]
    if artifact.type == "python":
        data = select_artifact_result(artifact, {"path": []})
        if isinstance(data, str):
            data = json.loads(data)

        def visit(value, path):
            if not isinstance(value, dict) or len(path) >= 6 or len(paths) >= 100:
                return
            for key, child in value.items():
                if len(paths) >= 100:
                    break
                if isinstance(child, (dict, list)):
                    child_path = [*path, key]
                    paths.append(child_path)
                    visit(child, child_path)

        visit(data, [])
    for path in paths:
        try:
            table = result_table(artifact, {"path": path})
        except (ValueError, TypeError, OSError):
            continue
        if table and table_option(table):
            return True
    return False


def analysis_groups(artifacts):
    """Use execution-owned task labels, not a hard-coded list of business topics."""
    groups = {}
    for artifact in artifacts:
        name = artifact.metadata.get("agent_name")
        if (
            not name
            or artifact.status != "succeeded"
            or artifact.type not in {"sql", "python"}
        ):
            continue
        try:
            if not _has_tabular_result(artifact):
                continue
        except (ValueError, TypeError, OSError):
            continue
        groups.setdefault(name, []).append(artifact.artifact_id)
    return groups


def missing_analysis_groups(spec, groups):
    """Recommendations alone do not replace the underlying analysis sections."""
    body = {
        **spec,
        "sections": [
            {k: v for k, v in section.items() if k != "recommendations"}
            for section in spec.get("sections", [])
        ],
    }
    selected = set(chart_sources(body))
    return [
        {"analysis": name, "artifact_ids": ids}
        for name, ids in groups.items()
        if not selected.intersection(ids)
    ]


def _table_selections(spec, artifacts):
    """Preserve section, producer and slice identity, including nested tables."""
    by_id = {a.artifact_id: a for a in artifacts}
    scopes = [
        (None, {"kpis": spec.get("kpis", [])}),
        *enumerate(spec.get("sections", [])),
    ]
    for section_index, section in scopes:
        for source_id in chart_sources({"sections": [section]}):
            artifact = by_id.get(source_id)
            if (
                artifact is None
                or artifact.type not in {"sql", "python"}
                or artifact.status != "succeeded"
            ):
                continue
            candidate_groups = []
            authored_table = section.get("table") or {}
            if authored_table.get("artifact_id") == source_id:
                candidate_groups.append([(authored_table, True)])

            def references(node):
                if isinstance(node, dict):
                    if node.get("artifact_id") == source_id and "columns" not in node:
                        selector = {k: node[k] for k in ("field", "path") if k in node}
                        path = selector.get("path", [])
                        candidate_groups.append(
                            [
                                ({**selector, "path": path[:size]}, False)
                                for size in range(len(path), -1, -1)
                            ]
                        )
                    for key, value in node.items():
                        if key != "table" and not (
                            key == "chart"
                            and isinstance(value, dict)
                            and "option" in value
                        ):
                            references(value)
                elif isinstance(node, list):
                    for value in node:
                        references(value)

            references(section)
            if not candidate_groups:
                if "option" in (section.get("chart") or {}):
                    continue
                candidate_groups.append([({}, False)])
            seen = set()
            for candidate_group in candidate_groups:
                for candidate, explicit in candidate_group:
                    selector = {
                        key: candidate[key]
                        for key in ("field", "path")
                        if key in candidate
                    }
                    try:
                        table = result_table(
                            artifact,
                            selector or None,
                            candidate.get("columns"),
                            candidate.get("limit"),
                            candidate.get("offset", 0),
                        )
                        if not table or not table_option(table):
                            continue
                        if not explicit and (table["selector"].get("path") or [])[
                            -1:
                        ] == ["rows"]:
                            parent = {
                                **table["selector"],
                                "path": table["selector"]["path"][:-1],
                            }
                            enclosing = result_table(artifact, parent)
                            if enclosing and table_option(enclosing):
                                table = enclosing
                        identity = json.dumps(
                            [
                                source_id,
                                table["selector"],
                                table["fields"],
                                table["offset"],
                                table["limit"],
                            ],
                            sort_keys=True,
                        )
                        if identity not in seen:
                            seen.add(identity)
                            yield section_index, artifact, table, identity
                        # Don't broaden a selected nested slice to unrelated ancestors.
                        if not explicit:
                            break
                    except (ValueError, TypeError, OSError, KeyError):
                        continue


def _chart_covers(artifact, source, table):
    if (
        artifact.type != "chart"
        or artifact.status != "succeeded"
        or artifact.chart_type == "response_table"
    ):
        return False
    if artifact.spec.get("option") is not None:
        if artifact.spec.get("authored_option"):
            return any(
                reference["artifact_id"] == source.artifact_id
                and {
                    key: reference[key] for key in ("field", "path") if key in reference
                }
                == table["selector"]
                for reference in artifact.spec["source_references"]
            )
        return (
            artifact.spec.get("source_artifact_id") == source.artifact_id
            and artifact.spec.get("source_selector") == table["selector"]
            and artifact.spec.get("projection")
            == {
                "fields": table["fields"],
                "offset": table["offset"],
                "limit": table["limit"],
            }
        )
    # A chart of another producer's inputs need not visualize every input.
    return source.artifact_id in artifact.input_artifact_ids


def prepare_report_charts(spec: Any, artifacts, sink):
    """Add executable, immutable charts for selected tabular evidence."""
    if (
        sink is None
        or not isinstance(spec, dict)
        or not isinstance(spec.get("sections"), list)
    ):
        return spec
    from .report_chart_options import prepare_option_charts, prepared_chart_id

    spec = prepare_option_charts(spec, artifacts, sink)
    artifacts = list(sink.snapshot())
    sections = [dict(section) for section in spec["sections"]]
    by_id = {a.artifact_id: a for a in artifacts}
    additions, prepared = [], {}
    for section_index, artifact, table, identity in _table_selections(spec, artifacts):
        section = sections[section_index] if section_index is not None else None
        current = (section or {}).get("chart") or {}
        if any(
            _chart_covers(by_id[ref], artifact, table)
            for ref in current.get("refs", [])
            if ref in by_id
        ):
            continue
        if identity in prepared:
            if section is not None and current.get("refs") == [artifact.artifact_id]:
                section["chart"] = prepared[identity]
            continue
        started = perf_counter()
        option = table_option(table)
        title = (
            artifact.metadata.get("agent_name")
            or (section or {}).get("heading")
            or artifact.name
            or "分析图表"
        )
        chart_spec = {
            "renderer": "echarts",
            "source_artifact_id": artifact.artifact_id,
            "source_selector": table["selector"],
            "data": table["data"],
            "option": option,
            "height": max(320, 245 * len(option["series"]) + 35),
            "projection": {
                "fields": table["fields"],
                "offset": table["offset"],
                "limit": table["limit"],
            },
        }
        chart_id = prepared_chart_id(
            sink, chart_spec, [artifact.artifact_id], title, started
        )
        node = {"refs": [artifact.artifact_id, chart_id], "caption": title}
        if section is not None and (
            not current or current.get("refs") == [artifact.artifact_id]
        ):
            section["chart"] = node
        else:
            additions.append({"heading": title + " · 数据图表", "chart": node})
        prepared[identity] = node
    return {**spec, "sections": [*sections, *additions]}


def selected_chart_gaps(spec, artifacts, html):
    """A saved presentation must not bypass preparation on a later invocation."""
    from .report_binding import iter_binding_tags, parse_binding

    bound_ids = set()
    for match in iter_binding_tags(html):
        binding = parse_binding(match)
        if binding["attributes"].get("data-dbgpt-chart-id") or match.groupdict().get(
            "tag", ""
        ).lower() in {"figure", "img", "svg", "canvas"}:
            bound_ids.update(binding["artifact_ids"])
    displayed = [
        a for a in artifacts if a.type == "chart" and a.artifact_id in bound_ids
    ]
    from .report_chart_options import option_chart_spec

    for section in spec.get("sections", []):
        node = section.get("chart") or {}
        if isinstance(node.get("option"), dict):
            try:
                expected = option_chart_spec(node, artifacts)
            except (ValueError, TypeError, OSError, KeyError):
                return True
            if not any(chart.spec == expected for chart in displayed):
                return True
    return any(
        not any(_chart_covers(chart, source, table) for chart in displayed)
        for _, source, table, _ in _table_selections(spec, artifacts)
    )
