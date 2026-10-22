"""Harness engine default: fresh deployments start on the pi harness.

The default is availability-gated — without the pi CLI a bare deployment
falls back to the built-in dbgpt engine instead of a dead preference.
"""

from types import SimpleNamespace

import pytest

from dbgpt_app.openapi.api_v1 import harness_pi_stream as hps
from dbgpt_app.openapi.api_view_model import ConversationVo


@pytest.fixture
def pref_env(tmp_path, monkeypatch):
    monkeypatch.setattr(hps.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path)))
    return tmp_path


def test_fresh_deployment_defaults_to_pi_when_cli_present(pref_env, monkeypatch):
    monkeypatch.setattr(hps, "_probe_pi_cli", lambda: (True, "/usr/bin/pi"))
    assert hps.get_harness_engine_pref() == "pi"


def test_fresh_deployment_falls_back_to_dbgpt_without_cli(pref_env, monkeypatch):
    monkeypatch.setattr(hps, "_probe_pi_cli", lambda: (False, "pi CLI not found"))
    assert hps.get_harness_engine_pref() == "dbgpt"


def test_persisted_preference_wins_over_default(pref_env, monkeypatch):
    monkeypatch.setattr(hps, "_probe_pi_cli", lambda: (True, "/usr/bin/pi"))
    (pref_env / "harness_engine.json").write_text('{"engine": "dbgpt"}')
    assert hps.get_harness_engine_pref() == "dbgpt"


def test_invalid_engine_normalizes_to_project_default(pref_env, monkeypatch):
    monkeypatch.setattr(hps, "_probe_pi_cli", lambda: (True, "/usr/bin/pi"))
    assert hps.set_harness_engine_pref("bogus") == "pi"


def test_request_override_beats_preference(pref_env, monkeypatch):
    monkeypatch.setattr(hps, "_probe_pi_cli", lambda: (True, "/usr/bin/pi"))
    dialogue = ConversationVo(conv_uid="c1", ext_info={"harness_engine": "dbgpt"})
    assert hps.resolve_harness_engine(dialogue) == "dbgpt"
