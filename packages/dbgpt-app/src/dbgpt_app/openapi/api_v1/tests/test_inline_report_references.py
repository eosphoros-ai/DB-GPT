"""Visible reference literals must render captured values, never dictionary reprs."""

import inspect
import json
from html import escape
from types import SimpleNamespace

import pytest

from dbgpt.core.interface.report_capture import (
    ArtifactCaptureContext,
    InMemoryArtifactSink,
    capture_python_execution,
)
from dbgpt_app.openapi.api_v1.tools.html_interpreter import (
    _bind_generated_chart_images,
    _render_placeholder_parts,
    _resolve_inline_report_references,
    _resolve_template_references,
    make_html_interpreter,
    report_template_contract,
)


def test_english_month_year_is_a_date_not_a_metric():
    from dbgpt_app.openapi.api_v1.tools.report_binding import is_document_number

    assert is_document_number("2017", " - Aug 2018", "Jan ", None)
    assert is_document_number("2018", "", "Jan 2017 - Aug ", None)
    assert not is_document_number("2017", " orders", "Total ", None)


@pytest.mark.parametrize(
    "value,prefix,suffix",
    [
        ("0", "无评价为空，不可当作 ", " 分"),
        ("0", "无评价记录为空值，不按 ", " 分处理"),
        ("0", "缺失评分不能将其当成 ", " 分"),
        ("0", "无评价不计为 ", " 分"),
        ("0", "Holiday_Flag 为 ", "/1 标记"),
        ("1", "Holiday_Flag 为 0/", " 标记"),
        ("1", "Holiday_Flag 为 ", " 的记录共"),
        ("1", "节假日标记为 ", " 的记录共"),
        ("1", "on_time 定义：实际送达不晚于预计送达为 ", "，逾期为 0；"),
        ("0", "on_time 定义：实际送达不晚于预计送达为 1，逾期为 ", "；"),
        ("0", "无评价订单为空值而非 ", " 分"),
        ("10", "截至 ", " 月"),
        ("12", "", " 月为高峰"),
        ("20", "门店 ", "、门店"),
        ("33", "Store ", " is a category"),
        ("10", "销售额排名前 ", " 的门店"),
    ],
)
def test_report_definition_numbers_are_not_measured_values(value, prefix, suffix):
    from dbgpt_app.openapi.api_v1.tools.report_binding import is_document_number

    assert is_document_number(value, suffix, prefix, None)


@pytest.mark.parametrize(
    "value,prefix,suffix",
    [
        ("0", "评分为 ", " 分"),
        ("0", "缺失评分按 ", " 分统计"),
        ("20", "门店 ", " 家"),
        ("20", "门店收入为 ", " 万元"),
        ("1", "Holiday_Flag 为 ", "%"),
        ("1", "节假日标记为 ", "%"),
        ("13", "截至 ", " 月"),
        ("999", "收入 ", " 元"),
    ],
)
def test_observed_numbers_still_need_evidence(value, prefix, suffix):
    from dbgpt_app.openapi.api_v1.tools.report_binding import is_document_number

    assert not is_document_number(value, suffix, prefix, None)


def test_explicit_english_recommendation_count_is_recognized():
    from dbgpt_app.openapi.api_v1.agentic_data_api import (
        _requested_recommendation_count,
    )

    assert _requested_recommendation_count("report with three recommendations") == 3
    assert (
        _requested_recommendation_count("give 3 highest-priority recommendations") == 3
    )
    assert _requested_recommendation_count("please give recommendations") is None


@pytest.mark.parametrize(
    "body",
    [
        "<p>建议一：复核成本。</p>" * 3,
        "<p>建议一：</p><p>建议二： </p><p>建议三：</p>",
        "<p>收入增长。</p><p>负债较高。</p><p>行业数据缺失。</p>",
        "<p>建议一：复核成本。</p><p>建议二：跟踪回款。</p>",
    ],
)
def test_recommendation_paragraphs_still_require_distinct_nonempty_actions(body):
    from dbgpt_app.openapi.api_v1.tools.html_interpreter import (
        _validate_recommendation_requirement,
    )

    assert _validate_recommendation_requirement("<h2>结论与建议</h2>" + body, 3)


def test_labelled_advice_outside_recommendation_section_does_not_count():
    from dbgpt_app.openapi.api_v1.tools.html_interpreter import (
        _validate_recommendation_requirement,
    )

    html = (
        "<h2>数据口径</h2><p>建议一：复核成本。</p><p>建议二：跟踪回款。</p>"
        "<p>建议三：复核融资期限。</p><h2>结论与建议</h2><p>继续观察。</p>"
    )
    assert _validate_recommendation_requirement(html, 3)


