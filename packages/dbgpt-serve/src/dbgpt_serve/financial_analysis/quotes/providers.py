"""Tencent quote/symbol resolution and Eastmoney A-share sector quotes."""

import asyncio
import logging
import re
from collections.abc import Callable
from datetime import date, datetime
from decimal import DecimalException
from typing import Literal, Optional

import httpx

from .exchanges import SOURCE_ERRORS
from .models import (
    BEIJING,
    CLOCK_SKEW_TOLERANCE,
    Listing,
    Quote,
    Sector,
    SectorMover,
    SectorQuote,
    expected_day,
    number,
)

logger = logging.getLogger(__name__)

SMARTBOX = "https://smartbox.gtimg.cn/s3/"
EASTMONEY_SUGGEST = "https://searchapi.eastmoney.com/api/suggest/get"
TENCENT_QUOTE = "https://qt.gtimg.cn/q="
EASTMONEY_MEMBERS = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
EASTMONEY_DAILY = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
PAGE_SIZE = 500
QUOTE_COLUMNS = (
    "f3~05~NEW_BOARD_CODE~BOARD_PCT,f124~05~NEW_BOARD_CODE~BOARD_STAMP,"
    "f104~05~NEW_BOARD_CODE~UP,f105~05~NEW_BOARD_CODE~DOWN,"
    "f106~05~NEW_BOARD_CODE~FLAT,f3~01~SECURITY_CODE~STOCK_PCT,"
    "f124~01~SECURITY_CODE~STOCK_STAMP"
)

CODE_RE = re.compile(
    r"(?:(sh|sz|bj|hk)[.:\s-]*)?(\d{1,6})(?:[.:\s-]*(sh|sz|bj|hk))?", re.I
)
RMB_RE = re.compile(r"人民币(?:柜台)?|人民幣(?:櫃台)?|\b(?:RMB|CNY)\b", re.I)
HKD_RE = re.compile(r"港元(?:柜台)?|港币(?:柜台)?|\bHKD\b", re.I)
SECTOR_CODE_RE = re.compile(r"(?:90\.)?(BK\d{4})", re.I)
SECTOR_SUFFIX_RE = re.compile(r"(?:相关)?(?:行业板块|概念板块|板块|行业|(?<!控)股)$")

MARKETS = {
    "沪股": "sh",
    "沪市": "sh",
    "上交所": "sh",
    "Shanghai": "sh",
    "深股": "sz",
    "深市": "sz",
    "深交所": "sz",
    "Shenzhen": "sz",
    "北交所": "bj",
    "北证": "bj",
    "Beijing": "bj",
    "港股": "hk",
    "港交所": "hk",
    "H股": "hk",
    "Hong Kong": "hk",
    "H-share": "hk",
    "A股": "cn",
    "A-share": "cn",
}
SH_ETF_PREFIXES = (
    "510",
    "511",
    "512",
    "513",
    "515",
    "516",
    "518",
    "560",
    "561",
    "562",
    "563",
    "588",
)

# (market, code, canonical_name, extra_aliases)
_INDEX_SPECS: tuple[
    tuple[Literal["sh", "sz", "hk"], str, str, tuple[str, ...]], ...
] = (
    ("sh", "000001", "上证指数", ("上证综指", "沪指", "上证", "sse composite")),
    ("sz", "399001", "深证成指", ("深成指", "深指", "szse component")),
    ("sz", "399006", "创业板指", ("创业板指数", "创业板", "chinext")),
    ("sh", "000300", "沪深300", ("沪深300指数", "csi 300", "csi300")),
    ("sh", "000016", "上证50", ("sse 50",)),
    ("sh", "000905", "中证500", ("csi 500",)),
    ("sh", "000688", "科创50", ("科创50指数", "star 50")),
    ("hk", "HSI", "恒生指数", ("恒指", "hsi", "hang seng")),
    (
        "hk",
        "HSTECH",
        "恒生科技指数",
        ("恒生科技", "恒科", "恒科指", "hstech", "hang seng tech"),
    ),
    ("hk", "HSCEI", "恒生国企指数", ("国企指数", "hscei")),
)
INDICES: dict[str, Listing] = {}
INDEX_ALIASES: dict[str, Listing] = {}
for _mkt, _code, _name, _extra in _INDEX_SPECS:
    _item = Listing(market=_mkt, code=_code, name=_name, asset_type="index")
    INDICES[_item.symbol] = _item
    for _a in (_name, _item.symbol, _item.label, *_extra):
        INDEX_ALIASES[_a.casefold()] = _item

