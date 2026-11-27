"""Official close verification via SSE, SZSE, and HKEX Main Board daily reports."""

import asyncio
import html
import logging
import re
from collections import OrderedDict
from datetime import date, datetime
from decimal import DecimalException
from time import monotonic
from typing import NamedTuple, Optional
from weakref import WeakValueDictionary

import httpx

from .models import BEIJING, Listing, Quote, number

logger = logging.getLogger(__name__)

SSE_API = "https://yunhq.sse.com.cn:32042/v1/sh1"
SZSE_API = "https://www.szse.cn/api/market/ssjjhq"
HKEX_DIR = "https://www.hkex.com.hk/eng/stat/smstat/dayquot/"
SNAP_FIELDS = "code,name,date,time,open,high,low,last,prev_close,volume,amount"
DAY_FIELDS = "date,open,high,low,close,volume,amount"


def exchange_page_url(item: Listing, fallback: str = "") -> str:
    """Return a human-readable exchange quote web page URL for a listing."""
    if item.market == "sh":
        if item.asset_type == "etf":
            return (
                "https://www.sse.com.cn/assortment/fund/list/etfinfo/basic/"
                f"index.shtml?FUNDID={item.code}"
            )
        return (
            "https://www.sse.com.cn/assortment/stock/list/info/company/"
            f"index.shtml?COMPANY_CODE={item.code}"
        )
    if item.market == "sz":
        return f"https://www.szse.cn/market/trend/index.html?code={item.code}"
    if item.market == "hk" and item.code.isdigit():
        return (
            "https://www.hkex.com.hk/Market-Data/Securities-Prices/Equities/"
            f"Equities-Quote?sym={int(item.code)}&sc_lang=zh-HK"
        )
    return fallback


SOURCE_ERRORS = (
    httpx.HTTPError,
    ValueError,
    KeyError,
    IndexError,
    TypeError,
    AttributeError,
    DecimalException,
)


async def mainland_snapshot(
    client: httpx.AsyncClient, item: Listing
) -> Optional[Quote]:
    if item.market not in {"sh", "sz"}:
        return None
    try:
        if item.market == "sh":
            r = await client.get(
                f"{SSE_API}/snap/{item.code}", params={"select": SNAP_FIELDS}
            )
            r.raise_for_status()
            a = r.json()["snap"]
            if a[0] != item.code:
                return None
            stamp = datetime.strptime(f"{a[2]}{str(a[3]).zfill(6)}", "%Y%m%d%H%M%S")
            name, opening, high, low, last, previous, turnover = a[1], *a[4:9], a[10]
            suspended = False
        else:
            r = await client.get(
                f"{SZSE_API}/getTimeData", params={"marketId": 1, "code": item.code}
            )
            r.raise_for_status()
            d = r.json()["data"]
            if d["code"] != item.code:
                return None
            stamp = datetime.fromisoformat(d["marketTime"])
            keys = ("name", "open", "high", "low", "now", "close", "amount")
            name, opening, high, low, last, previous, turnover = (
                d.get(k) for k in keys
            )
            suspended = d.get("status") in ("停牌", "SUSPENDED")
        q = Quote(
            listing=item.model_copy(update={"name": name or item.name}),
            day=stamp.date(),
            as_of=stamp.replace(tzinfo=BEIJING),
            source="上交所" if item.market == "sh" else "深交所",
            url=exchange_page_url(item, str(r.url)),
            last=number(last, positive=True),
            previous=number(previous, positive=True),
            opening=number(opening, positive=True),
            high=number(high, positive=True),
            low=number(low, positive=True),
            turnover=number(turnover),
            suspended=suspended,
        )
        if q.turnover is not None and q.turnover < 0:
            q.turnover = None
        q.calculate()
        return q if q.last is not None or q.suspended else None
    except SOURCE_ERRORS as exc:
        logger.debug("Mainland snapshot failed for %s: %s", item.symbol, exc)
        return None


async def daily_close(client: httpx.AsyncClient, item: Listing, day: date):
    if item.market not in {"sh", "sz"}:
        return None
    try:
        if item.market == "sh":
            resp = await client.get(
                f"{SSE_API}/dayk/{item.code}",
                params={"select": DAY_FIELDS, "begin": -3, "end": -1},
            )
            resp.raise_for_status()
            data = resp.json()
            if data["code"] != item.code:
                return None
            rows, key, col = data["kline"], day.strftime("%Y%m%d"), 4
        else:
            resp = await client.get(
                f"{SZSE_API}/getHistoryData",
                params={"marketId": 1, "code": item.code, "cycleType": 32},
            )
            resp.raise_for_status()
            data = resp.json()["data"]
            if data["code"] != item.code:
                return None
            rows, key, col = data["picupdata"], day.isoformat(), 2
        for row in reversed(rows):
            if str(row[0]) == key:
                close = number(row[col], positive=True)
                return (
                    (close, exchange_page_url(item, str(resp.url)))
                    if close is not None
                    else None
                )
    except SOURCE_ERRORS as exc:
        logger.debug("Daily close failed for %s: %s", item.symbol, exc)
    return None


