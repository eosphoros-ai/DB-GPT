"""Concise bilingual Markdown renderer for structured quote snapshots."""

from decimal import ROUND_HALF_UP, Decimal
from itertools import groupby
from typing import Optional

from .models import CENT, QuoteRow, Snapshot, latest_expected_day

PHASES = {
    "preopen": ("开盘前", "before open"),
    "opening_auction": ("开市竞价", "opening auction"),
    "trading": ("交易中", "trading"),
    "lunch": ("午休", "lunch break"),
    "closing_auction": ("收市竞价", "closing auction"),
    "random_close": ("随机收市时段", "random closing"),
    "auction_ended": ("收盘竞价已结束", "closing auction ended"),
    "after_hours": ("盘后固定价格交易", "after-hours trading"),
    "closed": ("已收市", "market closed"),
    "holiday": ("休市日", "non-trading day"),
    "unknown": ("时段待核实", "session unverified"),
}
REASONS = {
    "unsupported": (
        "代码、市场或币种暂不支持（支持沪深京A股、ETF、港股、主要指数及A股板块）",
        "unsupported symbol or market (CN/HK stocks, ETFs, indices, A-share sectors)",
    ),
    "not_found": (
        "未匹配到个股、指数或 A 股板块",
        "no matching stock, index, or sector",
    ),
    "sector_not_found": (
        "未匹配到 A 股板块，请输入具体行业或概念名称",
        "no matching A-share sector; enter an industry or theme",
    ),
    "sector_market": (
        "板块行情仅覆盖 A 股行业和概念，港股可查个股或恒生/恒生科技指数",
        "sector quotes cover A-share boards; HK stocks/indices are available by name",
    ),
    "sector_lookup_failed": ("板块名称检索暂不可用", "sector lookup unavailable"),
    "sector_unavailable": ("暂未取得带交易日期的板块行情", "no dated sector quote"),
    "lookup_failed": ("名称检索源不可用", "symbol lookup unavailable"),
    "timeout": ("查询超时", "request timed out"),
    "missing_quote": ("行情源未返回有效报价", "no valid quote returned"),
    "daily_unavailable": (
        "当日港交所主板日报未发布或未覆盖",
        "HKEX bulletin unavailable",
    ),
    "different_close": (
        "交易所快照与日线收盘价不一致",
        "snapshot and daily close differ",
    ),
    "close_pending": ("交易所收盘记录待核对", "exchange close pending"),
    "close_unsupported": (
        "该品种无交易所收盘日报复核，展示行情源最新报价",
        "no exchange close check for this security; showing latest feed quote",
    ),
    "market_open": (
        "当前尚未收盘，展示行情源最新报价",
        "market not yet closed; showing latest feed quote",
    ),
}
LABELS = {
    "last": ("最新价", "last"),
    "close": ("收盘价", "closing price"),
    "previous": ("前收", "previous close"),
    "opening": ("开盘", "open"),
    "high": ("最高", "high"),
    "low": ("最低", "low"),
    "turnover": ("成交额", "turnover"),
    "amplitude": ("振幅", "amplitude"),
}
CLOSED_LIKE = {
    "closed",
    "holiday",
    "after_hours",
    "auction_ended",
    "closing_auction",
    "random_close",
}
_ESC = str.maketrans(
    {
        "\\": "\\\\",
        "|": "\\|",
        "[": "\\[",
        "]": "\\]",
        "<": "&lt;",
        ">": "&gt;",
        "*": "\\*",
        "\n": " ",
        "\r": " ",
    }
)


def clean(text: str) -> str:
    return text.translate(_ESC)


def _t(en: bool, zh: str, eng: str) -> str:
    return eng if en else zh


def fmt_num(value: Optional[Decimal], *, signed=False, percent=False) -> str:
    if value is None:
        return "—"
    digits = CENT if percent or value == value.quantize(CENT) else Decimal("0.001")
    rounded = value.quantize(digits, rounding=ROUND_HALF_UP)
    sign = "−" if rounded < 0 else "+" if signed and rounded > 0 else ""
    return sign + format(abs(rounded), "f") + ("%" if percent else "")


