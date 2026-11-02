"""Prepare arbitrary JSON ECharts options using exact captured result references.

There is no series-type whitelist. Presentation options are author-controlled;
data containers are resolved from immutable SQL/Python outputs, never guessed.
"""

import json
import logging
import re
from time import perf_counter

from dbgpt.core.interface.report_capture import (
    capture_chart_execution,
    normalize_artifact_result_selector,
    select_artifact_result,
)

logger = logging.getLogger(__name__)


def _validate_chart_data_shapes(option):
    """Reject resolved row objects where ECharts expects axis/scalar values."""
    for configuration in _option_configurations(option):
        for axis_name in ("xAxis", "yAxis"):
            axes = configuration.get(axis_name, [])
            axes = axes if isinstance(axes, list) else [axes]
            for axis in axes:
                if not isinstance(axis, dict):
                    continue
                values = axis.get("data")
                if isinstance(values, list) and any(
                    isinstance(value, dict)
                    and (
                        "value" not in value or isinstance(value["value"], (dict, list))
                    )
                    for value in values
                ):
                    raise ValueError(
                        "REPORT_CHART_DATA_SHAPE_INVALID: "
                        f"{axis_name}.data contains full result rows; select one "
                        "category field or use dataset with series.encode"
                    )
        series = configuration.get("series", [])
        series = series if isinstance(series, list) else [series]
        for item in series:
            if not isinstance(item, dict) or item.get("type") not in {
                "line",
                "bar",
                "scatter",
                "effectScatter",
                "pie",
                "funnel",
                "pictorialBar",
                "heatmap",
                "boxplot",
                "candlestick",
            }:
                continue
            values = item.get("data")
            if isinstance(values, list) and any(
                isinstance(value, dict) and "value" not in value for value in values
            ):
                raise ValueError(
                    "REPORT_CHART_DATA_SHAPE_INVALID: series.data contains full "
                    "result rows; select the numeric field or use dataset with "
                    "series.encode"
                )


def _option_configurations(value):
    yield value
    if isinstance(value.get("baseOption"), dict):
        yield from _option_configurations(value["baseOption"])
    for frame in value.get("options", []):
        if isinstance(frame, dict):
            yield from _option_configurations(frame)
    for media in value.get("media", []):
        if isinstance(media, dict) and isinstance(media.get("option"), dict):
            yield from _option_configurations(media["option"])


