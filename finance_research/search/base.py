"""Search provider abstraction for public financial data discovery."""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SearchResult(BaseModel):
    """A single search result with provenance-friendly metadata.

    ``structured`` carries a provider pre-parsed payload so structured data
    sources (e.g. Eastmoney) can flow exact values into the pipeline without
    relying on text/LLM extraction. Expected keys (all optional, amounts in
    100-million yuan, ratios in percent):

        fiscal_period, report_type, revenue, gross_profit, net_profit,
        gross_margin, net_margin, operating_cash_flow, revenue_yoy,
        net_profit_yoy, revenue_qoq, net_profit_qoq,
        segments: [{name, amount, ratio}], regions: [{name, amount, ratio}]
    """

    title: str = Field(..., description="Result title.")
    url: str = Field(..., description="Result URL.")
    snippet: str = Field("", description="Search snippet.")
    source: str = Field("search", description="Search provider name.")
    snippet_only: bool = Field(
        False,
        description=(
            "True when the snippet is the full available content (offline/mock), "
            "so the pipeline should skip network fetching."
        ),
    )
    structured: Optional[Dict[str, Any]] = Field(
        None, description="Provider pre-parsed structured financial data."
    )


class SearchProvider(ABC):
    """Abstract interface for pluggable search backends."""

    name: str = "base"

    @abstractmethod
    def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        """Return up to ``num_results`` results for ``query``."""


class BaiduSearchProvider(SearchProvider):
    """Baidu search via HTML scraping (no API key required).

    Baidu returns redirect links (``/link?url=...``) rather than the real
    source URLs; where possible the real URL is recovered from the result's
    ``data-landurl`` / ``mu`` attributes. Results are marked ``snippet_only``
    so the pipeline uses the reliable search snippet as evidence instead of
    fetching the (often JS-redirected) target page.
    """

    name = "baidu"

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://www.baidu.com/",
    }

    @staticmethod
    def _resolve_url(link_tag) -> str:
        """Recover the real destination URL from a Baidu result anchor."""
        real = link_tag.get("data-landurl") or link_tag.get("mu")
        return real or link_tag.get("href") or ""

    def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        import re

        import requests
        from bs4 import BeautifulSoup

        if num_results <= 0:
            return []
        session = requests.Session()
        session.headers.update(self.HEADERS)
        try:
            resp = session.get(
                "https://www.baidu.com/s",
                params={"wd": query, "rn": max(num_results, 8)},
                timeout=15,
            )
        except requests.RequestException as exc:
            logger.warning("Baidu search request failed: %s", exc)
            return []
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        results: List[SearchResult] = []
        for block in soup.find_all("div", class_=re.compile("^result")):
            title_tag = block.find("h3")
            link_tag = title_tag.find("a", href=True) if title_tag else None
            if not title_tag or not link_tag:
                continue
            snippet_tag = block.find(
                "span", class_=re.compile("^(content-right_|c-abstract)")
            )
            snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
            results.append(
                SearchResult(
                    title=title_tag.get_text(strip=True),
                    url=self._resolve_url(link_tag),
                    snippet=snippet,
                    source=self.name,
                    snippet_only=True,
                )
            )
        if not results:
            logger.warning(
                "Baidu returned no parseable results for query %r "
                "(possible anti-bot verification).",
                query,
            )
        return results[:num_results]


