"""End-to-end orchestration: search -> parse -> extract -> store -> analyze."""

import datetime
import json
import logging
from io import BytesIO
from typing import Dict, List, Optional
from urllib.parse import urlparse

import pandas as pd

from .analyze.analyzer import analyze_company_metrics, compare_companies
from .extract.extractor import LLMExtractor, extract_metrics, extract_metrics_from_tables
from .extract.metrics import FinancialMetrics
from .parse.html_parser import extract_tables, extract_text, fetch_html, fetch_pdf_bytes
from .parse.pdf_parser import extract_pdf_tables, extract_pdf_text
from .parse.tabular_parser import dataframe_to_text, parse_tabular_bytes
from .report.generator import generate_markdown_report
from .search.base import SearchProvider, SearchResult
from .store.models import FinancialMetric, Provenance, Report
from .store.repository import Store

logger = logging.getLogger(__name__)


class FinancePipeline:
    """Runs the full public-finance research chain against a data store."""

    def __init__(
        self,
        store: Store,
        search_provider: SearchProvider,
        extractor: Optional[LLMExtractor] = None,
        max_results: int = 3,
    ):
        self.store = store
        self.search = search_provider
        self.extractor = extractor
        self.max_results = max_results

    # ------------------------------------------------------------------ #
    # Parsing helpers
    # ------------------------------------------------------------------ #
    def _parse_result(self, result: SearchResult):
        """Fetch and parse a single search result into text + tables."""
        if result.structured:
            # Structured data source (e.g. Eastmoney): no fetching needed; keep
            # the provider name so provenance can distinguish API vs page data.
            return result.source, (result.snippet or result.title), []

        url = result.url
        source_type = (
            "pdf" if urlparse(url).path.lower().endswith(".pdf") else "html"
        )
        if result.snippet_only:
            # Offline/mock source: snippet is the available text.
            return source_type, (result.snippet or result.title), []

        text = ""
        tables: List[pd.DataFrame] = []
        if source_type == "pdf":
            text = result.snippet or result.title
            try:
                pdf_bytes = fetch_pdf_bytes(url)
                pages = extract_pdf_text(BytesIO(pdf_bytes))
                text = "\n".join(page for _, page in pages if page).strip() or text
                tables = [df for _, _, df in extract_pdf_tables(BytesIO(pdf_bytes))]
            except Exception as exc:  # noqa: BLE001 - fall back to search snippet
                logger.warning("Failed to fetch/parse PDF %s: %s", url, exc)
        else:
            try:
                html = fetch_html(url)
                text = extract_text(html)
                tables = extract_tables(html)
            except Exception as exc:  # noqa: BLE001 - keep pipeline resilient
                logger.warning("Failed to fetch/parse HTML %s: %s", url, exc)
                text = f"{result.title}\n{result.snippet}"
        return source_type, text, tables

    @staticmethod
    def _parse_upload(filename: str, data: bytes):
        """Parse an uploaded file into ``(source_type, text, tables)``."""
        name = (filename or "").lower()
        if name.endswith(".pdf"):
            text = "\n".join(
                page for _, page in extract_pdf_text(BytesIO(data)) if page
            )
            tables = [df for _, _, df in extract_pdf_tables(BytesIO(data))]
            return "pdf", text, tables
        if name.endswith((".xlsx", ".xls", ".xlsm", ".csv")):
            tables, labels = parse_tabular_bytes(data, filename)
            blocks = []
            for i, df in enumerate(tables):
                label = labels[i] if i < len(labels) else f"表格{i + 1}"
                blocks.append(f"{label}:\n{dataframe_to_text(df)}")
            source_type = "excel" if name.endswith((".xlsx", ".xls", ".xlsm")) else "csv"
            return source_type, "\n\n".join(blocks), tables
        text = data.decode("utf-8", errors="replace")
        return "upload", text, []

    # ------------------------------------------------------------------ #
    # Metric extraction + provenance
    # ------------------------------------------------------------------ #
    @staticmethod
    def _merge_structured(metrics: FinancialMetrics, structured: dict) -> FinancialMetrics:
        """Overlay provider pre-parsed structured values onto extracted metrics."""
        scalar_map = {
            "revenue": "revenue",
            "gross_profit": "gross_profit",
            "net_profit": "net_profit",
            "gross_margin": "gross_margin",
            "net_margin": "net_margin",
            "operating_cash_flow": "operating_cash_flow",
        }
        for field, key in scalar_map.items():
            if structured.get(key) is not None:
                setattr(metrics, field, structured[key])
        if structured.get("fiscal_period"):
            metrics.fiscal_period = structured["fiscal_period"]
        if structured.get("report_type"):
            metrics.report_type = structured["report_type"]
        return metrics

    _METRIC_LABELS = {
        "revenue": "营业收入",
        "gross_profit": "毛利",
        "net_profit": "净利润",
        "gross_margin": "毛利率",
        "net_margin": "净利率",
        "operating_cash_flow": "经营现金流净额",
    }
    _METRIC_UNITS = {
        "revenue": "亿元",
        "gross_profit": "亿元",
        "net_profit": "亿元",
        "gross_margin": "%",
        "net_margin": "%",
        "operating_cash_flow": "亿元",
    }
    _SOURCE_LABELS = {
        "eastmoney": "东方财富F10",
        "baidu": "百度搜索",
        "mock": "示例数据",
    }

    @classmethod
    def _structured_evidence(cls, result: SearchResult, structured: dict) -> dict:
        """Build precise per-metric evidence snippets for structured sources."""
        source = cls._SOURCE_LABELS.get(result.source, result.source)
        period = structured.get("fiscal_period", "")
        evidence = {}
        for field, label in cls._METRIC_LABELS.items():
            value = structured.get(field)
            if value is None:
                continue
            unit = cls._METRIC_UNITS[field]
            evidence[field] = f"{source} {period} · {label} {value:.2f} {unit}"
        return evidence

    @staticmethod
    def _to_metric_rows(
        company_name: str, provenance_id: str, metrics_list: List[FinancialMetrics]
    ) -> List[FinancialMetric]:
        """Convert a list of extracted metrics into persistable rows.

        Rows are deduplicated by ``(metric_name, fiscal_period)`` so the text
        extractor and the table extractor never double-count the same cell.
        """
        rows = []
        seen = set()
        for metrics in metrics_list:
            for row in metrics.as_flat_rows():
                key = (row["metric_name"], metrics.fiscal_period)
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    FinancialMetric(
                        provenance_id=provenance_id,
                        company_name=company_name,
                        fiscal_period=metrics.fiscal_period,
                        report_type=metrics.report_type,
                        metric_name=row["metric_name"],
                        metric_value=row["metric_value"],
                        evidence=row.get("evidence") or metrics.evidence,
                    )
                )
        return rows

    def _extract_and_store(
        self,
        company_name: str,
        result: SearchResult,
        source_type: str,
        text: str,
        tables: List[pd.DataFrame],
    ) -> List[FinancialMetric]:
        metrics = extract_metrics(text, company_name, self.extractor)
        if result.structured:
            metrics = self._merge_structured(metrics, result.structured)
            # Structured sources carry exact values: synthesize precise,
            # per-metric evidence instead of reusing the full snippet.
            metrics.evidence_by_metric = self._structured_evidence(
                result, result.structured
            )
            metrics.evidence = " | ".join(metrics.evidence_by_metric.values())
        metrics_list = [metrics]
        metrics_list.extend(extract_metrics_from_tables(tables, company_name))

        provenance = self.store.add_provenance(
            Provenance(
                source_type=source_type,
                source_url=result.url,
                title=result.title,
                raw_text=text[:2000],
                captured_at=datetime.datetime.utcnow(),
                extracted_at=datetime.datetime.utcnow(),
            )
        )

        metric_rows = self._to_metric_rows(company_name, provenance.id, metrics_list)
        self.store.add_metrics(metric_rows)
        return metric_rows

    def _extract_from_upload(
        self,
        company_name: str,
        filename: str,
        source_type: str,
        text: str,
        tables: List[pd.DataFrame],
    ) -> List[FinancialMetric]:
        """Extract metrics from an uploaded file and store with file provenance."""
        table_metrics = extract_metrics_from_tables(tables, company_name)
        if source_type in ("csv", "excel") and table_metrics:
            # Tabular files are already structured: prefer the table extractor.
            metrics_list = table_metrics
        else:
            metrics_list = [extract_metrics(text, company_name, self.extractor)]
            metrics_list.extend(table_metrics)

        provenance = self.store.add_provenance(
            Provenance(
                source_type=source_type,
                source_file=filename,
                title=filename,
                raw_text=text[:2000],
                captured_at=datetime.datetime.utcnow(),
                extracted_at=datetime.datetime.utcnow(),
            )
        )

        metric_rows = self._to_metric_rows(company_name, provenance.id, metrics_list)
        self.store.add_metrics(metric_rows)
        return metric_rows

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def analyze_company(
        self,
        company_name: str,
        query: str,
        uploaded_files: Optional[List[dict]] = None,
    ) -> dict:
        """Discover and analyze a single company; returns report + citations.

        ``uploaded_files`` is an optional list of ``{"filename": str,
        "data": bytes}`` entries that are parsed and analysed jointly with the
        discovered public sources.
        """
        results = self.search.search(query, num_results=self.max_results)
        all_metric_rows = []
        citations = []
        segment_records: List[dict] = []
        region_records: List[dict] = []

        for result in results[: self.max_results]:
            source_type, text, tables = self._parse_result(result)
            metric_rows = self._extract_and_store(
                company_name, result, source_type, text, tables
            )
            all_metric_rows.extend(
                {
                    "metric_name": m.metric_name,
                    "metric_value": m.metric_value,
                    "fiscal_period": m.fiscal_period,
                    "report_type": m.report_type,
                }
                for m in metric_rows
            )
            citations.extend(
                self._build_citations(metric_rows, source_type, result.url, None)
            )
            self._collect_breakdown(
                result.structured, source_type, result.url,
                metric_rows, segment_records, region_records
            )

        for uploaded in uploaded_files or []:
            filename = uploaded.get("filename", "upload")
            data = uploaded.get("data") or b""
            source_type, text, tables = self._parse_upload(filename, data)
            metric_rows = self._extract_from_upload(
                company_name, filename, source_type, text, tables
            )
            all_metric_rows.extend(
                {
                    "metric_name": m.metric_name,
                    "metric_value": m.metric_value,
                    "fiscal_period": m.fiscal_period,
                    "report_type": m.report_type,
                }
                for m in metric_rows
            )
            citations.extend(
                self._build_citations(metric_rows, source_type, None, filename)
            )

        analysis = analyze_company_metrics(all_metric_rows)
        report_md = generate_markdown_report(
            title=f"{company_name} 财报分析报告",
            companies=[company_name],
            analysis=analysis,
            comparison=pd.DataFrame(),
            citations=citations,
            segments=segment_records,
            regions=region_records,
        )
        self.store.add_report(
            Report(
                title=f"{company_name} 财报分析报告",
                companies=json.dumps([company_name], ensure_ascii=False),
                content=report_md,
                citations=json.dumps(citations, ensure_ascii=False),
            )
        )
        return {
            "report": report_md,
            "citations": citations,
            "analysis": analysis,
            "segments": segment_records,
            "regions": region_records,
        }

    @staticmethod
    def _build_citations(
        metric_rows: List[FinancialMetric],
        source_type: str,
        source_url: Optional[str],
        source_file: Optional[str],
    ) -> List[dict]:
        citations = []
        for m in metric_rows:
            citations.append(
                {
                    "metric": m.metric_name,
                    "fiscal_period": m.fiscal_period,
                    "report_type": m.report_type,
                    "metric_value": m.metric_value,
                    "source_type": source_type,
                    "source_url": source_url,
                    "source_file": source_file,
                    "page": None,
                    "table_name": None,
                    "evidence": m.evidence,
                    "extracted_at": datetime.datetime.utcnow().isoformat(),
                }
            )
        return citations

    @staticmethod
    def _collect_breakdown(
        structured: Optional[dict],
        source_type: str,
        source_url: Optional[str],
        metric_rows: List[FinancialMetric],
        segment_records: List[dict],
        region_records: List[dict],
    ) -> None:
        """Accumulate segment/region revenue breakdowns for the report."""
        if not structured:
            return
        period = structured.get("fiscal_period")
        report_type = structured.get("report_type")
        if period is None:
            period = metric_rows[0].fiscal_period if metric_rows else None
        extracted_at = datetime.datetime.utcnow().isoformat()

        for key, target in (("segments", segment_records), ("regions", region_records)):
            items = structured.get(key) or []
            normalized = []
            for item in items:
                if isinstance(item, dict):
                    normalized.append(
                        {
                            "name": item.get("name") or item.get("segment"),
                            "amount": item.get("amount"),
                            "ratio": item.get("ratio"),
                        }
                    )
            if normalized:
                target.append(
                    {
                        "fiscal_period": period,
                        "report_type": report_type,
                        "source_type": source_type,
                        "source_url": source_url,
                        "extracted_at": extracted_at,
                        "items": normalized,
                    }
                )

    def compare(self, companies: List[str], queries: List[str]) -> dict:
        """Discover and compare exactly two companies."""
        if len(companies) != 2:
            raise ValueError(
                "comparison currently supports exactly two companies"
            )
        if len(queries) != 2:
            raise ValueError(
                "companies and queries must have the same length: "
                f"{len(companies)} != {len(queries)}"
            )
        per_company = {}
        citations_by_company = {}
        for company, query in zip(companies, queries, strict=True):
            result = self.analyze_company(company, query)
            per_company[company] = result["analysis"]
            citations_by_company[company] = result["citations"]

        comparison = None
        if len(per_company) == 2:
            names = list(per_company)
            comparison = compare_companies(per_company[names[0]], per_company[names[1]])

        report_md = generate_markdown_report(
            title=f"{' vs '.join(companies)} 财务对比报告",
            companies=companies,
            analysis={},
            comparison=comparison,
            citations=[
                c
                for company_cites in citations_by_company.values()
                for c in company_cites
            ],
        )
        return {
            "report": report_md,
            "comparison": comparison,
            "analysis": per_company,
            "citations_by_company": citations_by_company,
        }
