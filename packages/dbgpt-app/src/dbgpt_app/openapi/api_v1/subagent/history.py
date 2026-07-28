"""Bounded persistence helpers for parallel sub-agent execution history."""

import copy
import json
from typing import Any, Dict, List, MutableMapping, Optional

MAX_SUBAGENT_HISTORY_BYTES = 256 * 1024

_MAX_STEPS_PER_AGENT = 15
_MAX_CHUNKS_PER_STEP = 2
_MAX_NAME_CHARS = 512
_MAX_GOAL_CHARS = 4_000
_MAX_INTENTION_CHARS = 1_000
_MAX_SQL_CHARS = 8_000
_MAX_RESULT_CHARS = 8_000
_MAX_TEXT_CHUNK_CHARS = 2_000
_MAX_RETAINED_HTML_BYTES = 192 * 1024
_MAX_IMAGE_CHUNK_CHARS = 4_096
_MAX_ARTIFACTS_PER_AGENT = 32
_MAX_ARTIFACT_REF_CHARS = 4_096
_SIZE_SAFETY_BYTES = 1_024

_HTML_OMITTED = "HTML output omitted from history to keep this conversation compact."
_IMAGE_OMITTED = "Large inline image omitted from history; open the generated artifact."
_OUTPUT_OMITTED = "Large step output omitted from history."


def _bounded_text(value: Any, max_chars: int) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    if not text:
        return None
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "…"


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _bounded_content(value: Any, max_chars: int) -> Any:
    if isinstance(value, str):
        return _bounded_text(value, max_chars) or ""
    try:
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        return _bounded_text(str(value), max_chars) or ""
    if len(encoded) <= max_chars:
        return copy.deepcopy(value)
    return encoded[:max_chars] + "…"


def _copy_chunks(raw_chunks: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_chunks, list):
        return []

    chunks: List[Dict[str, Any]] = []
    for raw_chunk in raw_chunks[:_MAX_CHUNKS_PER_STEP]:
        if not isinstance(raw_chunk, dict) or raw_chunk.get("content") is None:
            continue
        output_type = str(raw_chunk.get("output_type") or "text")
        if output_type == "html":
            content = raw_chunk.get("content")
            # Keep HTML atomic: a truncated document cannot render reliably.
            # The aggregate cache below bounds all retained HTML across agents.
            if (
                not isinstance(content, str)
                or len(content.encode("utf-8")) > _MAX_RETAINED_HTML_BYTES
            ):
                copied_chunk: Dict[str, Any] = {
                    "output_type": "text",
                    "content": _HTML_OMITTED,
                }
            else:
                copied_chunk = {"output_type": "html", "content": content}
        elif output_type == "image":
            content = raw_chunk.get("content")
            if (
                not isinstance(content, str)
                or content.startswith("data:")
                or len(content) > _MAX_IMAGE_CHUNK_CHARS
            ):
                copied_chunk = {
                    "output_type": "text",
                    "content": _IMAGE_OMITTED,
                }
            else:
                copied_chunk = {"output_type": "image", "content": content}
        else:
            copied_chunk = {
                "output_type": output_type,
                "content": _bounded_content(
                    raw_chunk.get("content"),
                    _MAX_TEXT_CHUNK_CHARS,
                ),
            }
        title = _bounded_text(raw_chunk.get("title"), _MAX_NAME_CHARS)
        if title:
            copied_chunk["title"] = title
        chunks.append(copied_chunk)
    if len(raw_chunks) > _MAX_CHUNKS_PER_STEP:
        chunks.append({"output_type": "text", "content": _OUTPUT_OMITTED})
    return chunks


