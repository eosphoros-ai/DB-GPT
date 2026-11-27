"""Unit tests for the financial-analysis stock, index, ETF, and sector quote domain."""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal

import httpx
import pytest

from dbgpt_serve.financial_analysis.quotes import (
    BEIJING,
    DailyReports,
    Snapshot,
    direct_listing,
    expected_day,
    providers,
    query_quotes,
    render,
    session,
)

NOW = datetime(2026, 11, 23, 15, 45, tzinfo=BEIJING)
STAMP = int((NOW - timedelta(minutes=10)).timestamp())
SUGGEST = (
    'v_hint="sh~000847~腾讯济安~txja~ZS^hk~00700~腾讯控股~txkg~GP^'
    'hk~80700~腾讯控股r~txkgr~GP^hk~01698~腾讯音乐sw~txylsw~GP"'
)
SMIC = 'v_hint="sh~688981~中芯国际~zxgj~GP-A-KCB^hk~00981~中芯国际~zxgj~GP"'


def wire(
    symbol: str,
    name: str,
    last: str,
    prev: str,
    change: str,
    percent: str,
    *,
    stamp: str | None = None,
    kind: str | None = None,
    currency: str | None = None,
    turnover_rate: str = "",
    pe: str = "",
    market_cap: str = "",
    pb: str = "",
) -> bytes:
    hk = symbol[:2] == "hk"
    code = symbol[2:]
    f = [""] * 88
    f[1:6] = [name, code, last, prev, "335" if hk else "1475.35"]
    f[30:35] = [
        stamp or ("2026/11/23 15:42:00" if hk else "20261123153500"),
        change,
        percent,
        "344.60" if hk else "1478",
        "333" if hk else "1428",
    ]
    f[35] = f"{last}/56976/8224000000" if not hk else last
    f[37] = "10261000000" if hk else "822400"
    f[38] = turnover_rate
    f[39] = pe
    f[45] = market_cap
    f[46] = pb
    f[63 if hk else 61] = kind if kind is not None else ("GP" if hk else "GP-A")
    f[75 if hk else 82] = currency if currency is not None else ("HKD" if hk else "CNY")
    return ("v_" + symbol + '="' + "~".join(f) + '";').encode("gb18030")


HK = wire("hk00700", "腾讯控股", "344.60", "344.00", "0.60", "0.17")
SH = wire(
    "sh600519",
    "贵州茅台",
    "1439.00",
    "1485.75",
    "-46.75",
    "-3.15",
    turnover_rate="0.45",
    pe="21.50",
    market_cap="18076.50",
    pb="7.82",
)
BJ = wire("bj920157", "宇特光电", "25.00", "22.50", "2.50", "11.11")
ETF = wire("sh510300", "沪深300ETF", "4.100", "4.050", "0.050", "1.23", kind="JJ-ETF")
SH_IDX = wire(
    "sh000001",
    "上证指数",
    "3350.00",
    "3320.00",
    "30.00",
    "0.90",
    kind="ZS",
    currency="",
)
SZ_IDX = wire(
    "sz399001",
    "深证成指",
    "10800.00",
    "10700.00",
    "100.00",
    "0.93",
    kind="ZS",
    currency="",
)
CYB_IDX = wire(
    "sz399006",
    "创业板指",
    "2260.00",
    "2240.00",
    "20.00",
    "0.89",
    kind="ZS",
    currency="",
)
HSI_IDX = wire(
    "hkHSI",
    "恒生指数",
    "19500.00",
    "19300.00",
    "200.00",
    "1.04",
    kind="ZS",
    currency="",
)

SNAP = {
    "code": "600519",
    "snap": [
        "600519",
        "贵州茅台",
        20261123,
        153000,
        1475.35,
        1478,
        1428,
        1439,
        1485.75,
        5697589,
        8224000000,
    ],
}
BAR = {
    "code": "600519",
    "kline": [[20261123, 1475.35, 1478, 1428, 1439, 5697589, 8224000000]],
}
BULLETIN = """DATE: 23 NOV 2026
<a name = "quotations">QUOTATIONS</a>
*  700 TENCENT          HKD   344.00   345.90   348.60        30,000
                              346.00   345.80   333.00    10,111,100
<a name="short">SHORT SELLING</a>
"""
MEMBERS = [
    ("688195.SH", "腾景科技", 8),
    ("920157.BJ", "宇特光电", 11),
    ("300308.SZ", "中际旭创", 0),
    ("688172.SH", "燕东微", -2),
]