def render(snapshot: Snapshot, *, language="zh", detail: Optional[str] = None) -> str:
    en = language == "en"
    stamp = snapshot.queried_at.strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        _t(
            en,
            f"查询时间（北京时间） **{stamp}**。",
            f"Query time (Beijing) **{stamp}**.",
        )
    ]
    for is_sector, group in groupby(snapshot.rows, key=lambda r: r.kind == "sector"):
        if is_sector:
            for row in group:
                lines.extend(["", *_render_sector(row, snapshot, en, detail)])
        elif detail not in {"gainers", "losers"}:
            lines.extend(["", *_render_listings(list(group), snapshot, en, detail)])
    return "\n".join(lines).strip()


def _render_sector(
    row: QuoteRow, snapshot: Snapshot, en: bool, detail: Optional[str]
) -> list[str]:
    if row.sector_candidates:
        hdr = _t(
            en,
            f"**{clean(row.requested)}** 涵盖多个 A 股板块。回复名称或序号即可。",
            f"**{clean(row.requested)}** covers several A-share sectors. "
            "Reply with a name or number.",
        )
        return [
            hdr,
            "",
            *(
                f"{n}. {clean(s.name)}（{s.code}）"
                for n, s in enumerate(row.sector_candidates, 1)
            ),
        ]
    s, q = row.sector, row.sector_quote
    if not s:
        reason_text = REASONS.get(row.reason, REASONS["sector_unavailable"])[int(en)]
        return [f"**{clean(row.requested)}** · {reason_text}"]
    source = f"[{_t(en, '东方财富', 'Eastmoney')}]({s.url})"
    board_label = _t(en, "A 股板块指数", "A-share sector index")
    title = f"**{clean(s.name)}（{s.code}）** · {board_label}"
    if not q:
        return [title, "", f"{REASONS['sector_unavailable'][int(en)]} {source}"]
    if detail in LABELS:
        field = LABELS[detail][int(en)]
        no_field = _t(
            en, f"这次板块快照未保存{field}。", f"No {field} in saved sector quote."
        )
        return [title, "", f"{no_field} {source}"]

    as_of = q.as_of.strftime("%Y-%m-%d %H:%M:%S") if q.as_of else q.day.isoformat()
    age = ""
    if q.day < snapshot.queried_at.date():
        stale = latest_expected_day("sh", snapshot.queried_at) != q.day
        age = (
            _t(en, " · 较早交易日行情", " · older trading day")
            if stale
            else _t(en, " · 最近交易日", " · latest trading day")
        )
    pct = (
        fmt_num(q.percent, signed=True, percent=True)
        if q.percent is not None
        else _t(en, "暂无数据", "unavailable")
    )
    breadth = " / ".join(
        str(v) if v is not None else "—" for v in (q.rising, q.falling, q.flat)
    )
    dlabel = (
        _t(en, "行情时间（北京）", "Source time (Beijing)")
        if q.as_of
        else (
            _t(en, "成分股行情日期", "Constituent quote date")
            if q.percent is None
            else _t(en, "板块日线日期", "Daily bar date")
        )
    )
    lines = [
        title,
        "",
        _t(
            en,
            f"板块整体涨跌 **{pct}** · 上涨 / 下跌 / 平盘 **{breadth}** 家",
            f"Sector change **{pct}** · Up / down / flat **{breadth}**",
        ),
        "",
        f"{dlabel} {as_of}{age} · {source}",
    ]
    if (
        q.ranked_members is not None
        and q.total_members is not None
        and q.ranked_members < q.total_members
    ):
        lines.append(
            _t(
                en,
                f"成分股排名覆盖当日有效报价 {q.ranked_members}/{q.total_members} 家。",
                f"Coverage: {q.ranked_members}/{q.total_members} constituents.",
            )
        )
    for side, heading in (
        ("gainers", _t(en, "领涨个股", "Top gainers")),
        ("losers", _t(en, "领跌个股", "Top decliners")),
    ):
        if detail in {"gainers", "losers"} and side != detail:
            continue
        movers, count = getattr(q, side), q.rising if side == "gainers" else q.falling
        if movers:
            lines.extend(
                [
                    "",
                    f"**{heading}**",
                    "",
                    _t(
                        en,
                        "| 股票 | 涨跌幅 | 行情时间（北京） |",
                        "| Stock | Change | Source time (Beijing) |",
                    ),
                    "| --- | ---: | --- |",
                    *(
                        f"| {clean(m.name)} {m.code} "
                        f"| {fmt_num(m.percent, signed=True, percent=True)} "
                        f"| {m.as_of:%H:%M:%S} |"
                        for m in movers
                    ),
                ]
            )
        elif movers == [] or count == 0:
            none = (
                _t(en, "没有上涨成分股", "No advancing constituents")
                if side == "gainers"
                else _t(en, "没有下跌成分股", "No declining constituents")
            )
            lines.extend(["", f"**{heading}** · {none}"])
        else:
            unavail = _t(
                en, "当日成分股排名数据不足", "Same-day constituent ranking unavailable"
            )
            lines.extend(["", f"**{heading}** · {unavail}"])
    return lines


