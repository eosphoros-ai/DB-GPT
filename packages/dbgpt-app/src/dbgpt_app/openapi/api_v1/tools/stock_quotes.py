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
from dbgpt_serve.financial_analysis.quotes.providers import _name_key

MAX_CONSECUTIVE_FAILURES = 2
_CONTEXT_PREFIX_RE = re.compile(r"^(?:\[(?:Database|Knowledge): [^\]]+\]\s*)+")


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
                snap = Snapshot.model_validate(payload["stock_quote_snapshot"])
                if any(r.outcome != "unavailable" for r in snap.rows):
                    return snap
                continue
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
        names.update((lst.name, _name_key(lst.name), lst.code, lst.label, lst.symbol))
        if lst.market == "hk" and lst.code.isdigit():
            stripped = lst.code.lstrip("0") or "0"
            names.update((stripped, f"{stripped}.hk", f"hk{stripped}"))
    return {n.casefold() for n in names if n}


def _term_variants(term: str) -> set[str]:
    raw = term.strip()
    variants = {raw.casefold()}
    bracket = re.search(r"[(（]\s*([^()（）]+?)\s*[)）]", raw)
    if bracket:
        variants.add(bracket[1].strip().casefold())
        prefix = raw[: bracket.start()].strip()
        if prefix:
            variants.add(prefix.casefold())
            variants.add(_name_key(prefix))
    bare, _, _ = qualifiers(raw)
    if bare:
        variants.add(bare.casefold())
        variants.add(_name_key(bare))
    return {v for v in variants if v}


def _match_recall_indices(snapshot: Snapshot, terms: list[str]) -> Optional[list[int]]:
    """Match requested recall terms to snapshot row indices in snapshot order."""
    if not terms:
        return list(range(len(snapshot.rows)))
    row_name_sets = [_row_names(r) for r in snapshot.rows]
    matched: set[int] = set()
    for term in terms:
        variants = _term_variants(term)
        hits = [idx for idx, r_names in enumerate(row_name_sets) if variants & r_names]
        if not hits:
            # Allow unambiguous substring match (e.g. "茅台" -> "贵州茅台").
            sub_hits = [
                idx
                for idx, r_names in enumerate(row_name_sets)
                if any(len(v) >= 2 and any(v in rn for rn in r_names) for v in variants)
            ]
            if len(sub_hits) == 1:
                hits = sub_hits
        if not hits:
            return None
        matched.update(hits)
    return sorted(matched)


def _strip_context_prefix(text: str) -> str:
    return _CONTEXT_PREFIX_RE.sub("", (text or "").strip()).strip()


def _resolved_term(row: QuoteRow) -> str:
    if row.sector:
        return row.sector.code
    return row.quote.listing.label if row.quote else row.requested


