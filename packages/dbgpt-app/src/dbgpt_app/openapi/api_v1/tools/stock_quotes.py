"""Thin ReAct tool adapter around ``dbgpt_serve.financial_analysis.quotes``."""

import json
import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, ValidationError

from dbgpt.agent.resource.tool.base import tool
from dbgpt_serve.financial_analysis.quotes import (
    Listing,
    QuoteRow,
    Snapshot,
    qualifiers,
    query_quotes,
    render,
)

MAX_CONSECUTIVE_FAILURES = 2


class QuoteRequest(BaseModel):
    stocks: list[str] = Field(
        description=(
            "Ordered stock names/codes, indices (上证指数, 恒生指数, 大盘), "
            "or A-share sectors; pass [] to reuse the previous group."
        )
    )
    operation: Literal["latest", "recall", "select"] = "latest"
    detail: Literal[
        "",
        "last",
        "close",
        "previous",
        "opening",
        "high",
        "low",
        "turnover",
        "amplitude",
        "gainers",
        "losers",
    ] = ""


def previous_quote_snapshot(history) -> Optional[Snapshot]:
    """Restore the latest typed quote snapshot from conversation history."""
    for message in reversed(history):
        if message.type != "view":
            continue
        try:
            payload = (
                json.loads(message.content)
                if isinstance(message.content, str)
                else message.content
            )
            if not isinstance(payload, dict):
                continue
            ref = payload.get("suite_binding") or payload.get("suite_reference") or {}
            if (ref.get("suite") or ref.get("name")) not in (
                None,
                "financial-analysis",
            ):
                continue
            if payload.get("stock_quote_snapshot"):
                return Snapshot.model_validate(payload["stock_quote_snapshot"])
            if ref.get("command") == "/查股票" and ref.get("skill_loaded") is not False:
                return None
        except ValidationError:
            return None
        except (ValueError, TypeError, AttributeError):
            continue
    return None


def _row_names(row: QuoteRow) -> set[str]:
    names = {row.requested}
    if row.sector:
        names.update((row.sector.name, row.sector.code))
    if row.quote:
        lst = row.quote.listing
        names.update((lst.name, lst.code, lst.label))
    return {n.casefold() for n in names}


def _resolved_term(row: QuoteRow) -> str:
    if row.sector:
        return row.sector.code
    return row.quote.listing.label if row.quote else row.requested


def _match_candidate(snapshot: Snapshot, selection: str) -> Optional[tuple[int, str]]:
    """Match a unique candidate in pending 'choose' rows as (row_idx, code)."""
    choice = re.sub(
        r"^(?:我选|选择|选|那就|那|option)\s*", "", selection.strip(), flags=re.I
    )
    key = choice.strip(" 。呢吧？?").removesuffix("板块").casefold()
    ordinal = re.fullmatch(r"第?([1-9一二三四五六七八九])(?:个|项)?", key)
    pos = (
        int(ordinal[1])
        if ordinal and ordinal[1].isdigit()
        else ("一二三四五六七八九".index(ordinal[1]) + 1 if ordinal else None)
    )
    bare, market, currency = qualifiers(key)
    matches: set[tuple[int, str]] = set()
    for row_idx, row in enumerate(snapshot.rows):
        for opt_idx, item in enumerate(row.sector_candidates or row.candidates, 1):
            is_lst = isinstance(item, Listing)
            label = item.label if is_lst else item.code
            names = {v.casefold() for v in (item.name, item.code, label)}
            if is_lst:
                if (
                    market
                    and market != item.market
                    and not (market == "cn" and item.market in {"sh", "sz", "bj"})
                ):
                    continue
                if currency and currency != item.currency:
                    continue
                if market or currency:
                    names.update(("", row.requested.casefold()))
            sym_hit = re.search(
                rf"(?<![a-z0-9.]){re.escape(label.casefold())}(?![a-z0-9.])", key
            )
            if opt_idx == pos or key in names or bare.casefold() in names or sym_hit:
                matches.add((row_idx, label))
    return next(iter(matches)) if len(matches) == 1 else None


