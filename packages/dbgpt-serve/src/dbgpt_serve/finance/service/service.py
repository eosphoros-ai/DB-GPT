"""Business service for the finance research module.

Wraps the standalone ``finance_research`` core package and exposes it to the
serve layer.
"""

import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from dbgpt.component import BaseComponent, SystemApp

from ..config import SERVE_SERVICE_COMPONENT_NAME, ServeConfig

logger = logging.getLogger(__name__)


def _import_core():
    """Import the standalone ``finance_research`` core package.

    The core package lives at the repository root, so we add it to ``sys.path``
    as a fallback when it is not installed as a workspace package.
    """
    try:
        from finance_research.pipeline import FinancePipeline
        from finance_research.search import get_search_provider
        from finance_research.store import Store
    except ImportError:
        _ROOT = str(Path(__file__).resolve().parents[6])
        if _ROOT not in sys.path:
            sys.path.insert(0, _ROOT)
        from finance_research.pipeline import FinancePipeline
        from finance_research.search import get_search_provider
        from finance_research.store import Store
    return FinancePipeline, get_search_provider, Store


class Service(BaseComponent):
    """Service that runs the public finance research pipeline."""

    name = SERVE_SERVICE_COMPONENT_NAME

    def __init__(self, system_app: SystemApp, config: Optional[ServeConfig] = None):
        super().__init__(system_app)
        self._system_app = system_app
        self._config = config or ServeConfig()
        self._pipeline: Optional[Any] = None
        self._store: Optional[Any] = None

    def init_app(self, system_app: SystemApp):
        self._system_app = system_app

    @property
    def config(self) -> ServeConfig:
        """Return the internal ServeConfig."""
        return self._config

    def _ensure_pipeline(self):
        if self._pipeline is None:
            FinancePipeline, get_search_provider, Store = _import_core()
            self._store = Store(self._config.db_path)
            provider = get_search_provider(self._config.search_provider)
            self._pipeline = FinancePipeline(
                store=self._store,
                search_provider=provider,
                max_results=self._config.max_results,
            )
        return self._pipeline

    def analyze_company(
        self,
        company: str,
        query: Optional[str] = None,
        uploaded_files: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict:
        """Run the full chain for a single company and return report + citations."""
        query = query or f"{company} 年报 财报 营业收入 净利润"
        pipeline = self._ensure_pipeline()
        result = pipeline.analyze_company(
            company, query=query, uploaded_files=uploaded_files
        )
        return {
            "company": company,
            "report": result["report"],
            "metrics": self._build_metrics(result["citations"]),
            "segments": result.get("segments", []),
            "regions": result.get("regions", []),
            "citations": result["citations"],
        }

    def compare_companies(
        self, companies: List[str], queries: Optional[List[str]] = None
    ) -> Dict:
        """Discover and compare multiple companies."""
        if len(companies) != 2:
            raise ValueError("comparison currently supports exactly two companies")
        queries = queries or [f"{c} 年报 财报 营业收入 净利润" for c in companies]
        if len(queries) != len(companies):
            raise ValueError("companies and queries must have the same length")
        pipeline = self._ensure_pipeline()
        result = pipeline.compare(companies, queries)

        metrics_by_company = {}
        for company in companies:
            citations = result.get("citations_by_company", {}).get(company, [])
            metrics_by_company[company] = self._build_metrics(citations)

        comparison = []
        if result.get("comparison") is not None and not result["comparison"].empty:
            comparison = result["comparison"].to_dict(orient="records")
        return {
            "companies": companies,
            "report": result["report"],
            "comparison": comparison,
            "metrics": metrics_by_company,
        }

    @staticmethod
    def _build_metrics(citations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Group flat citations into per-metric provenance-rich series.

        Annual and quarterly rows are kept as separate series (the quarterly
        ones get a ``(quarterly)`` suffix). Each metric carries ``latest_yoy``
        (annual) or ``latest_qoq`` (quarterly) computed from the last two
        available values.
        """
        by_key: Dict[tuple, List[Dict[str, Any]]] = defaultdict(list)
        for cite in citations:
            report_type = cite.get("report_type") or "annual"
            name = cite.get("metric") or "unknown"
            by_key[(name, report_type)].append(cite)

        metrics: List[Dict[str, Any]] = []
        for (name, report_type), rows in by_key.items():
            rows_sorted = sorted(rows, key=lambda r: str(r.get("fiscal_period") or ""))
            points = [
                {
                    "fiscal_period": r.get("fiscal_period"),
                    "value": r.get("metric_value"),
                    "source_type": r.get("source_type"),
                    "source_url": r.get("source_url"),
                    "source_file": r.get("source_file"),
                    "page": r.get("page"),
                    "table_name": r.get("table_name"),
                    "evidence": r.get("evidence"),
                    "extracted_at": r.get("extracted_at"),
                }
                for r in rows_sorted
            ]
            values = [
                r.get("metric_value")
                for r in rows_sorted
                if r.get("metric_value") is not None
            ]
            pct = None
            if len(values) >= 2 and values[-2] != 0:
                pct = (values[-1] - values[-2]) / abs(values[-2]) * 100

            label = name if report_type == "annual" else f"{name} ({report_type})"
            latest_yoy = pct if report_type == "annual" else None
            latest_qoq = pct if report_type == "quarterly" else None
            metrics.append(
                {
                    "name": label,
                    "report_type": report_type,
                    "latest_yoy": latest_yoy,
                    "latest_qoq": latest_qoq,
                    "points": points,
                }
            )
        return metrics