def _trim_retained_html(
    state: MutableMapping[str, Dict[str, Any]],
) -> None:
    """Keep complete recent HTML documents within a small aggregate cache."""
    html_chunks = []
    total_bytes = 0
    for agent in state.values():
        for step in agent.get("steps") or []:
            for chunk in step.get("chunks") or []:
                if (
                    isinstance(chunk, dict)
                    and chunk.get("output_type") == "html"
                    and isinstance(chunk.get("content"), str)
                ):
                    content_bytes = len(chunk["content"].encode("utf-8"))
                    html_chunks.append((chunk, content_bytes))
                    total_bytes += content_bytes

    for chunk, content_bytes in html_chunks:
        if total_bytes <= _MAX_RETAINED_HTML_BYTES:
            break
        _replace_chunk(chunk, _HTML_OMITTED)
        total_bytes -= content_bytes


def _new_agent(agent_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "agent_id": agent_id,
        "name": _bounded_text(
            event.get("agent_name") or agent_id,
            _MAX_NAME_CHARS,
        )
        or agent_id,
        "status": "running",
        "lane": _coerce_int(event.get("lane")),
        "batch_id": _coerce_int(event.get("batch_id")),
        "artifact_count": 0,
        "steps": [],
    }


def _copy_artifact(raw_artifact: Dict[str, Any]) -> Optional[Dict[str, str]]:
    raw_url = raw_artifact.get("url")
    if (
        not isinstance(raw_url, str)
        or raw_url.startswith("data:")
        or len(raw_url) > _MAX_ARTIFACT_REF_CHARS
    ):
        return None
    if not raw_url:
        return None
    artifact = {
        "type": _bounded_text(raw_artifact.get("type"), 32) or "file",
        "url": raw_url,
    }
    title = _bounded_text(raw_artifact.get("title"), _MAX_NAME_CHARS)
    if title:
        artifact["title"] = title
    return artifact


def update_subagent_history(
    state: MutableMapping[str, Dict[str, Any]],
    event: Dict[str, Any],
) -> None:
    """Merge one SSE lifecycle event into a persistable sub-agent snapshot."""
    event_type = event.get("type")
    if event_type == "subagent.artifacts":
        for item in event.get("items") or []:
            if not isinstance(item, dict) or not item.get("agent_id"):
                continue
            agent_id = str(item["agent_id"])
            agent = state.setdefault(agent_id, _new_agent(agent_id, item))
            agent["artifact_count"] = _coerce_int(agent.get("artifact_count")) + 1
            artifact = _copy_artifact(item)
            if artifact:
                artifacts = agent.setdefault("artifacts", [])
                if artifact not in artifacts:
                    if len(artifacts) < _MAX_ARTIFACTS_PER_AGENT:
                        artifacts.append(artifact)
                    else:
                        agent["artifacts_truncated"] = True
        return

    if event_type not in {"agent.start", "agent.step", "agent.done"}:
        return
    if not event.get("agent_id"):
        return

    agent_id = str(event["agent_id"])
    agent = state.setdefault(agent_id, _new_agent(agent_id, event))

    if event_type == "agent.start":
        agent["name"] = (
            _bounded_text(
                event.get("agent_name") or agent.get("name") or agent_id,
                _MAX_NAME_CHARS,
            )
            or agent_id
        )
        goal = _bounded_text(event.get("goal"), _MAX_GOAL_CHARS)
        if goal:
            agent["goal"] = goal
        agent["lane"] = _coerce_int(event.get("lane"), agent.get("lane", 0))
        agent["batch_id"] = _coerce_int(event.get("batch_id"), agent.get("batch_id", 0))
        return

    if event_type == "agent.step":
        action = _bounded_text(event.get("action"), _MAX_NAME_CHARS)
        if not action:
            return
        step: Dict[str, Any] = {"action": action}
        intention = _bounded_text(event.get("intention"), _MAX_INTENTION_CHARS)
        sql = _bounded_text(event.get("sql"), _MAX_SQL_CHARS)
        chunks = _copy_chunks(event.get("chunks"))
        if intention:
            step["intention"] = intention
        if sql:
            step["sql"] = sql
        if chunks:
            step["chunks"] = chunks
        steps = agent.setdefault("steps", [])
        if len(steps) >= _MAX_STEPS_PER_AGENT:
            steps.pop(0)
            agent["history_truncated"] = True
        steps.append(step)
        _trim_retained_html(state)
        return

    status = str(event.get("status") or "done")
    agent["status"] = (
        status if status in {"running", "done", "timeout", "failed"} else "done"
    )
    result = _bounded_text(event.get("result"), _MAX_RESULT_CHARS)
    if result:
        agent["result"] = result
    if event.get("elapsed_ms") is not None:
        agent["elapsed_ms"] = max(0, _coerce_int(event.get("elapsed_ms")))
    agent["batch_id"] = _coerce_int(event.get("batch_id"), agent.get("batch_id", 0))


