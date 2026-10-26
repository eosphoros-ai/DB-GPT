"""Synthetic regressions for extraction boundaries and exact arithmetic."""

import importlib.util
from decimal import Decimal
from pathlib import Path

import pytest

from dbgpt_serve.financial_analysis.calculations import calculate

from .fixtures import extracted


@pytest.fixture
def extractor(monkeypatch):
    scripts = (
        Path(__file__).resolve().parents[6]
        / "skills"
        / "financial-report-analyzer"
        / "scripts"
    )
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location(
        "financial_foundation_extractor", scripts / "financial_document.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "raw,unit,expected,reason",
    [
        ("1,234.5678", "万元", "12345678.0000", None),
        ("（12.50）", "元", "-12.50", None),
        ("0", "元", "0", None),
        ("—", "元", None, "missing_value"),
        ("12", "USD", None, "unknown_unit"),
    ],
)
def test_amounts_preserve_precision_zero_and_missingness(
    extractor, raw, unit, expected, reason
):
    assert extractor.amount(raw, unit) == (expected, reason)


def test_narrative_amounts_are_never_substituted_for_missing_tables(extractor):
    result = extractor.build_result(
        [
            {
                "page": 1,
                "text": (
                    "合成股份有限公司\n2024年年度报告\n营业收入1000万元，利润200万元。"
                ),
                "tables": [],
            }
        ],
        "synthetic-document",
        "synthetic.pdf",
    )
    assert result["_meta"]["status"] == "unsupported"
    assert result["_meta"]["humanVerified"] is False
    assert not result["evidence"]
    assert all(fact["normalizedValue"] is None for fact in result["facts"])


@pytest.mark.parametrize(
    "previous,current,expected,reason",
    [
        ("100.01", "200.02", "100", None),
        ("-10", "10", "200", None),
        ("0", "10", None, "zero_denominator"),
        (None, "10", None, "missing_input"),
    ],
)
def test_growth_uses_exact_values_and_preserves_unavailable_reasons(
    previous, current, expected, reason
):
    facts = [
        *extracted(year="2023", values={"revenue": previous})["facts"],
        *extracted(year="2024", values={"revenue": current})["facts"],
    ]
    trace = next(
        item for item in calculate(facts, "2024") if item["code"] == "revenue_yoy"
    )
    assert trace["reason"] == reason
    if expected is None:
        assert trace["result"] is None
        assert trace["status"] == "unavailable"
    else:
        assert Decimal(trace["result"]) == Decimal(expected)
        assert len(trace["inputFactIds"]) == 2


def test_incompatible_currency_is_not_silently_converted():
    facts = extracted(values={"revenue": "100", "net_profit": "20"})["facts"]
    facts[0]["currency"] = "USD"
    trace = next(
        item for item in calculate(facts, "2024") if item["code"] == "revenue_yoy"
    )
    assert trace["reason"] == "incompatible_input"
    assert trace["result"] is None
