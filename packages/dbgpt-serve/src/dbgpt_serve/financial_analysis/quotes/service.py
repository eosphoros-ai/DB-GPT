"""Orchestrate stock, index, ETF, and sector quote lookups with deadline control."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, time
from typing import Optional, TypeVar

import httpx

from .exchanges import DAILY_REPORTS, DailyReports, daily_close, mainland_snapshot
from .models import (
    BEIJING,
    CLOCK_SKEW_TOLERANCE,
    Listing,
    Quote,
    QuoteRow,
    Sector,
    Snapshot,
    Verification,
    expected_day,
    session,
)
from .providers import resolve, sector_quote, tencent

CLOSING_PHASES = {"auction_ended", "after_hours", "closed", "holiday"}
T = TypeVar("T")


async def _before(job: Awaitable[T], deadline: float) -> Optional[T]:
    try:
        return await asyncio.wait_for(
            job, max(0, deadline - asyncio.get_running_loop().time())
        )
    except asyncio.TimeoutError:
        return None


def _is_future(quote: Quote, now: datetime) -> bool:
    return bool(quote.as_of and quote.as_of > now + CLOCK_SKEW_TOLERANCE)


async def _select_quote(
    client: httpx.AsyncClient,
    item: Listing,
    quote: Optional[Quote],
    clock: Callable[[], datetime],
    confirm_close: bool,
    reports: DailyReports,
    deadline: float,
) -> tuple[Optional[Quote], Verification]:
    verifiable = item.asset_type == "stock" and item.market in {"sh", "sz", "hk"}
    needs_fallback = verifiable and (
        quote is None
        or (item.market != "hk" and (quote.previous is None or "change" in quote.gaps))
    )
    day = (
        expected_day(item.market, clock().date())
        if confirm_close
        and verifiable
        and session(item.market, clock()) in CLOSING_PHASES
        else None
    )
    pending = Verification(reason="close_pending" if confirm_close else "", day=day)
    if day is None and not needs_fallback:
        return quote, pending

    if item.market == "hk":
        if quote is None:
            retry = await _before(tencent(client, [item]), deadline)
            quote = (retry or {}).get(item.symbol)
            if quote and _is_future(quote, clock()):
                quote = None
        if day is None:
            return quote, pending
        if quote is None and item.name == item.code:
            return None, Verification(reason="missing_quote")
        official = await _before(reports.get(client, day, item), deadline)
        if official is None:
            return quote, Verification(
                reason="daily_unavailable", source="港交所", day=day
            )
        if quote:
            official = official.model_copy(update={"listing": quote.listing})
        url = official.url
    else:
        official = await _before(mainland_snapshot(client, item), deadline)
        if not official or not official.as_of or _is_future(official, clock()):
            return quote, pending
        latest = (
            official
            if quote is None
            or official.day > quote.day
            or (needs_fallback and official.day == quote.day)
            else quote
        )
        if (
            day is None
            or official.day != day
            or official.as_of.time() < time(14, 59, 55)
        ):
            return latest, pending
        bar = await _before(daily_close(client, item, day), deadline)
        if not bar or bar[0] != official.last:
            if bar:
                pending.reason = "different_close"
            return latest, pending
        url = bar[1]

    ev = Verification(
        status="confirmed", source=official.source, url=url, day=day, fields=["last"]
    )
    if quote and quote.day == day and quote.last != official.last:
        ev.other_price, ev.other_source = quote.last, quote.source
        ev.other_as_of, ev.other_url = quote.as_of, quote.url
    return official, ev


async def _fetch_listings(
    client, listings, clock, start, timeout, confirm_close, reports
) -> dict[str, tuple[Optional[Quote], Verification]]:
    if not listings:
        return {}
    deadline, quote_deadline = start + timeout, start + timeout * 0.7
    chunks = [
        tencent(client, listings[i : i + 60]) for i in range(0, len(listings), 60)
    ]
    primary: dict[str, Quote] = {}
    for chunk in await asyncio.gather(*(_before(j, quote_deadline) for j in chunks)):
        primary.update(chunk or {})
    now = clock()
    quotes = {k: q for k, q in primary.items() if q.as_of and not _is_future(q, now)}
    selected = await asyncio.gather(
        *(
            _select_quote(
                client,
                item,
                quotes.get(item.symbol),
                clock,
                confirm_close,
                reports,
                deadline,
            )
            for item in listings
        )
    )
    return dict(zip((item.symbol for item in listings), selected))


async def query_quotes(
    stocks: list[str],
    *,
    confirm_close: bool = False,
    client: Optional[httpx.AsyncClient] = None,
    now: Optional[datetime] = None,
    reports: DailyReports = DAILY_REPORTS,
    timeout: float = 20,
) -> Snapshot:
    """Resolve requested subjects, batch quotes, and preserve input order."""
    if client is None:
        async with httpx.AsyncClient(
            timeout=5,
            limits=httpx.Limits(max_connections=8),
            headers={"User-Agent": "DB-GPT stock quotes"},
        ) as own_client:
            return await query_quotes(
                stocks,
                confirm_close=confirm_close,
                client=own_client,
                now=now,
                reports=reports,
                timeout=timeout,
            )

    def clock() -> datetime:
        return now.astimezone(BEIJING) if now is not None else datetime.now(BEIJING)

    start = asyncio.get_running_loop().time()
    deadline = start + timeout
    cleaned = [s.strip() for s in stocks if s.strip()]
    unique_terms = list(dict.fromkeys(cleaned))
    limit = asyncio.Semaphore(8)

    matches = await asyncio.gather(
        *(
            _before(resolve(client, s, limit), start + timeout * 0.4)
            for s in unique_terms
        )
    )
    expanded: dict[str, list[tuple[Optional[str], QuoteRow]]] = {}
    selected: dict[str, Listing] = {}
    sectors: dict[str, Sector] = {}

    for term, result in zip(unique_terms, matches):
        candidates, reason = result or ([], "timeout")
        if reason == "expand":
            group = []
            for item in candidates:
                assert isinstance(item, Listing)
                selected[item.symbol] = item
                group.append(
                    (item.symbol, QuoteRow(requested=item.name, kind=item.asset_type))
                )
            expanded[term] = group
            continue
        row = QuoteRow(requested=term, reason=reason)
        if reason.startswith("sector_") or (
            candidates and isinstance(candidates[0], Sector)
        ):
            row.kind = "sector"
            if len(candidates) == 1:
                row.sector = candidates[0]  # type: ignore[assignment]
                sectors[row.sector.code] = row.sector
            elif candidates:
                row.outcome, row.sector_candidates = "choose", candidates  # type: ignore[assignment]
        elif len(candidates) == 1:
            item = candidates[0]
            assert isinstance(item, Listing)
            row.kind = item.asset_type
            selected[item.symbol] = item
            expanded[term] = [(item.symbol, row)]
            continue
        elif candidates:
            row.outcome, row.candidates = "choose", candidates  # type: ignore[assignment]
        expanded[term] = [(None, row)]

    listing_values, sector_values = await asyncio.gather(
        _fetch_listings(
            client,
            list(selected.values()),
            clock,
            start,
            timeout,
            confirm_close,
            reports,
        ),
        asyncio.gather(
            *(sector_quote(client, s, clock, limit, deadline) for s in sectors.values())
        ),
    )
    by_sector, stamp, final_rows = dict(zip(sectors, sector_values)), clock(), []
    for term in cleaned:
        for sym, row in expanded[term]:
            if row.sector:
                row.sector_quote = by_sector[row.sector.code]
                row.outcome = "quoted" if row.sector_quote else "unavailable"
                if not row.sector_quote:
                    row.reason = "sector_unavailable"
            elif sym is not None:
                quote, row.verification = listing_values[sym]
                row.phase = session(selected[sym].market, stamp)
                if quote:
                    row.quote, row.outcome = quote, "quoted"
                else:
                    row.reason = row.verification.reason or "missing_quote"
            final_rows.append(row.model_copy(deep=True))
    return Snapshot(queried_at=stamp, rows=final_rows)
