"""Bounded report repairs backed by the existing HTML renderer and artifact sink."""

import functools
import hashlib
import inspect
import json
import logging
import re
from pathlib import Path

from dbgpt.configs.model_config import PILOT_PATH
from dbgpt.core.interface.report_capture import (
    ArtifactCaptureContext,
    InMemoryArtifactSink,
)

from .report_spec import merge_report_data

MAX_RENDER_ATTEMPTS = 3
MAX_INVOCATION_FAILURES = 3
MAX_DOCUMENT_ATTEMPTS = 6
MAX_PREFLIGHT_ATTEMPTS = 6
MAX_REPORT_CALLS = (
    MAX_RENDER_ATTEMPTS
    + MAX_DOCUMENT_ATTEMPTS
    + MAX_PREFLIGHT_ATTEMPTS
    + MAX_INVOCATION_FAILURES
)

logger = logging.getLogger(__name__)


async def render_saved_report(state, skills_dir, *, allow_unavailable_references=False):
    """Finalize saved content once without an LLM or another analysis execution.

    Retry budgets constrain model-driven repairs. This deterministic render uses
    the same document, result and citation validation even after that budget is
    exhausted, so a policy fix can unblock an existing complete report.
    """
    calculation = state.get("_report_missing_calculation")
    if calculation and not calculation.get("result_artifact_id"):
        return False
    presentation = state.get("_report_presentation") or {}
    if presentation.get("content") and not state.get("_report_html_error"):
        return True
    saved = state.get("_report_saved_arguments") or {}
    if not any(saved.get(key) for key in ("template_path", "html", "file_path")):
        return False
    from .html_interpreter import make_html_interpreter

    arguments = {
        key: saved[key]
        for key in ("html", "title", "file_path", "template_path", "data")
        if key in saved
    }
    try:
        renderer = inspect.unwrap(
            make_html_interpreter(
                state,
                skills_dir,
                allow_unavailable_references=allow_unavailable_references,
            )
        )
        result = json.loads(await renderer(**arguments))
        if state.get("_report_html_error") or not any(
            chunk.get("output_type") == "html" for chunk in result.get("chunks", [])
        ):
            return False
        for key in (
            "_report_retry_exhausted",
            "_report_failure_response",
            "_report_agent_failure",
            "_report_last_render_error",
        ):
            state.pop(key, None)
    except Exception as error:
        state["_report_html_error"] = str(error) or type(error).__name__
        logger.exception("Unable to finalize the saved report")
        return False
    try:
        _save_checkpoint(state, arguments, None)
    except Exception:
        logger.exception("Unable to checkpoint the finalized report")
    return True


def _checkpoint_path(conv_uid):
    token = str(conv_uid or "unknown")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", token):
        token = hashlib.sha256(token.encode()).hexdigest()
    return Path(PILOT_PATH) / "tmp" / token / "report-repair" / "checkpoint.json"


def retain_html_candidate(state, html, title):
    """Keep the latest partial document, while protecting a complete candidate."""
    if not isinstance(html, str) or not html.strip():
        return
    state["_report_last_attempt_html"] = html
    previous = state.get("_report_pending_html", "")

    def complete(value):
        return bool(
            re.search(r"<html(?:\s|>)", value, re.I)
            and re.search(r"<body(?:\s|>)", value, re.I)
            and re.search(r"</body\s*>", value, re.I)
            and re.search(r"</html\s*>\s*$", value, re.I)
        )

    if not complete(previous) or complete(html):
        state["_report_pending_html"] = html
        state["_report_pending_title"] = title


