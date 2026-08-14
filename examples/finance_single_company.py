"""Demo: single-company financial report analysis (offline, end-to-end).

Run from the repo root:

    python examples/finance_single_company.py

This uses the mock search provider so it runs without any API key, and
demonstrates the full chain: search -> parse -> extract -> store ->
analyze -> cited report.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from finance_research.pipeline import FinancePipeline
from finance_research.search import MockSearchProvider, SearchResult
from finance_research.store import Store

COMPANY = "示例科技"

# Each search result represents one fiscal year of the company's filings.
SAMPLE_RESULTS = [
    SearchResult(
        title=f"{COMPANY} 2022 年度报告",
        url="https://example.com/company-a/2022-annual.pdf",
        snippet="示例科技 2022 年营业收入 100 亿元，净利润 10 亿元，经营活动现金流净额 12 亿元。",
        source="mock",
    ),
    SearchResult(
        title=f"{COMPANY} 2023 年度报告",
        url="https://example.com/company-a/2023-annual.pdf",
        snippet="示例科技 2023 年营业收入 120 亿元，净利润 15 亿元，经营活动现金流净额 18 亿元。",
        source="mock",
    ),
    SearchResult(
        title=f"{COMPANY} 2024 年度报告",
        url="https://example.com/company-a/2024-annual.pdf",
        snippet="示例科技 2024 年营业收入 140 亿元，净利润 20 亿元，经营活动现金流净额 25 亿元。",
        source="mock",
    ),
]


def main() -> None:
    store = Store("finance_demo.db")
    provider = MockSearchProvider(SAMPLE_RESULTS)
    pipeline = FinancePipeline(store=store, search_provider=provider)

    result = pipeline.analyze_company(COMPANY, query=f"{COMPANY} 年报 营业收入 净利润")
    print(result["report"])


if __name__ == "__main__":
    main()
