"""Context budgets must retain reference closure or fail explicitly."""

from copy import deepcopy

import pytest

from dbgpt_serve.financial_analysis.analysis import model_context
from dbgpt_serve.financial_analysis.questions import question_context

from .fixtures import extracted
from .test_comparison_analysis import comparison_report


def single_report_with_many_sources(snippet):
    data = extracted()
    fact = data["facts"][0]
    evidence = data["evidence"][0]
    sources = [dict(evidence, id=f"source-{i}", snippet=snippet) for i in range(101)]
    fact["evidenceExcerptIds"] = [e["id"] for e in sources]
    return {
        "mode": "report",
        "report": {"companyName": data["company_name"], "fiscalPeriod": "2024"},
        "facts": [fact],
        "calculations": [],
        "evidence": sources,
        "findings": [],
    }


def test_single_report_keeps_all_sources_of_retained_facts():
    context = model_context(single_report_with_many_sources("SYNTHETIC source"))
    assert len(context["evidence"]) == 101
    assert set(context["facts"][0]["evidenceExcerptIds"]) == {
        e["id"] for e in context["evidence"]
    }


def test_single_report_rejects_oversized_context_instead_of_dropping_sources():
    with pytest.raises(ValueError, match="Unsupported analysis context"):
        model_context(single_report_with_many_sources("x" * 600))


def test_narrow_question_can_read_an_oversized_comparison():
    report = comparison_report()
    # Large unrelated disclosures exceed the full-context budget, while a
    # revenue question still has a complete, bounded set of facts and sources.
    fact = next(f for f in report["facts"] if f["metricCode"] == "total_assets")
    source = next(
        e for e in report["evidence"] if e["id"] in fact["evidenceExcerptIds"]
    )
    for index in range(500):
        extra = dict(deepcopy(source), id=f"extra-{index}", snippet="x" * 350)
        report["evidence"].append(extra)
        fact["evidenceExcerptIds"].append(extra["id"])
    with pytest.raises(ValueError, match="Comparison context too large"):
        model_context(report)
    context = question_context(report, "营业收入如何？")
    assert context["facts"]
    assert all(
        f["metricCode"] in {"revenue", "cost_of_sales", "net_profit"}
        for f in context["facts"]
    )
    evidence_ids = {e["id"] for e in context["evidence"]}
    assert all(set(f["evidenceExcerptIds"]) <= evidence_ids for f in context["facts"])
