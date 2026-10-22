"""Visible reference literals must render captured values, never dictionary reprs."""

import inspect
import json
from html import escape

import pytest

from dbgpt.core.interface.report_capture import (
    ArtifactCaptureContext,
    InMemoryArtifactSink,
    capture_python_execution,
)
from dbgpt_app.openapi.api_v1.tools.html_interpreter import (
    _render_placeholder_parts,
    _resolve_inline_report_references,
    _resolve_template_references,
    make_html_interpreter,
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
