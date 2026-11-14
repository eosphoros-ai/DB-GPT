from dbgpt.agent.core.context.budget import DEFAULT_MAX_CONTEXT_TOKENS
from dbgpt_app.config import AgentContextParameters


def test_agent_context_parameters_non_positive_max_context_tokens_fall_back_to_default(  # noqa: E501
):
    cfg = AgentContextParameters(max_context_tokens=0)
    assert cfg.max_context_tokens == DEFAULT_MAX_CONTEXT_TOKENS

    cfg = AgentContextParameters(max_context_tokens=-1)
    assert cfg.max_context_tokens == DEFAULT_MAX_CONTEXT_TOKENS