CN_CORE_INDICES = [INDICES["sh000001"], INDICES["sz399001"], INDICES["sz399006"]]
HK_CORE_INDICES = [INDICES["hkHSI"], INDICES["hkHSTECH"]]
BROAD_MARKET_ALIASES = {
    **{
        k: CN_CORE_INDICES
        for k in (
            "大盘",
            "今日大盘",
            "a股大盘",
            "沪深大盘",
            "a股",
            "沪深a股",
            "大盘指数",
            "a-share market",
        )
    },
    **{k: HK_CORE_INDICES for k in ("港股大盘", "港股指数")},
}

TECH_SECTORS = (
    Sector(code="BK1036", name="半导体"),
    Sector(code="BK0737", name="软件开发"),
    Sector(code="BK1037", name="消费电子"),
)
OPTICAL_MODULES = Sector(code="BK1136", name="光通信模块")
KNOWN_SECTORS = {
    **{s.name: s for s in TECH_SECTORS},
    "光模块": OPTICAL_MODULES,
    "光模块概念": OPTICAL_MODULES,
    "cpo": OPTICAL_MODULES,
    OPTICAL_MODULES.name: OPTICAL_MODULES,
    "optical modules": OPTICAL_MODULES,
    "semiconductors": TECH_SECTORS[0],
}
BROAD_TECH = {
    "科技",
    "科技类",
    "科技概念",
    "tech stocks",
    "technology stocks",
    "technology",
}


def mainland_security(code: str) -> tuple[Optional[str], Literal["stock", "etf"]]:
    if len(code) != 6:
        return None, "stock"
    if code.startswith(("600", "601", "603", "605", "688")):
        return "sh", "stock"
    if code.startswith(SH_ETF_PREFIXES):
        return "sh", "etf"
    if code.startswith(("000", "001", "002", "003", "300", "301")):
        return "sz", "stock"
    if code.startswith("159"):
        return "sz", "etf"
    if code.startswith(("430", "83", "87", "920")):
        return "bj", "stock"
    return None, "stock"


def qualifiers(term: str) -> tuple[str, str, str]:
    market = next(
        (v for k, v in MARKETS.items() if k.casefold() in term.casefold()), ""
    )
    currency = "CNY" if RMB_RE.search(term) else "HKD" if HKD_RE.search(term) else ""
    text = HKD_RE.sub("", RMB_RE.sub("", term))
    for label in MARKETS:
        text = re.sub(re.escape(label), "", text, flags=re.I)
    return text.strip(" ：:的()（）-"), market, currency


def direct_listing(
    text: str, market: str = "", currency: str = ""
) -> Optional[Listing]:
    cleaned = text.strip()
    if (idx := INDEX_ALIASES.get(cleaned.casefold())) is not None:
        if (
            market
            and market != idx.market
            and not (market == "cn" and idx.market in {"sh", "sz"})
        ):
            return None
        return idx
    match = CODE_RE.fullmatch(cleaned)
    if not match:
        return None
    prefix, code, suffix = match.groups()
    places = {s.lower() for s in (prefix, suffix, market) if s}
    inferred_market, asset_type = mainland_security(code)
    if "cn" in places:
        places.remove("cn")
        places.add(inferred_market or "unsupported")
    if len(places) > 1:
        return None
    venue = next(iter(places), None) or (inferred_market if len(code) == 6 else "hk")
    if venue is None and len(code) == 6 and code.startswith("399"):
        venue = "sz"
    if venue in {"sh", "sz"} and (venue + code) in INDICES:
        return INDICES[venue + code]
    if venue == "hk" and len(code) <= 5:
        code = code.zfill(5)
        ccy, asset_type = ("CNY" if code.startswith("8") else "HKD"), "stock"
    elif venue and venue == inferred_market:
        ccy = "CNY"
    else:
        return None
    if currency and currency != ccy:
        return None
    return Listing(
        market=venue, code=code, name=code, currency=ccy, asset_type=asset_type
    )


