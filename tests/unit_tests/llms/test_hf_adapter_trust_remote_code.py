import logging

import pytest

from dbgpt.model.adapter import hf_adapter
from dbgpt.model.adapter.hf_adapter import (
    HFLLMDeployModelParameters,
    NewHFChatModelAdapter,
)


class _DummyAdapter(NewHFChatModelAdapter):
    def do_match(self, lower_model_name_or_path=None):
        return True


@pytest.fixture(autouse=True)
def reset_warning_flag():
    hf_adapter._TRUST_REMOTE_CODE_WARNING_EMITTED = False
    yield
    hf_adapter._TRUST_REMOTE_CODE_WARNING_EMITTED = False


def test_trust_remote_code_default_is_still_true():
    # Non-breaking hardening: the default is intentionally kept as-is here so that
    # maintainers can decide whether to flip it to False. This test documents the
    # current behaviour and must be updated if that decision is made.
    assert HFLLMDeployModelParameters(name="dummy").trust_remote_code is True
    assert (
        HFLLMDeployModelParameters(
            name="dummy", trust_remote_code=False
        ).trust_remote_code
        is False
    )


def test_load_warns_when_remote_code_is_trusted(monkeypatch, caplog):
    monkeypatch.setattr(
        "dbgpt.model.adapter.loader.huggingface_loader",
        lambda adapter, params: ("model", "tokenizer"),
    )
    adapter = _DummyAdapter()

    with caplog.at_level(logging.WARNING, logger="dbgpt.model.adapter.hf_adapter"):
        result = adapter.load_from_params(HFLLMDeployModelParameters(name="dummy"))

    assert result == ("model", "tokenizer")
    assert any(
        "trust_remote_code=True" in record.getMessage() for record in caplog.records
    ), "loading a model with trust_remote_code=True must log a warning"


def test_load_does_not_warn_when_remote_code_is_disabled(monkeypatch, caplog):
    monkeypatch.setattr(
        "dbgpt.model.adapter.loader.huggingface_loader",
        lambda adapter, params: ("model", "tokenizer"),
    )
    adapter = _DummyAdapter()

    with caplog.at_level(logging.WARNING, logger="dbgpt.model.adapter.hf_adapter"):
        adapter.load_from_params(
            HFLLMDeployModelParameters(name="dummy", trust_remote_code=False)
        )

    assert not any(
        "trust_remote_code=True" in record.getMessage() for record in caplog.records
    )


def test_warning_is_emitted_only_once(monkeypatch, caplog):
    monkeypatch.setattr(
        "dbgpt.model.adapter.loader.huggingface_loader",
        lambda adapter, params: ("model", "tokenizer"),
    )
    adapter = _DummyAdapter()
    params = HFLLMDeployModelParameters(name="dummy")

    with caplog.at_level(logging.WARNING, logger="dbgpt.model.adapter.hf_adapter"):
        adapter.load_from_params(params)
        adapter.load_from_params(params)

    warnings = [
        record
        for record in caplog.records
        if "trust_remote_code=True" in record.getMessage()
    ]
    assert len(warnings) == 1