def test_financial_template_marks_missing_charts_without_empty_image_hosts():
    from pathlib import Path

    from dbgpt_app.openapi.api_v1.tools.html_interpreter import (
        _render_template_with_bindings,
    )

    root = next(p for p in Path(__file__).resolve().parents if (p / "skills").is_dir())
    template = (
        root / "skills/financial-report-analyzer/templates/report_template.html"
    ).read_text(encoding="utf-8")
    contract = report_template_contract(template)
    html = _render_template_with_bindings(
        template,
        {field: "定性分析，缺失数据不作推断。" for field in contract["prose_fields"]},
        [],
    )
    assert '<img src=""' not in html
    assert 'class="chart-container"' not in html
    assert all(
        label in html
        for label in [
            "核心财务指标对比图未生成",
            "盈利能力指标图未生成",
            "资产结构图未生成",
        ]
    )
    assert "现金流与利润质量" in html and "营运效率分析" in html


def test_stdout_only_python_is_not_advertised_as_a_result_producer():
    from dbgpt_app.openapi.api_v1.tools.report_evidence import result_evidence_catalog

    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="stdout-only"))
    identifier = capture_python_execution(
        code="print(60.19)",
        duration_ms=1,
        status="succeeded",
        exit_code=0,
        stdout="gmv growth % 60.19",
        stderr="",
        artifact_sink=sink,
    )
    assert identifier
    assert result_evidence_catalog(sink.snapshot()) == []


def test_chart_host_accepts_duplicate_identical_capture_only():
    def chart(identifier, digest):
        return SimpleNamespace(
            artifact_id=identifier,
            type="chart",
            status="succeeded",
            output=SimpleNamespace(uri="/images/chart.png", sha256=digest),
            input_artifact_ids=[],
        )

    html = '<div class="chart-container"><img src="/images/chart.png"></div>'
    result = _bind_generated_chart_images(
        html, [chart("chart-1", "abc"), chart("chart-2", "abc")]
    )
    assert result.count('data-dbgpt-artifacts="chart-1"') == 2
    assert (
        _bind_generated_chart_images(
            html, [chart("chart-1", "abc"), chart("chart-2", "def")]
        )
        == html
    )


@pytest.fixture
def captured_reference():
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="inline-reference"))
    identifier = capture_python_execution(
        code="REPORT_RESULT = {'CHART_DATA_JSON': {'overview': {'rows': 6435}}}",
        duration_ms=1,
        status="succeeded",
        exit_code=0,
        stdout="",
        stderr="",
        result_inline={"CHART_DATA_JSON": {"overview": {"rows": 6435}}},
        artifact_sink=sink,
    )
    return (
        {
            "artifact_id": identifier,
            "field": "CHART_DATA_JSON",
            "path": ["overview", "rows"],
            "format": "number",
        },
        sink.snapshot(),
    )


def test_mixed_inline_reference_accepts_quoted_and_empty_paths(captured_reference):
    node, artifacts = captured_reference
    identifier = node["artifact_id"]
    mixed = (
        f'{{artifact_id:"{identifier}",field:"CHART_DATA_JSON",'
        'path:["overview","rows"]}'
    )
    result = _resolve_inline_report_references(mixed, artifacts)
    assert "6,435" in result and identifier in result
    empty = f'{{artifact_id:"{identifier}",field:"CHART_DATA_JSON",path:[]}}'
    assert identifier in _resolve_inline_report_references(empty, artifacts)


def test_mixed_reference_accepts_quoted_special_character_keys():
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="special-key"))
    identifier = capture_python_execution(
        code="metrics",
        duration_ms=1,
        status="succeeded",
        exit_code=0,
        stdout="",
        stderr="",
        result_inline={"kpi": {"字段完整率%": 85.88}},
        artifact_sink=sink,
    )
    content = f'{{artifact_id:"{identifier}",field:"kpi",path:["字段完整率%"]}}'
    assert "85.88" in _resolve_inline_report_references(content, sink.snapshot())
    with pytest.raises(ValueError):
        _resolve_inline_report_references(
            content.replace("字段完整率%", "不存在%"), sink.snapshot()
        )


