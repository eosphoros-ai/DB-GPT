"""Financial metric extraction: LLM-backed JSON extraction + rule fallback."""

import logging
import os
import re
from typing import Dict, List, Optional

from .metrics import FinancialMetrics

logger = logging.getLogger(__name__)


class LLMExtractor:
    """Extract structured metrics from text using an OpenAI-compatible LLM."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.deepseek.com/v1",
        model: str = "deepseek-chat",
        timeout: float = 30.0,
    ):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.base_url = base_url
        self.model = model
        self.timeout = timeout

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def extract(self, text: str, company_name: str) -> Optional[FinancialMetrics]:
        """Extract metrics via LLM JSON output; returns None if unavailable."""
        if not self.available:
            return None
        try:
            from openai import OpenAI
        except ImportError:
            return None

        try:
            client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
                max_retries=1,
            )
            schema_hint = (
                '{"company_name": str, "report_type": str, "fiscal_period": str, '
                '"revenue": float, "gross_profit": float, "net_profit": float, '
                '"gross_margin": float, "net_margin": float, '
                '"operating_cash_flow": float, '
                '"segment_revenue": [{"segment": str, "amount": float}], '
                '"region_revenue": [{"segment": str, "amount": float}], '
                '"evidence": str}'
            )
            prompt = (
                "从以下财报文本中抽取关键财务指标，严格返回 JSON，缺失值用 null。\n"
                f"公司名: {company_name}\n"
                f"JSON 格式: {schema_hint}\n\n"
                f"财报文本:\n{text[:6000]}"
            )
            resp = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0,
            )
            content = resp.choices[0].message.content
            if not content:
                logger.warning("LLM returned empty content; falling back to rules.")
                return None
            return FinancialMetrics.model_validate_json(content)
        except Exception as exc:  # noqa: BLE001 - keep the rule fallback available
            logger.warning("LLM extraction failed, using rule fallback: %s", exc)
            return None


def _detect_period(text: str) -> str:
    """Detect a fiscal period such as ``2024`` or ``2025Q1`` from text."""
    match = re.search(r"(20\d{2})\s*Q([1-4])", text)
    if match:
        return f"{match.group(1)}Q{match.group(2)}"
    match = re.search(r"(20\d{2})\s*年", text)
    if match:
        return match.group(1)
    match = re.search(r"(20\d{2})", text)
    return match.group(1) if match else "unknown"


def _snippet_around(text: str, start: int, end: int, radius: int = 80) -> str:
    """Return bounded surrounding text for a match, for provenance evidence."""
    lo = max(0, start - radius)
    hi = min(len(text), end + radius)
    return text[lo:hi].replace("\n", " ").strip()


def rules_based_extract(text: str, company_name: str) -> FinancialMetrics:
    """Deterministic fallback extractor using keyword lookups.

    This is intentionally conservative: it finds indicator labels such as
    ``营业收入`` / ``净利润`` and grabs the following number, and stores the
    surrounding text as evidence so results stay traceable.
    """
    keyword_map = {
        "revenue": ["营业收入", "营业总收入", "营收", "revenue"],
        "net_profit": ["净利润", "归母净利润", "net profit"],
        "gross_profit": ["毛利", "gross profit"],
        "gross_margin": ["毛利率"],
        "net_margin": ["净利率"],
        "operating_cash_flow": [
            "经营活动产生的现金流量净额",
            "经营活动现金流净额",
            "经营现金流",
        ],
    }
    metrics = FinancialMetrics(
        company_name=company_name, fiscal_period=_detect_period(text)
    )
    values: Dict[str, float] = {}
    evidence_by_metric: Dict[str, str] = {}

    # Absolute-amount metrics must not match the trailing 率 of a ratio label
    # (e.g. 毛利 must not capture 毛利率 40.5%). Ratios keep no guard.
    _amount_metrics = {"revenue", "net_profit", "gross_profit", "operating_cash_flow"}

    for metric_name, keywords in keyword_map.items():
        for keyword in keywords:
            guard = "(?!率)" if metric_name in _amount_metrics else ""
            # Match "label ... value" where value may contain commas/decimals.
            pattern = re.compile(
                rf"{re.escape(keyword)}{guard}[^0-9\-]*(-?[\d,]+(?:\.\d+)?)"
            )
            match = pattern.search(text)
            if match:
                raw = match.group(1).replace(",", "")
                values[metric_name] = float(raw)
                evidence_by_metric[metric_name] = _snippet_around(
                    text, match.start(), match.end()
                )
                break

    metrics.revenue = values.get("revenue")
    metrics.net_profit = values.get("net_profit")
    metrics.gross_profit = values.get("gross_profit")
    metrics.gross_margin = values.get("gross_margin")
    metrics.net_margin = values.get("net_margin")
    metrics.operating_cash_flow = values.get("operating_cash_flow")
    metrics.evidence_by_metric = evidence_by_metric
    metrics.evidence = " | ".join(
        f"{name}: {snippet}" for name, snippet in evidence_by_metric.items()
    )
    return metrics


def extract_metrics(
    text: str,
    company_name: str,
    extractor: Optional[LLMExtractor] = None,
) -> FinancialMetrics:
    """Best-effort extraction: LLM first, rule-based fallback."""
    if extractor and extractor.available:
        try:
            llm_result = extractor.extract(text, company_name)
        except Exception as exc:  # noqa: BLE001 - always fall back to rules
            logger.warning("Extractor failed, using rule fallback: %s", exc)
            llm_result = None
        if llm_result is not None:
            return llm_result
    return rules_based_extract(text, company_name)


_TABLE_KEYWORDS = {
    "revenue": ["营业收入", "营业总收入", "营收"],
    "net_profit": ["净利润", "归母净利润"],
    "gross_profit": ["毛利"],
    "gross_margin": ["毛利率"],
    "net_margin": ["净利率"],
    "operating_cash_flow": [
        "经营活动产生的现金流量净额",
        "经营活动现金流净额",
        "经营现金流",
    ],
}


def _strip_unit(cell) -> str:
    """Remove whitespace and unit suffixes so keyword matching is robust."""
    text = str(cell).strip().replace(" ", "")
    for suffix in ("（亿元）", "(亿元)", "（万元）", "(万元)", "（元）", "(元)", "亿元", "万元"):
        text = text.replace(suffix, "")
    return text


def _match_metric(cell) -> Optional[str]:
    cell = _strip_unit(cell)
    for metric, keywords in _TABLE_KEYWORDS.items():
        for kw in keywords:
            if kw in cell:
                return metric
    return None


def _period_label(header) -> str:
    """Normalize a period column header (``2023`` / ``2023年`` / ``2023Q1``)."""
    import re

    s = str(header).strip()
    m = re.match(r"^(20\d{2})\s*(年|Q[1-4])?$", s)
    if m:
        return m.group(1) if not m.group(2) or m.group(2) == "年" else f"{m.group(1)}{m.group(2)}"
    return s


def extract_metrics_from_tables(tables, company_name: str) -> List[FinancialMetrics]:
    """Extract metrics directly from structured tables (CSV/Excel/HTML).

    Detects a metric-name column (whose cells match financial keywords) and
    period columns (year-like headers or numeric columns), then reads the
    value at each (metric, period) cell. Returns one ``FinancialMetrics`` per
    detected period. This complements the text-based extractor for tabular
    sources where wide-format (metrics x years) layout is common.
    """
    import pandas as pd

    results: List[FinancialMetrics] = []
    for df in tables:
        if df is None or getattr(df, "empty", True):
            continue
        df = df.copy()
        cols = list(df.columns)

        metric_col_idx = None
        for idx in range(df.shape[1]):
            vals = [
                v for v in df.iloc[:, idx] if v is not None and str(v).strip()
            ]
            if not vals:
                continue
            matches = sum(1 for v in vals if _match_metric(v))
            if matches >= max(1, int(len(vals) * 0.5)):
                metric_col_idx = idx
                break
        if metric_col_idx is None:
            metric_col_idx = 0

        period_cols = []
        for idx, col in enumerate(cols):
            if idx == metric_col_idx:
                continue
            header = _period_label(col)
            if header != str(col).strip():
                period_cols.append((idx, header))
                continue
            numeric = pd.to_numeric(df.iloc[:, idx], errors="coerce")
            if numeric.notna().any():
                period_cols.append((idx, header))
        if not period_cols:
            continue

        for pidx, period in period_cols:
            report_type = "quarterly" if re.search(r"Q[1-4]$", str(period)) else "annual"
            metrics = FinancialMetrics(
                company_name=company_name, fiscal_period=period, report_type=report_type
            )
            found = False
            for _, row in df.iterrows():
                metric = _match_metric(row.iloc[metric_col_idx])
                if metric is None:
                    continue
                val = pd.to_numeric(row.iloc[pidx], errors="coerce")
                if pd.isna(val):
                    continue
                setattr(metrics, metric, float(val))
                found = True
            if found:
                results.append(metrics)
    return results
