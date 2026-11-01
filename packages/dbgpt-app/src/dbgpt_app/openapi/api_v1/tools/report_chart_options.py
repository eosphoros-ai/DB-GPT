"""Prepare arbitrary JSON ECharts options using exact captured result references.

There is no series-type whitelist. Presentation options are author-controlled;
data containers are resolved from immutable SQL/Python outputs, never guessed.
"""

import json
import re
from time import perf_counter

from dbgpt.core.interface.report_capture import (
    capture_chart_execution,
    normalize_artifact_result_selector,
    select_artifact_result,
)


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

    def resolve(value, data=False, path=()):
        if isinstance(value, dict):
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
                return read(value)[0]
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
            return [resolve(item, data, path) for item in value]
        if data and value is not None:
            raise ValueError(
                (
                    "REPORT_CHART_OPTION_INVALID: data containers must use captured "
                    "result references; select an existing result or capture the "
                    "missing calculation"
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

    def configurations(value):
        yield value
        if isinstance(value.get("baseOption"), dict):
            yield from configurations(value["baseOption"])
        for frame in value.get("options", []):
            if isinstance(frame, dict):
                yield from configurations(frame)
        for media in value.get("media", []):
            if isinstance(media, dict) and isinstance(media.get("option"), dict):
                yield from configurations(media["option"])

    configurations_with_series = []
    for configuration in configurations(option):
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
            chart_spec = option_chart_spec(node, artifacts)
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