def test_inline_metric_id_resolves_from_session_catalog(captured_reference):
    node, artifacts = captured_reference
    metrics = {
        "metric-1": {
            "artifact_id": node["artifact_id"],
            "selector": {"field": node["field"], "path": node["path"]},
        }
    }
    result = _resolve_inline_report_references(
        '<b>{"metric_id":"metric-1"}</b>', artifacts, metrics
    )
    assert "6,435" in result and node["artifact_id"] in result
    with pytest.raises(ValueError, match="unknown metric_id"):
        _resolve_inline_report_references('{"metric_id":"missing"}', artifacts, metrics)


@pytest.mark.parametrize("syntax", ["python", "json", "unquoted"])
@pytest.mark.parametrize("encoded", [False, True])
def test_inline_reference_displays_real_value_and_keeps_binding(
    captured_reference, syntax, encoded
):
    node, artifacts = captured_reference
    if syntax == "python":
        literal = repr(node)
    elif syntax == "json":
        literal = json.dumps(node)
    else:
        literal = (
            "{artifact_id: "
            + node["artifact_id"]
            + ", field: CHART_DATA_JSON, path: overview.rows, format: number}"
        )
    if encoded:
        literal = escape(literal)
    html = "<p>本报告基于 <strong>" + literal + "</strong> 条记录。</p>"
    result = _resolve_inline_report_references(html, artifacts)
    assert "6,435" in result
    assert "{'artifact_id'" not in result
    assert "{&quot;artifact_id" not in result
    assert 'data-dbgpt-artifacts="' + node["artifact_id"] + '"' in result
    assert "overview" in result and "rows" in result


@pytest.mark.parametrize("tag", ["script", "style", "code", "pre"])
def test_inline_reference_does_not_rewrite_examples_or_attributes(
    captured_reference, tag
):
    node, artifacts = captured_reference
    literal = repr(node)
    html = (
        '<div title="' + literal + '"><' + tag + ">" + literal + "</" + tag + "></div>"
    )
    assert _resolve_inline_report_references(html, artifacts) == html


def test_invalid_single_quoted_reference_is_rejected(captured_reference):
    node, artifacts = captured_reference
    node["path"] = ["overview", "missing"]
    with pytest.raises(ValueError, match="REPORT_TEMPLATE_REFERENCE_INVALID"):
        _resolve_inline_report_references("<p>" + repr(node) + "</p>", artifacts)


def test_incomplete_single_quoted_reference_is_rejected(captured_reference):
    node, artifacts = captured_reference
    with pytest.raises(ValueError, match="incomplete inline reference"):
        _resolve_inline_report_references("<p>" + repr(node)[:-1] + "</p>", artifacts)


def test_placeholder_singular_ref_keeps_exact_value_and_binding(captured_reference):
    node, artifacts = captured_reference
    resolved = _resolve_template_references(
        {"text": "记录总数：", "ref": node}, artifacts
    )
    html = _render_placeholder_parts(resolved)
    assert "记录总数：" in html and "6,435" in html
    assert node["artifact_id"] in html and "overview" in html


def test_placeholder_rejects_ambiguous_or_unresolved_ref(captured_reference):
    node, artifacts = captured_reference
    resolved = _resolve_template_references(node, artifacts)
    with pytest.raises(ValueError, match="either ref or refs"):
        _render_placeholder_parts({"text": "值", "ref": resolved, "refs": [resolved]})
    with pytest.raises(ValueError, match="REPORT_TEMPLATE_PROSE_INVALID"):
        _render_placeholder_parts({"text": "值", "ref": {"value": "99"}})


def test_unquoted_bracket_path_resolves_mapping_keys_and_list_indices():
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="inline-path"))
    identifier = capture_python_execution(
        code="result = 42",
        duration_ms=1,
        status="succeeded",
        exit_code=0,
        stdout="",
        stderr="",
        result_inline={"history": {"2019": {"values": [42]}}},
        artifact_sink=sink,
    )
    html = f"<p>{{artifact_id:{identifier},field:history,path:[2019,values,0]}}</p>"
    result = _resolve_inline_report_references(html, sink.snapshot())
    assert ">42</span>" in result
    assert 'data-dbgpt-artifacts="' + identifier + '"' in result