def _name_key(name: str) -> str:
    name = re.sub(r"(?:-|(?<=[\u3400-\u9fff]))(?:r|sw|w)$", "", name.casefold())
    return re.sub(r"控股$|股份有限公司$", "", name).strip()


def _exact_name(listing: Listing, text: str) -> bool:
    return _name_key(text) in {
        _name_key(listing.name),
        listing.name.casefold(),
        listing.lookup_alias.casefold(),
    }


def _match_candidates(
    items: list[Listing], text: str, market: str, currency: str
) -> list[Listing]:
    eligible = list(
        {
            i.symbol: i
            for i in items
            if (
                not market
                or i.market == market
                or (market == "cn" and i.market in {"sh", "sz", "bj"})
            )
            and (not currency or i.currency == currency)
        }.values()
    )
    if not currency:
        hkd_names = {
            _name_key(i.name)
            for i in eligible
            if i.market == "hk" and i.currency == "HKD"
        }
        eligible = [
            i
            for i in eligible
            if not (
                i.market == "hk"
                and i.currency == "CNY"
                and _name_key(i.name) in hkd_names
            )
        ]
    exact = [i for i in eligible if _exact_name(i, text)]
    if exact:
        return exact
    key = _name_key(text)
    return [i for i in eligible if key and key in i.name.casefold()]


def _parse_smartbox(body: bytes) -> list[Listing]:
    raw = re.sub(
        r"\\u([a-fA-F0-9]{4})",
        lambda m: chr(int(m[1], 16)),
        body.decode("gb18030", errors="replace"),
    )
    match = re.search(r'v_hint="([^"]*)"', raw)
    if not match:
        return []
    found = []
    for record in match[1].split("^"):
        parts = record.split("~")
        if len(parts) < 5 or not parts[4].startswith(("GP", "JJ", "ETF")):
            continue
        if listed := direct_listing(parts[1], parts[0]):
            asset = "etf" if parts[4].startswith(("JJ", "ETF")) else listed.asset_type
            found.append(
                listed.model_copy(
                    update={
                        "name": parts[2],
                        "lookup_alias": parts[3],
                        "asset_type": asset,
                    }
                )
            )
    return found


def _parse_eastmoney_equities(data: dict) -> list[Listing]:
    found = []
    for item in (data.get("QuotationCodeTable") or {}).get("Data") or []:
        cls, stype = item.get("Classify"), item.get("SecurityTypeName")
        if cls == "AStock":
            market = {"沪A": "sh", "深A": "sz", "京A": "bj"}.get(stype)
        elif cls == "HK" and stype == "港股":
            market = "hk"
        elif cls == "Fund" and stype in {"ETF", "LOF"}:
            market, _ = mainland_security(str(item.get("Code", "")))
        else:
            continue
        if (
            market
            and item.get("Name")
            and (listed := direct_listing(str(item["Code"]), market))
        ):
            found.append(
                listed.model_copy(
                    update={
                        "name": item["Name"],
                        "lookup_alias": item.get("PinYin") or "",
                    }
                )
            )
    return found


def _sector_candidates(data: dict, text: str) -> tuple[list[Sector], bool]:
    key = text.casefold()
    found = {}
    for item in (data.get("QuotationCodeTable") or {}).get("Data") or []:
        code, name = item.get("Code", ""), item.get("Name") or ""
        if (
            item.get("Classify") == "BK"
            and item.get("QuoteID") == f"90.{code}"
            and re.fullmatch(r"BK\d{4}", code)
            and name
            and (key in name.casefold() or text.upper() in (code, f"90.{code}"))
        ):
            found[code] = Sector(code=code, name=name)
    sectors = list(found.values())
    exact = [s for s in sectors if key in {s.name.casefold(), s.code.casefold()}]
    if not exact:
        exact = [s for s in sectors if s.name.rstrip("ⅠⅡⅢ").casefold() == key]
    return (exact or sectors)[:8], bool(exact)