class EastmoneySearchProvider(SearchProvider):
    """Structured A-share financial data via the Eastmoney public data API.

    Unlike a text search engine, this returns one synthetic result per fiscal
    period whose ``structured`` payload carries exact, machine-readable values
    (revenue, gross/net profit, gross/net margin, operating cash flow, YoY,
    QoQ, and segment/region revenue). Annual and quarterly periods are both
    emitted so the pipeline can compute yearly trends, YoY and QoQ. The source
    URL points to the Eastmoney F10 financial-analysis page so every metric
    stays traceable.
    """

    name = "eastmoney"

    SUGGEST_URL = "https://searchapi.eastmoney.com/api/suggest/get"
    DATA_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    COMPOSITION_URL = (
        "https://emweb.securities.eastmoney.com/PC_HSF10/BusinessAnalysis/PageAjax"
    )
    SUGGEST_TOKEN = "D43BF722C8E33BDC906FB84D85E326E8"
    F10_URL = (
        "https://emweb.securities.eastmoney.com/PC_HSF10/"
        "NewFinanceAnalysis/Index?type=web&code={market_code}"
    )

    def _resolve(self, query: str):
        """Resolve a company name (or 6-digit code) to (code, secucode, name)."""
        import re

        import requests

        # If the query already looks like a 6-digit stock code, use it directly.
        match = re.search(r"\b(\d{6})\b", query)
        if match:
            code = match.group(1)
            suffix = "SH" if code.startswith(("6", "9")) else "SZ"
            return code, f"{code}.{suffix}", query

        # Strip search noise so the suggest API sees a bare company name.
        clean = re.sub(
            r"(年报|季报|中报|财报|公告|报告|营业收入|净利润|营收|净利|"
            r"现金流|经营|分析|对比|财务|年度|数据)",
            " ",
            query,
        )
        clean = re.sub(r"\s+", " ", clean).strip() or query

        try:
            resp = requests.get(
                self.SUGGEST_URL,
                params={
                    "input": clean,
                    "type": "14",
                    "token": self.SUGGEST_TOKEN,
                    "count": "5",
                },
                timeout=15,
            )
            items = resp.json().get("QuotationCodeTable", {}).get("Data", []) or []
        except Exception as exc:  # noqa: BLE001 - network resilience
            logger.warning("Eastmoney suggest failed for %r: %s", query, exc)
            return None
        hk_fallback = None
        for item in items:
            code = str(item.get("Code", ""))
            name = item.get("Name", query)
            classify = str(item.get("Classify", ""))
            sec_type = str(item.get("SecurityTypeName", ""))
            if classify == "AStock" or sec_type.endswith("A"):
                suffix = "SH" if str(item.get("MktNum", "1")) == "1" else "SZ"
                return code, f"{code}.{suffix}", name
            if classify == "HK":
                # Prefer the ordinary share: skip warrants (购/沽/牛/熊) and the
                # RMB counter (-R / -WR / -RS) which duplicates the main line.
                if name and (
                    "购" in name
                    or "沽" in name
                    or "牛" in name
                    or "熊" in name
                    or name.endswith(("-R", "-WR", "-RS"))
                ):
                    if hk_fallback is None:
                        hk_fallback = (code, f"{code}.HK", name)
                    continue
                return code, f"{code}.HK", name
        if hk_fallback:
            return hk_fallback
        return None

    def _fetch(self, report_name: str, secucode: str) -> dict:
        """Fetch one Eastmoney datacenter report keyed by ``REPORT_DATE``."""
        import requests

        try:
            resp = requests.get(
                self.DATA_URL,
                params={
                    "reportName": report_name,
                    "columns": "ALL",
                    "filter": f'(SECUCODE="{secucode}")',
                    "pageNumber": "1",
                    "pageSize": "60",
                    "sortColumns": "REPORT_DATE",
                    "sortTypes": "-1",
                },
                timeout=20,
            )
            data = resp.json().get("result", {}).get("data", []) or []
        except Exception as exc:  # noqa: BLE001 - network resilience
            logger.warning("Eastmoney fetch %s failed: %s", report_name, exc)
            return {}
        return {str(row.get("REPORT_DATE", ""))[:10]: row for row in data}

    def _fetch_composition(self, market_code: str) -> dict:
        """Fetch 主营构成 (main business composition) grouped by report date.

        Returns ``{date: {"segments": [...], "regions": [...]}}`` where each
        entry is ``{"name", "amount" (亿), "ratio" (%)}``. Eastmoney's
        ``MAINOP_TYPE`` maps 2 -> 按产品 (business segment) and 3 -> 按地区
        (region).
        """
        import requests

        by_date: Dict[str, Dict[str, list]] = {}
        try:
            resp = requests.get(
                self.COMPOSITION_URL, params={"code": market_code}, timeout=20
            )
            items = resp.json().get("zygcfx", []) or []
        except Exception as exc:  # noqa: BLE001 - network resilience
            logger.warning("Eastmoney composition fetch failed: %s", exc)
            return by_date
        for item in items:
            date = str(item.get("REPORT_DATE", ""))[:10]
            mtype = str(item.get("MAINOP_TYPE", ""))
            name = item.get("ITEM_NAME")
            amount = item.get("MAIN_BUSINESS_INCOME")
            ratio = item.get("MBI_RATIO")
            if not name or amount is None:
                continue
            entry = {
                "name": name,
                "amount": amount / 1e8,
                "ratio": (ratio * 100) if ratio is not None else None,
            }
            bucket = by_date.setdefault(date, {"segments": [], "regions": []})
            if mtype == "2":  # 按产品 = 分业务收入
                bucket["segments"].append(entry)
            elif mtype == "3":  # 按地区 = 分地区收入
                bucket["regions"].append(entry)
        return by_date

    @staticmethod
    def _to_q(date: str) -> str:
        """Map a period date (``2025-12-31``) to a quarter label (``2025Q4``)."""
        quarter = {"03-31": "Q1", "06-30": "Q2", "09-30": "Q3", "12-31": "Q4"}
        return f"{date[:4]}{quarter.get(date[5:], '')}"

    def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        resolved = self._resolve(query)
        if not resolved:
            return []
        code, secucode, name = resolved
        if secucode.endswith(".HK"):
            return self._search_hk(name, secucode, num_results)
        return self._search_a(name, secucode, num_results)

    def _search_a(self, name: str, secucode: str, num_results: int) -> List[SearchResult]:
        """Search A-share financials via the main finance + composition reports."""
        market_code = secucode.split(".")[1] + secucode.split(".")[0]

        main = self._fetch("RPT_F10_FINANCE_MAINFINADATA", secucode)
        composition = self._fetch_composition(market_code)

        def _yi(value):
            """Convert an Eastmoney raw amount (yuan) to 100-million (亿)."""
            return None if value is None else value / 1e8

        def _single(field: str) -> dict:
            """Derive single-quarter values for a cumulative (YTD) field.

            Chinese A-share interim figures are year-to-date. The first quarter
            of each year is already single-quarter; other quarters are recovered
            by differencing the previous cumulative period. ``prev`` resets at
            each year boundary and whenever a value is missing so a stale
            carry-over never spans multiple quarters or years.
            """
            out: Dict[str, Optional[float]] = {}
            prev: Optional[float] = None
            prev_year: Optional[str] = None
            for date in sorted(main):
                val = main[date].get(field)
                if val is None:
                    out[date] = None
                    prev, prev_year = None, None
                    continue
                year = date[:4]
                new_year = prev_year != year
                out[date] = val if (new_year or prev is None) else (val - prev)
                prev, prev_year = val, year
            return out

        single_rev = _single("TOTALOPERATEREVE")
        single_net = _single("PARENTNETPROFIT")

        results: List[SearchResult] = []
        emitted = 0
        for date in sorted(main, reverse=True):
            mrow = main[date]
            year = date[:4]
            rev_yi = _yi(mrow.get("TOTALOPERATEREVE"))
            if rev_yi is None:
                continue
            net_yi = _yi(mrow.get("PARENTNETPROFIT"))
            cash_yi = _yi(mrow.get("NETCASH_OPERATE_PK"))
            gross_yi = _yi(mrow.get("MLR"))
            gross_margin = mrow.get("XSMLL")
            net_margin = mrow.get("XSJLL")
            rev_yoy = mrow.get("TOTALOPERATEREVETZ")
            net_yoy = mrow.get("PARENTNETPROFITTZ")
            rev_qoq = mrow.get("DJD_TOI_QOQ")
            net_qoq = mrow.get("DJD_DPNP_QOQ")
            comp = composition.get(date, {"segments": [], "regions": []})

            # Emit an annual result for every year-end period, plus a quarterly
            # result for each quarter (Q1-Q4) so QoQ chains are complete.
            for report_type, period, use_rev, use_net in self._periods(
                date, year, rev_yi, net_yi, single_rev, single_net
            ):
                structured = {
                    "fiscal_period": period,
                    "report_type": report_type,
                    "revenue": use_rev,
                    "gross_profit": gross_yi if report_type == "annual" else None,
                    "net_profit": use_net,
                    "gross_margin": gross_margin if report_type == "annual" else None,
                    "net_margin": net_margin if report_type == "annual" else None,
                    "operating_cash_flow": cash_yi if report_type == "annual" else None,
                    "revenue_yoy": rev_yoy if report_type == "annual" else None,
                    "net_profit_yoy": net_yoy if report_type == "annual" else None,
                    "revenue_qoq": rev_qoq if report_type == "quarterly" else None,
                    "net_profit_qoq": net_qoq if report_type == "quarterly" else None,
                    "segments": comp["segments"],
                    "regions": comp["regions"],
                }

                title = (
                    f"{name} {year} 年度报告"
                    if report_type == "annual"
                    else f"{name} {period} 季报"
                )
                fragments = []
                if use_rev is not None:
                    fragments.append(f"营业收入 {use_rev:.2f} 亿元")
                if use_net is not None:
                    fragments.append(f"净利润 {use_net:.2f} 亿元")
                if report_type == "annual":
                    if gross_margin is not None:
                        fragments.append(f"毛利率 {gross_margin:.2f}%")
                    if net_margin is not None:
                        fragments.append(f"净利率 {net_margin:.2f}%")
                snippet = (
                    f"{name} {period} " + "，".join(fragments) + "。"
                    if fragments
                    else f"{name} {period}。"
                )

                results.append(
                    SearchResult(
                        title=title,
                        url=self.F10_URL.format(market_code=market_code),
                        snippet=snippet,
                        source=self.name,
                        snippet_only=True,
                        structured=structured,
                    )
                )
                emitted += 1
                if emitted >= num_results:
                    return results
        return results

    def _search_hk(self, name: str, secucode: str, num_results: int) -> List[SearchResult]:
        """Search Hong-Kong-listed financials via the HK main-indicator report.

        HK filings use ``RPT_HKF10_FN_GMAININDICATOR`` whose field names differ
        from the A-share report (``OPERATE_INCOME``, ``HOLDER_PROFIT``, etc.)
        and whose ``REPORT_TYPE`` marks ``/FY`` (annual), ``/Q1``, ``/Q6``
        (interim) and ``/Q9`` periods. Margins are already percentages, and no
        total operating-cash-flow field is exposed, so that metric is omitted.
        """
        main = self._fetch("RPT_HKF10_FN_GMAININDICATOR", secucode)
        code = secucode.split(".")[0]
        f10_url = f"https://quote.eastmoney.com/hk/{code}.html"

        def _yi(value):
            return None if value is None else value / 1e8

        def _single(field: str) -> dict:
            out: Dict[str, Optional[float]] = {}
            prev: Optional[float] = None
            prev_year: Optional[str] = None
            for date in sorted(main):
                val = main[date].get(field)
                if val is None:
                    out[date] = None
                    prev, prev_year = None, None
                    continue
                year = date[:4]
                new_year = prev_year != year
                out[date] = val if (new_year or prev is None) else (val - prev)
                prev, prev_year = val, year
            return out

        single_rev = _single("OPERATE_INCOME")
        single_net = _single("HOLDER_PROFIT")

        results: List[SearchResult] = []
        emitted = 0
        for date in sorted(main, reverse=True):
            mrow = main[date]
            year = date[:4]
            rt = str(mrow.get("REPORT_TYPE", ""))
            rev_yi = _yi(mrow.get("OPERATE_INCOME"))
            if rev_yi is None:
                continue
            net_yi = _yi(mrow.get("HOLDER_PROFIT"))
            gross_yi = _yi(mrow.get("GROSS_PROFIT"))
            gross_margin = mrow.get("GROSS_PROFIT_RATIO")
            net_margin = mrow.get("NET_PROFIT_RATIO")

            if "/FY" in rt:
                report_type, period = "annual", year
                use_rev, use_net = rev_yi, net_yi
            else:
                q_map = {"Q1": "Q1", "Q6": "Q2", "Q9": "Q3"}
                q = next((v for k, v in q_map.items() if f"/{k}" in rt), "Q1")
                report_type, period = "quarterly", f"{year}{q}"
                use_rev = _yi(single_rev.get(date))
                use_net = _yi(single_net.get(date))

            structured = {
                "fiscal_period": period,
                "report_type": report_type,
                "revenue": use_rev,
                "gross_profit": gross_yi if report_type == "annual" else None,
                "net_profit": use_net,
                "gross_margin": gross_margin if report_type == "annual" else None,
                "net_margin": net_margin if report_type == "annual" else None,
                "operating_cash_flow": None,
                "segments": [],
                "regions": [],
            }

            title = f"{name} {year} 年度报告" if report_type == "annual" else f"{name} {period} 季报"
            fragments = []
            if use_rev is not None:
                fragments.append(f"营业收入 {use_rev:.2f} 亿元")
            if use_net is not None:
                fragments.append(f"净利润 {use_net:.2f} 亿元")
            if report_type == "annual":
                if gross_margin is not None:
                    fragments.append(f"毛利率 {gross_margin:.2f}%")
                if net_margin is not None:
                    fragments.append(f"净利率 {net_margin:.2f}%")
            snippet = (
                f"{name} {period} " + "，".join(fragments) + "。"
                if fragments
                else f"{name} {period}。"
            )

            results.append(
                SearchResult(
                    title=title,
                    url=f10_url,
                    snippet=snippet,
                    source=self.name,
                    snippet_only=True,
                    structured=structured,
                )
            )
            emitted += 1
            if emitted >= num_results:
                return results
        return results

    @staticmethod
    def _periods(
        date: str,
        year: str,
        rev_yi: Optional[float],
        net_yi: Optional[float],
        single_rev: Dict[str, Optional[float]],
        single_net: Dict[str, Optional[float]],
    ):
        """Yield ``(report_type, period, revenue, net_profit)`` tuples.

        A year-end date yields both an annual result and a Q4 quarterly result;
        every other date yields a single quarterly result.
        """
        def _yi(v):
            return None if v is None else v / 1e8

        if date.endswith("-12-31"):
            yield "annual", year, rev_yi, net_yi
            yield "quarterly", f"{year}Q4", _yi(single_rev.get(date)), _yi(
                single_net.get(date)
            )
        else:
            q = EastmoneySearchProvider._to_q(date)
            yield "quarterly", q, _yi(single_rev.get(date)), _yi(single_net.get(date))