def _save_checkpoint(state, arguments, error):
    sink = state.get("_report_artifact_sink")
    artifacts = sink.snapshot() if sink is not None else []
    path = _checkpoint_path(state.get("conv_id"))
    argument_html = arguments.get("html")
    argument_html = argument_html if isinstance(argument_html, str) else ""
    argument_title = arguments.get("title")
    argument_title = argument_title if isinstance(argument_title, str) else "Report"
    payload = {
        "version": 1,
        "conv_uid": state.get("conv_id"),
        "run_id": getattr(getattr(sink, "context", None), "run_id", None),
        "arguments": state.get("_report_saved_arguments", arguments),
        "error": error,
        "render_error": state.get("_report_last_render_error"),
        "phase": "render"
        if state.get("_report_render_phase")
        or state.get("_report_html_attempted")
        or state.get("_report_pending_html")
        else "analysis",
        "original_request": state.get("_report_original_request"),
        "execution_progress": state.get("_report_execution_progress", {}),
        "pending_html": state.get("_report_pending_html", argument_html),
        "last_attempt_html": state.get("_report_last_attempt_html", argument_html),
        "title": state.get("_report_pending_title", argument_title),
        "artifacts": [artifact.model_dump(mode="json") for artifact in artifacts],
        "attempt_count": state.get("_report_render_attempts", 0),
        "document_attempt_count": state.get("_report_document_attempts", 0),
        "preflight_attempt_count": state.get("_report_preflight_attempts", 0),
        "tool_call_count": state.get("_report_tool_call_count", 0),
        "missing_calculation": state.get("_report_missing_calculation"),
        "calculation_requests": state.get("_report_calculation_requests", 0),
        "draft": state.get("_report_draft"),
        "model_output": state.get("_report_model_output"),
        "invocation_failure_count": state.get("_report_invocation_failures", 0),
        "invocation_error": state.get("_report_last_invocation_error"),
        "execution_step_map": state.get("_report_execution_step_map", {}),
        "required_recommendation_count": state.get(
            "_report_required_recommendation_count"
        ),
        "knowledge_requested": state.get("_report_knowledge_requested", False),
        "knowledge_space": state.get("_report_knowledge_space"),
        "trusted_template_scripts": state.get("_report_saved_template_scripts", False),
        "template_path": state.get("_report_template_path")
        or (
            (state.get("_report_saved_arguments") or {}).get("template_path")
            if isinstance(state.get("_report_saved_arguments"), dict)
            else ""
        )
        or "",
        "complete": not bool(error),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)
    pending_path = path.with_name("pending.html")
    pending_temporary = pending_path.with_suffix(".tmp")
    pending_temporary.write_text(payload["pending_html"], encoding="utf-8")
    pending_temporary.replace(pending_path)
    path.with_name("last-attempt.html").write_text(
        payload["last_attempt_html"], encoding="utf-8"
    )
    state["_report_checkpoint_path"] = str(path)
    state["_report_pending_path"] = str(pending_path)
    draft = state.get("_report_draft")
    if isinstance(draft, dict) and draft.get("content"):
        draft_path = path.with_name("draft.html")
        draft_path.write_text(draft["content"], encoding="utf-8")
        state["_report_draft_path"] = str(draft_path)


def is_report_resume_request(text):
    """Recognize report continuation with instructions as well as a bare resume."""
    return bool(
        re.search(
            r"(?:重试|恢复|修复|继续).{0,24}(?:报告|渲染)|"
            r"(?:报告|渲染).{0,24}(?:重试|恢复|修复|继续)|"
            r"(?:retry|resume|continue).{0,24}(?:report|render)|"
            r"\bretry_saved\b|"
            r"^\s*(?:继续|继续分析|继续执行|continue|resume)\s*[。.!！]?\s*$",
            text,
            re.I,
        )
    )


def restore_report_checkpoint(conv_uid, state, *, include_completed=False):
    """Resume an explicitly requested report repair without changing artifact IDs."""
    from pydantic import TypeAdapter

    from dbgpt.core.interface.report import Artifact

    path = _checkpoint_path(conv_uid)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("conv_uid") != conv_uid or (
        payload.get("complete") and not include_completed
    ):
        return None
    sink = InMemoryArtifactSink(
        ArtifactCaptureContext(conv_uid=conv_uid, run_id=payload["run_id"])
    )
    adapter = TypeAdapter(Artifact)
    for raw in payload["artifacts"]:
        sink.record(adapter.validate_python(raw))
    state["_report_pending_html"] = payload.get("pending_html", "")
    state["_report_last_attempt_html"] = payload.get(
        "last_attempt_html", state["_report_pending_html"]
    )
    state["_report_pending_title"] = payload.get("title", "Report")
    state["_report_saved_template_scripts"] = payload.get(
        "trusted_template_scripts", False
    )
    state["_report_saved_arguments"] = payload.get("arguments", {})
    saved_template = (payload.get("arguments") or {}).get("template_path")
    state["_report_template_path"] = (
        payload.get("template_path") or saved_template or ""
    )
    state["_report_last_render_error"] = payload.get("render_error") or payload.get(
        "error"
    )
    state["_report_execution_step_map"] = payload.get("execution_step_map", {})
    state["_report_required_recommendation_count"] = payload.get(
        "required_recommendation_count"
    )
    state["_report_knowledge_requested"] = payload.get("knowledge_requested", False)
    state["_report_knowledge_space"] = payload.get("knowledge_space") or state.get(
        "_report_knowledge_space"
    )
    state["_report_render_phase"] = payload.get("phase", "render") == "render"
    state["_report_resume_analysis"] = not state["_report_render_phase"]
    state["_report_original_request"] = payload.get("original_request")
    state["_report_execution_progress"] = payload.get("execution_progress", {})
    state["_report_missing_calculation"] = payload.get("missing_calculation")
    state["_report_calculation_requests"] = payload.get("calculation_requests", 0)
    state["_report_draft"] = payload.get("draft")
    state["_report_checkpoint_path"] = str(path)
    state["_report_pending_path"] = str(path.with_name("pending.html"))
    if state["_report_render_phase"]:
        # A stop applies to the old invocation's budget. An explicit resume has
        # a fresh bounded budget and should receive the actual renderer error.
        previous = payload.get("render_error") or payload.get("error") or ""
        state["_report_html_error"] = previous.split("\nREPORT_REPAIR_STOPPED:", 1)[0]
    return sink