HKEX_MONTHS = "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split()
HKEX_HEADER = re.compile(
    r"""<a\s+name\s*=\s*["']quotations["']\s*>QUOTATIONS</a>""", re.I
)
HKEX_NEXT = re.compile(r"<a\s+name\s*=", re.I)
HKEX_FIRST = re.compile(
    r"^\s*[*#@ +\-]*\s*(\d{1,5})\s+(.+?)\s+(HKD|CNY|RMB|USD)"
    r"\s+(\S+)\s+\S+\s+(\S+)\s+\S+\s*$"
)
HKEX_SECOND = re.compile(r"^\s+(\S+)\s+\S+\s+(\S+)\s+(\S+)\s*$")


class _DailyRow(NamedTuple):
    name: str
    previous: str
    high: str
    last: str
    low: str
    turnover: str


def parse_hkex_daily(text: str, day: date) -> dict[tuple[str, str], _DailyRow]:
    stamp = re.search(r"DATE:\s*(\d{1,2})\s+([A-Z]{3})\s+(\d{4})", text[:20000])
    section = HKEX_HEADER.search(text)
    if (
        not stamp
        or not section
        or (int(stamp[1]), stamp[2], int(stamp[3]))
        != (day.day, HKEX_MONTHS[day.month - 1], day.year)
    ):
        return {}
    end = HKEX_NEXT.search(text, section.end())
    body = text[section.end() : end.start() if end else len(text)]
    result: dict[tuple[str, str], _DailyRow] = {}
    first = None
    for line in body.splitlines():
        if first and (second := HKEX_SECOND.fullmatch(line)):
            code, name, ccy, previous, high = first.groups()
            currency = "CNY" if ccy == "RMB" else ccy
            result[code.zfill(5), currency] = _DailyRow(
                name, previous, high, *second.groups()
            )
            first = None
            continue
        first = HKEX_FIRST.fullmatch(line)
    return result


class DailyReports:
    """Cache HKEX daily quotation indexes and coalesce concurrent downloads."""

    def __init__(self):
        self.cache: OrderedDict[date, tuple[float, dict]] = OrderedDict()
        self.locks: WeakValueDictionary = WeakValueDictionary()

    async def get(
        self, client: httpx.AsyncClient, day: date, item: Listing
    ) -> Optional[Quote]:
        lock = self.locks.setdefault((asyncio.get_running_loop(), day), asyncio.Lock())
        async with lock:
            entry = self.cache.get(day)
            if entry is None or (not entry[1] and monotonic() - entry[0] > 60):
                self.cache[day] = (monotonic(), await self._load(client, day))
                self.cache.move_to_end(day)
                if len(self.cache) > 5:
                    self.cache.popitem(last=False)
            row = self.cache[day][1].get((item.code, item.currency))
        if row is None or (last := number(row.last, positive=True)) is None:
            return None
        quote = Quote(
            listing=item.model_copy(update={"name": html.unescape(row.name)}),
            day=day,
            source="港交所",
            url=exchange_page_url(item, HKEX_DIR + day.strftime("d%y%m%de.htm")),
            last=last,
            previous=number(row.previous, positive=True),
            high=number(row.high, positive=True),
            low=number(row.low, positive=True),
            turnover=number(row.turnover),
        )
        quote.calculate()
        return quote

    @staticmethod
    async def _load(client: httpx.AsyncClient, day: date) -> dict:
        name = day.strftime("d%y%m%de.htm")
        try:
            directory = await client.get(HKEX_DIR + "qtn.asp")
            directory.raise_for_status()
            pattern = rf"""href\s*=\s*['"](?:[^'"]*/)?{re.escape(name)}['"]"""
            if not re.search(pattern, directory.text, re.I):
                return {}
            # HKEX full daily bulletins are ~25 MB uncompressed; allow 15s read.
            response = await client.get(HKEX_DIR + name, timeout=15)
            response.raise_for_status()
            return await asyncio.to_thread(
                parse_hkex_daily, response.content.decode("latin1"), day
            )
        except SOURCE_ERRORS as exc:
            logger.warning("HKEX daily report load failed for %s: %s", day, exc)
            return {}


DAILY_REPORTS = DailyReports()
