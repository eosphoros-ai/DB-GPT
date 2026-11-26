import json
from copy import deepcopy

import pytest

from dbgpt_serve.financial_analysis import workflow
from dbgpt_serve.financial_analysis.analysis import InvalidFindings, validate_findings
from dbgpt_serve.financial_analysis.comparison_report import build_comparison
from dbgpt_serve.financial_analysis.questions import question_context, validate_answer

from .fixtures import extracted, member, report_config


def comparison_report(revenue="1500.01"):
    result = build_comparison(
        [
            member(extracted(), "a"),
            member(
                extracted(
                    "合成乙股份有限公司",
                    values={
                        "revenue": revenue,
                        "net_profit": "200",
                        "non_recurring_net_profit": "160",
                        "operating_cash_flow": "250",
                        "cost_of_sales": "800",
                        "total_assets": "2500",
                        "total_liabilities": "900",
                        "selling_expenses": "40",
                        "administrative_expenses": "50",
                        "research_expenses": "20",
                        "financial_expenses": "-8",
                    },
                    token="b",
                ),
                "b",
            ),
        ],
        {
            "id": "12345678-1234-4234-8234-123456789012",
            "token": "test",
            "started_at": "",
            "completed_at": "",
        },
        report_config(),
    )
    result["analysis"] = {
        "status": "partial",
        "driver": "agent",
        "modelName": "synthetic",
        "startedAt": "",
        "completedAt": None,
        "rejectedCount": 0,
    }
    return workflow.initialize(result)


def comparison_finding(report, metric="revenue"):
    calc = next(
        c for c in report["calculations"] if c["code"] == metric + "_difference"
    )
    facts = [f for f in report["facts"] if f["id"] in calc["inputFactIds"]]
    return {
        "section": "overview",
        "title": "披露差额与解释限制",
        "summary": "{{calculation:" + calc["id"] + "}}，需结合业务结构与附注核对。",
        "supportStatus": "partial",
        "factIds": [],
        "calculationIds": [calc["id"]],
        "evidenceExcerptIds": [],
        "counterEvidence": [],
        "unresolvedQuestions": ["变化原因尚需核对附注。"],
        "entityIds": sorted({f["entityId"] for f in facts}),
        "periods": sorted({f["fiscalPeriod"] for f in facts}),
        "metricCodes": sorted({f["metricCode"] for f in facts}),
        "subjectEntityId": calc["subjectEntityId"],
        "baselineEntityId": calc["baselineEntityId"],
        "comparisonDirection": calc["direction"],
    }


def test_structural_direction_entity_metric_and_causality_validation():
    report = comparison_report()
    finding = comparison_finding(report)
    assert validate_findings(json.dumps({"findings": [finding]}), report)[0]
    cases = [
        {"comparisonDirection": "lower"},
        {"entityIds": [finding["entityIds"][0]]},
        {"subjectEntityId": finding["baselineEntityId"]},
        {"metricCodes": ["net_profit"]},
        {"summary": finding["summary"] + "，由于客户流失导致。"},
    ]
    for patch in cases:
        with pytest.raises(InvalidFindings):
            validate_findings(
                json.dumps({"findings": [{**finding, **patch}]}), report, strict=True
            )


@pytest.mark.parametrize("field", ["title", "summary"])
@pytest.mark.parametrize(
    "direction,revenue",
    [("higher", "1500.01"), ("lower", "500.01"), ("equal", "1000.01")],
)
@pytest.mark.parametrize("claim", ["higher", "lower", "equal"])
def test_narrative_direction_matches_calculation_in_title_and_summary(
    field, direction, revenue, claim
):
    report = comparison_report(revenue)
    finding = comparison_finding(report)
    assert finding["comparisonDirection"] == direction
    wording = {"higher": "高于基准", "lower": "低于基准", "equal": "与基准持平"}[claim]
    finding[field] = wording if field == "title" else finding[field] + wording
    raw = json.dumps({"findings": [finding]})
    if claim == direction:
        assert validate_findings(raw, report, strict=True)[0]
    else:
        with pytest.raises(InvalidFindings) as error:
            validate_findings(raw, report, strict=True)
        assert any(
            issue["code"] == "narrative_direction_mismatch"
            for issue in error.value.details
        )


def test_non_equivalence_disclaimer_is_not_an_equality_claim():
    report = comparison_report()
    finding = comparison_finding(report)
    finding["summary"] += "数值差异不等于企业优劣。"
    assert validate_findings(json.dumps({"findings": [finding]}), report, strict=True)[
        0
    ]


def test_topic_patches_preserve_other_findings_and_published_versions():
    report = comparison_report()
    report = workflow.start_topic(report, "operating")
    finding = comparison_finding(report)
    report = workflow.save_topic(
        report, "operating", findings=[{**finding, "comparisonDirection": "lower"}]
    )
    assert workflow.topic(report, "operating")["status"] == "needs_revision"
    report = workflow.save_topic(
        report,
        "operating",
        patches=[{"finding_index": 0, "changes": {"comparisonDirection": "higher"}}],
    )
    assert workflow.topic(report, "operating")["status"] == "ready"
    assert report["findings"][0]["entityIds"] == finding["entityIds"]
    old = deepcopy(report["findings"])
    report = workflow.start_topic(report, "cashflow")
    assert report["findings"] == old
    assert (
        "draftFindings" not in workflow.public_snapshot(report)["workflow"]["topics"][0]
    )


def test_scoped_question_uses_saved_numbers_and_no_new_computation():
    report = comparison_report()
    context = question_context(report, "合成乙股份有限公司营业收入")
    assert len(context["facts"]) <= 6
    assert len(json.dumps(context, ensure_ascii=False)) < 25000
    calc = next(c for c in context["calculations"] if c["code"] == "revenue_difference")
    raw = {
        "answer": "{{calculation:" + calc["id"] + "}}，具体原因需核对附注。",
        "factIds": [],
        "calculationIds": [calc["id"]],
        "evidenceExcerptIds": [],
        "insufficientEvidence": False,
    }
    assert validate_answer(json.dumps(raw), context, report)["citations"]
    raw["answer"] = "新增指标为12345。"
    with pytest.raises(ValueError):
        validate_answer(json.dumps(raw), context, report)


def test_failed_comparison_topic_keeps_valid_subset_and_original_failure():
    report = workflow.start_topic(comparison_report(), "operating")
    valid = comparison_finding(report)
    invalid = dict(valid, comparisonDirection="lower")
    for _ in range(3):
        report = workflow.save_topic(report, "operating", findings=[valid, invalid])
    item = workflow.topic(report, "operating")
    assert item["status"] == "failed" and item["issues"]
    assert len(item["findingIds"]) == len(report["findings"]) == 1
    assert report["findings"][0]["comparisonDirection"] == "higher"