def save_execution_checkpoint(state, error):
    """Retain existing evidence when execution stops before report rendering."""
    _save_checkpoint(state, state.get("_report_saved_arguments", {}), error)


def _failure_identity(error):
    """Location shifts and unrelated HTML edits do not count as repair progress."""
    code, _, details = error.partition(":")
    try:
        entries, _ = json.JSONDecoder().raw_decode(details.lstrip())
    except ValueError:
        return None
    if not isinstance(entries, list):
        return None
    stable = [
        {
            key: value
            for key, value in entry.items()
            if key not in {"html_offset", "html_line", "old"}
        }
        for entry in entries
        if isinstance(entry, dict)
    ]
    for entry in stable:
        if isinstance(entry.get("container"), str):
            entry["container"] = re.sub(r", HTML offset \d+", "", entry["container"])
    return code + ":" + json.dumps(stable, sort_keys=True, ensure_ascii=False)


def _record_failure(
    state,
    arguments,
    error,
    *,
    reached_renderer,
    document_incomplete=False,
    preflight=False,
    instruction_hint=None,
):
    """Budget document assembly, complete renders and invalid calls separately."""
    if state.get("_report_retry_exhausted"):
        return state.get("_report_failure_response") or json.dumps(
            {
                "chunks": [
                    {
                        "output_type": "text",
                        "content": state.get("_report_html_error", error),
                    }
                ],
                "error_code": "REPORT_REPAIR_STOPPED",
                "retryable": False,
            },
            ensure_ascii=False,
        )
    if preflight:
        state["_report_last_render_error"] = error
        fingerprint_key = "_report_last_preflight_fingerprint"
        count = state.get("_report_preflight_attempts", 0) + 1
        state["_report_preflight_attempts"] = count
        limit = MAX_PREFLIGHT_ATTEMPTS
        candidate = state.get("_report_saved_arguments", arguments)
    elif document_incomplete:
        state["_report_last_render_error"] = error
        fingerprint_key = "_report_last_document_fingerprint"
        count = min(
            state.get("_report_document_attempts", 0) + 1, MAX_DOCUMENT_ATTEMPTS
        )
        state["_report_document_attempts"] = count
        limit = MAX_DOCUMENT_ATTEMPTS
        candidate = (
            state.get("_report_saved_arguments", arguments)
            if arguments.get("template_path")
            else state.get("_report_pending_html", "")
        )
    elif reached_renderer:
        state["_report_last_render_error"] = error
        fingerprint_key = "_report_last_error_fingerprint"
        count = state.get("_report_render_attempts", 0)
        limit = MAX_RENDER_ATTEMPTS
        candidate = state.get("_report_last_attempt_html", "") or arguments
    else:
        state["_report_last_invocation_error"] = error
        fingerprint_key = "_report_last_invocation_error_fingerprint"
        count = min(
            state.get("_report_invocation_failures", 0) + 1, MAX_INVOCATION_FAILURES
        )
        state["_report_invocation_failures"] = count
        limit = MAX_INVOCATION_FAILURES
        candidate = arguments
    if isinstance(candidate, dict):
        # retry_saved changes execution mode, not the assembled content.
        candidate = {
            key: value
            for key, value in candidate.items()
            if key not in {"retry_saved", "repair_patches"}
        }
    encoded = json.dumps(candidate, sort_keys=True, ensure_ascii=False)
    identity = _failure_identity(error)
    fingerprint = (
        identity
        if reached_renderer
        and error.startswith("REPORT_TARGET_BINDING_REQUIRED:")
        and identity
        else (identity or error) + ":" + hashlib.sha256(encoded.encode()).hexdigest()
    )
    repeated = state.get(fingerprint_key) == fingerprint
    # A complete template is regenerated from a spec. Its length/prefix may change
    # while recommendations or bindings improve, and cannot measure progress.
    # Tail preservation applies only to repairing raw, truncated HTML.
    if (
        document_incomplete
        and error.startswith("HTML_DOCUMENT_INCOMPLETE:")
        and not arguments.get("template_path")
    ):
        previous_length = state.get("_report_document_length")
        previous_prefix_length = state.get("_report_document_prefix_length", 0)
        previous_prefix_hash = state.get("_report_document_prefix_hash")
        if previous_length is not None:
            repeated = (
                repeated
                or len(candidate) <= previous_length
                or (
                    hashlib.sha256(
                        candidate[:previous_prefix_length].encode()
                    ).hexdigest()
                    != previous_prefix_hash
                )
            )
        state["_report_document_length"] = len(candidate)
        state["_report_document_prefix_length"] = max(0, len(candidate) - 240)
        state["_report_document_prefix_hash"] = hashlib.sha256(
            candidate[: state["_report_document_prefix_length"]].encode()
        ).hexdigest()
    state[fingerprint_key] = fingerprint
    exhausted = (
        repeated
        or count >= limit
        or state.get("_report_tool_call_count", 0) >= MAX_REPORT_CALLS
    )
    state["_report_retry_exhausted"] = exhausted
    state["_report_html_error"] = error
    _save_checkpoint(state, arguments, error)
    if exhausted:
        stage = (
            "preflight"
            if preflight
            else "document"
            if document_incomplete
            else "render"
            if reached_renderer
            else "invocation"
        )
        instruction = (
            f"REPORT_REPAIR_STOPPED: repeated {stage} failure without progress "
            f"or {stage} limit reached. "
        )
    elif state.get("_report_saved_arguments", {}).get("template_path"):
        placeholder_mode = (state.get("_report_template_contract") or {}).get(
            "mode"
        ) == "placeholders"
        instruction = (
            "Keep the saved template and artifacts. Call retry_saved=true with "
            "data containing the corrected or missing named placeholders; existing "
            "fields are preserved. Use the fields declared by this template, "
            "not the business REPORT_SPEC/sections schema. Do not resend rendered "
            "HTML or rerun completed analysis. "
            if placeholder_mode
            else "Keep the saved template and artifacts. Fix the spec: call "
            "retry_saved=true "
            "with data (REPORT_SPEC) carrying the complete corrected spec, or use "
            "REPORT_SPEC_APPEND to add only missing sections/kpis, and a smaller "
            "spec when the previous call was cut off. Rendered HTML patches are not "
            "accepted for a template report. REPORT_SPEC updates preserve omitted "
            "root fields, replace sections/kpis lists, and delete root fields set "
            "to null. Remove unsupported root fields with null when repairing. "
        )
        if error.startswith("REPORT_REQUIREMENT_MISSING:") and not placeholder_mode:
            instruction += (
                "Use the document assembly budget to append the missing actionable "
                "items under sections[].recommendations, with heading containing "
                "建议 or recommendations. Changed template HTML is progress even "
                "at the same length; an identical failed candidate still stops. "
            )
    elif state.get("_report_pending_html", "").strip():
        instruction = (
            'Use retry_saved=true with repair_patches=[{"old":"exact unique saved HTML '
            'anchor","new":"corrected anchor"}]. Supply html_offset only for '
            "repeated anchors; "
            "it must point to the beginning of old, not a number inside an "
            "expanded element. "
            "Copy from saved HTML, not an earlier model draft. For "
            "truncation, extend the "
            "saved tail with missing content. Preserve existing evidence. "
            "The latest renderer errors replace previous targets; do not "
            "repeat accepted patches. "
        )
    else:
        instruction = "Correct only the tool arguments; reuse completed evidence. "
    if instruction_hint:
        instruction = instruction_hint + instruction
    attempts = state.get("_report_render_attempts", 0)
    invocation_failures = state.get("_report_invocation_failures", 0)
    document_attempts = state.get("_report_document_attempts", 0)
    preflight_attempts = state.get("_report_preflight_attempts", 0)
    previous = state.get("_report_last_render_error")
    previous_code = previous.split(":", 1)[0] if previous else None
    repair_context = None
    if not reached_renderer and error.startswith("REPORT_REPAIR_INPUT_INVALID:"):
        try:
            targets, _ = json.JSONDecoder().raw_decode(
                (previous or "").partition(":")[2].lstrip()
            )
        except ValueError:
            targets = []
        if isinstance(targets, list):
            repair_context = {
                "pending_html_sha256": hashlib.sha256(
                    state.get("_report_pending_html", "").encode()
                ).hexdigest(),
                "target_count": len(targets),
                "target_examples": targets[:3],
            }
            instruction += (
                "Read the saved HTML before retrying. Current target examples: "
                + json.dumps(targets[:3], ensure_ascii=False)
                + ". "
            )
    message = (
        f"{error}\n{instruction}Render attempts: {attempts}/{MAX_RENDER_ATTEMPTS}; "
        f"document assembly attempts: {document_attempts}/{MAX_DOCUMENT_ATTEMPTS}; "
        f"preflight attempts: {preflight_attempts}/{MAX_PREFLIGHT_ATTEMPTS}; "
        "consecutive invocation failures: "
        f"{invocation_failures}"
        "/"
        f"{MAX_INVOCATION_FAILURES}"
        "; "
        f"saved HTML: {state['_report_pending_path']}; "
        f"original artifacts: {state['_report_checkpoint_path']}. "
        "Do not rerun completed analysis."
    )
    if not reached_renderer and previous_code:
        message += (
            f" Previous renderer error: {previous_code}; details remain in checkpoint."
        )
    if exhausted:
        state["_report_html_error"] = message
    result = json.dumps(
        {
            "chunks": [{"output_type": "text", "content": message}],
            "error_code": error.split(":", 1)[0],
            "previous_render_error_code": previous_code,
            "render_attempts": attempts,
            "document_attempts": document_attempts,
            "preflight_attempts": preflight_attempts,
            "call_count": state.get("_report_tool_call_count", 0),
            "phase": "preflight"
            if preflight
            else "document"
            if document_incomplete
            else "render"
            if reached_renderer
            else "invocation",
            "invocation_failures": invocation_failures,
            "retryable": not exhausted,
            **({"repair_context": repair_context} if repair_context else {}),
            **(
                {"model_output": state["_report_model_output"]}
                if state.get("_report_model_output")
                else {}
            ),
        },
        ensure_ascii=False,
    )
    state["_report_failure_response"] = result
    return result