def _envelope(
    content: str,
    user_request: str,
    operation: str,
    *,
    needs_selection: bool = False,
    stop_retrying: bool = False,
) -> str:
    instr = (
        "Answer using only observed data. Keep source links, timestamps, and units. "
        "Never label '收盘价待确认'/'close pending' as an official closing price."
    )
    if needs_selection:
        instr += (
            " Present candidates and wait for the user's choice before calling select."
        )
    if stop_retrying:
        instr += " Stop retrying unavailable/out-of-scope queries and explain directly."
    return json.dumps(
        {
            "chunks": [{"output_type": "markdown", "content": content}],
            "model_context": {
                "user_request": user_request,
                "operation": operation,
                "needs_selection": needs_selection,
                "stop_retrying": stop_retrying,
                "instructions": instr,
            },
        },
        ensure_ascii=False,
    )


def _handle_recall(
    snapshot: Optional[Snapshot], terms, detail, language, state, user_query
):
    en = language == "en"
    if not snapshot:
        msg = (
            "No structured quote was saved."
            if en
            else "这次会话未保存可回看的行情快照。"
        )
        return _envelope(msg, user_query, "recall", stop_retrying=True)
    selected = snapshot.rows
    if terms:
        wanted = {t.casefold() for t in terms}
        selected = [r for r in snapshot.rows if wanted & _row_names(r)]
        if not wanted <= {n for r in selected for n in _row_names(r)}:
            msg = (
                "Requested subject absent from saved quote."
                if en
                else "上次报价未包含所选标的。"
            )
            return _envelope(msg, user_query, "recall", stop_retrying=True)
    recalled = snapshot.model_copy(update={"rows": selected})
    if any(r.quote or r.sector_quote for r in recalled.rows):
        state["financial_other_source_used"] = True
    return _envelope(
        render(recalled, language=language, detail=detail or None),
        user_query,
        "recall",
        needs_selection=any(r.outcome == "choose" for r in recalled.rows),
    )