async def resolve(
    client: httpx.AsyncClient, term: str, lookup_limit: asyncio.Semaphore
) -> tuple[list[Listing | Sector], str]:
    raw_key = term.strip().casefold()
    if raw_key in BROAD_MARKET_ALIASES:
        return list(BROAD_MARKET_ALIASES[raw_key]), "expand"
    if raw_key in INDEX_ALIASES:
        return [INDEX_ALIASES[raw_key]], ""
    text, market, currency = qualifiers(term)
    text = re.sub(r"的?股票$", "", text)
    bracket = re.search(r"[(（]\s*([^()（）]+?)\s*[)）]", term)
    if bracket and (
        CODE_RE.fullmatch(bracket[1]) or bracket[1].casefold() in INDEX_ALIASES
    ):
        text = bracket[1]
    if text.casefold() in INDEX_ALIASES:
        return [INDEX_ALIASES[text.casefold()]], ""
    if CODE_RE.fullmatch(text):
        item = direct_listing(text, market, currency)
        return ([item], "") if item else ([], "unsupported")

    scope = re.sub(r"^(?:美股|美國|美国|沪深京?|中国内地|中国大陆)(?:的)?", "", text)
    scope = SECTOR_SUFFIX_RE.sub("", scope).strip(" 的").casefold()
    code_match = SECTOR_CODE_RE.fullmatch(scope)
    sector_only = (
        scope != text.casefold()
        or bool(code_match)
        or scope in KNOWN_SECTORS
        or scope in BROAD_TECH
    )
    if sector_only and (
        market not in {"", "cn"}
        or currency not in {"", "CNY"}
        or text.startswith(("美股", "美国", "美國"))
    ):
        return [], "sector_market"
    if scope in BROAD_TECH:
        return list(TECH_SECTORS), ""
    if scope in KNOWN_SECTORS:
        return [KNOWN_SECTORS[scope]], ""
    if code_match:
        code_upper = code_match[1].upper()
        for sector in (*TECH_SECTORS, OPTICAL_MODULES):
            if sector.code == code_upper:
                return [sector], ""
    if not scope:
        return [], "sector_not_found" if sector_only else "not_found"
    async with lookup_limit:
        return await _resolve_remote(
            client, scope if sector_only else text, market, currency, sector_only
        )


async def _resolve_remote(
    client: httpx.AsyncClient, text: str, market: str, currency: str, sector_only: bool
) -> tuple[list[Listing | Sector], str]:
    errors, partial = 0, []
    if not sector_only:
        try:
            resp = await client.get(SMARTBOX, params={"q": text, "t": "all"})
            resp.raise_for_status()
            partial = _match_candidates(
                _parse_smartbox(resp.content), text, market, currency
            )
            if any(_exact_name(i, text) for i in partial):
                return partial, ""
        except SOURCE_ERRORS as exc:
            logger.debug("Smartbox lookup failed for %s: %s", text, exc)
            errors += 1
    try:
        resp = await client.get(
            EASTMONEY_SUGGEST, params={"input": text, "type": 14, "count": 80}
        )
        resp.raise_for_status()
        data = resp.json()
        sectors, exact_board = _sector_candidates(data, text)
        if sector_only:
            return sectors, "" if sectors else "sector_not_found"
        candidates = _match_candidates(
            _parse_eastmoney_equities(data), text, market, currency
        )
        if any(_exact_name(i, text) for i in candidates):
            return candidates, ""
        partial = partial or candidates
        if sectors and (
            exact_board or not partial or any(s.name == text + "概念" for s in sectors)
        ):
            if market not in {"", "cn"} or currency not in {"", "CNY"}:
                return [], "sector_market"
            return sectors, ""
    except SOURCE_ERRORS as exc:
        logger.debug("Eastmoney suggest failed for %s: %s", text, exc)
        errors += 1
    if partial:
        return partial, ""
    err_key = "sector_lookup_failed" if sector_only else "lookup_failed"
    miss_key = "sector_not_found" if sector_only else "not_found"
    return [], err_key if errors else miss_key