def board_rows(code: str, members=MEMBERS, *, up=2, down=1, flat=1):
    return [
        {
            "SECUCODE": sym,
            "SECURITY_CODE": sym[:6],
            "SECURITY_NAME_ABBR": name,
            "NEW_BOARD_CODE": code,
            "STOCK_PCT": pct,
            "STOCK_STAMP": STAMP,
            "BOARD_STAMP": STAMP,
            "BOARD_PCT": 1.25,
            "UP": up,
            "DOWN": down,
            "FLAT": flat,
        }
        for sym, name, pct in members
    ]


def board_page(rows, *, count=None, pages=1):
    return httpx.Response(
        200,
        json={
            "success": True,
            "result": {
                "count": len(rows) if count is None else count,
                "pages": pages,
                "data": rows,
            },
        },
    )


def endpoint(req: httpx.Request) -> httpx.Response:
    host, path = req.url.host, req.url.path
    if host == "smartbox.gtimg.cn":
        q = req.url.params["q"]
        raw = {
            "腾讯": SUGGEST,
            "中芯国际": SMIC,
            "贵州茅台": 'v_hint="sh~600519~贵州茅台~gzmt~GP-A"',
        }.get(q, "")
        return httpx.Response(200, content=raw.encode("gb18030"))
    if host == "qt.gtimg.cn":
        catalog = [
            ("sh600519", SH),
            ("hk00700", HK),
            ("bj920157", BJ),
            ("sh510300", ETF),
            ("sh000001", SH_IDX),
            ("sz399001", SZ_IDX),
            ("sz399006", CYB_IDX),
            ("hkHSI", HSI_IDX),
        ]
        return httpx.Response(
            200, content=b"\n".join(row for sym, row in catalog if sym in path)
        )
    if str(req.url).startswith(providers.EASTMONEY_MEMBERS):
        code = req.url.params["filter"].split('"')[1]
        return board_page(board_rows(code))
    if "/snap/" in path:
        return httpx.Response(200, json=SNAP)
    if "/dayk/" in path:
        return httpx.Response(200, json=BAR)
    return httpx.Response(503)


async def lookup(stocks, handler=endpoint, now=NOW, **kwargs):
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        return await query_quotes(
            stocks, client=client, now=now, reports=DailyReports(), **kwargs
        )


def test_equities_valuation_order_and_disambiguation():
    result = asyncio.run(lookup(["腾讯", "贵州茅台", "中芯国际"]))
    hk, sh, smic = result.rows
    assert hk.quote.percent.quantize(Decimal(".01")) == Decimal(".17")
    assert sh.quote.percent.quantize(Decimal(".01")) == Decimal("-3.15")
    assert sh.quote.pe == Decimal("21.50") and sh.quote.pb == Decimal("7.82")
    assert sh.quote.market_cap == Decimal("18076.50")
    assert sh.quote.turnover_rate == Decimal("0.45")
    assert [c.label for c in smic.candidates] == ["688981.SH", "00981.HK"]
    md = render(result)
    assert "PE 21.50" in md and "总市值 18076.50 亿元" in md and "换手率 0.45%" in md
    assert md.index("00700.HK") < md.index("600519.SH")


def test_major_indices_broad_market_bj_and_etf():
    assert direct_listing("sh000001").asset_type == "index"
    assert direct_listing("000001").label == "000001.SZ"
    assert direct_listing("399001").label == "399001.SZ"
    assert direct_listing("920157").label == "920157.BJ"
    assert direct_listing("510300").asset_type == "etf"

    result = asyncio.run(lookup(["大盘", "恒生指数", "920157.BJ", "510300.SH"]))
    codes = [row.quote.listing.label for row in result.rows]
    assert codes == [
        "000001.SH",
        "399001.SZ",
        "399006.SZ",
        "HSI.HK",
        "920157.BJ",
        "510300.SH",
    ]
    md = render(result)
    assert "3350.00 点" in md and "19500.00 点" in md and "宇特光电" in md


def test_rounding_tolerance_and_clock_skew():
    # A 0.01% source rounding difference must not trigger reference_conflict.
    one_tick = wire("sh600519", "贵州茅台", "1439.00", "1485.75", "-46.75", "-3.14")
    bad_ref = wire("sh600519", "贵州茅台", "1439.00", "1485.75", "-40.00", "-2.69")
    ok_row = asyncio.run(
        lookup(["600519.SH"], lambda _: httpx.Response(200, content=one_tick))
    ).rows[0]
    assert (
        ok_row.quote.change == Decimal("-46.75") and "change" not in ok_row.quote.gaps
    )
    bad_row = asyncio.run(
        lookup(["600519.SH"], lambda _: httpx.Response(200, content=bad_ref))
    ).rows[0]
    assert (
        bad_row.quote.change is None
        and bad_row.quote.gaps["change"] == "reference_conflict"
    )

    # 30s ahead source clock (minor NTP skew) is accepted; +10min is rejected.
    slightly_ahead = asyncio.run(
        lookup(["00700.HK"], now=datetime(2026, 11, 23, 15, 41, 30, tzinfo=BEIJING))
    ).rows[0]
    assert slightly_ahead.outcome == "quoted"
    far_future = asyncio.run(
        lookup(["00700.HK"], now=datetime(2026, 11, 23, 15, 30, 0, tzinfo=BEIJING))
    ).rows[0]
    assert far_future.outcome == "unavailable"


