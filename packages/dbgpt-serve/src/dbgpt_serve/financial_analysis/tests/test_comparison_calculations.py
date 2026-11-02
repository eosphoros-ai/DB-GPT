from decimal import Decimal

from dbgpt_serve.financial_analysis.comparison_alignment import align
from dbgpt_serve.financial_analysis.comparison_calculations import calculate_comparison

from .fixtures import extracted, member, report_config


def compute(a, b, kind="peer"):
    config = report_config(kind)
    aligned = align([member(a, "a"), member(b, "b")], config)
    return aligned, calculate_comparison(aligned, config)


def test_exact_difference_and_percentage_points_with_complete_inputs():
    a = extracted(values={"revenue": "100.01", "cost_of_sales": "60.006"})
    b = extracted(
        "合成乙股份有限公司",
        values={"revenue": "200.02", "cost_of_sales": "100.01"},
        token="b",
    )
    aligned, calculations = compute(a, b)
    diff = next(c for c in calculations if c["code"] == "revenue_difference")
    pp = next(c for c in calculations if c["code"] == "gross_margin_difference")
    assert diff["result"] == "100.01"
    assert Decimal(pp["result"]) == Decimal("10")
    assert pp["unit"] == "百分点" and len(pp["inputFactIds"]) == 4
    assert diff["subjectEntityId"] != diff["baselineEntityId"]
    assert len({c["id"] for c in calculations}) == len(calculations)
    assert all(i in {f["id"] for f in aligned["facts"]} for i in pp["inputFactIds"])


def test_zero_denominator_and_missing_never_become_zero_results():
    a = extracted(values={"revenue": "0", "cost_of_sales": "2"})
    b = extracted("合成乙股份有限公司", values={"revenue": None}, token="b")
    _, calculations = compute(a, b)
    assert (
        next(c for c in calculations if c["code"] == "gross_margin")["reason"]
        == "zero_denominator"
    )
    diff = next(c for c in calculations if c["code"] == "revenue_difference")
    assert diff["result"] is None and diff["reason"]


def test_trend_requires_shared_disclosure_and_handles_negative_base():
    a = extracted(year="2023", values={"net_profit": "-100"})
    b = extracted(year="2024", values={"net_profit": "-60"}, token="b")
    _, unpaired = compute(a, b, "trend")
    assert (
        next(c for c in unpaired if c["code"] == "net_profit_growth")["reason"]
        == "trend_basis_gap"
    )
    prior = extracted(year="2023", values={"net_profit": "-100"}, token="b")
    b["facts"].extend(prior["facts"])
    b["evidence"].extend(prior["evidence"])
    _, paired = compute(a, b, "trend")
    growth = next(c for c in paired if c["code"] == "net_profit_growth")
    assert growth["result"] == "40.0"
    assert any("负基数" in step for step in growth["steps"])


def test_incompatible_basis_cannot_enter_differences():
    a, b = extracted(), extracted("合成乙股份有限公司", token="b")
    b["facts"][0]["statementScope"] = "母公司"
    _, calculations = compute(a, b)
    assert (
        next(c for c in calculations if c["code"] == "revenue_difference")["result"]
        is None
    )


def test_trend_baseline_difference_and_adjacent_growth_use_distinct_periods():
    a = extracted(year="2022", values={"revenue": "100"})
    b = extracted(year="2023", values={"revenue": "150"}, token="b")
    c = extracted(year="2024", values={"revenue": "180"}, token="c")
    b["facts"].extend(
        extracted(year="2022", values={"revenue": "100"}, token="b")["facts"]
    )
    c["facts"].extend(
        extracted(year="2023", values={"revenue": "150"}, token="c")["facts"]
    )
    config = report_config("trend", baseline="b")
    aligned = align([member(a, "a"), member(b, "b"), member(c, "c")], config)
    calculations = calculate_comparison(aligned, config)
    difference = next(
        c
        for c in calculations
        if c["code"] == "revenue_difference" and c["subjectPeriod"] == "2024"
    )
    growth = next(
        c
        for c in calculations
        if c["code"] == "revenue_growth" and c["subjectPeriod"] == "2024"
    )
    assert difference["baselinePeriod"] == growth["baselinePeriod"] == "2023"
    assert difference["result"] == "30" and growth["result"] == "20.0"
    earlier = next(
        c
        for c in calculations
        if c["code"] == "revenue_difference" and c["subjectPeriod"] == "2022"
    )
    assert earlier["result"] == "-50" and earlier["direction"] == "lower"
