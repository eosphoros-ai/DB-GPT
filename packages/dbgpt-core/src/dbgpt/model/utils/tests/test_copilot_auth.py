"""Protocol regressions for the previously missing OAuth device-flow helper."""

from urllib.parse import parse_qs

import httpx
import pytest

from dbgpt.model.utils import copilot_auth

VALID_START = {
    "device_code": "test-device-code",
    "user_code": "TEST-CODE",
    "verification_uri": "https://github.com/login/device",
    "interval": 5,
    "expires_in": 900,
}


def mock_github(monkeypatch, payload, status=200):
    requests = []
    original = httpx.AsyncClient

    def handle(request):
        requests.append(request)
        if isinstance(payload, Exception):
            raise payload
        return httpx.Response(status, json=payload)

    monkeypatch.setenv("GITHUB_COPILOT_OAUTH_CLIENT_ID", "test-client")
    monkeypatch.setattr(
        copilot_auth.httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs),
    )
    return requests


@pytest.mark.asyncio
async def test_start_uses_configured_app_without_requesting_extra_scopes(monkeypatch):
    requests = mock_github(monkeypatch, {**VALID_START, "unknown": "not-forwarded"})
    ok, message, result = await copilot_auth.start_device_flow()
    assert ok and message == "" and result == VALID_START
    assert str(requests[0].url) == "https://github.com/login/device/code"
    assert parse_qs(requests[0].content.decode()) == {"client_id": ["test-client"]}


@pytest.mark.asyncio
async def test_missing_client_id_fails_without_network(monkeypatch):
    monkeypatch.delenv("GITHUB_COPILOT_OAUTH_CLIENT_ID", raising=False)
    ok, message, data = await copilot_auth.start_device_flow()
    assert not ok and "GITHUB_COPILOT_OAUTH_CLIENT_ID" in message and data == {}
    assert await copilot_auth.poll_device_flow("code") == ("error", None)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"error": "incorrect_client_credentials"},
        {**VALID_START, "device_code": ""},
        {**VALID_START, "user_code": None},
        {**VALID_START, "verification_uri": "https://example.invalid/device"},
        {**VALID_START, "interval": 0},
        {**VALID_START, "interval": True},
        {**VALID_START, "expires_in": -1},
    ],
)
async def test_invalid_start_response_is_not_forwarded(monkeypatch, payload):
    mock_github(monkeypatch, payload)
    ok, _, data = await copilot_auth.start_device_flow()
    assert not ok and data == {}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload,expected",
    [
        ({"error": "authorization_pending"}, ("pending", None)),
        ({"error": "slow_down"}, ("slow_down", None)),
        ({"error": "expired_token"}, ("error", None)),
        ({"error": "access_denied"}, ("error", None)),
        ({"error": "incorrect_device_code"}, ("error", None)),
        (
            {"access_token": "private-test-token", "token_type": "bearer"},
            ("success", "private-test-token"),
        ),
        ({"access_token": "", "token_type": "bearer"}, ("error", None)),
        ({"access_token": "untyped"}, ("error", None)),
        ({"error": "access_denied", "access_token": "untrusted"}, ("error", None)),
        ([], ("error", None)),
    ],
)
async def test_poll_protocol_states(monkeypatch, payload, expected):
    requests = mock_github(monkeypatch, payload)
    assert await copilot_auth.poll_device_flow("test-device-code") == expected
    assert str(requests[0].url) == "https://github.com/login/oauth/access_token"
    assert parse_qs(requests[0].content.decode()) == {
        "client_id": ["test-client"],
        "device_code": ["test-device-code"],
        "grant_type": ["urn:ietf:params:oauth:grant-type:device_code"],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure", [httpx.ConnectError("offline"), httpx.ReadTimeout("timeout")]
)
async def test_network_failures_do_not_leak_sensitive_response_details(
    monkeypatch, failure
):
    mock_github(monkeypatch, failure)
    assert not (await copilot_auth.start_device_flow())[0]
    assert await copilot_auth.poll_device_flow("code") == ("error", None)


@pytest.mark.asyncio
async def test_http_error_is_not_accepted_as_authorization(monkeypatch):
    mock_github(monkeypatch, {"access_token": "not-valid", "token_type": "bearer"}, 403)
    assert not (await copilot_auth.start_device_flow())[0]
    assert await copilot_auth.poll_device_flow("code") == ("error", None)