def parse_tencent(body: bytes, requested: dict[str, Listing]) -> dict[str, Quote]:
    quotes: dict[str, Quote] = {}
    decoded = body.decode("gb18030", errors="replace")
    for symbol, raw in re.findall(
        r'v_((?:sh|sz|bj|hk)[A-Za-z0-9]+)="([^"]*)"', decoded
    ):
        item = requested.get(symbol)
        if item is None:
            continue
        f = raw.split("~")
        hk = item.market == "hk"
        try:
            if f[2].upper() != item.code.upper():
                continue
            kind = (f[63] if hk else f[61]) if len(f) > (63 if hk else 61) else ""
            ccy = (f[75] if hk else f[82]) if len(f) > (75 if hk else 82) else ""
            if item.asset_type == "stock" and (
                not kind.startswith("GP") or ccy != item.currency
            ):
                continue
            if item.asset_type == "etf" and (
                (kind and not kind.startswith(("JJ", "ETF", "GP")))
                or (ccy and item.currency and ccy != item.currency)
            ):
                continue
            if item.asset_type == "index" and kind and not kind.startswith("ZS"):
                continue
            ts = f[30].strip()
            stamp = datetime.strptime(
                ts, "%Y/%m/%d %H:%M:%S" if "/" in ts else "%Y%m%d%H%M%S"
            ).replace(tzinfo=BEIJING)
            compound = f[35].split("/")
            turnover = number(
                f[37] if hk else compound[2] if len(compound) == 3 else None
            )
            if not hk and turnover is None and (wan := number(f[37])) is not None:
                turnover = wan * 10000
            extra = (
                {
                    "turnover_rate": number(f[38]),
                    "pe": number(f[39]),
                    "market_cap": number(f[45], positive=True),
                    "pb": number(f[46]),
                }
                if not hk and item.asset_type == "stock" and len(f) > 46
                else {}
            )
            quote = Quote(
                listing=item.model_copy(update={"name": f[1] or item.name}),
                day=stamp.date(),
                as_of=stamp,
                source="腾讯财经",
                url=TENCENT_QUOTE + symbol,
                last=number(f[3], positive=True),
                previous=number(f[4], positive=True),
                opening=number(f[5], positive=True),
                high=number(f[33], positive=True),
                low=number(f[34], positive=True),
                turnover=turnover if turnover is not None and turnover >= 0 else None,
                suspended=(
                    len(f) > 40
                    and f[40].strip().upper() in {"停牌", "SUSPENDED", "HALT"}
                )
                or "停牌" in f[1],
                **extra,
            )
            quote.calculate(number(f[31]), number(f[32]))
            if quote.last is not None or quote.suspended:
                quotes[symbol] = quote
        except (ValueError, IndexError, DecimalException) as exc:
            logger.debug("Skipping malformed Tencent row %s: %s", symbol, exc)
    return quotes


async def tencent(client: httpx.AsyncClient, items: list[Listing]) -> dict[str, Quote]:
    if not items:
        return {}
    try:
        resp = await client.get(TENCENT_QUOTE + ",".join(i.symbol for i in items))
        resp.raise_for_status()
        return parse_tencent(resp.content, {i.symbol: i for i in items})
    except SOURCE_ERRORS as exc:
        logger.warning("Tencent batch quote failed: %s", exc)
        return {}


def _count(value: object) -> Optional[int]:
    return (
        value
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0
        else None
    )


def _epoch_stamp(value: object, now: datetime) -> Optional[datetime]:
    stamp = _count(value)
    if not stamp or stamp > (now + CLOCK_SKEW_TOLERANCE).timestamp():
        return None
    return datetime.fromtimestamp(stamp, BEIJING)


async def _get_json(client, url, params, limit, deadline) -> dict:
    async def fetch():
        async with limit:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            payload = resp.json()
            return payload if isinstance(payload, dict) else {}

    try:
        return await asyncio.wait_for(
            fetch(), max(0, deadline - asyncio.get_running_loop().time())
        )
    except (asyncio.TimeoutError, *SOURCE_ERRORS) as exc:
        logger.debug("Sector request failed (%s): %s", url, exc)
        return {}


def _with_rankings(
    quote: Optional[SectorQuote], rows: list[dict], now: datetime
) -> Optional[SectorQuote]:
    movers = []
    for row in rows:
        stamp, pct, name = (
            _epoch_stamp(row.get("STOCK_STAMP"), now),
            number(row.get("STOCK_PCT")),
            row.get("SECURITY_NAME_ABBR"),
        )
        if stamp and pct is not None and isinstance(name, str) and name:
            movers.append(
                SectorMover(code=row["SECUCODE"], name=name, percent=pct, as_of=stamp)
            )
    if quote is None:
        if not movers:
            return None
        quote = SectorQuote(day=max(m.as_of for m in movers).date())
    same_day = [m for m in movers if m.as_of.date() == quote.day]
    if not same_day:
        return quote
    up = sorted(
        (m for m in same_day if m.percent > 0), key=lambda m: (-m.percent, m.code)
    )
    down = sorted(
        (m for m in same_day if m.percent < 0), key=lambda m: (m.percent, m.code)
    )
    quote.ranked_members, quote.total_members = len(same_day), len(rows)
    quote.gainers = [] if quote.rising == 0 else (up[:3] if up else None)
    quote.losers = [] if quote.falling == 0 else (down[:3] if down else None)
    return quote


