"""Tests for the Gemini proxy default model."""

import pytest

from dbgpt.model.proxy.llms.gemini import GEMINI_DEFAULT_MODEL
from dbgpt.model.utils.models_dev import get_models_dev_models

# Shut down on the Gemini API (https://ai.google.dev/gemini-api/docs/deprecations
# and /changelog): the 1.5 models on 2025-09-29, the 2.0 models on 2026-06-01.
SHUT_DOWN = {
    "gemini-1.5-pro",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
    "gemini-2.0-flash",
    "gemini-2.0-flash-001",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash-lite-001",
}


def test_default_model_is_still_served():
    assert GEMINI_DEFAULT_MODEL not in SHUT_DOWN


def test_default_model_is_in_the_gemini_catalog():
    models = {m["model"] for m in get_models_dev_models("proxy/gemini") or []}
    assert GEMINI_DEFAULT_MODEL in models


def test_client_built_without_a_model_names_no_shut_down_model():
    pytest.importorskip("google.generativeai")
    from dbgpt.model.proxy.llms.gemini import GeminiLLMClient

    client = GeminiLLMClient(api_key="test-key")
    assert not SHUT_DOWN.intersection(client.model_names)
    assert client.model_names == [GEMINI_DEFAULT_MODEL]
