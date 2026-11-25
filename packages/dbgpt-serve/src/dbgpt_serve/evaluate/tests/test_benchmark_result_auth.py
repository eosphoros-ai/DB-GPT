"""Regression tests: benchmark-result reads must require an API key.

Issue #3396: ``GET /benchmark/result/{evaluate_code}`` used the conditional
``check_api_key`` guard, which allows all callers through when the deployment
configures no API keys, and the read path never checked ownership. An
anonymous caller could read another user's evaluation record by code.

The route now uses the fail-closed ``check_api_key_strict`` guard: a valid
configured API key is required, even on deployments that configure no keys
at all. These tests drive the real router with a test client and assert
that anonymous callers (with or without a bogus key, keys configured or
not) never get the record, while a caller with a valid key still can.
"""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ..api import endpoints
from ..api.endpoints import get_benchmark_service, get_service

EVALUATE_CODE = "POC_EVAL_2026"
API_KEY = "test-api-key"


class _FakeSummary:
    """Minimal stand-in for BenchmarkSummaryEntity."""

    def __init__(self):
        self.round_id = 1
        self.output_path = "/tmp/out.xlsx"
        self.llm_code = "qwen-plus"
        self.right = 8
        self.wrong = 2
        self.failed = 0
        self.exception = 0


class _FakeBenchmarkResultDao:
    """BenchmarkResultDao stand-in returning one summary for the code."""

    def list_summaries_by_task(self, evaluate_code, limit=10000, offset=0):
        if evaluate_code == EVALUATE_CODE:
            return [_FakeSummary()]
        return []


class _FakeBenchmarkService:
    """BenchmarkService stand-in: the record belongs to alice."""

    def get_benchmark_by_evaluate_code(self, evaluate_code):
        if evaluate_code == EVALUATE_CODE:
            return SimpleNamespace(scene_value="simple", user_name="alice")
        return None


def _make_service(api_keys):
    """Fake evaluate Service carrying only the configured API keys."""
    return SimpleNamespace(config=SimpleNamespace(api_keys=api_keys))


@pytest.fixture
def make_client(monkeypatch):
    monkeypatch.setattr(endpoints, "BenchmarkResultDao", _FakeBenchmarkResultDao)

    def _make_client(api_keys):
        app = FastAPI()
        app.include_router(endpoints.router)
        app.dependency_overrides[get_service] = lambda: _make_service(api_keys)
        app.dependency_overrides[get_benchmark_service] = _FakeBenchmarkService
        return TestClient(app)

    return _make_client


def test_anonymous_cannot_read_other_users_record(make_client):
    client = make_client(API_KEY)
    res = client.get(f"/benchmark/result/{EVALUATE_CODE}")
    assert res.status_code == 401


def test_wrong_api_key_cannot_read_record(make_client):
    client = make_client(API_KEY)
    res = client.get(
        f"/benchmark/result/{EVALUATE_CODE}",
        headers={"Authorization": "Bearer wrong-key"},
    )
    assert res.status_code == 401


def test_valid_api_key_can_read_record(make_client):
    client = make_client(API_KEY)
    res = client.get(
        f"/benchmark/result/{EVALUATE_CODE}",
        headers={"Authorization": f"Bearer {API_KEY}"},
    )
    assert res.status_code == 200
    assert res.json()["data"]["evaluate_code"] == EVALUATE_CODE
    assert res.json()["data"]["summaries"]


def test_anonymous_cannot_read_when_no_keys_configured(make_client):
    # Regression for #3396: the default deployment configures no API keys,
    # and the old conditional guard allowed all callers through (200).
    client = make_client(None)
    res = client.get(f"/benchmark/result/{EVALUATE_CODE}")
    assert res.status_code == 401


def test_any_bearer_token_rejected_when_no_keys_configured(make_client):
    client = make_client(None)
    res = client.get(
        f"/benchmark/result/{EVALUATE_CODE}",
        headers={"Authorization": "Bearer anything"},
    )
    assert res.status_code == 401


def test_conditional_guard_still_allows_all_on_other_routes(make_client):
    # The shared check_api_key guard is unchanged: routes that keep it
    # still allow all callers through when no keys are configured.
    client = make_client(None)
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
