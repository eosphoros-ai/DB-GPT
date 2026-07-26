"""Unit tests for result relay (plan stage 3, Task 3.3)."""

from dbgpt_app.openapi.api_v1.subagent.result import extract_subagent_result


class _Report:
    def __init__(self, content):
        self.content = content


class _Reply:
    def __init__(self, content=None, action_report=None):
        self.content = content
        self.action_report = action_report


def test_extract_prefers_action_report_content():
    reply = _Reply(content="raw", action_report=_Report("final conclusion"))
    out = extract_subagent_result(reply, {}, "T", "done")
    assert out["result"] == "final conclusion"
    assert out["status"] == "done"
    assert out["title"] == "T"


def test_extract_falls_back_to_content():
    reply = _Reply(content="just content", action_report=None)
    out = extract_subagent_result(reply, {}, "T", "done")
    assert out["result"] == "just content"


def test_extract_unwraps_terminate_output_without_react_protocol():
    raw = r"""``````vis-thinking
I should summarize the work before returning it.
``````
Thought: The analysis is complete.
Action: terminate
Action Input: {"output": "## Final result\n\nUSA and UK both have 5 users."}"""
    reply = _Reply(content="fallback", action_report=_Report(raw))

    out = extract_subagent_result(reply, {}, "T", "done")

    assert out["result"] == "## Final result\n\nUSA and UK both have 5 users."
    assert "Thought:" not in out["result"]
    assert "Action Input:" not in out["result"]
    assert "vis-thinking" not in out["result"]


def test_extract_handles_none_reply():
    out = extract_subagent_result(None, {}, "T", "timeout")
    assert out["result"] == ""
    assert out["status"] == "timeout"


def test_extract_collects_artifacts_as_path_refs_not_bytes():
    sub_state = {"generated_images": ["/images/a.png", "/images/b.png"]}
    out = extract_subagent_result(_Reply(content="x"), sub_state, "T", "done")
    assert out["artifacts"] == [
        {"type": "image", "url": "/images/a.png"},
        {"type": "image", "url": "/images/b.png"},
    ]
    # Purity: result text never contains image bytes/base64.
    assert "base64" not in out["result"]


def test_extract_no_artifacts_when_state_empty():
    out = extract_subagent_result(_Reply(content="x"), {}, "T", "done")
    assert out["artifacts"] == []
