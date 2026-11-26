import pytest

from dbgpt_app.openapi.api_v1.public_progress import (
    PublicProgressStream,
    public_assistant_text,
    react_public_intention,
)


def test_partial_react_intention_never_includes_private_fields():
    text = "Thought: private reasoning\nAction Inten"
    assert react_public_intention(text) == ""
    text += "tion: 制定分析计划"
    assert react_public_intention(text) == "制定分析计划"
    assert react_public_intention(text + "\nAction Re") == "制定分析计划"
    assert react_public_intention(text + "\nAction Reason: why") == "制定分析计划"
    assert (
        react_public_intention("Thought: private\nAction Intention:\nAction: bash")
        == ""
    )


def test_progress_snapshot_updates_keep_order_and_close_on_interrupt():
    history = []
    stream = PublicProgressStream(history)
    first = stream.update(1, "先分析", streaming=True)
    history.append({"id": "tool-1"})
    last = stream.update(1, "先分析数据，再比较趋势。", streaming=False)
    assert first["id"] == last["id"]
    assert [item["id"] for item in history] == ["progress-1", "tool-1"]
    stream.update(2, "继续", streaming=True)
    assert stream.finish_all()[0]["streaming"] is False
    assert history[-1]["status"] == "done"


@pytest.mark.parametrize("chunk_size", [1, 2, 5, 17])
@pytest.mark.parametrize("bold", [False, True])
def test_native_protocol_fields_never_leak_at_any_chunk_boundary(chunk_size, bold):
    def label(name):
        return f"**{name}:**" if bold else f"{name}:"

    raw = (
        f"{label('Thought')} private reasoning\ncontinued reasoning\n"
        f"{label('Action Intention')} 核对日期格式，再统计门店销售。\n"
        f"{label('Action Reason')} private explanation\n"
        f"{label('Action')} sql_query\n"
        f'{label("Action Input")} {{"sql": "SELECT 1"}}'
    )
    history = []
    progress = PublicProgressStream(history)
    for offset in range(chunk_size, len(raw) + chunk_size, chunk_size):
        event = progress.update(1, raw[:offset], streaming=True)
        if event:
            assert event["content"] in "核对日期格式，再统计门店销售。"
            assert event["streaming"] is True
    event = progress.update(1, raw, streaming=False)
    assert event["content"] == "核对日期格式，再统计门店销售。"
    assert history[0]["progress_content"] == event["content"]
    assert history[0]["status"] == "done"


def test_protocol_only_message_is_not_public_narration():
    raw = "Thought: private reasoning\nAction: sql_query\nAction Input: {}"
    assert public_assistant_text(raw) == ""
    progress = PublicProgressStream([])
    assert progress.update(1, raw, streaming=True) is None
    assert progress.history_steps == []


def test_ordinary_multiline_narration_keeps_streaming_and_markdown():
    text = "先核对日期格式。\n\n**然后**比较各门店销售。"
    for offset in range(1, len(text) + 1):
        prefix = text[:offset]
        expected = prefix
        if prefix.rsplit("\n", 1)[-1] in ("*", "**"):
            expected = prefix.rsplit("\n", 1)[0] + "\n"
        assert public_assistant_text(prefix, streaming=True) == expected
    assert (
        public_assistant_text("先读取数据。\nThought: private\nAction: read")
        == "先读取数据。"
    )
