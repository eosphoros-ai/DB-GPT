from types import SimpleNamespace

import pytest

from dbgpt_app.openapi.api_v1 import agentic_data_api


class _FakeLlmClient:
    def __init__(self, context_length: int):
        self.context_length = context_length
        self.requested_models = []

    async def get_model_metadata(self, model_name: str):
        self.requested_models.append(model_name)
        return SimpleNamespace(context_length=self.context_length)


def _patch_agent_context(monkeypatch, agent_context):
    system_app = SimpleNamespace(
        config=SimpleNamespace(
            configs={
                "app_config": SimpleNamespace(
                    service=SimpleNamespace(
                        web=SimpleNamespace(agent_context=agent_context)
                    )
                )
            }
        )
    )
    monkeypatch.setattr(agentic_data_api.CFG, "SYSTEM_APP", system_app)


@pytest.mark.asyncio
async def test_context_budget_uses_model_metadata_when_config_is_auto(monkeypatch):
    agent_context = SimpleNamespace(max_context_tokens=0, reserved_tokens=2048)
    _patch_agent_context(monkeypatch, agent_context)
    llm_client = _FakeLlmClient(context_length=32768)

    config = await agentic_data_api._load_context_budget_config(
        llm_client=llm_client,
        model_name="qwen",
    )

    assert config.max_context_tokens == 32768
    assert config.effective_budget == 30720
    assert llm_client.requested_models == ["qwen"]


@pytest.mark.asyncio
async def test_context_budget_keeps_explicit_config_over_model_metadata(monkeypatch):
    agent_context = SimpleNamespace(max_context_tokens=64000, reserved_tokens=4096)
    _patch_agent_context(monkeypatch, agent_context)
    llm_client = _FakeLlmClient(context_length=32768)

    config = await agentic_data_api._load_context_budget_config(
        llm_client=llm_client,
        model_name="qwen",
    )

    assert config.max_context_tokens == 64000
    assert config.effective_budget == 59904
    assert llm_client.requested_models == []
