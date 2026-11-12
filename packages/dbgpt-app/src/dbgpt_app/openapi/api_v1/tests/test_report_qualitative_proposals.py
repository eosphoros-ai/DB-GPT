"""Qualitative recommendations must stay distinct from observed metrics."""

import pytest

from dbgpt.core.interface.report_capture import (
    ArtifactCaptureContext,
    InMemoryArtifactSink,
    capture_sql_execution,
)
from dbgpt_app.openapi.api_v1.tools.html_interpreter import (
    _render_template_with_bindings,
    _standalone_proposal_texts,
    _validate_evidence_bindings,
)
from dbgpt_app.openapi.api_v1.tools.report_spec import validate_report_spec


def test_qualitative_proposal_renders_with_separate_supporting_value():
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="qualitative"))
    artifact_id = capture_sql_execution(
        sql="select 20 as late_rate",
        database="test",
        duration_ms=1,
        columns=["late_rate"],
        rows=[{"late_rate": 20}],
        artifact_sink=sink,
    )
    spec = {
        "sections": [
            {
                "heading": "建议",
                "recommendations": [
                    {
                        "title": "改善配送",
                        "lines": [
                            {
                                "parts": [
                                    "当前逾期率 ",
                                    {
                                        "artifact_id": artifact_id,
                                        "path": ["rows", 0, "late_rate"],
                                    },
                                    "%",
                                    {"proposal": "逐步压降逾期率"},
                                ]
                            }
                        ],
                    }
                ],
            }
        ]
    }
    from pathlib import Path

    template = (
        Path(__file__).resolve().parents[7]
        / "skills/business-report/templates/business_report.html"
    ).read_text(encoding="utf8")
    html = _render_template_with_bindings(
        template, {"REPORT_SPEC": spec}, sink.snapshot()
    )
    assert "建议目标（非观测值）：逐步压降逾期率" in html
    assert artifact_id in html
    assert "20" in html


def test_numeric_and_qualitative_proposals_are_both_accepted():
    for proposal in ({"proposal": "降低到10%"}, {"proposal": "降低逾期率"}):
        spec = {
            "sections": [
                {
                    "recommendations": [
                        {"title": "改善", "lines": [{"parts": [proposal]}]}
                    ]
                }
            ]
        }
        assert validate_report_spec(spec)["sections"][0]["recommendations"]


def test_qualitative_proposal_is_not_valid_in_observed_prose():
    with pytest.raises(ValueError, match="REPORT_TEMPLATE_SPEC_INVALID"):
        validate_report_spec({"sections": [{"intro": [[{"proposal": "降低逾期率"}]]}]})


def test_numeric_goal_is_not_mistaken_for_an_observed_number():
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="proposal-number"))
    artifact_id = capture_sql_execution(
        sql="select 20 as late_rate",
        database="test",
        duration_ms=1,
        columns=["late_rate"],
        rows=[{"late_rate": 20}],
        artifact_sink=sink,
    )
    spec = {
        "sections": [
            {
                "heading": "建议",
                "recommendations": [
                    {
                        "title": "改善",
                        "lines": [{"parts": [{"proposal": "将逾期率降至10%"}]}],
                    }
                ],
            }
        ]
    }
    html = (
        '<p data-dbgpt-artifacts="' + artifact_id + '">'
        '<span data-dbgpt-value-role="proposal">'
        "建议目标（非观测值）：将逾期率降至10%</span></p>"
    )
    artifacts = sink.snapshot()
    types = {artifact_id: "sql"}
    assert _validate_evidence_bindings(
        html, [artifact_id], artifact_types=types, artifacts=artifacts
    )
    assert (
        _validate_evidence_bindings(
            html,
            [artifact_id],
            artifact_types=types,
            artifacts=artifacts,
            proposal_texts=_standalone_proposal_texts(spec),
        )
        is None
    )
