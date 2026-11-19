"""Tests for the trust_remote_code warning in the vLLM adapter."""

import dataclasses
import logging
import sys
import types

import pytest

from dbgpt.model.adapter import trust_remote_code as trc
from dbgpt.model.adapter.vllm_adapter import (
    VLLMDeployModelParameters,
    VLLMModelAdapterWrapper,
)


@pytest.fixture(autouse=True)
def reset_warning_state(monkeypatch):
    """Reset the warn-once flag and the global logging threshold for each test."""
    monkeypatch.setattr(trc, "_TRUST_REMOTE_CODE_WARNING_EMITTED", False)
    monkeypatch.setattr(logging.root.manager, "disable", logging.NOTSET)


@pytest.fixture
def fake_vllm(monkeypatch):
    """Stub vLLM so ``load_from_params`` runs without GPU, weights or network."""
    captured = {}

    @dataclasses.dataclass
    class AsyncEngineArgs:
        model: str
        trust_remote_code: bool = False

    class _Tokenizer:
        # ``vllm >= 0.2.7`` wraps the tokenizer in an object with ``.tokenizer``.
        tokenizer = "tokenizer"

    class _InnerEngine:
        tokenizer = _Tokenizer()

    class _Engine:
        engine = _InnerEngine()

    class AsyncLLMEngine:
        @staticmethod
        def from_engine_args(engine_args):
            """Capture the engine args and return a stub engine."""
            captured["engine_args"] = engine_args
            return _Engine()

    fake_vllm = types.ModuleType("vllm")
    fake_vllm.AsyncLLMEngine = AsyncLLMEngine
    fake_engine = types.ModuleType("vllm.engine")
    fake_arg_utils = types.ModuleType("vllm.engine.arg_utils")
    fake_arg_utils.AsyncEngineArgs = AsyncEngineArgs
    fake_engine.arg_utils = fake_arg_utils
    fake_vllm.engine = fake_engine
    monkeypatch.setitem(sys.modules, "vllm", fake_vllm)
    monkeypatch.setitem(sys.modules, "vllm.engine", fake_engine)
    monkeypatch.setitem(sys.modules, "vllm.engine.arg_utils", fake_arg_utils)
    return captured


def _warned(caplog) -> bool:
    """Whether the trust_remote_code warning was logged."""
    return any(
        "trust_remote_code=True" in record.getMessage() for record in caplog.records
    )


def _load(adapter, params, caplog):
    """Load ``params`` while capturing warnings from the shared helper."""
    with caplog.at_level(logging.WARNING, logger=trc.__name__):
        return adapter.load_from_params(params)


def test_trust_remote_code_default_is_still_true():
    """The vLLM default is intentionally unchanged by this hardening."""
    # Non-breaking hardening: the default is kept as-is so maintainers can decide
    # whether to flip it. This test documents the current behaviour and must be
    # updated if that decision is made.
    assert VLLMDeployModelParameters(name="dummy").trust_remote_code is True
    assert (
        VLLMDeployModelParameters(
            name="dummy", trust_remote_code=False
        ).trust_remote_code
        is False
    )


def test_load_from_params_warns_when_remote_code_is_trusted(fake_vllm, caplog):
    """Loading with trust_remote_code=True warns and forwards the value."""
    adapter = VLLMModelAdapterWrapper()

    _, tokenizer = _load(adapter, VLLMDeployModelParameters(name="dummy"), caplog)

    assert fake_vllm["engine_args"].trust_remote_code is True
    assert tokenizer == "tokenizer"
    assert _warned(caplog), "loading with trust_remote_code=True must log a warning"


def test_load_from_params_does_not_warn_when_remote_code_is_disabled(fake_vllm, caplog):
    """An explicit trust_remote_code=False does not warn and reaches vLLM."""
    adapter = VLLMModelAdapterWrapper()

    _load(
        adapter,
        VLLMDeployModelParameters(name="dummy", trust_remote_code=False),
        caplog,
    )

    assert fake_vllm["engine_args"].trust_remote_code is False
    assert not _warned(caplog)


def test_warning_is_emitted_only_once(fake_vllm, caplog):
    """Loading several models warns at most once per process."""
    adapter = VLLMModelAdapterWrapper()
    params = VLLMDeployModelParameters(name="dummy")

    _load(adapter, params, caplog)
    _load(adapter, params, caplog)

    warnings = [
        record
        for record in caplog.records
        if "trust_remote_code=True" in record.getMessage()
    ]
    assert len(warnings) == 1


def test_extras_override_does_not_warn_when_remote_code_is_disabled(fake_vllm, caplog):
    """``extras`` is merged into the vLLM kwargs last, so it decides the value."""
    adapter = VLLMModelAdapterWrapper()

    _load(
        adapter,
        VLLMDeployModelParameters(name="dummy", extras={"trust_remote_code": False}),
        caplog,
    )

    assert fake_vllm["engine_args"].trust_remote_code is False
    assert not _warned(caplog)


def test_extras_can_enable_remote_code_and_warns(fake_vllm, caplog):
    """A truthy ``extras`` override is warned about even if the parameter is False."""
    adapter = VLLMModelAdapterWrapper()

    _load(
        adapter,
        VLLMDeployModelParameters(
            name="dummy",
            trust_remote_code=False,
            extras={"trust_remote_code": True},
        ),
        caplog,
    )

    assert fake_vllm["engine_args"].trust_remote_code is True
    assert _warned(caplog)


def test_flag_is_not_consumed_while_warning_logging_is_disabled(fake_vllm, caplog):
    """The flag is left unset when WARNING logging is disabled."""
    adapter = VLLMModelAdapterWrapper()
    params = VLLMDeployModelParameters(name="dummy")

    caplog.set_level(logging.ERROR, logger=trc.__name__)
    adapter.load_from_params(params)
    assert trc._TRUST_REMOTE_CODE_WARNING_EMITTED is False

    caplog.set_level(logging.WARNING, logger=trc.__name__)
    adapter.load_from_params(params)

    assert _warned(caplog)


def test_flag_is_not_consumed_when_logging_raises(fake_vllm, monkeypatch, caplog):
    """A logging failure leaves the flag unset and warns on the next load."""

    class _RaisingFilter(logging.Filter):
        def filter(self, record):
            """Simulate a broken logging filter."""
            raise RuntimeError("logging is broken")

    adapter = VLLMModelAdapterWrapper()
    params = VLLMDeployModelParameters(name="dummy")
    logger = logging.getLogger(trc.__name__)
    raising_filter = _RaisingFilter()
    monkeypatch.setattr(logger, "filters", logger.filters + [raising_filter])

    with pytest.raises(RuntimeError):
        adapter.load_from_params(params)

    assert trc._TRUST_REMOTE_CODE_WARNING_EMITTED is False
    # The warning lock must be released even though logging raised.
    assert trc._TRUST_REMOTE_CODE_WARNING_LOCK.acquire(blocking=False)
    trc._TRUST_REMOTE_CODE_WARNING_LOCK.release()

    logger.removeFilter(raising_filter)
    caplog.set_level(logging.WARNING, logger=trc.__name__)
    caplog.clear()
    adapter.load_from_params(params)

    assert _warned(caplog)