def _match_candidate(snapshot: Snapshot, selection: str) -> Optional[tuple[int, str]]:
    """Match a unique candidate in pending 'choose' rows as (row_idx, code)."""
    choice = re.sub(
        r"^(?:我选|选择|选|那就|那|option)\s*", "", selection.strip(), flags=re.I
    )
    choice = re.sub(r"\s*(?:\(recommended\)|（推荐）)\s*$", "", choice, flags=re.I)
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
    card_rendered: bool = False,
) -> str:
    if needs_selection and not stop_retrying:
        instr = (
            "Multiple candidates require user disambiguation IN THIS SAME TURN. "
            "Immediately call the `question` tool NOW (do NOT call `terminate` "
            "yet) with each candidate as an option (label with name and code, "
            "e.g. '半导体（BK1036）' or '中芯国际 688981.SH'; set multiple=true "
            "for sector choices). After `question` returns the user's pick, "
            "call `query_stock_quotes(operation='select', stocks=[...])` in the "
            "same turn, then deliver one unified final answer. If the user "
            "dismisses the question, answer with the already-quoted results."
        )
    else:
        instr = (
            "Answer using only observed data. Keep units and necessary caveats. "
            "Never label '收盘价待确认'/'close pending' as an official closing price."
        )
        if card_rendered:
            instr += (
                " A structured quote card is already rendered above your reply; lead "
                "with a concise takeaway and answer the user's extended questions "
                "without repeating the full raw Markdown table."
            )
        else:
            instr += " Keep source links and timestamps."
        if needs_selection:
            instr += (
                " Call `question` to ask the user to pick a candidate before "
                "calling `select`."
            )
        if stop_retrying:
            instr += (
                " Stop retrying unavailable/out-of-scope queries and explain directly."
            )
        if not needs_selection:
            instr += " Deliver your final answer via the `terminate(output=...)` tool."
    return json.dumps(
        {
            "chunks": [{"output_type": "markdown", "content": content}],
            "model_context": {
                "user_request": user_request,
                "operation": operation,
                "needs_selection": needs_selection,
                "stop_retrying": stop_retrying,
                "card_rendered": card_rendered,
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
    matched_indices = _match_recall_indices(snapshot, terms)
    if matched_indices is None:
        msg = (
            "Requested subject absent from saved quote."
            if en
            else "上次报价未包含所选标的。"
        )
        return _envelope(msg, user_query, "recall", stop_retrying=True)
    selected = [snapshot.rows[i] for i in matched_indices]
    recalled = snapshot.model_copy(update={"rows": selected})
    has_quoted = any(r.quote or r.sector_quote for r in recalled.rows)
    if has_quoted:
        state["financial_other_source_used"] = True
        compact = snapshot.model_copy(
            update={
                "display_mode": "compact",
                "recall_detail": detail or None,
                "recall_indices": matched_indices,
            }
        )
        state["stock_quote_snapshot"] = compact.model_dump(mode="json")
    return _envelope(
        render(recalled, language=language, detail=detail or None),
        user_query,
        "recall",
        needs_selection=any(r.outcome == "choose" for r in recalled.rows),
        card_rendered=has_quoted,
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
        state["_stock_quote_tool_ran"] = True
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
            clean_query = _strip_context_prefix(user_query)
            if current is not None:
                new_replies = clarifications[clarification_count:]
                if not new_replies:
                    choices = []
                elif all(_match_candidate(snapshot, c) for c in new_replies):
                    choices = new_replies
                elif terms and all(_match_candidate(snapshot, t) for t in terms):
                    choices = terms
                else:
                    choices = []
            elif _match_candidate(snapshot, clean_query):
                choices = [clean_query]
            elif terms and all(_match_candidate(snapshot, t) for t in terms):
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
            pairs = list(dict.fromkeys(m for m in matched if m is not None))
            fetched = (
                await lookup([code for _, code in pairs], confirm_close=True)
                if want_close
                else await lookup([code for _, code in pairs])
            )
            # Merge resolved candidate(s) in-place, supporting multi-pick from one group
            # while preserving other turn stocks.
            replacements: dict[int, list[QuoteRow]] = {}
            for (row_idx, _), new_row in zip(pairs, fetched.rows):
                replacements.setdefault(row_idx, []).append(new_row)
            merged_rows: list[QuoteRow] = []
            for idx, old_row in enumerate(snapshot.rows):
                if idx in replacements:
                    merged_rows.extend(replacements[idx])
                else:
                    merged_rows.append(old_row)
            current = fetched.model_copy(
                update={
                    "rows": merged_rows,
                    "display_mode": "full",
                    "recall_detail": None,
                    "recall_indices": None,
                }
            )
            current_includes_close = want_close
            clarification_count = len(clarifications)
            consecutive_failures = 0
            has_visible = any(r.outcome != "unavailable" for r in current.rows)
            if has_visible:
                state["stock_quote_snapshot"] = current.model_dump(mode="json")
            if any(r.quote or r.sector_quote for r in current.rows):
                state["financial_other_source_used"] = True
            still_choose = any(r.outcome == "choose" for r in current.rows)
            state["_stock_quote_needs_question"] = still_choose
            return _envelope(
                render(fetched, language=language, detail=detail or None),
                user_query,
                "select",
                needs_selection=still_choose,
                card_rendered=has_visible and not still_choose,
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
            orig_by_lookup: dict[str, str] = {}
            for orig, lk in zip(terms, lookups):
                if orig != lk:
                    orig_by_lookup.setdefault(lk.casefold(), orig)
            if orig_by_lookup:
                result = result.model_copy(
                    update={
                        "rows": [
                            r.model_copy(update={"requested": orig})
                            if (orig := orig_by_lookup.get(r.requested.casefold()))
                            else r
                            for r in result.rows
                        ]
                    }
                )
        all_bad = bool(result.rows) and all(
            r.outcome == "unavailable" for r in result.rows
        )
        if all_bad:
            consecutive_failures += 1
            failed_queries.add(sig)
        else:
            current, current_includes_close = result, want_close
            clarification_count = len(clarifications)
            consecutive_failures = 0
            state["stock_quote_snapshot"] = result.model_dump(mode="json")
        if any(r.quote or r.sector_quote for r in result.rows):
            state["financial_other_source_used"] = True
        needs_sel = any(r.outcome == "choose" for r in result.rows)
        state["_stock_quote_needs_question"] = needs_sel
        return _envelope(
            render(result, language=language, detail=detail or None),
            user_query,
            "latest",
            needs_selection=needs_sel,
            stop_retrying=all_bad and consecutive_failures >= MAX_CONSECUTIVE_FAILURES,
            card_rendered=not all_bad and bool(result.rows) and not needs_sel,
        )

    return query_stock_quotes
