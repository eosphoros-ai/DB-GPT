import pytest

from dbgpt.agent.core.base_agent import _raise_for_terminal_llm_error
from dbgpt.util.error_types import LLMChatError


@pytest.mark.parametrize(
    "reply",
    [
        "LLMServer Generate Error, Please CheckErrorInfo.: Connection error.",
        "**LLMServer Generate Error, Please CheckErrorInfo.**: Connection error.",
    ],
)
def test_model_gateway_error_text_stops_agent_retry_loop(reply: str) -> None:
    with pytest.raises(LLMChatError, match="模型服务连接失败"):
        _raise_for_terminal_llm_error(reply)


@pytest.mark.parametrize(
    "reply",
    [
        None,
        "",
        "The report contains a section named Connection Error.",
        "The LLM server generated the requested dashboard successfully.",
    ],
)
def test_normal_model_text_is_not_rejected(reply: str | None) -> None:
    _raise_for_terminal_llm_error(reply)
