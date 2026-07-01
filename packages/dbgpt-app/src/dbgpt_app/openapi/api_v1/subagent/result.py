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
            text_result = action_report.content
        else:
            text_result = getattr(reply, "content", None) or ""

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