def _truncation_hint(state) -> str | None:
    """Tell the model its arguments were cut off by the output limit.

    A report spec that repeats one reference node per table cell overruns the
    model's output budget, and an unparsable call is otherwise indistinguishable
    from a careless syntax error.
    """
    output = state.get("_report_model_output")
    if not isinstance(output, dict) or output.get("finish_reason") != "length":
        return None
    return (
        "The arguments were cut off by the model output limit, so no render was "
        "attempted. Emit a much smaller payload: keep template_path, and name each "
        'table as {"artifact_id": "<producer id>", "columns": [{"field": "gmv", '
        '"label": "GMV", "format": "money2"}]} so the engine expands the rows - never '
        "write one reference node per cell, and drop optional prose. "
    )


def record_report_invocation_failure(state, raw_call, reason):
    """Retain malformed calls without consuming the actual render budget."""
    if state.get("_report_retry_exhausted"):
        return state.get("_report_failure_response")
    state["_report_tool_call_count"] = state.get("_report_tool_call_count", 0) + 1
    state["_report_html_attempted"] = True
    error = (
        "HTML_TOOL_ARGUMENT_INVALID: html_interpreter arguments could not be parsed: "
        + str(reason)[:1000]
    )
    result = _record_failure(
        state,
        {"raw_call": str(raw_call)},
        error,
        reached_renderer=False,
        instruction_hint=_truncation_hint(state),
    )
    path = Path(state["_report_checkpoint_path"]).with_name("last-model-call.txt")
    path.write_text(str(raw_call), encoding="utf-8")
    state["_report_html_error"] = json.loads(result)["chunks"][0]["content"]
    return result


