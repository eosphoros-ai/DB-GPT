"""Synthetic regressions for extraction boundaries and exact arithmetic."""

import importlib.util
import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from dbgpt_serve.financial_analysis.calculations import calculate

from .fixtures import annual_report_pdf, extracted


@pytest.fixture
def extractor(monkeypatch):
    """Load the checkout's Skill extractor without an installed Skill package."""
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


@pytest.mark.parametrize("error_type", [FileNotFoundError, PermissionError, ValueError])
def test_skill_error_boundary_redacts_paths(monkeypatch, tmp_path, capsys, error_type):
    scripts = (
        Path(__file__).resolve().parents[6] / "skills/financial-report-analyzer/scripts"
    )
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location(
        "financial_skill_entry", scripts / "extract_financials.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    private_path = str(tmp_path / "private-materialized-session.pdf")

    def fail(path):
        raise error_type("cannot parse " + private_path)

    monkeypatch.setattr(module, "extract_document", fail)
    result = module.extract_financials(private_path)
    assert result["error"] is True
    assert result["code"] == "PDF_EXTRACTION_FAILED"
    assert result["errorType"] == error_type.__name__
    captured = capsys.readouterr()
    assert private_path not in json.dumps(result) + captured.out + captured.err


def test_skill_cli_returns_safe_json_for_a_missing_file(tmp_path):
    script = (
        Path(__file__).resolve().parents[6]
        / "skills/financial-report-analyzer/scripts/extract_financials.py"
    )
    private_path = str(tmp_path / "missing-materialized-session.pdf")
    result = subprocess.run(
        [sys.executable, str(script), private_path],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 1
    assert json.loads(result.stdout)["code"] == "PDF_EXTRACTION_FAILED"
    assert private_path not in result.stdout + result.stderr


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
    """Normalize supported amounts without converting missing values to zero."""
    assert extractor.amount(raw, unit) == (expected, reason)


def test_narrative_amounts_are_never_substituted_for_missing_tables(extractor):
    """Leave unsupported reports unavailable instead of mining narrative numbers."""
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
    """Calculate exact growth or retain the specific unavailable-input reason."""
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
    """Reject mismatched currency without assuming a foreign-exchange conversion."""
    facts = extracted(values={"revenue": "100", "net_profit": "20"})["facts"]
    facts[0]["currency"] = "USD"
    trace = next(
        item for item in calculate(facts, "2024") if item["code"] == "revenue_yoy"
    )
    assert trace["reason"] == "incompatible_input"
    assert trace["result"] is None


@pytest.mark.parametrize(
    "unit,currency,expected",
    [
        ("美元", "USD", "美元 (USD)"),
        ("万元", "CNY", "万元 (CNY)"),
        (None, None, "未知单位 (未知币种)"),
        ("元", "CNY", "元 (CNY)"),
    ],
)
def test_trace_steps_preserve_input_unit_and_currency(unit, currency, expected):
    """Show each fact's real unit and currency even when calculation is rejected."""
    facts = [
        *extracted(year="2024", values={"revenue": "100"})["facts"],
        *extracted(year="2023", values={"revenue": "80"})["facts"],
    ]
    facts[0].update(unit=unit, currency=currency)
    trace = next(
        item for item in calculate(facts, "2024") if item["code"] == "revenue_yoy"
    )
    assert trace["steps"][0] == f"2024 revenue = 100 {expected}"
    assert trace["steps"][1] == "2023 revenue = 80 元 (CNY)"
    if (unit, currency) == ("元", "CNY"):
        assert trace["status"] == "calculated"
        assert Decimal(trace["result"]) == 25
    else:
        assert trace["status"] == "unavailable"
        assert trace["reason"] == "incompatible_input"
        assert trace["result"] is None


def test_blank_amount_cell_keeps_its_logical_column(extractor):
    """Keep a blank current-year amount from shifting the preceding-year value."""
    rows = [
        ["项目", "2024年", "2023年"],
        ["营业收入", "100", "90"],
        ["营业成本", "", "80"],
    ]
    boxes = [
        [(0, y, 100, y + 10), (100, y, 200, y + 10), (200, y, 300, y + 10)]
        for y in (0, 10, 20)
    ]
    result = extractor.structure_table(rows, boxes, (0, 0, 300, 30))
    assert result["status"] == "mapped"
    assert result["rows"][2] == ["营业成本", None, "80"]
    assert result["sourceCells"][2][1] == []
    assert result["sourceCells"][2][2] == [[2, 2]]


def test_overlapping_amount_geometry_is_rejected(extractor):
    """Reject an amount box spanning two year columns rather than guessing."""
    rows = [["营业收入", "100", "90"], ["营业成本", "70", "80"]]
    boxes = [
        [(0, 0, 100, 10), (100, 0, 200, 10), (200, 0, 300, 10)],
        [(0, 10, 100, 20), (150, 10, 250, 20), (250, 10, 300, 20)],
    ]
    assert extractor.structure_table(rows, boxes, (0, 0, 300, 20)) == {
        "status": "ambiguous",
        "reason": "ambiguous_column_geometry",
    }


def test_real_pdf_extraction_keeps_exact_values_and_page_evidence(extractor, tmp_path):
    """Exercise pdfplumber's real page, table-row, and cleanup APIs end to end."""
    pytest.importorskip("pdfplumber")
    path = tmp_path / "synthetic-annual-report.pdf"
    path.write_bytes(annual_report_pdf())
    result = extractor.extract_document(path)
    revenue = {
        fact["fiscalPeriod"]: fact
        for fact in result["facts"]
        if fact["metricCode"] == "revenue"
    }
    assert result["_meta"]["status"] == "parsed"
    assert result["_meta"]["humanVerified"] is False
    assert result["document"]["pageCount"] == 1
    assert revenue["2024"]["normalizedValue"] == "100.25"
    assert revenue["2023"]["normalizedValue"] == "90.00"
    assert revenue["2024"]["unit"] == "元"
    assert revenue["2024"]["currency"] == "CNY"
    evidence = {item["id"]: item for item in result["evidence"]}
    for fact in revenue.values():
        assert fact["extractionStatus"] == "parsed"
        assert fact["evidenceExcerptIds"]
        for identifier in fact["evidenceExcerptIds"]:
            assert evidence[identifier]["page"] == 1
