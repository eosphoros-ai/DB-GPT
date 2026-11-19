from dbgpt_app.config import AgentContextParameters


def test_agent_context_parameters_preserve_auto_detection():
    assert AgentContextParameters().max_context_tokens == 0
    cfg = AgentContextParameters(max_context_tokens=0)
    assert cfg.max_context_tokens == 0

    cfg = AgentContextParameters(max_context_tokens=-1)
    assert cfg.max_context_tokens == 0
    assert AgentContextParameters(max_context_tokens=32768).max_context_tokens == 32768
