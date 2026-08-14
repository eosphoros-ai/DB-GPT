"""Cited research report generation (markdown)."""

from typing import Dict, List, Optional

import pandas as pd


def _fmt(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:,.2f}"
    return str(value)


def _is_quarterly(name: str) -> bool:
    return name.endswith("(quarterly)") or name.endswith("(季报)")


def _summary_lines(analysis: Dict[str, pd.Series]) -> List[str]:
    """Build a concise executive summary from the analysed series."""
    lines: List[str] = []

    def _latest_pct(series: pd.Series):
        if series is None or len(series) < 2:
            return None
        prev = series.iloc[-2]
        if prev == 0:
            return None
        return (series.iloc[-1] - prev) / abs(prev) * 100

    years = set()
    for series in analysis.values():
        years.update(str(p) for p in series.index)
    lines.append(
        f"- 报告覆盖 {len(years)} 个报告期（{'、'.join(sorted(years))}），"
        "数据均可通过文末引用回溯到原始来源。"
    )

    revenue = analysis.get("revenue")
    if revenue is not None and len(revenue):
        yoy = _latest_pct(revenue)
        line = f"- 最新报告期营业收入 {revenue.iloc[-1]:,.2f} 亿元"
        if yoy is not None:
            line += f"，同比增长 {yoy:+.2f}%"
        lines.append(line)

    net_profit = analysis.get("net_profit")
    if net_profit is not None and len(net_profit):
        yoy = _latest_pct(net_profit)
        line = f"- 最新报告期净利润 {net_profit.iloc[-1]:,.2f} 亿元"
        if yoy is not None:
            line += f"，同比增长 {yoy:+.2f}%"
        lines.append(line)

    # Quarterly single-quarter series -> report QoQ instead of YoY.
    rev_q = analysis.get("revenue (quarterly)")
    if rev_q is not None and len(rev_q) >= 2:
        qoq = _latest_pct(rev_q)
        if qoq is not None:
            lines.append(f"- 单季营业收入环比 {qoq:+.2f}%（{rev_q.index[-1]}）。")

    margin_parts = []
    for name, label in (("gross_margin", "毛利率"), ("net_margin", "净利率")):
        series = analysis.get(name)
        if series is not None and len(series):
            margin_parts.append(f"{label} {series.iloc[-1]:.2f}%")
    if margin_parts:
        lines.append(f"- 盈利能力：{'，'.join(margin_parts)}。")
    return lines


def _df_to_markdown(df: pd.DataFrame) -> str:
    """Render a DataFrame as a Markdown table (no external dependency)."""
    cols = list(df.columns)
    lines = []
    lines.append("| " + " | ".join(str(c) for c in cols) + " |")
    lines.append("| " + " | ".join("---" for _ in cols) + " |")
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(_fmt(row[c]) for c in cols) + " |")
    return "\n".join(lines)


def _breakdown_section(title: str, records: List[dict]) -> List[str]:
    """Render segment/region revenue breakdowns as markdown."""
    if not records:
        return []
    lines = [f"## {title}", ""]
    for record in records:
        period = record.get("fiscal_period") or "-"
        items = record.get("items") or []
        if not items:
            continue
        lines.append(f"### {period}")
        lines.append("")
        lines.append("| 项目 | 收入(亿元) | 占比 |")
        lines.append("| --- | --- | --- |")
        for item in items:
            amount = _fmt(item.get("amount"))
            ratio = item.get("ratio")
            ratio_str = f"{ratio:.2f}%" if ratio is not None else "-"
            lines.append(f"| {item.get('name', '-')} | {amount} | {ratio_str} |")
        lines.append("")
    return lines


def generate_markdown_report(
    title: str,
    companies: List[str],
    analysis: Dict[str, pd.Series],
    comparison: pd.DataFrame,
    citations: List[dict],
    segments: Optional[List[dict]] = None,
    regions: Optional[List[dict]] = None,
) -> str:
    """Render a traceable research report as markdown.

    ``citations`` is a list of ``{metric, source_url, source_file, page,
    table_name, extracted_at}`` dicts used to build the reference list.
    ``segments`` / ``regions`` carry business-segment and regional revenue
    breakdowns (``[{fiscal_period, items: [{name, amount, ratio}]}]``).
    """
    lines: List[str] = []
    lines.append(f"# {title}\n")
    lines.append(f"分析公司：{', '.join(companies)}\n")

    if analysis:
        lines.append("## 摘要\n")
        lines.extend(_summary_lines(analysis))
        lines.append("")

    lines.append("## 关键指标\n")
    for name, series in analysis.items():
        lines.append(f"### {name}\n")
        for period, value in series.items():
            lines.append(f"- {period}: {_fmt(value)}")
        if len(series) >= 2:
            pct = series.pct_change() * 100
            label = "最新环比" if _is_quarterly(name) else "最新同比"
            lines.append(f"- {label}: {_fmt(pct.iloc[-1])}%\n")
        lines.append("")

    lines.extend(_breakdown_section("分业务收入", segments or []))
    lines.extend(_breakdown_section("分地区收入", regions or []))

    if comparison is not None and not comparison.empty:
        lines.append("## 对比分析\n")
        lines.append(_df_to_markdown(comparison))
        lines.append("")

    lines.append("## 风险提示\n")
    lines.append("- 数据均来自公开资料与自动抽取，请以原始公告为准。\n")
    lines.append("- 跨期口径差异可能影响可比性。\n")

    lines.append("## 数据引用\n")
    for i, cite in enumerate(citations, start=1):
        loc = cite.get("source_url") or cite.get("source_file") or "未知来源"
        page = f"，第 {cite['page']} 页" if cite.get("page") else ""
        table = f"，表 {cite['table_name']}" if cite.get("table_name") else ""
        period = f"（{cite['fiscal_period']}）" if cite.get("fiscal_period") else ""
        lines.append(
            f"{i}. {cite.get('metric', '')}{period} — {loc}{page}{table}"
            f"（抽取时间 {cite.get('extracted_at', '-')}）"
        )
        if cite.get("evidence"):
            lines.append(f"   证据原文: {cite['evidence']}")

    return "\n".join(lines)