def fail_running_subagent_history(
    state: MutableMapping[str, Dict[str, Any]],
) -> None:
    """Finalize unfinished agents before persisting an interrupted lead run."""
    for agent in state.values():
        if agent.get("status") == "running":
            agent["status"] = "failed"
            agent.setdefault("result", "Execution was interrupted before completion.")


def _snapshot_size(snapshot: List[Dict[str, Any]]) -> int:
    # Measure the incremental bytes using the same default JSON separators as
    # both production serialization layers. The sentinel reproduces the comma
    # added to an existing payload, while the safety margin covers surrounding
    # view-message metadata.
    base_payload = json.dumps({"_base": None}, ensure_ascii=False)
    snapshot_payload = json.dumps(
        {"_base": None, "sub_agents": snapshot},
        ensure_ascii=False,
    )
    base_record = json.dumps({"content": base_payload}, ensure_ascii=False)
    snapshot_record = json.dumps({"content": snapshot_payload}, ensure_ascii=False)
    return (
        len(snapshot_record.encode("utf-8"))
        - len(base_record.encode("utf-8"))
        + _SIZE_SAFETY_BYTES
    )


def _replace_chunk(chunk: Dict[str, Any], message: str) -> None:
    chunk["output_type"] = "text"
    chunk["content"] = message


def _nested_value_size(value: Any) -> int:
    """Measure one value after the same two JSON encodings used by history."""
    serialized = json.dumps(value, ensure_ascii=False)
    return len(json.dumps(serialized, ensure_ascii=False).encode("utf-8"))


def _latest_agent_suffix(
    snapshot: List[Dict[str, Any]],
    max_bytes: int,
) -> List[Dict[str, Any]]:
    """Retain the largest recent suffix that fits, using logarithmic probes."""
    low = 0
    high = len(snapshot)
    best: List[Dict[str, Any]] = []
    while low <= high:
        count = (low + high) // 2
        candidate = copy.deepcopy(snapshot[-count:]) if count else []
        if candidate and count < len(snapshot):
            candidate[0]["history_truncated"] = True
        if _snapshot_size(candidate) <= max_bytes:
            best = candidate
            low = count + 1
        else:
            high = count - 1
    return best


