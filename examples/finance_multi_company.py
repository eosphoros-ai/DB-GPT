"""Demo: multi-company financial comparison (offline, end-to-end).

Run from the repo root:

    python examples/finance_multi_company.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from finance_research.pipeline import FinancePipeline
from finance_research.search import MockSearchProvider, SearchResult
from finance_research.store import Store

COMPANIES = ["示例科技", "示例制造"]

RESULTS_BY_COMPANY = {
    "示例科技": [
        SearchResult(
            title="示例科技 2023 年度报告",
            url="https://example.com/a/2023.pdf",
            snippet="示例科技 2023 年营业收入 120 亿元，净利润 15 亿元。",
            source="mock",
        ),
        SearchResult(
            title="示例科技 2024 年度报告",
            url="https://example.com/a/2024.pdf",
            snippet="示例科技 2024 年营业收入 140 亿元，净利润 20 亿元。",
            source="mock",
        ),
    ],
    "示例制造": [
        SearchResult(
            title="示例制造 2023 年度报告",
            url="https://example.com/b/2023.pdf",
            snippet="示例制造 2023 年营业收入 95 亿元，净利润 12 亿元。",
            source="mock",
        ),
        SearchResult(
            title="示例制造 2024 年度报告",
            url="https://example.com/b/2024.pdf",
            snippet="示例制造 2024 年营业收入 115 亿元，净利润 18 亿元。",
            source="mock",
        ),
    ],
}


def main() -> None:
    store = Store("finance_compare_demo.db")

    per_company = {}
    for company, results in RESULTS_BY_COMPANY.items():
        pipeline = FinancePipeline(
            store=store, search_provider=MockSearchProvider(results)
        )
        per_company[company] = pipeline.analyze_company(
            company, query=f"{company} 年报"
        )["analysis"]

    from finance_research.analyze import compare_companies
    from finance_research.report import generate_markdown_report

    comparison = compare_companies(
        per_company[COMPANIES[0]], per_company[COMPANIES[1]]
    )
    report = generate_markdown_report(
        title=f"{COMPANIES[0]} vs {COMPANIES[1]} 财务对比报告",
        companies=list(COMPANIES),
        analysis={},
        comparison=comparison,
        citations=[],
    )
    print(report)


if __name__ == "__main__":
    main()
