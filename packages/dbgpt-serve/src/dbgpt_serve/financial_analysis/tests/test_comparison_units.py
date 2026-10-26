import importlib.util
from pathlib import Path


def test_source_amounts_normalize_yuan_wanyuan_yiyuan_without_float(monkeypatch):
    root = next(p for p in Path(__file__).resolve().parents if (p / "skills").is_dir())
    script = root / "skills/financial-report-analyzer/scripts/financial_document.py"
    monkeypatch.syspath_prepend(str(script.parent))
    spec = importlib.util.spec_from_file_location("comparison_document_units", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for raw, unit, expected in [
        ("1,234.56", "元", "1234.56"),
        ("1,234.56", "万元", "12345600.00"),
        ("0.12345678", "亿元", "12345678.00000000"),
        ("(12.50)", "万元", "-125000.00"),
    ]:
        assert module.amount(raw, unit) == (expected, None)
    assert module.amount("—", "元") == (None, "missing_value")
    assert module.amount("12", "未知") == (None, "unknown_unit")