def build_subagent_history_snapshot(
    state: MutableMapping[str, Dict[str, Any]],
    max_bytes: int = MAX_SUBAGENT_HISTORY_BYTES,
) -> List[Dict[str, Any]]:
    """Return a deterministic snapshot compacted to a hard byte budget."""
    if max_bytes <= 0:
        return []

    snapshot = copy.deepcopy(
        sorted(
            state.values(),
            key=lambda item: (
                _coerce_int(item.get("batch_id")),
                _coerce_int(item.get("lane")),
                str(item.get("agent_id") or ""),
            ),
        )
    )
    snapshot_size = _snapshot_size(snapshot)
    if snapshot_size <= max_bytes:
        return snapshot

    # First compact optional prose and ordinary output in one pass. SQL and
    # complete HTML remain available for the execution-detail view.
    for agent in snapshot:
        for step in agent.get("steps") or []:
            if step.get("sql"):
                step["sql"] = _bounded_text(step["sql"], 2_000)
            if step.get("intention"):
                step["intention"] = _bounded_text(step["intention"], 500)
            for chunk in step.get("chunks") or []:
                if isinstance(chunk, dict) and chunk.get("output_type") not in {
                    "html",
                    "image",
                }:
                    chunk["content"] = _bounded_content(
                        chunk.get("content"),
                        500,
                    )
        if agent.get("goal"):
            agent["goal"] = _bounded_text(agent["goal"], 1_000)
        if agent.get("result"):
            agent["result"] = _bounded_text(agent["result"], 1_000)
    snapshot_size = _snapshot_size(snapshot)
    if snapshot_size <= max_bytes:
        return snapshot

    # Ordinary chunks duplicate the dispatch summary and are the first detail
    # to remove. Keep image references and complete HTML documents.
    for agent in snapshot:
        for step in agent.get("steps") or []:
            chunks = [
                chunk
                for chunk in step.get("chunks") or []
                if isinstance(chunk, dict)
                and chunk.get("output_type") in {"html", "image"}
            ]
            if chunks:
                step["chunks"] = chunks
            else:
                step.pop("chunks", None)
    snapshot_size = _snapshot_size(snapshot)
    if snapshot_size <= max_bytes:
        return snapshot

    # Drop the oldest complete HTML documents only as needed. Estimate the
    # cumulative reduction, then perform one exact snapshot measurement.
    html_chunks = [
        chunk
        for agent in snapshot
        for step in agent.get("steps") or []
        for chunk in step.get("chunks") or []
        if isinstance(chunk, dict)
        and chunk.get("output_type") == "html"
        and isinstance(chunk.get("content"), str)
    ]
    required_reduction = snapshot_size - max_bytes
    reduced_bytes = 0
    for chunk in html_chunks:
        content = chunk["content"]
        reduced_bytes += max(
            0,
            _nested_value_size(content) - _nested_value_size(_HTML_OMITTED),
        )
        _replace_chunk(chunk, _HTML_OMITTED)
        if reduced_bytes >= required_reduction:
            break
    if html_chunks:
        snapshot_size = _snapshot_size(snapshot)
        if snapshot_size <= max_bytes:
            return snapshot

    # Bound detailed traces uniformly instead of repeatedly serializing after
    # every removed step.
    for agent in snapshot:
        steps = agent.get("steps") or []
        if len(steps) > 5:
            agent["steps"] = steps[-5:]
            agent["history_truncated"] = True
    snapshot_size = _snapshot_size(snapshot)
    if snapshot_size <= max_bytes:
        return snapshot

    # Preserve one action (and a short SQL statement) for every agent before
    # considering removal of whole agents.
    for agent in snapshot:
        agent["name"] = _bounded_text(agent.get("name"), 256) or str(
            agent.get("agent_id") or "sub-agent"
        )
        agent.pop("goal", None)
        agent.pop("result", None)
        steps = agent.get("steps") or []
        if steps:
            step = steps[-1]
            step["action"] = _bounded_text(step.get("action"), 256) or "unknown"
            step.pop("intention", None)
            step.pop("chunks", None)
            if step.get("sql"):
                step["sql"] = _bounded_text(step["sql"], 500)
            agent["steps"] = [step]
            agent["history_truncated"] = True
    snapshot_size = _snapshot_size(snapshot)
    if snapshot_size <= max_bytes:
        return snapshot

    # At very high configured concurrency, keep every task row even if its
    # detailed trace no longer fits.
    for agent in snapshot:
        if agent.get("steps"):
            agent["steps"] = []
            agent["history_truncated"] = True
    if _snapshot_size(snapshot) <= max_bytes:
        return snapshot

    # A pathological number of agents can still exceed the hard cap. Retain
    # the most recent batches and mark the first retained row as truncated.
    return _latest_agent_suffix(snapshot, max_bytes)
