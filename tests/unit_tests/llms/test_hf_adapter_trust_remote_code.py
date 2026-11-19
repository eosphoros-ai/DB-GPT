import logging
import sys
import types

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


@pytest.fixture
def fake_transformers(monkeypatch):
    """Stub enough of transformers to run ``NewHFChatModelAdapter.load``."""
    captured = {}

    class _AutoModel:
        @staticmethod
        def from_pretrained(model_path, **kwargs):
            captured.update(kwargs)
            return object()

    class _AutoTokenizer:
        @staticmethod
        def from_pretrained(model_path, **kwargs):
            return object()

    fake = types.ModuleType("transformers")
    fake.__version__ = "4.99.0"
    fake.AutoModel = _AutoModel
    fake.AutoModelForCausalLM = _AutoModel
    fake.AutoProcessor = _AutoTokenizer
    fake.AutoTokenizer = _AutoTokenizer
    monkeypatch.setitem(sys.modules, "transformers", fake)
    return captured


def _warned(caplog) -> bool:
    return any(
        "trust_remote_code=True" in record.getMessage() for record in caplog.records
    )


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


def test_load_from_params_warns_when_remote_code_is_trusted(monkeypatch, caplog):
    monkeypatch.setattr(
        "dbgpt.model.adapter.loader.huggingface_loader",
        lambda adapter, params: ("model", "tokenizer"),
    )
    adapter = _DummyAdapter()

    with caplog.at_level(logging.WARNING, logger="dbgpt.model.adapter.hf_adapter"):
        result = adapter.load_from_params(HFLLMDeployModelParameters(name="dummy"))

    assert result == ("model", "tokenizer")
    assert _warned(caplog), "loading with trust_remote_code=True must log a warning"


def test_load_from_params_does_not_warn_when_remote_code_is_disabled(
    monkeypatch, caplog
):
    monkeypatch.setattr(
        "dbgpt.model.adapter.loader.huggingface_loader",
        lambda adapter, params: ("model", "tokenizer"),
    )
    adapter = _DummyAdapter()

    with caplog.at_level(logging.WARNING, logger="dbgpt.model.adapter.hf_adapter"):
        adapter.load_from_params(
            HFLLMDeployModelParameters(name="dummy", trust_remote_code=False)
        )

    assert not _warned(caplog)


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


def test_load_warns_and_forwards_trusted_remote_code(fake_transformers, caplog):
    adapter = _DummyAdapter()

    with caplog.at_level(logging.WARNING, logger="dbgpt.model.adapter.hf_adapter"):
        adapter.load("dummy", {})

    assert fake_transformers["trust_remote_code"] is True
    assert _warned(caplog)


def test_load_forwards_explicit_disable_without_warning(fake_transformers, caplog):
    adapter = _DummyAdapter()

    with caplog.at_level(logging.WARNING, logger="dbgpt.model.adapter.hf_adapter"):
        adapter.load("dummy", {"trust_remote_code": False})

    assert fake_transformers["trust_remote_code"] is False
    assert not _warned(caplog)


def test_huggingface_loader_forwards_params_trust_remote_code(monkeypatch):
    import dbgpt.core.interface.parameter as parameter_mod
    import dbgpt.model.adapter.loader as loader_mod

    captured = {}

    class _CaptureAdapter(_DummyAdapter):
        def load(self, model_path, from_pretrained_kwargs):
            captured.update(from_pretrained_kwargs)
            return object(), object()

    fake_torch = types.ModuleType("torch")
    fake_torch.float32 = "float32"
    fake_torch.float16 = "float16"
    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    fake_compression = types.ModuleType("dbgpt.model.llm.compression")
    fake_compression.compress_module = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "dbgpt.model.llm.compression", fake_compression)
    monkeypatch.setattr(parameter_mod, "get_device", lambda: "cpu")

    params = HFLLMDeployModelParameters(
        name="dummy", path="dummy-model", trust_remote_code=False
    )
    loader_mod.huggingface_loader(_CaptureAdapter(), params)

    assert captured["trust_remote_code"] is False
