"""Sub-agent result relay (plan stage 3, design spec §4.4 / §问题2).

Industry convention (Anthropic / deer-flow): only the compressed text
conclusion flows back into the lead agent's context; artifacts (images /
HTML) flow to the frontend out-of-band as path references — NOT as bytes,
and NOT into the lead agent's token budget.

``ActionOutput`` already has three layers — content (text conclusion) /
view (render) / resource_value (artifact ref). The observation handed back
to the lead LLM contains only ``text_result``; ``artifacts`` are surfaced to
the frontend and the final artifact aggregation only.
"""

from typing import Any, Dict, List

from dbgpt.agent.util.react_parser import ReActOutputParser


def _extract_final_answer(text: str) -> str:
    """Extract the user-facing answer from a ReAct terminate envelope.

    A sub-agent's ``ActionOutput.content`` can contain the complete model
    response (Thought / Action / Action Input), not just the terminate tool's
    ``output`` value. Relaying that envelope leaks internal reasoning into the
    lead agent context and produces an unreadable wall of protocol text in the
    UI. Keep ordinary Markdown untouched, but unwrap a valid terminal step.

    Args:
        text: Candidate sub-agent result text.

    Returns:
        The terminate ``result``/``output`` when present, otherwise ``text``.
    """
    if not text:
        return text
    try:
        parser = ReActOutputParser()
        final_answer = parser.get_final_output(parser.parse(text))
    except Exception:
        # Result extraction is a presentation/safety improvement and must not
        # turn an otherwise successful sub-task into a failed dispatch.
        final_answer = None
    return str(final_answer) if final_answer is not None else text


def extract_subagent_result(
    reply: Any,
    sub_state: dict,
    title: str,
    status: str,
) -> Dict[str, Any]:
    """Extract the relay structure from a sub-agent reply + its react_state.

    Args:
        reply: The ``AgentMessage`` returned by ``generate_reply`` (or None).
        sub_state: The sub-agent's react_state (source of artifact refs).
        title: Sub-task title for display / aggregation.
        status: One of ``done`` / ``timeout`` / ``failed``.

    Returns:
        A dict ``{title, status, result, artifacts}`` where:
        - ``result`` is the compressed text conclusion (goes to lead context),
        - ``artifacts`` is a list of path references (goes to the frontend),
          never bytes/base64.
    """
    # Prefer the terminate/action conclusion (action_report.content), exactly
    # as the main link extracts its final answer (agentic_data_api.py).
    text_result = ""
    if reply is not None:
        action_report = getattr(reply, "action_report", None)
        if action_report is not None and getattr(action_report, "content", None):
            text_result = _extract_final_answer(action_report.content)
        else:
            text_result = _extract_final_answer(getattr(reply, "content", None) or "")

    # Artifacts are path references collected in the sub-agent's own state —
    # never the image bytes. The frontend resolves /images/... URLs itself.
    artifacts: List[Dict[str, str]] = [
        {"type": "image", "url": url}
        for url in (sub_state.get("generated_images") or [])
    ]

    return {
        "title": title,
        "status": status,
        "result": text_result,
        "artifacts": artifacts,
    }


def attach_agent_attribution(
    artifacts: List[Dict[str, Any]],
    agent_id: str,
    agent_name: str,
) -> List[Dict[str, Any]]:
    """Tag each artifact item with its source sub-agent.

    The ``subagent.artifacts`` SSE event carries a flat list; without
    per-agent attribution the frontend cannot tell which sub-agent produced
    which artifact (needed for the per-row artifact count and the
    "by <agent>" label in the files tab). This mutates each item in place
    (``setdefault`` so a caller-provided value wins) and returns the same
    list for convenience.
    """
    for a in artifacts or []:
        if isinstance(a, dict):
            a.setdefault("agent_id", agent_id)
            a.setdefault("agent_name", agent_name)
    return artifacts