def _unit(ccy: str, asset_type: str, en: bool) -> str:
    if asset_type == "index" or not ccy:
        return "pts" if en else "点"
    return (
        ccy if en else {"HKD": "港元", "CNY": "元人民币", "USD": "美元"}.get(ccy, ccy)
    )


def _render_listings(
    rows: list[QuoteRow], snapshot: Snapshot, en: bool, detail: Optional[str]
) -> list[str]:
    idx, stop, delim = int(en), ("." if en else "。"), (", " if en else "，")
    lines = (
        []
        if detail
        else [
            _t(
                en,
                "| 标的 | 最新价 | 涨跌额 | 涨跌幅 | 状态 | 源时间 |",
                "| Symbol | Last | Change | Change % | Status | Source time |",
            ),
            "| --- | ---: | ---: | ---: | --- | --- |",
        ]
    )
    notes, conclusions, currencies = [], [], set()
    for row in rows:
        q = row.quote
        if q is None:
            opts = (", " if en else "、").join(
                f"{clean(i.name)} {i.label}"
                + (f" ({i.currency})" if i.currency else "")
                for i in row.candidates
            )
            reason = (
                (_t(en, "请选择上市地或柜台：", "Choose a listing: ") + opts)
                if opts
                else REASONS.get(row.reason, REASONS["missing_quote"])[idx]
            )
            (notes if detail else lines).append(
                f"- {clean(row.requested)} · {reason}"
                if detail
                else f"| {clean(row.requested)} | — | — | — | {reason} | — |"
            )
            continue

        name, label, ccy = (
            clean(q.listing.name),
            f"{clean(q.listing.name)} {q.listing.label}",
            q.listing.currency,
        )
        unit = _unit(ccy, q.listing.asset_type, en)
        if ccy:
            currencies.add(ccy)
        asof = q.as_of.strftime("%Y-%m-%d %H:%M:%S") if q.as_of else q.day.isoformat()
        fields = {
            k: fmt_num(getattr(q, k))
            for k in ("last", "previous", "opening", "high", "low")
        }
        fields["amplitude"] = fmt_num(q.amplitude, percent=True)
        t_ccy = ccy or ("HKD" if q.listing.market == "hk" else "CNY")
        fields["turnover"] = (
            f"{q.turnover / Decimal(100_000_000):.2f} "
            + _t(en, "亿" + _unit(t_ccy, "stock", False), f"× 100M {t_ccy}")
            if q.turnover is not None
            else "—"
        )
        v = row.verification
        links = f"[{q.source}]({q.url})"
        if v.url and v.url != q.url:
            links += f" · [{v.source}{_t(en, '收盘复核', ' close')}]({v.url})"
        if v.other_url and v.other_url != q.url:
            links += f" · [{v.other_source}{_t(en, '原报价', ' quote')}]({v.other_url})"

        if detail:
            if detail == "close" and v.status != "confirmed":
                val = fields["last"]
                if val != "—":
                    val += f" {unit}"
                else:
                    val += _t(en, "（原快照缺少该字段）", " (source field unavailable)")
                if v.reason == "close_unsupported":
                    status_lbl = _t(
                        en,
                        "无交易所收盘复核，最新报价",
                        "no exchange close check, latest quote",
                    )
                elif v.reason == "market_open":
                    status_lbl = _t(
                        en,
                        "尚未收盘，盘中最新报价",
                        "market open, latest quote",
                    )
                elif v.reason == "different_close":
                    status_lbl = _t(
                        en,
                        "收盘价待确认（交易所快照与日线不一致），最近报价",
                        "close pending (snapshot/daily close differ), latest quote",
                    )
                else:
                    status_lbl = _t(
                        en,
                        "收盘价待确认，最近报价",
                        "close pending, latest quote",
                    )
                notes.append(f"- {label} · {status_lbl} **{val}** · {asof} · {links}")
                continue
            val = fields["last" if detail == "close" else detail]
            if (
                detail in {"last", "close", "previous", "opening", "high", "low"}
                and val != "—"
            ):
                val += f" {unit}"
            if val == "—":
                val += _t(en, "（原快照缺少该字段）", " (source field unavailable)")
            notes.append(
                f"- {label} · {LABELS[detail][idx]} **{val}** · {asof} · {links}"
            )
            continue

        state = PHASES.get(row.phase, PHASES["unknown"])[idx]
        if q.suspended:
            state += " · " + _t(en, "个股停牌", "suspended")
        if v.status == "confirmed":
            state += " · " + _t(en, "收盘价已确认", "confirmed close")
        elif (
            q.listing.asset_type == "stock"
            and q.listing.market in {"sh", "sz", "hk"}
            and row.phase in CLOSED_LIKE
        ):
            state += " · " + _t(
                en, "最近报价，收盘价待确认", "latest quote, close pending"
            )
        elif q.day < snapshot.queried_at.date():
            state += " · " + _t(en, "最近交易日报价", "prior quote")
        pct_str = fmt_num(q.percent, signed=True, percent=True)
        lines.append(
            f"| {label} | {fmt_num(q.last)} {unit} "
            f"| {fmt_num(q.change, signed=True)} | **{pct_str}** | {state} | {asof} |"
        )

        if q.percent is not None:
            if q.percent == 0:
                conclusions.append(name + _t(en, "平盘", " was flat"))
            else:
                verb = (
                    _t(en, "上涨 ", " rose ")
                    if q.percent > 0
                    else _t(en, "下跌 ", " fell ")
                )
                conclusions.append(
                    f"{name}{verb}{fmt_num(abs(q.percent), percent=True)}"
                )
        details = [
            f"{LABELS[k][idx]} {fields[k]}"
            for k in ("previous", "opening", "low", "high", "amplitude", "turnover")
            if fields[k] != "—"
        ]
        if q.turnover_rate is not None:
            tr_lbl = _t(en, "换手率", "turnover rate")
            details.append(f"{tr_lbl} {fmt_num(q.turnover_rate, percent=True)}")
        if q.market_cap is not None:
            mc_lbl = _t(en, "总市值", "market cap")
            mc_unit = _t(en, " 亿元", " × 100M CNY")
            details.append(f"{mc_lbl} {fmt_num(q.market_cap)}{mc_unit}")
        if q.pe is not None:
            details.append(f"PE {fmt_num(q.pe)}")
        if q.pb is not None:
            details.append(f"PB {fmt_num(q.pb)}")
        if q.last is not None and q.last == q.high:
            details.append(_t(en, "等于当日最高价", "at session high"))
        if absent := [LABELS[k][idx] for k in LABELS if k in q.gaps]:
            details.append(
                _t(en, "来源缺项：", "source field unavailable: ")
                + (", " if en else "、").join(absent)
            )
        if "change" in q.gaps:
            details.append(_t(en, "涨跌与来源参考口径冲突", "change basis conflicts"))
        if v.other_price is not None:
            details.append(
                f"{v.other_source} {fmt_num(v.other_price)}"
                + (f" ({v.other_as_of:%H:%M:%S})" if v.other_as_of else "")
            )
        if v.reason:
            details.append(REASONS.get(v.reason, REASONS["close_pending"])[idx])
        notes.append(f"- {label} · {delim.join(details)}{stop} {links}")

    if conclusions and not detail:
        lines.extend(["", "**" + delim.join(conclusions) + stop + "**"])
    lines.extend(["", *notes])
    if len(currencies) > 1 and not detail:
        lines.extend(
            [
                "",
                _t(
                    en,
                    "各行按柜台原币报价，涨跌幅可直接对照。",
                    "Prices use each listing's currency; "
                    "percentage changes are comparable.",
                ),
            ]
        )
    return lines
