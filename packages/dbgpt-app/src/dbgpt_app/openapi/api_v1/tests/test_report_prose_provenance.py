"""Numeric prose must retain category provenance and declared goal semantics."""

import pytest

from dbgpt.core.interface.report_capture import (
    ArtifactCaptureContext,
    InMemoryArtifactSink,
    capture_python_execution,
)
from dbgpt_app.openapi.api_v1.tools.html_interpreter import (
    _bind_unwrapped_numeric_claims,
    _validate_evidence_bindings,
)


def capture(sink, result):
    return capture_python_execution(
        code="result",
        duration_ms=1,
        status="succeeded",
        exit_code=0,
        stdout="",
        stderr="",
        result_inline=result,
        artifact_sink=sink,
    )


def validate(html, sink, **kwargs):
    artifacts = sink.snapshot()
    return _validate_evidence_bindings(
        html,
        [a.artifact_id for a in artifacts],
        artifact_types={a.artifact_id: a.type for a in artifacts},
        artifacts=artifacts,
        **kwargs,
    )


def test_autobinding_keeps_declared_goal_intact():
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="goals"))
    source = capture(sink, {"rating": 4.0})
    text = "建议目标（非观测值）：压缩至 9 天以内，评分提升至 4.0 分以上。"
    html = (
        '<p data-dbgpt-artifacts="'
        + source
        + '"><span data-dbgpt-value-role="proposal">'
        + text
        + "</span></p>"
    )
    bound = _bind_unwrapped_numeric_claims(html, sink.snapshot())
    assert bound == html
    assert validate(bound, sink, proposal_texts={text}) is None
    assert validate(bound, sink)  # A role attribute alone does not authorize goals.


@pytest.mark.parametrize(
    "label,display",
    [
        ("45-60", "45—60"),
        ("2.8-3.2", "2.8—3.2"),
        (">90", "高于 90"),
        ("<30", "低于 30"),
    ],
)
def test_captured_category_labels_have_exact_selectors(label, display):
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="labels"))
    source = capture(sink, {"bins": [{"bin": label, "mean": 100}]})
    bound = _bind_unwrapped_numeric_claims(
        '<div data-dbgpt-artifacts="'
        + source
        + '"><p>温度'
        + display
        + "：100</p></div>",
        sink.snapshot(),
    )
    assert source in bound and "bin" in bound
    assert validate(bound, sink) is None
    assert validate(
        _bind_unwrapped_numeric_claims("<p>高于 999</p>", sink.snapshot()), sink
    )


def test_wrong_label_selector_does_not_validate_shared_endpoint():
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="mismatch"))
    source = capture(sink, {"bin": "45-60"})
    html = (
        '<span data-dbgpt-artifacts="'
        + source
        + '" data-dbgpt-artifact-selectors=\'{"'
        + source
        + '":{"field":"bin"}}\'>45—90</span>'
    )
    assert validate(html, sink)


def test_typed_result_can_disambiguate_serialized_chart_numbers():
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="typed"))
    source = capture(sink, {"meta": {"stores": 45}})
    capture(sink, {"CHART_DATA_JSON": '{"data":[{"temperature":45}]}'})
    bound = _bind_unwrapped_numeric_claims("<p>45 家门店</p>", sink.snapshot())
    assert source in bound
    assert validate(bound, sink) is None
    capture(sink, {"other_metric": 45})
    ambiguous = _bind_unwrapped_numeric_claims("<p>45 家门店</p>", sink.snapshot())
    assert "data-dbgpt-artifacts" not in ambiguous
    assert validate(ambiguous, sink)


def test_numeric_string_is_an_index_only_in_arrays():
    from dbgpt.core.interface.report_capture import (
        normalize_artifact_result_selector,
        select_artifact_result,
    )

    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="coordinates"))
    artifact_id = capture(sink, {"payload": '{"rows":[{"0":"zero"}]}'})
    artifact = sink.snapshot()[0]
    selector = {"field": "payload", "path": ["rows", "0", "0"]}
    assert normalize_artifact_result_selector(artifact, selector) == {
        "field": "payload",
        "path": ["rows", 0, "0"],
    }
    assert select_artifact_result(artifact, selector) == "zero"
    assert artifact.artifact_id == artifact_id


def test_inline_missing_field_has_same_partial_policy_as_structured_reference():
    from dbgpt_app.openapi.api_v1.tools.html_interpreter import (
        _resolve_inline_report_references,
        _resolve_template_references,
    )

    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="partial-prose"))
    source = capture(sink, {"captured": 42})
    node = {"artifact_id": source, "field": "missing"}
    html = "<p>{artifact_id:" + source + ",field:missing}</p>"
    with pytest.raises(ValueError, match="RESULT_SELECTOR_INVALID"):
        _resolve_inline_report_references(html, sink.snapshot())
    unavailable = []
    assert (
        _resolve_inline_report_references(
            html, sink.snapshot(), unavailable=unavailable
        )
        == "<p>--</p>"
    )
    assert (
        _resolve_template_references(
            node, sink.snapshot(), unavailable_references=unavailable
        )
        == "--"
    )
    assert [issue["reference"] for issue in unavailable] == [node, node]
    assert all("captured" in issue["error"] for issue in unavailable)


def test_saved_data_patch_preserves_other_sections_and_rejects_missing_paths():
    from dbgpt_app.openapi.api_v1.tools.report_spec import merge_report_data

    saved = {"REPORT_SPEC": {"sections": [{"heading": "A"}, {"heading": "B"}]}}
    patch = {"path": "$.data.REPORT_SPEC.sections[0].heading", "value": "Fixed"}
    repaired = merge_report_data(saved, {"REPORT_DATA_PATCHES": [patch]})
    assert repaired["REPORT_SPEC"]["sections"] == [
        {"heading": "Fixed"},
        {"heading": "B"},
    ]
    with pytest.raises(ValueError, match="unknown saved path"):
        merge_report_data(
            saved, {"REPORT_DATA_PATCHES": [patch, {**patch, "path": "$.data.unknown"}]}
        )
    assert saved["REPORT_SPEC"]["sections"][0]["heading"] == "A"
