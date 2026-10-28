"""Map pi RPC session events onto engine-neutral HarnessEvents.

Reference: pi docs ``json.md`` (shared session-event shapes)
and ``rpc.md``. The mapping is intentionally lossless at the
kind level — consumers see unified events plus the raw record
under ``data.pi`` when they need engine detail.
"""

from typing import Any, Dict, Optional

from ..base import HarnessEvent, HarnessEventKind

#: truncation caps for text carried inside events.
_MAX_TEXT = 8_000
_MAX_DELTA = 2_000
#: Tool results may carry full reports (html envelopes); keep them intact
#: so the artifact pipeline can promote embedded payloads. Display-side
#: caps are applied downstream instead.
_MAX_TOOL_RESULT = 4_000_000


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else (text[:limit] + "…[truncated]")


def _assistant_text_from_message(message: Any) -> str:
    """Extract plain text from a pi assistant message value.

    ``message.content`` is either a string or a list of content
    blocks (``{"type": "text", "text": ...} / {"type": "thinking",
    "thinking": ...}``); only text blocks are public output.
    """
    if message is None:
        return ""
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        return content
    texts: list = []
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "text":
                texts.append(str(block.get("text", "")))
    if texts:
        return "".join(texts)
    return ""


def map_rpc_event(record: Dict[str, Any], round_no: int) -> Optional[HarnessEvent]:
    """Translate one pi RPC event record.

    Returns ``None`` for records with no neutral representation
    (queue updates, session info, extension noise, ...).
    """
    etype = record.get("type")

    if etype == "turn_start":
        return HarnessEvent(kind=HarnessEventKind.TURN_START, round=round_no)

    if etype == "message_update":
        inner = record.get("assistantMessageEvent") or {}
        itype = inner.get("type")
        if itype == "text_delta":
            return HarnessEvent(
                kind=HarnessEventKind.TEXT_DELTA,
                text=str(inner.get("delta", "")),
                round=round_no,
                data={"stream": "text"},
            )
        if itype == "thinking_delta":
            return HarnessEvent(
                kind=HarnessEventKind.THINKING_DELTA,
                text=_clip(str(inner.get("delta", "")), _MAX_DELTA),
                round=round_no,
                data={"stream": "thinking"},
            )
        return None

    if etype == "message_end":
        message = record.get("message") or {}
        role = message.get("role")
        text = _assistant_text_from_message(message)
        if role == "assistant":
            if message.get("stopReason") == "error":
                return HarnessEvent(
                    kind=HarnessEventKind.ERROR,
                    text=str(message.get("errorMessage") or "pi model request failed"),
                    round=round_no,
                    data={"source": "model"},
                )
            return HarnessEvent(
                kind=HarnessEventKind.MESSAGE_END,
                text=text,
                round=round_no,
                data={
                    "has_tool_calls": any(
                        isinstance(block, dict) and block.get("type") == "toolCall"
                        for block in (message.get("content") or [])
                    ),
                },
            )
        return None

    if etype == "turn_end":
        return HarnessEvent(kind=HarnessEventKind.TURN_END, round=round_no)

    if etype == "tool_execution_start":
        # The tool call itself was already surfaced via
        # toolcall_end inside message_update; this event begins
        # local execution. ``args`` feeds the UI gist line (SQL etc).
        return HarnessEvent(
            kind=HarnessEventKind.TOOL_START,
            tool_name=str(record.get("toolName", "")),
            round=round_no,
            data={
                "tool_call_id": record.get("toolCallId"),
                "args": record.get("args"),
            },
        )

    if etype == "tool_execution_update":
        partial = record.get("partialResult") or {}
        detail = _summarize_tool_result(partial)
        return HarnessEvent(
            kind=HarnessEventKind.TOOL_OUTPUT,
            tool_name=str(record.get("toolName", "")),
            text=detail,
            round=round_no,
            data={"tool_call_id": record.get("toolCallId")},
        )

    if etype == "tool_execution_end":
        result = record.get("result") or {}
        detail = _summarize_tool_result(result)
        return HarnessEvent(
            kind=HarnessEventKind.TOOL_END,
            tool_name=str(record.get("toolName", "")),
            text=detail,
            round=round_no,
            data={
                "tool_call_id": record.get("toolCallId"),
                "is_error": bool(record.get("isError", False)),
                "duration_ms": record.get("durationMs"),
            },
        )

    if etype == "auto_retry_start":
        return HarnessEvent(
            kind=HarnessEventKind.RETRY,
            text=str(record.get("errorMessage", "")),
            round=round_no,
            data={
                "attempt": record.get("attempt"),
                "max_attempts": record.get("maxAttempts"),
            },
        )

    if etype in ("compaction_start", "compaction_end"):
        ev = HarnessEvent(kind=HarnessEventKind.COMPACTING, round=round_no)
        ev.data["phase"] = "start" if etype == "compaction_start" else "end"
        ev.data["reason"] = record.get("reason")
        result = record.get("result")
        if isinstance(result, dict):
            ev.data["summary"] = result.get("summary", "")
        return ev

    if etype in ("agent_settled", "agent_end"):
        # pi <= 0.74.x rpc emits ``agent_end`` as the run-completion
        # event; newer builds call it ``agent_settled``. Accept both.
        return HarnessEvent(
            kind=HarnessEventKind.SETTLED,
            round=round_no,
            data={"aborted": bool(record.get("aborted", False))},
        )

    if etype == "extension_error":
        return HarnessEvent(
            kind=HarnessEventKind.ERROR,
            text=str(record.get("error", "extension error")),
            round=round_no,
            data={"source": "extension"},
        )

    return None


def _summarize_tool_result(result: Any) -> str:
    """Extract readable text from a pi tool result value.

    Tool results keep full payloads (html reports can be tens of KB);
    display-side caps are applied by the SSE translation layer.
    """
    if isinstance(result, str):
        return _clip(result, _MAX_TOOL_RESULT)
    if isinstance(result, dict):
        content = result.get("content")
        parts = []
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        parts.append(str(block.get("text", "")))
                    elif block.get("type") == "image":
                        parts.append("[image output]")
        elif isinstance(content, str):
            parts.append(content)
        joined = "\n".join(p for p in parts if p)
        if joined:
            return _clip(joined, _MAX_TOOL_RESULT)
        # fall back to compact JSON
        try:
            return _clip(json_dumps(result), _MAX_TOOL_RESULT)
        except Exception:  # pragma: no cover
            return ""
    return ""


def json_dumps(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, default=str)
