"""Saved evidence must support references actually used by a finding."""

import json
from types import SimpleNamespace

import pytest

from dbgpt_serve.financial_analysis.analysis import InvalidFindings, validate_findings
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