def apply_repair_patches(html, patches):
    """Resolve all edits against one saved document, then apply them atomically."""
    if patches is None:
        return html
    if not isinstance(patches, list):
        raise ValueError("REPORT_REPAIR_INPUT_INVALID: repair_patches must be a list")
    edits = []
    for index, patch in enumerate(patches):
        if (
            not isinstance(patch, dict)
            or not isinstance(patch.get("old"), str)
            or not patch["old"]
            or not isinstance(patch.get("new"), str)
        ):
            raise ValueError(
                (
                    "REPORT_REPAIR_INPUT_INVALID: "
                    "repair_patches["
                    f"{index}"
                    "] requires nonempty old and string "
                    "new"
                )
            )
        start = patch.get("html_offset")
        if start is not None:
            if (
                type(start) is int
                and 0 <= start <= len(html)
                and not html.startswith(patch["old"], start)
                and "<" in patch["old"]
                and html.count(patch["old"]) == 1
            ):
                # An author may expand a numeric anchor to its whole inline
                # element while retaining the number's offset. The exact,
                # unique HTML anchor is sufficient to locate the same edit.
                start = html.index(patch["old"])
            if (
                type(start) is not int
                or start < 0
                or not html.startswith(patch["old"], start)
            ):
                raise ValueError(
                    "REPORT_REPAIR_INPUT_INVALID: "
                    "repair_patches["
                    f"{index}"
                    "] does not match old at html_offset; "
                    "read the saved HTML and copy its exact reported anchor. "
                    + json.dumps(
                        {
                            "attribute": f"repair_patches[{index}].html_offset",
                            "html_offset": start,
                            "html_line": html.count("\n", 0, start) + 1
                            if type(start) is int and 0 <= start <= len(html)
                            else None,
                            "unique_old_offset": html.index(patch["old"])
                            if html.count(patch["old"]) == 1
                            else None,
                        },
                        ensure_ascii=False,
                    )
                    + ". read_file offset is a zero-based line number; use html_line "
                    "minus one. "
                    "If old is unique, omit html_offset; never guess a stale offset."
                )
        else:
            count = html.count(patch["old"])
            if count != 1:
                raise ValueError(
                    (
                        "REPORT_REPAIR_INPUT_INVALID: "
                        "repair_patches["
                        f"{index}"
                        "].old matches "
                        f"{count}"
                        " locations; read the saved HTML and copy its exact reported "
                        "anchor, or supply the reported "
                        "html_offset"
                    )
                )
            start = html.index(patch["old"])
        edits.append((start, start + len(patch["old"]), patch["new"], index))
    edits.sort()
    for previous, current in zip(edits, edits[1:]):
        if current[0] < previous[1]:
            raise ValueError(
                (
                    "REPORT_REPAIR_INPUT_INVALID: "
                    "repair_patches["
                    f"{previous[3]}"
                    "] and repair_patches["
                    f"{current[3]}"
                    "] overlap in saved HTML; merge them into one "
                    "patch"
                )
            )
    for start, end, replacement, _ in reversed(edits):
        html = html[:start] + replacement + html[end:]
    return html