async def sector_quote(
    client: httpx.AsyncClient,
    sector: Sector,
    clock: Callable[[], datetime],
    limit: asyncio.Semaphore,
    deadline: float,
) -> Optional[SectorQuote]:
    async def page(n: int, until: float) -> dict:
        payload = await _get_json(
            client,
            EASTMONEY_MEMBERS,
            {
                "reportName": "RPT_F10_CORETHEME_BOARDTYPE",
                "filter": f'(NEW_BOARD_CODE="{sector.code}")',
                "columns": "SECUCODE,SECURITY_CODE,SECURITY_NAME_ABBR,NEW_BOARD_CODE",
                "quoteColumns": QUOTE_COLUMNS,
                "source": "HSF10",
                "client": "PC",
                "sortColumns": "SECUCODE",
                "sortTypes": 1,
                "pageSize": PAGE_SIZE,
                "pageNumber": n,
            },
            limit,
            until,
        )
        res = payload.get("result")
        return res if payload.get("success") is True and isinstance(res, dict) else {}

    start = asyncio.get_running_loop().time()
    first = await page(1, start + (deadline - start) * 0.75)
    rows = first.get("data") if isinstance(first.get("data"), list) else []
    head = next(
        (
            r
            for r in rows
            if isinstance(r, dict) and r.get("NEW_BOARD_CODE") == sector.code
        ),
        {},
    )
    stamp = _epoch_stamp(head.get("BOARD_STAMP"), clock())
    quote = (
        SectorQuote(
            day=stamp.date(),
            as_of=stamp,
            percent=number(head.get("BOARD_PCT")),
            rising=_count(head.get("UP")),
            falling=_count(head.get("DOWN")),
            flat=_count(head.get("FLAT")),
        )
        if stamp
        else None
    )
    if (
        not quote
        or quote.percent is None
        or quote.day < expected_day("sh", clock().date())
    ):
        quote = await _sector_daily_fallback(
            client, sector, quote, clock(), limit, deadline
        )

    total, pages = _count(first.get("count")), _count(first.get("pages"))
    if not total or not pages or pages != (total + PAGE_SIZE - 1) // PAGE_SIZE:
        return quote
    for part in await asyncio.gather(*(page(n, deadline) for n in range(2, pages + 1))):
        if (
            part.get("count") != total
            or part.get("pages") != pages
            or not isinstance(part.get("data"), list)
        ):
            return quote
        rows.extend(part["data"])
    valid = {
        r["SECUCODE"]: r
        for r in rows
        if isinstance(r, dict)
        and r.get("NEW_BOARD_CODE") == sector.code
        and re.fullmatch(r"\d{6}\.(?:SH|SZ|BJ)", str(r.get("SECUCODE")))
        and r["SECUCODE"].partition(".")[0] == r.get("SECURITY_CODE")
    }
    if len(rows) != total or len(valid) != len(rows) or not valid:
        return quote
    return _with_rankings(quote, list(valid.values()), clock())


async def _sector_daily_fallback(client, sector, quote, now, limit, deadline):
    payload = await _get_json(
        client,
        EASTMONEY_DAILY,
        {
            "secid": f"90.{sector.code}",
            "klt": 101,
            "fqt": 0,
            "lmt": 2,
            "end": now.strftime("%Y%m%d"),
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        },
        limit,
        deadline,
    )
    try:
        data = payload["data"]
        bar = data["klines"][-1].split(",")
        bar_day, pct = date.fromisoformat(bar[0]), number(bar[8])
        if (
            data["code"] == sector.code
            and data["market"] == 90
            and bar_day <= now.date()
            and pct is not None
        ):
            if quote and bar_day == quote.day and quote.percent is None:
                quote.percent, quote.as_of = pct, None
            elif not quote or bar_day > quote.day:
                return SectorQuote(day=bar_day, percent=pct)
    except SOURCE_ERRORS:
        pass
    return quote
