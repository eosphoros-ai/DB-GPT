from copy import deepcopy

from dbgpt_serve.financial_analysis.comparison_alignment import align
from dbgpt_serve.financial_analysis.comparison_report import build_comparison
from dbgpt_serve.financial_analysis.comparison_schema import validate_snapshot

from .fixtures import extracted, member, report_config


def test_company_facts_never_overwrite_and_equal_disclosures_remain_auditable():
    first = extracted()
    second = extracted("合成乙股份有限公司", token="b")
    third = extracted(token="c")
    result = align(
        [member(first, "a"), member(second, "b"), member(third, "c")], report_config()
    )
    assert len(result["entities"]) == 2
    assert len(result["facts"]) == len(first["facts"]) * 3
    revenue = [c for c in result["cells"] if c["metricCode"] == "revenue"]
    assert len(revenue) == 2
    assert sorted(len(c["candidateFactIds"]) for c in revenue) == [1, 2]


def test_unexplained_conflict_is_not_latest_or_first_wins():
    first = extracted(values={"revenue": "100"})
    second = extracted(values={"revenue": "120"}, token="b")
    result = align([member(first, "a"), member(second, "b")], report_config("trend"))
    assert (
        next(c for c in result["cells"] if c["metricCode"] == "revenue")["dataStatus"]
        == "conflict"
    )


def test_scope_attribution_currency_and_period_type_are_separate_from_availability():
    for key, value in [
        ("statementScope", "母公司"),
        ("attribution", "overall"),
        ("currency", "USD"),
        ("periodType", "instant"),
    ]:
        a, b = extracted(), extracted("合成乙股份有限公司", token="b")
        b["facts"][0][key] = value
        result = align([member(a, "a"), member(b, "b")], report_config())
        revenue = [c for c in result["cells"] if c["metricCode"] == "revenue"]
        assert all(c["dataStatus"] == "available" for c in revenue)
        assert all(c["comparability"]["status"] == "incomparable" for c in revenue)


def test_identity_ambiguity_and_wrong_modes_require_clarification():
    a, b = extracted(), extracted("合成乙股份有限公司", token="b")
    a["company_identity"] = {"candidates": ["合成甲", "合成丁"]}
    result = align([member(a, "a"), member(b, "b")], report_config())
    assert result["clarifications"] and not result["comparisonReady"]
    result = align([member(extracted(), "a"), member(b, "b")], report_config("trend"))
    assert not result["comparisonReady"]


def test_snapshot_protocol_rejects_floats_and_unknown_versions():
    report = build_comparison(
        [
            member(extracted(), "a"),
            member(extracted("合成乙股份有限公司", token="b"), "b"),
        ],
        {"id": "run", "token": "test", "started_at": "", "completed_at": ""},
        report_config(),
    )
    validate_snapshot(report)
    bad = deepcopy(report)
    bad["facts"][0]["normalizedValue"] = 1.2
    import pytest

    with pytest.raises(ValueError):
        validate_snapshot(bad)
    with pytest.raises(ValueError):
        validate_snapshot({"schemaVersion": 3, "mode": "comparison"})


def test_explicit_before_after_pair_is_preserved_and_selected_by_policy():
    first = extracted(values={"revenue": "100"})
    newer = extracted(values={"revenue": "120"}, token="b")
    base_evidence = newer["evidence"][0]
    newer["sourceObservations"] = [
        {
            "metricCode": "revenue",
            "fiscalPeriod": "2024",
            "rawValue": value,
            "normalizedValue": value,
            "sourceUnit": "元",
            "sourcePeriod": {
                "year": "2024",
                "role": "annual",
                "adjustment": adjustment,
            },
            "evidence": dict(base_evidence, id=base_evidence["id"] + "-" + adjustment),
        }
        for value, adjustment in [("100", "before"), ("120", "after")]
    ]
    aligned = align([member(first, "a"), member(newer, "b")], report_config("trend"))
    cell = next(c for c in aligned["cells"] if c["metricCode"] == "revenue")
    assert cell["selectionReason"] == "explicit_paired_restatement"
    assert len(cell["candidateFactIds"]) == 3
    assert (
        next(f for f in aligned["facts"] if f["id"] == cell["factId"])[
            "normalizedValue"
        ]
        == "120"
    )
    assert any(f["adjustment"] == "before" for f in aligned["facts"])
    assert all(
        e in {i["id"] for i in aligned["evidence"]}
        for f in aligned["facts"]
        for e in f["evidenceExcerptIds"]
    )