def test_calendar_sessions_and_post_2026_fallback():
    assert session("sh", datetime(2026, 11, 23, 12, 5, tzinfo=BEIJING)) == "lunch"
    assert (
        session("hk", datetime(2026, 12, 24, 12, 2, tzinfo=BEIJING))
        == "closing_auction"
    )
    assert session("hk", datetime(2026, 7, 1, 10, 0, tzinfo=BEIJING)) == "holiday"
    # Post-2026 weekdays gracefully fall back instead of returning "unknown".
    assert session("sh", datetime(2028, 6, 1, 10, 0, tzinfo=BEIJING)) == "trading"
    assert session("sh", datetime(2028, 6, 3, 10, 0, tzinfo=BEIJING)) == "holiday"
    assert expected_day("sh", datetime(2028, 6, 4).date()).weekday() == 4


def test_close_confirmation_sse_and_hkex_coalescing():
    calls = []

    async def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req.url.path)
        if req.url.path.endswith("qtn.asp"):
            return httpx.Response(200, text='<a href="d261123e.htm">23</a>')
        if req.url.path.endswith(".htm"):
            await asyncio.sleep(0.01)
            return httpx.Response(200, text=BULLETIN)
        return endpoint(req)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            reports = DailyReports()
            return await asyncio.gather(
                query_quotes(
                    ["00700.HK", "600519.SH"],
                    confirm_close=True,
                    client=client,
                    now=NOW.replace(hour=17),
                    reports=reports,
                ),
                query_quotes(
                    ["00700.HK"],
                    confirm_close=True,
                    client=client,
                    now=NOW.replace(hour=17),
                    reports=reports,
                ),
            )

    first, second = asyncio.run(run())
    hk, sh = first.rows
    assert hk.verification.status == "confirmed" and hk.quote.last == Decimal("346.00")
    assert sh.verification.status == "confirmed" and sh.quote.last == Decimal("1439")
    assert second.rows[0].quote.last == Decimal("346.00")
    assert sum(p.endswith(".htm") for p in calls) == 1


def test_sector_intraday_drift_and_suspended_constituent_keep_rankings():
    # Board UP/DOWN counts drifted intraday and one constituent is suspended ('-').
    rows = board_rows("BK1136", up=5, down=2, flat=1)
    rows[2]["STOCK_PCT"] = "-"
    result = asyncio.run(lookup(["光模块"], lambda _: board_page(rows)))
    sq = result.rows[0].sector_quote
    assert sq.percent == Decimal("1.25")
    assert [m.code for m in sq.gainers] == ["920157.BJ", "688195.SH"]
    assert [m.code for m in sq.losers] == ["688172.SH"]
    assert sq.ranked_members == 3 and sq.total_members == 4
    md = render(result)
    assert "覆盖当日有效报价 3/4 家" in md and "宇特光电" in md and "燕东微" in md


@pytest.mark.parametrize("second_page", ["ok", "duplicate", "timeout"])
def test_sector_pagination_rejects_corrupt_or_incomplete_pages(
    second_page, monkeypatch
):
    monkeypatch.setattr(providers, "PAGE_SIZE", 2)
    rows = board_rows("BK1136")

    async def handler(req: httpx.Request) -> httpx.Response:
        n = int(req.url.params["pageNumber"])
        if n == 2 and second_page == "timeout":
            await asyncio.sleep(2)
        part = rows[:2] if n == 1 or second_page == "duplicate" else rows[2:]
        return board_page(part, count=4, pages=2)

    result = asyncio.run(lookup(["光模块"], handler, timeout=0.25))
    sq = result.rows[0].sector_quote
    assert sq.percent == Decimal("1.25")
    assert (sq.gainers is not None) == (second_page == "ok")


def test_legacy_snapshot_deserialization():
    snap = Snapshot.model_validate(
        {
            "version": 1,
            "queried_at": NOW,
            "rows": [
                {
                    "requested": "某股票",
                    "outcome": "unavailable",
                    "reason": "missing_quote",
                }
            ],
        }
    )
    assert snap.rows[0].kind == "stock" and "标的 | 最新价" in render(snap)