def test_declared_required_prose_rejects_captured_na():
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="missing-prose"))
    capture_python_execution(
        code="result = None",
        duration_ms=1,
        status="succeeded",
        exit_code=0,
        stdout="",
        stderr="",
        result_inline={"ANALYSIS": "N/A"},
        artifact_sink=sink,
    )
    template = "<!-- dbgpt-required: ANALYSIS --><p>{{ANALYSIS}}</p>"
    assert report_template_contract(template)["prose_fields"] == ["ANALYSIS"]
    from dbgpt_app.openapi.api_v1.tools.html_interpreter import (
        _render_template_with_bindings,
    )

    with pytest.raises(ValueError, match="REPORT_REQUIREMENT_MISSING.*ANALYSIS"):
        _render_template_with_bindings(template, {}, sink.snapshot())


@pytest.mark.asyncio
@pytest.mark.parametrize("shape", ["literal", "paragraph_list", "paragraph"])
async def test_template_report_resolves_python_literal_before_source_validation(
    captured_reference, tmp_path, monkeypatch, shape
):
    from dbgpt_app.openapi.api_v1.tools import report_repair

    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    node, artifacts = captured_reference
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="inline-reference"))
    for artifact in artifacts:
        sink.record(artifact)
    template = tmp_path / "skills" / "example" / "report.html"
    template.parent.mkdir(parents=True)
    template.write_text(
        "<!DOCTYPE html><html><head><title>报告</title></head>"
        "<body><p>{{SUMMARY}}</p></body></html>",
        encoding="utf-8",
    )
    state = {"conv_id": "inline-reference", "_report_artifact_sink": sink}
    renderer = inspect.unwrap(make_html_interpreter(state, str(tmp_path / "skills")))
    summary = (
        '记录总数：<strong data-dbgpt-artifacts="'
        + node["artifact_id"]
        + '">'
        + repr(node)
        + "</strong>"
    )
    if shape != "literal":
        summary = {"type": "p", "text": "记录总数：", "refs": [node]}
        if shape == "paragraph_list":
            summary = [summary, {"type": "p", "text": "记录已核验。"}]
    response = json.loads(
        await renderer(
            title="数据报告",
            template_path="example/report.html",
            data={"SUMMARY": summary},
        )
    )
    assert not state.get("_report_html_error"), response
    assert any(chunk["output_type"] == "html" for chunk in response["chunks"])
    html = state["_report_presentation"]["content"]
    assert "6,435" in html
    assert "{'artifact_id'" not in html and "{&#x27;artifact_id" not in html
    assert "{'type':" not in html and "{&#x27;type&#x27;:" not in html
    assert node["artifact_id"] in html


@pytest.mark.parametrize("tag", [None, "p", "li", "span"])
def test_structured_prose_renders_text_and_reference_in_order(captured_reference, tag):
    node, artifacts = captured_reference
    block = {"text": "<em>记录总数：</em>", "refs": [node, node]}
    if tag:
        block["type"] = tag
    rendered = _render_placeholder_parts(_resolve_template_references(block, artifacts))
    assert rendered.count(">6,435</span>") == 2
    assert rendered.index("<em>记录总数：</em>") < rendered.index("6,435")
    assert 'data-dbgpt-artifacts="' + node["artifact_id"] + '"' in rendered
    if tag:
        assert rendered.startswith("<" + tag + ">")
        assert rendered.endswith("</" + tag + ">")
    assert "'text':" not in rendered and "'refs':" not in rendered


@pytest.mark.parametrize(
    "block",
    [
        {"type": "unknown", "text": "说明"},
        {"type": "p", "text": "说明", "unexpected": True},
        {"type": "p", "text": "说明", "refs": "missing"},
        {"type": "p", "text": "说明", "refs": [{"unknown": "value"}]},
        {"type": "p", "text": {"nested": "说明"}},
    ],
)
def test_unsupported_prose_object_is_rejected_instead_of_stringified(block):
    with pytest.raises(ValueError, match="REPORT_TEMPLATE_PROSE_INVALID"):
        _render_placeholder_parts(block)


def test_structured_prose_still_validates_markup_and_source(captured_reference):
    node, artifacts = captured_reference
    block = {"type": "p", "text": '<img src="x" onerror="alert(1)">', "refs": [node]}
    resolved = _resolve_template_references(block, artifacts)
    with pytest.raises(ValueError, match="REPORT_TEMPLATE_DATA_UNSAFE"):
        _render_placeholder_parts(resolved)
    block["text"] = "记录数："
    node["path"] = ["overview", "missing"]
    with pytest.raises(ValueError, match="REPORT_TEMPLATE_REFERENCE_INVALID"):
        _resolve_template_references(block, artifacts)