class MockSearchProvider(SearchProvider):
    """Deterministic provider generating sample financial data (offline demo).

    When no explicit results are supplied, it synthesizes three fiscal years
    of sample financial figures from the query's company name so the demo
    produces a meaningful, traceable report without any external API.
    """

    name = "mock"

    def __init__(self, results: Optional[List[SearchResult]] = None):
        self._results = results

    def search(self, query: str, num_results: int = 10) -> List[SearchResult]:
        if self._results is not None:
            return [
                r.model_copy(update={"snippet_only": True})
                for r in self._results[:num_results]
            ]
        return self._generate(query, num_results)

    @staticmethod
    def _generate(query: str, num_results: int) -> List[SearchResult]:
        import re

        company = re.split(r"[年报季度财报\s]", query)[0].strip() or "示例公司"
        results = []
        base = 100.0
        for i, year in enumerate((2022, 2023, 2024)):
            revenue = base * (1 + 0.15 * i)
            net_profit = revenue * 0.12
            gross_profit = revenue * 0.40
            cash_flow = revenue * 0.15
            snippet = (
                f"{company} {year} 年营业收入 {revenue:.0f} 亿元，"
                f"净利润 {net_profit:.0f} 亿元，毛利 {gross_profit:.0f} 亿元，"
                f"经营活动现金流净额 {cash_flow:.0f} 亿元。"
            )
            results.append(
                SearchResult(
                    title=f"{company} {year} 年度报告",
                    url=f"https://example.com/{year}-annual.pdf",
                    snippet=snippet,
                    source=MockSearchProvider.name,
                    snippet_only=True,
                )
            )
        return results[:num_results]


def get_search_provider(name: str, **kwargs) -> SearchProvider:
    """Factory to build a search provider from a config name."""
    providers = {
        "baidu": BaiduSearchProvider,
        "mock": MockSearchProvider,
        "eastmoney": EastmoneySearchProvider,
    }
    if name not in providers:
        raise ValueError(f"Unknown search provider: {name}")
    return providers[name](**kwargs)