def make_stock_quote_tool(state, *, history=(), query=None):
    previous = previous_quote_snapshot(history)
    current: Optional[Snapshot] = None
    current_includes_close = False
    clarification_count = 0
    consecutive_failures = 0
    failed_queries: set[tuple[str, ...]] = set()

    @tool(
        args_schema=QuoteRequest,
        description=(
            "Query CN/BJ/HK stocks, ETFs, major CN/HK indices (上证指数, 深证成指, "
            "创业板指, 沪深300, 恒生指数, 恒生科技, 大盘), and A-share sectors. "
            "Operations: latest (fresh), recall (saved snapshot), select (after user "
            "picks a candidate). Pass [] to reuse previous subjects; detail='close' "
            "only for explicit official closing price requests."
        ),
    )
    async def query_stock_quotes(
        stocks: list[str], operation: str = "latest", detail: str = ""
    ) -> str:
        nonlocal \
            current, \
            current_includes_close, \
            clarification_count, \
            consecutive_failures
        QuoteRequest(stocks=stocks, operation=operation, detail=detail)
        terms = [t.strip() for t in stocks if t.strip()]
        language = state.get("_report_language", "zh")
        en = language == "en"
        user_query = state.get("financial_user_query", "")
        snapshot = current or previous
        rows = snapshot.rows if snapshot else []
        clarifications = state.get("user_clarifications", [])

        if operation == "recall":
            return _handle_recall(snapshot, terms, detail, language, state, user_query)

        lookup = query or query_quotes
        want_close = detail == "close"

        if operation == "select":
            if not snapshot or not any(r.outcome == "choose" for r in rows):
                msg = (
                    "No candidate list pending."
                    if en
                    else "当前没有待选择的候选标的或板块。"
                )
                return _envelope(msg, user_query, "select", stop_retrying=True)
            if current is not None:
                choices = clarifications[clarification_count:]
            elif _match_candidate(snapshot, user_query):
                choices = [user_query]
            elif terms and all(t.casefold() in user_query.casefold() for t in terms):
                choices = terms
            else:
                choices = []
            matched = (
                [_match_candidate(snapshot, c) for c in choices] if choices else []
            )
            if not matched or not all(matched):
                return _envelope(
                    render(snapshot, language=language),
                    user_query,
                    "select",
                    needs_selection=True,
                    stop_retrying=True,
                )
            pairs = [m for m in matched if m is not None]
            fetched = (
                await lookup([code for _, code in pairs], confirm_close=True)
                if want_close
                else await lookup([code for _, code in pairs])
            )
            # Merge resolved candidate(s) in-place, preserving other turn stocks.
            merged_rows = list(snapshot.rows)
            for (row_idx, _), new_row in zip(pairs, fetched.rows):
                merged_rows[row_idx] = new_row
            current = fetched.model_copy(update={"rows": merged_rows})
            current_includes_close = want_close
            clarification_count = len(clarifications)
            consecutive_failures = 0
            state["stock_quote_snapshot"] = current.model_dump(mode="json")
            if any(r.quote or r.sector_quote for r in current.rows):
                state["financial_other_source_used"] = True
            return _envelope(
                render(fetched, language=language, detail=detail or None),
                user_query,
                "select",
                needs_selection=any(r.outcome == "choose" for r in current.rows),
            )

        terms = terms or [r.requested for r in rows]
        if not terms:
            msg = (
                "Specify a stock, index, or sector."
                if en
                else "请指定要查询的股票、指数或板块。"
            )
            return _envelope(msg, user_query, "latest", stop_retrying=True)
        lookups = [
            saved.pop()
            if len(
                saved := {
                    _resolved_term(r) for r in rows if t.casefold() in _row_names(r)
                }
            )
            == 1
            else t
            for t in terms
        ]
        sig = tuple(k.casefold() for k in lookups)
        if sig in failed_queries or consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            msg = (
                "Out of supported scope (CN/BJ/HK stocks, ETFs, major CN/HK indices, "
                "A-share sectors; US stocks and market-wide rankings unsupported)."
                if en
                else (
                    "所查标的暂无可用行情或超出支持范围（支持沪深京A股、ETF、港股、"
                    "主要中港指数及A股板块，暂不支持美股与全市场涨跌幅排行）。"
                )
            )
            return _envelope(msg, user_query, "latest", stop_retrying=True)

        if (
            current is not None
            and (not want_close or current_includes_close)
            and lookups == [_resolved_term(r) for r in current.rows]
        ):
            result = current
        else:
            result = (
                await lookup(lookups, confirm_close=True)
                if want_close
                else await lookup(lookups)
            )
            if len(result.rows) == len(terms):
                result = result.model_copy(
                    update={
                        "rows": [
                            r.model_copy(update={"requested": t})
                            for r, t in zip(result.rows, terms)
                        ]
                    }
                )
            current, current_includes_close = result, want_close
            clarification_count = len(clarifications)
            state["stock_quote_snapshot"] = result.model_dump(mode="json")

        all_bad = bool(result.rows) and all(
            r.outcome == "unavailable" for r in result.rows
        )
        if all_bad:
            consecutive_failures += 1
            failed_queries.add(sig)
        else:
            consecutive_failures = 0
        if any(r.quote or r.sector_quote for r in result.rows):
            state["financial_other_source_used"] = True
        return _envelope(
            render(result, language=language, detail=detail or None),
            user_query,
            "latest",
            needs_selection=any(r.outcome == "choose" for r in result.rows),
            stop_retrying=all_bad and consecutive_failures >= MAX_CONSECUTIVE_FAILURES,
        )

    return query_stock_quotes
