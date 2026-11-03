"""Saved evidence must support references actually used by a finding."""

import json
from types import SimpleNamespace

import pytest

from dbgpt_serve.financial_analysis.analysis import (
    InvalidFindings,
    _render_text,
    validate_findings,
)
from dbgpt_serve.financial_analysis.report import build_report

from .fixtures import extracted


@pytest.fixture
def report():
    return build_report(
        extracted(),
        {
            "id": "synthetic-run",
            "token": "synthetic",
            "started_at": "",
            "completed_at": "",
        },
        SimpleNamespace(file_id="a", display_name="synthetic.pdf", size_bytes=32),
    )


def finding(report):
    revenue = next(f for f in report["facts"] if f["metricCode"] == "revenue")
    return {
        "section": "overview",
        "title": "披露数据与解释边界",
        "summary": "已披露{{fact:" + revenue["id"] + "}}，变化原因需核对附注。",
        "supportStatus": "partial",
        "factIds": [revenue["id"]],
        "calculationIds": [],
        "evidenceExcerptIds": [],
        "counterEvidence": [],
        "unresolvedQuestions": [],
    }


@pytest.mark.parametrize("kind", ["fact", "calculation"])
def test_unused_declarations_do_not_attach_unrelated_evidence(report, kind):
    valid = finding(report)
    invalid = finding(report)
    if kind == "fact":
        extra = next(f for f in report["facts"] if f["metricCode"] == "total_assets")
        invalid["factIds"].append(extra["id"])
    else:
        extra = next(c for c in report["calculations"] if c["status"] == "calculated")
        invalid["calculationIds"] = [extra["id"]]
        invalid["factIds"] = sorted(set(invalid["factIds"] + extra["inputFactIds"]))
    with pytest.raises(InvalidFindings) as error:
        validate_findings(json.dumps({"findings": [invalid]}), report, strict=True)
    assert any(issue["code"] == "unused_reference" for issue in error.value.details)
    accepted, rejected = validate_findings(
        json.dumps({"findings": [valid, invalid]}), report
    )
    assert len(accepted) == rejected == 1
    assert accepted[0]["factIds"] == valid["factIds"]
    revenue = next(f for f in report["facts"] if f["id"] == valid["factIds"][0])
    assert set(accepted[0]["evidenceExcerptIds"]) == set(revenue["evidenceExcerptIds"])


def test_used_calculation_retains_its_declared_input_facts_and_evidence(report):
    draft = finding(report)
    calc = next(c for c in report["calculations"] if c["status"] == "calculated")
    draft.update(
        summary="已披露{{calculation:" + calc["id"] + "}}，解释仍需核对附注。",
        factIds=calc["inputFactIds"],
        calculationIds=[calc["id"]],
    )
    saved = validate_findings(json.dumps({"findings": [draft]}), report, strict=True)[
        0
    ][0]
    assert set(saved["factIds"]) == set(calc["inputFactIds"])
    assert set(saved["evidenceExcerptIds"]) == {
        e
        for f in report["facts"]
        if f["id"] in calc["inputFactIds"]
        for e in f["evidenceExcerptIds"]
    }


@pytest.mark.parametrize("field", ["title", "counterEvidence", "unresolvedQuestions"])
def test_references_in_other_finding_text_are_kept(report, field):
    draft = finding(report)
    fact = next(f for f in report["facts"] if f["metricCode"] == "total_assets")
    draft["factIds"].append(fact["id"])
    text = "{{fact:" + fact["id"] + "}}"
    draft[field] = text if field == "title" else [text]
    saved = validate_findings(json.dumps({"findings": [draft]}), report, strict=True)[
        0
    ][0]
    assert set(saved["factIds"]) == set(draft["factIds"])


def test_numeric_error_does_not_claim_used_calculation_and_inputs_are_unused(report):
    draft = finding(report)
    calc = next(c for c in report["calculations"] if c["status"] == "calculated")
    draft.update(
        summary="{{calculation:" + calc["id"] + "}}，小于1。",
        factIds=calc["inputFactIds"],
        calculationIds=[calc["id"]],
    )
    with pytest.raises(InvalidFindings) as error:
        validate_findings(json.dumps({"findings": [draft]}), report, strict=True)
    assert not any(i["code"] == "unused_reference" for i in error.value.details)
    issue = next(i for i in error.value.details if "invalid_tokens" in i)
    assert issue["invalid_tokens"] == ["1"]
    assert "保留有效占位符" in issue["hint"]


def test_undeclared_question_reference_receives_an_actionable_patch(report):
    draft = finding(report)
    fact = next(f for f in report["facts"] if f["metricCode"] == "total_assets")
    draft["unresolvedQuestions"] = ["{{fact:" + fact["id"] + "}}的构成需核对。"]
    with pytest.raises(InvalidFindings) as error:
        validate_findings(json.dumps({"findings": [draft]}), report, strict=True)
    issue = next(
        i for i in error.value.details if i["code"] == "Reference not declared"
    )
    assert issue["undeclared_references"] == [{"kind": "fact", "id": fact["id"]}]
    draft.update(issue["suggested_changes"])
    saved, rejected = validate_findings(
        json.dumps({"findings": [draft]}), report, strict=True
    )
    assert rejected == 0
    assert fact["id"] in saved[0]["factIds"]


def test_unknown_or_cross_topic_references_are_not_suggested_as_valid(report):
    draft = finding(report)
    fact = next(f for f in report["facts"] if f["metricCode"] == "total_assets")
    for ref in ("invented", fact["id"]):
        draft["unresolvedQuestions"] = ["{{fact:" + ref + "}}的构成需核对。"]
        with pytest.raises(InvalidFindings) as error:
            validate_findings(
                json.dumps({"findings": [draft]}),
                report,
                strict=True,
                allowed_fact_ids=set(draft["factIds"]),
            )
        issue = next(
            i for i in error.value.details if i["code"] == "Reference not declared"
        )
        assert "suggested_changes" not in issue


@pytest.mark.parametrize(
    "prefix,expected",
    [
        ("2019年管理费用率为", "2019年管理费用率为12.67%"),
        ("较2019年的", "较2019年的管理费用率 12.67%"),
        ("本期", "本期2019 年管理费用率 12.67%"),
        ("2018年管理费用率为", "2018年管理费用率为2019 年管理费用率 12.67%"),
        ("2019年销售费用率为", "2019年销售费用率为2019 年管理费用率 12.67%"),
    ],
)
def test_reference_rendering_omits_only_matching_metadata(prefix, expected):
    calc = {"name": "2019 年管理费用率", "displayResult": "12.67%"}
    used = set()
    assert (
        _render_text(
            prefix + "{{calculation:expense}}",
            {},
            {"expense": calc},
            used,
            periods=("2018", "2019"),
        )
        == expected
    )
    assert used == {("calculation", "expense")}


def test_fact_rendering_preserves_value_and_period_without_repeating_full_label():
    fact = {
        "fiscalPeriod": "2019",
        "metricName": "管理费用",
        "displayValue": "40,296,606.50 元",
    }
    assert (
        _render_text("2019年管理费用为{{fact:expense}}", {"expense": fact}, {}, set())
        == "2019年管理费用为40,296,606.50 元"
    )