def report_repair_guard(state):
    """Bound incomplete drafts independently of the initial render and two repairs."""

    def decorate(function):
        signature = inspect.signature(function)

        @functools.wraps(function)
        async def guarded(*args, **kwargs):
            if (
                state.get("_report_lock_after_completion")
                and state.get("_report_success_response")
                and not state.get("_report_html_error")
            ):
                return state["_report_success_response"]
            if state.get("_report_retry_exhausted"):
                if state.get("_report_failure_response"):
                    return state["_report_failure_response"]
                return json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": state["_report_html_error"],
                            }
                        ],
                        "error_code": "REPORT_REPAIR_STOPPED",
                        "retryable": False,
                    },
                    ensure_ascii=False,
                )
            state["_report_tool_call_count"] = (
                state.get("_report_tool_call_count", 0) + 1
            )
            arguments = dict(kwargs)
            source_arguments = dict(state.get("_report_saved_arguments", {}))
            reached_renderer = False
            state["_report_attempt_phase"] = "invocation"
            state["_report_render_phase"] = True
            try:
                try:
                    bound = signature.bind(*args, **kwargs)
                except TypeError as error:
                    raise ValueError(f"HTML_TOOL_ARGUMENT_INVALID: {error}") from error
                bound.apply_defaults()
                arguments = dict(bound.arguments)
                for attribute in ("html", "title", "file_path", "template_path"):
                    if not isinstance(arguments.get(attribute, ""), str):
                        raise ValueError(
                            (
                                "HTML_TOOL_ARGUMENT_INVALID: "
                                "attribute="
                                f"{attribute}"
                                "; expected a "
                                "string"
                            )
                        )
                if type(arguments.get("retry_saved", False)) is not bool:
                    raise ValueError(
                        (
                            "HTML_TOOL_ARGUMENT_INVALID: attribute=retry_saved; "
                            "expected a "
                            "boolean"
                        )
                    )
                if (
                    arguments.get("retry_saved")
                    and not state.get("_report_pending_html")
                    and not state.get("_report_saved_arguments")
                ):
                    # The explicit tool argument is sufficient recovery intent even
                    # when the user's wording did not match the initial prompt gate.
                    restored = restore_report_checkpoint(state.get("conv_id"), state)
                    if restored is not None:
                        current_sink = state.get("_report_artifact_sink")
                        if current_sink is not None:
                            for artifact in current_sink.snapshot():
                                restored.record(artifact)
                        state["_report_artifact_sink"] = restored
                        source_arguments = dict(
                            state.get("_report_saved_arguments", {})
                        )
                source_template = (source_arguments or {}).get("template_path") or ""
                established_template = (
                    state.get("_report_template_path") or source_template
                )
                if (
                    established_template
                    and not arguments.get("template_path")
                    and (arguments.get("html") or arguments.get("file_path"))
                ):
                    # The conversation already renders its report from a spec.
                    # A hand-written document bypasses the spec, cannot fit the
                    # output budget and used to erase the saved template.
                    raise ValueError(
                        "REPORT_TEMPLATE_REQUIRED: this conversation renders its "
                        f"report from template_path={established_template}; call "
                        "retry_saved=true with corrected template data instead "
                        "of html or file_path. "
                    )
                if (
                    not arguments.get("template_path")
                    and not arguments.get("html")
                    and not arguments.get("file_path")
                    and arguments.get("data")
                    and established_template
                ):
                    # A spec update for the template this turn already renders
                    # from: the model does not have to repeat the template path.
                    arguments["template_path"] = established_template
                if not arguments.get("retry_saved") and not any(
                    arguments.get(key, "").strip()
                    for key in ("html", "file_path", "template_path")
                ):
                    raise ValueError(
                        (
                            "HTML_TOOL_ARGUMENT_INVALID: provide html, file_path or "
                            "template_path, or retry_saved=true"
                        )
                    )
                can_update_template = bool(
                    arguments.get("template_path")
                    and not arguments.get("html")
                    and not arguments.get("file_path")
                    and (
                        arguments["template_path"]
                        == source_arguments.get("template_path")
                        or (
                            not source_arguments.get("template_path")
                            and state.get("_report_saved_template_scripts")
                        )
                    )
                )
                pending = state.get("_report_pending_html", "")
                saved_template = state.get("_report_template_path") or (
                    state.get("_report_saved_arguments") or {}
                ).get("template_path")
                if (
                    state.get("_report_html_error")
                    and pending.strip()
                    and not arguments.get("retry_saved")
                    and not can_update_template
                ):
                    if saved_template:
                        raise ValueError(
                            "REPORT_REPAIR_DATA_REQUIRED: this report renders from "
                            f"template_path={saved_template}; call retry_saved=true "
                            "with corrected template data only. Do not resend "
                            "html or repair_patches: the next render rebuilds the "
                            "document from the spec. "
                        )
                    raise ValueError(
                        "REPORT_REPAIR_PATCH_REQUIRED: use retry_saved=true with "
                        "repair_patches for saved HTML, "
                        "or update data using the same saved template; reuse completed "
                        "artifacts. "
                    )
                if arguments.get("retry_saved"):
                    saved = dict(source_arguments)
                    if saved.get("template_path") and bound.arguments.get(
                        "repair_patches"
                    ):
                        # A template report is rebuilt from its spec, so a rendered
                        # HTML patch is discarded by the next render and only costs
                        # output budget the model does not have.
                        raise ValueError(
                            "REPORT_REPAIR_DATA_REQUIRED: this report renders from "
                            f"template_path={saved['template_path']}; repair the spec "
                            "with retry_saved=true and template data only. HTML "
                            "repair_patches are not accepted for template reports. "
                        )
                    if (
                        saved.get("template_path")
                        and bound.arguments.get("data") is None
                    ):
                        # Falling through would replace the template with the saved
                        # rendered HTML and lose the spec that produced it.
                        raise ValueError(
                            "REPORT_REPAIR_DATA_REQUIRED: this report renders from "
                            f"template_path={saved['template_path']}; send retry_saved="
                            "true with the corrected template data instead of "
                            "re-rendering the saved HTML. "
                        )
                    if bound.arguments.get("data") is not None:
                        if not saved.get("template_path") or bound.arguments.get(
                            "repair_patches"
                        ):
                            raise ValueError(
                                (
                                    "REPORT_REPAIR_INPUT_INVALID: data repairs "
                                    "require a saved "
                                    "template and cannot be combined with HTML "
                                    "repair_patches"
                                )
                            )
                        previous_data = saved.get("data") or {}
                        if isinstance(previous_data, str):
                            try:
                                previous_data = json.loads(previous_data)
                            except ValueError:
                                previous_data = {}
                        updates = bound.arguments["data"]
                        if isinstance(updates, str):
                            try:
                                updates = json.loads(updates)
                            except json.JSONDecodeError as error:
                                raise ValueError(
                                    "REPORT_TEMPLATE_DATA_INVALID: attribute=data; "
                                    "JSON line "
                                    f"{error.lineno}"
                                    ", column "
                                    f"{error.colno}"
                                    ", position "
                                    f"{error.pos}"
                                    ": "
                                    f"{error.msg}"
                                ) from error
                        if not isinstance(updates, dict):
                            raise ValueError(
                                (
                                    "REPORT_TEMPLATE_DATA_INVALID: "
                                    "attribute=data must be a JSON "
                                    "object"
                                )
                            )
                        saved.update(
                            html="",
                            file_path="",
                            data=merge_report_data(
                                previous_data
                                if isinstance(previous_data, dict)
                                else {},
                                updates,
                            ),
                        )
                        state["_report_saved_arguments"] = saved
                    else:
                        saved.update(
                            html=state.get("_report_pending_html", ""),
                            title=state.get(
                                "_report_pending_title", arguments["title"]
                            ),
                            file_path="",
                            template_path="",
                            data=None,
                        )
                        if not saved["html"]:
                            raise ValueError(
                                (
                                    "REPORT_REPAIR_INPUT_INVALID: no saved HTML; "
                                    "correct the "
                                    "existing template_path/data or "
                                    "file_path"
                                )
                            )
                    arguments.update(
                        {
                            key: value
                            for key, value in saved.items()
                            if key in signature.parameters
                        }
                    )
                    arguments["retry_saved"] = True
                    arguments["repair_patches"] = bound.arguments.get("repair_patches")
                html = arguments.get("html", "")
                if arguments.get("template_path"):
                    # Remember the spec-driven contract for this conversation so a
                    # later hand-written document cannot silently replace it.
                    state["_report_template_path"] = arguments["template_path"]
                if not arguments.get("retry_saved") and can_update_template:
                    if isinstance(source_arguments.get("data"), dict) and isinstance(
                        arguments.get("data"), dict
                    ):
                        arguments["data"] = merge_report_data(
                            source_arguments["data"], arguments["data"]
                        )
                    if arguments.get("title") == "Report":
                        arguments["title"] = source_arguments.get("title", "Report")
                html = apply_repair_patches(html, arguments.get("repair_patches"))
                arguments["html"] = html
                if not arguments.get("retry_saved"):
                    state["_report_saved_arguments"] = dict(arguments)
                retain_html_candidate(state, html, arguments["title"])
                state.pop("_report_html_error", None)
                _save_checkpoint(
                    state, arguments, "HTML_RENDER_PENDING: awaiting renderer output"
                )
                state["_report_invocation_failures"] = 0
                state.pop("_report_last_invocation_error", None)
                state.pop("_report_last_invocation_error_fingerprint", None)
                reached_renderer = True
                state["_report_attempt_phase"] = "preflight"
                state["_report_last_attempt_html"] = ""
                result = await function(**arguments)
                payload = json.loads(result)
                if not state.get("_report_html_error") and not any(
                    chunk.get("output_type") == "html"
                    for chunk in payload.get("chunks", [])
                ):
                    state["_report_html_error"] = (
                        payload.get("error")
                        or "\n".join(
                            str(chunk.get("content") or "")
                            for chunk in payload.get("chunks", [])
                            if chunk.get("output_type") == "text"
                        )
                        or (
                            "HTML_RENDER_RESULT_INVALID: renderer returned no HTML "
                            "output"
                        )
                    )
            except Exception as error:
                state["_report_html_error"] = str(error) or type(error).__name__
                result = json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": state["_report_html_error"],
                            }
                        ]
                    },
                    ensure_ascii=False,
                )
            error = state.get("_report_html_error")
            preflight = (
                reached_renderer and state.get("_report_attempt_phase") == "preflight"
            )
            if error:
                incomplete = reached_renderer and error.startswith(
                    (
                        "HTML_DOCUMENT_INCOMPLETE:",
                        "REPORT_REQUIREMENT_MISSING",
                        "KB_REPORT_BINDING_REQUIRED:",
                    )
                )
                if reached_renderer and not incomplete and not preflight:
                    state["_report_render_attempts"] = (
                        state.get("_report_render_attempts", 0) + 1
                    )
                return _record_failure(
                    state,
                    arguments,
                    error,
                    reached_renderer=reached_renderer,
                    document_incomplete=incomplete,
                    preflight=preflight and not incomplete,
                )
            state["_report_render_attempts"] = (
                state.get("_report_render_attempts", 0) + 1
            )
            state.pop("_report_last_render_error", None)
            _save_checkpoint(state, arguments, None)
            state.pop("_report_last_error_fingerprint", None)
            return result

        return guarded

    return decorate