def option_chart_spec(node, artifacts):
    by_id = {artifact.artifact_id: artifact for artifact in artifacts}
    references = []

    def read(reference):
        identifier = reference.get("artifact_id")
        artifact = by_id.get(identifier)
        if (
            artifact is None
            or artifact.status != "succeeded"
            or artifact.type not in {"sql", "python"}
        ):
            raise ValueError(
                (
                    "REPORT_CHART_OPTION_INVALID: unknown or unsuccessful SQL/Python "
                    "source "
                    f"{identifier}"
                )
            )
        selector = normalize_artifact_result_selector(
            artifact,
            {key: reference[key] for key in ("field", "path") if key in reference}
            or {"path": []},
        )
        value = select_artifact_result(artifact, selector)
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except ValueError:
                pass
        selected = {"artifact_id": identifier, **selector}
        if selected not in references:
            references.append(selected)
        return value, selected

    def read_chart_data(reference, path):
        resolved = read(reference)[0]
        if (
            path[-2:] == ("dataset", "source")
            and isinstance(resolved, dict)
            and isinstance(resolved.get("rows"), list)
        ):
            reference = {
                **reference,
                "path": [*(reference.get("path") or []), "rows"],
            }
            resolved = read(reference)[0]
        return resolved

    def resolve(value, data=False, path=()):
        if isinstance(value, dict):
            if data and "$ref" in value:
                if set(value) - {"$ref", "field", "path"} or not isinstance(
                    value["$ref"], str
                ):
                    raise ValueError(
                        "REPORT_CHART_OPTION_INVALID: invalid $ref reference"
                    )
                producer = node.get("producer") or {}
                ref_text = value["$ref"]
                base_name = producer.get("field")
                if not base_name and producer.get("path"):
                    base_name = producer["path"][-1]
                if (
                    isinstance(base_name, str)
                    and ref_text.startswith(base_name + ".")
                    and len(value) == 1
                ):
                    components = ref_text[len(base_name) + 1 :].split(".")
                    if any(
                        not part or not part.replace("_", "a").isalnum()
                        for part in components
                    ):
                        raise ValueError(
                            "REPORT_CHART_OPTION_INVALID: invalid relative result path"
                        )
                    reference = {
                        key: producer[key]
                        for key in ("artifact_id", "field", "path")
                        if key in producer
                    }
                    current = read(reference)[0]
                    selected_path = list(reference.get("path") or [])
                    for index, component in enumerate(components):
                        if isinstance(current, list) and not component.isdecimal():
                            if index != len(components) - 1 or len(current) > 5000:
                                raise ValueError(
                                    "REPORT_CHART_OPTION_INVALID: unsupported or "
                                    "oversized column projection"
                                )
                            values = []
                            for row_index, row in enumerate(current):
                                if not isinstance(row, dict) or component not in row:
                                    raise ValueError(
                                        "REPORT_CHART_OPTION_INVALID: projection "
                                        "field missing from captured rows"
                                    )
                                selected = {
                                    **reference,
                                    "path": [*selected_path, row_index, component],
                                }
                                values.append(read(selected)[0])
                            return values
                        key = (
                            int(component)
                            if isinstance(current, list) and component.isdecimal()
                            else component
                        )
                        selected_path.append(key)
                        current = read({**reference, "path": selected_path.copy()})[0]
                    return current
                if value["$ref"] == "producer":
                    if not producer.get("artifact_id") or len(value) != 1:
                        raise ValueError(
                            "REPORT_CHART_OPTION_INVALID: $ref producer requires "
                            "an explicit producer and cannot override its selector"
                        )
                    reference = {
                        key: producer[key]
                        for key in ("artifact_id", "field", "path")
                        if key in producer
                    }
                else:
                    reference = {"artifact_id": value["$ref"]}
                    reference.update(
                        {key: value[key] for key in ("field", "path") if key in value}
                    )
                if (
                    len(reference) == 1
                    and producer.get("artifact_id") == reference["artifact_id"]
                ):
                    reference.update(
                        {
                            key: producer[key]
                            for key in ("field", "path")
                            if key in producer
                        }
                    )
                return read_chart_data(reference, path)
            if "artifact_id" in value:
                if set(value) - {"artifact_id", "field", "path"}:
                    raise ValueError(
                        (
                            "REPORT_CHART_OPTION_INVALID: chart data references "
                            "accept only "
                            "artifact_id, field and "
                            "path"
                        )
                    )
                return read_chart_data(value, path)
            return {
                key: resolve(
                    item,
                    data
                    or ("series" in path and key in {"data", "nodes", "links", "edges"})
                    or ("dataset" in path and key == "source")
                    or (
                        key == "data"
                        and any(
                            part.endswith("Axis") or part == "timeline" for part in path
                        )
                    ),
                    (*path, key),
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            # Models often repeat a captured column as literals. Recover its
            # provenance only when the entire ordered column matches uniquely.
            producer = node.get("producer") or {}
            if (
                data
                and value
                and producer.get("artifact_id")
                and all(
                    isinstance(item, (str, int, float)) and not isinstance(item, bool)
                    for item in value
                )
            ):
                source = read(producer)[0]
                base_path = list(producer.get("path") or [])
                if isinstance(source, dict) and isinstance(source.get("rows"), list):
                    source = source["rows"]
                    base_path.append("rows")
                if (
                    isinstance(source, list)
                    and len(source) == len(value)
                    and len(source) <= 5000
                    and all(isinstance(row, dict) for row in source)
                ):
                    matches = [
                        key
                        for key in source[0]
                        if all(key in row for row in source)
                        and [row[key] for row in source] == value
                    ]
                    if len(matches) == 1:
                        return [
                            read({**producer, "path": [*base_path, index, matches[0]]})[
                                0
                            ]
                            for index in range(len(source))
                        ]
            return [
                resolve(item, data, (*path, str(index)))
                for index, item in enumerate(value)
            ]
        if data and value is not None:
            raise ValueError(
                (
                    "REPORT_CHART_OPTION_INVALID: data containers must use captured "
                    "result references; select an existing result or capture the "
                    "missing calculation; invalid option path: "
                    f"{'.'.join(path)}; replace the entire data array with a "
                    "captured result reference, or use dataset and encode. "
                    "Do not repeat literal category labels."
                )
            )
        return value

    primary = node.get("producer")
    if not primary:
        primary = next(
            (
                {"artifact_id": identifier}
                for identifier in node.get("refs", [])
                if identifier in by_id and by_id[identifier].type in {"sql", "python"}
            ),
            None,
        )
    # Resolve references before selecting a primary source; option-only charts
    # can therefore omit refs and producer entirely.
    option = resolve(node["option"])
    if primary is None and references:
        primary = references[0]
    if primary is None:
        raise ValueError(
            (
                "REPORT_CHART_OPTION_INVALID: an option needs at least one "
                "captured SQL/Python "
                "source"
            )
        )
    dataset, primary = read(primary)

    configurations_with_series = []
    for configuration in _option_configurations(option):
        series = configuration.get("series")
        series = [series] if isinstance(series, dict) else series
        if series is None:
            continue
        if not isinstance(series, list) or any(
            not isinstance(item, dict) for item in series
        ):
            raise ValueError(
                (
                    "REPORT_CHART_OPTION_INVALID: series must contain ECharts series "
                    "objects"
                )
            )
        configurations_with_series.append((configuration, series))
    # Timeline/media frames may override part of a base series without type.
    if not any(
        isinstance(item.get("type"), str)
        for _, series in configurations_with_series
        for item in series
    ):
        raise ValueError(
            (
                "REPORT_CHART_OPTION_INVALID: series must contain ECharts series "
                "objects with "
                "type"
            )
        )
    # ECharts dataset/encode is the general entry point for tabular producers.
    # Explicit data/nodes/links are retained exactly for non-tabular charts.
    for configuration, series in configurations_with_series:
        if "dataset" in configuration or not any(
            "type" in item and "data" not in item and "nodes" not in item
            for item in series
        ):
            continue
        if isinstance(dataset, dict) and isinstance(dataset.get("rows"), list):
            configuration["dataset"] = {"source": dataset["rows"]}
            if dataset.get("columns"):
                configuration["dataset"]["dimensions"] = dataset["columns"]
        elif isinstance(dataset, list):
            configuration["dataset"] = {"source": dataset}
        else:
            raise ValueError(
                (
                    "REPORT_CHART_OPTION_INVALID: supply exact data references for a "
                    "non-tabular "
                    "producer"
                )
            )
    _validate_chart_data_shapes(option)
    maps = {}
    for name, reference in (node.get("maps") or {}).items():
        geojson, _ = read(reference)
        if (
            not isinstance(geojson, dict)
            or geojson.get("type") != "FeatureCollection"
            or not isinstance(geojson.get("features"), list)
        ):
            raise ValueError(
                (
                    "REPORT_CHART_OPTION_INVALID: maps must select captured GeoJSON "
                    "FeatureCollection "
                    "results"
                )
            )
        maps[name] = geojson
    # Reject non-JSON values (including NaN), without evaluating callbacks/code.
    json.dumps([option, maps], allow_nan=False)
    selectors = {
        reference["artifact_id"]: {
            key: reference[key] for key in ("field", "path") if key in reference
        }
        for reference in references
    }
    selectors[primary["artifact_id"]] = {
        key: primary[key] for key in ("field", "path") if key in primary
    }
    return {
        "renderer": "echarts",
        "source_artifact_id": primary["artifact_id"],
        "source_selector": {
            key: primary[key] for key in ("field", "path") if key in primary
        },
        "source_references": references,
        "source_selectors": selectors,
        "data": dataset,
        "option": option,
        "maps": maps,
        "height": node.get("height", 420),
        "authored_option": True,
    }


def prepared_chart_id(sink, spec, source_ids, title, started):
    """Reuse an immutable prepared chart, or capture it once through the core."""
    existing = next(
        (
            item
            for item in sink.snapshot()
            if item.type == "chart" and item.status == "succeeded" and item.spec == spec
        ),
        None,
    )
    if existing:
        return existing.artifact_id
    identifier = capture_chart_execution(
        input_artifact_ids=source_ids,
        chart_type="echarts",
        spec=spec,
        output_inline=spec,
        action="report_chart.prepare",
        name=title,
        duration_ms=max(0, int((perf_counter() - started) * 1000)),
        artifact_sink=sink,
    )
    if not identifier:
        raise ValueError("REPORT_CHART_CAPTURE_FAILED: " + ", ".join(source_ids))
    return identifier


def prepare_option_charts(spec, artifacts, sink):
    sections = []
    for section in spec["sections"]:
        section = dict(section)
        node = section.get("chart") or {}
        if isinstance(node.get("option"), dict):
            started = perf_counter()
            try:
                chart_spec = option_chart_spec(node, artifacts)
            except ValueError as error:
                if not (
                    str(error).startswith("REPORT_CHART_DATA_SHAPE_INVALID:")
                    and section.get("table")
                ):
                    raise
                logger.warning(
                    "Invalid authored chart data; using the captured section table: %s",
                    error,
                )
                section.pop("chart", None)
                sections.append(section)
                continue
            source_ids = list(
                dict.fromkeys(
                    ref["artifact_id"] for ref in chart_spec["source_references"]
                )
            )
            title = node.get("caption") or section.get("heading") or "分析图表"
            chart_id = prepared_chart_id(sink, chart_spec, source_ids, title, started)
            section["chart"] = {"refs": [*source_ids, chart_id], "caption": title}
        sections.append(section)
    return {**spec, "sections": sections}


# Reviewed renderer shared by placeholder-based skill templates. Chart data
# remains JSON in escaped attributes, never interpolated into executable code.
EXTRA_CHART_TEMPLATE = """
<section class="report-extra-charts">
{% for section in sections %}{% set c = section.chart %}
{% if c %}<figure data-dbgpt-artifacts="{{ c.refs|join(',') }}" data-dbgpt-evidence-label="{{ c.get('caption', '') }}">
{% if c.get('img') %}<img src="{{ c.img }}" alt="{{ c.get('caption', '') }}">
{% elif c.get('renderer') == 'echarts' %}
<div style="height:{{ c.get('height', 420) }}px" id="{{ c.host_id }}" data-dbgpt-extra-chart="true"
data-dbgpt-chart-renderer="echarts" data-dbgpt-chart-id="{{ c.chart_id }}"
data-dbgpt-artifacts="{{ c.refs|join(',') }}"
data-dbgpt-artifact-selectors='{{ (c.get('source_selectors') or c.producer.selectors)|tojson }}'
data-dbgpt-chart-option='{{ c.option|tojson }}' data-dbgpt-chart-maps='{{ c.get('maps', {})|tojson }}'></div>
{% endif %}<figcaption>{{ c.get('caption', '') }}</figcaption></figure>{% endif %}
{% endfor %}
</section>
<script>
(function() {
    function draw() {
        document.querySelectorAll('[data-dbgpt-extra-chart]').forEach(function(host) {
            try {
                const maps = JSON.parse(host.getAttribute('data-dbgpt-chart-maps') || '{}');
                Object.entries(maps).forEach(function(entry) { echarts.registerMap(entry[0], entry[1]); });
                const chart = echarts.init(host);
                chart.setOption(JSON.parse(host.getAttribute('data-dbgpt-chart-option')));
                window.addEventListener('resize', function() { chart.resize(); });
            } catch (error) {
                host.setAttribute('data-dbgpt-chart-error', String(error.message || error));
                host.textContent = '图表绘制失败：' + (error.message || error);
                console.error(error);
            }
        });
    }
    if (window.echarts) draw();
    else {
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js';
        script.onload = draw;
        script.onerror = function() {
            document.querySelectorAll('[data-dbgpt-extra-chart]').forEach(function(host) {
                host.setAttribute('data-dbgpt-chart-error', 'ECharts load failed');
                host.textContent = '图表绘制失败：ECharts 加载失败';
            });
        };
        document.head.appendChild(script);
    }
})();
</script>
"""  # noqa: E501


def append_extra_charts(html, sections):
    from jinja2 import StrictUndefined
    from jinja2.sandbox import SandboxedEnvironment

    environment = SandboxedEnvironment(autoescape=True, undefined=StrictUndefined)
    environment.globals.clear()
    fragment = environment.from_string(EXTRA_CHART_TEMPLATE).render(sections=sections)
    closing = re.search(r"</body\s*>", html, re.I)
    return (
        html[: closing.start()] + fragment + html[closing.start() :]
        if closing
        else html + fragment
    )
