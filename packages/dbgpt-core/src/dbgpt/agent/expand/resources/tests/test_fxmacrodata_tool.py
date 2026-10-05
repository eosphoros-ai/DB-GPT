"""Tests for the FXMacroData tools."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from ..fxmacrodata_tool import (
    FXMACRODATA_BASE_URL,
    FXMacroDataError,
    fxmacrodata_data_catalogue,
    fxmacrodata_indicator_history,
    fxmacrodata_latest_releases,
    fxmacrodata_release_calendar,
)

TEST_KEY = "test-key-123"


@pytest.fixture
def mock_requests_get():
    with patch("requests.get") as mock_get:
        yield mock_get


@pytest.fixture
def keyless(monkeypatch):
    monkeypatch.delenv("FXMACRODATA_API_KEY", raising=False)


@pytest.fixture
def with_key(monkeypatch):
    monkeypatch.setenv("FXMACRODATA_API_KEY", f"  {TEST_KEY}  ")


def _response(body=None, status_code=200, json_error=False) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    if json_error:
        response.json.side_effect = ValueError("not json")
    else:
        response.json.return_value = body
    return response


def _history_row(period: str, value: float) -> dict:
    return {
        "date": period,
        "val": value,
        "previous_value": value - 1,
        "announcement_datetime": 1789129800,
    }


def _data_row_count(view: str) -> int:
    return sum(1 for line in view.splitlines() if line.startswith("| 2026-"))


LATEST_BODY = {
    "currency": "USD",
    "data": [
        {
            "indicator": "inflation",
            "name": "Inflation (CPI)",
            "unit": "%YoY",
            "latest": {
                "date": "2026-08-31",
                "val": 3.4,
                "announcement_datetime": 1789129800,
            },
        }
    ],
    "freemium_delay": {
        "applied": True,
        "withheld_count": 1,
        "message": "Free access is delayed by 15 minutes.",
    },
}


def test_latest_releases_keyless(keyless, mock_requests_get):
    mock_requests_get.return_value = _response(LATEST_BODY)

    view = fxmacrodata_latest_releases("usd")

    args, kwargs = mock_requests_get.call_args
    assert args[0] == f"{FXMACRODATA_BASE_URL}/announcements/usd/latest"
    assert "X-API-Key" not in kwargs["headers"]
    assert kwargs["allow_redirects"] is False
    assert kwargs["timeout"] == 10
    assert view.startswith("### USD latest releases")
    assert "| inflation | Inflation (CPI) | 2026-08-31 | 3.4 | %YoY |" in view
    assert "2026-09-11 12:30 UTC" in view
    assert "> Note: Free access is delayed by 15 minutes." in view
    assert "1 release(s) published in the last 15 minutes" in view


def test_key_is_stripped_and_sent_as_header(with_key, mock_requests_get):
    mock_requests_get.return_value = _response({"data": []})

    fxmacrodata_latest_releases("EUR")

    _, kwargs = mock_requests_get.call_args
    assert kwargs["headers"]["X-API-Key"] == TEST_KEY


def test_invalid_key_is_rejected_without_echo(monkeypatch, mock_requests_get):
    monkeypatch.setenv("FXMACRODATA_API_KEY", "abc\ndef")

    with pytest.raises(FXMacroDataError) as error:
        fxmacrodata_latest_releases("USD")

    assert "abc" not in str(error.value)
    mock_requests_get.assert_not_called()


def test_indicator_history_follows_pagination(keyless, mock_requests_get):
    first = {
        "name": "Inflation (CPI)",
        "data": [_history_row("2026-08-31", 3.4), _history_row("2026-07-31", 3.3)],
        "pagination": {"has_more": True, "next_offset": 2},
        "freemium_window": {
            "applied": True,
            "message": "Anonymous access returns the most recent 90 days.",
        },
    }
    second = {
        "data": [_history_row("2026-06-30", 3.2)],
        "pagination": {"has_more": False},
    }
    mock_requests_get.side_effect = [_response(first), _response(second)]

    view = fxmacrodata_indicator_history(
        " usd ", " Inflation ", "2026-01-01", "2026-09-30", limit=3
    )

    first_call, second_call = mock_requests_get.call_args_list
    assert first_call.args[0] == f"{FXMACRODATA_BASE_URL}/announcements/usd/inflation"
    assert first_call.kwargs["params"] == {
        "start_date": "2026-01-01",
        "end_date": "2026-09-30",
        "limit": 3,
        "offset": 0,
    }
    assert second_call.kwargs["params"]["offset"] == 2
    assert second_call.kwargs["params"]["limit"] == 1
    assert view.startswith("### USD Inflation (CPI) (inflation)")
    assert _data_row_count(view) == 3
    assert "most recent 90 days" in view


def test_indicator_history_stops_at_limit(keyless, mock_requests_get):
    body = {
        "data": [_history_row("2026-08-31", 3.4), _history_row("2026-07-31", 3.3)],
        "pagination": {"has_more": True, "next_offset": 2},
    }
    mock_requests_get.return_value = _response(body)

    view = fxmacrodata_indicator_history("USD", "inflation", limit=2)

    assert mock_requests_get.call_count == 1
    assert _data_row_count(view) == 2


@pytest.mark.parametrize(
    "pagination",
    [
        "yes",
        {"has_more": "true", "next_offset": 2},
        {"has_more": True},
        {"has_more": True, "next_offset": "2"},
        {"has_more": True, "next_offset": True},
        {"has_more": True, "next_offset": 0},
    ],
)
def test_invalid_pagination_is_rejected(keyless, mock_requests_get, pagination):
    body = {"data": [_history_row("2026-08-31", 3.4)], "pagination": pagination}
    mock_requests_get.return_value = _response(body)

    with pytest.raises(FXMacroDataError, match="pagination|has_more|next_offset"):
        fxmacrodata_indicator_history("USD", "inflation", limit=5)


def test_null_pagination_means_single_page(keyless, mock_requests_get):
    body = {"data": [_history_row("2026-08-31", 3.4)], "pagination": None}
    mock_requests_get.return_value = _response(body)

    view = fxmacrodata_indicator_history("USD", "inflation", limit=5)

    assert mock_requests_get.call_count == 1
    assert "3.4" in view


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"currency": "US"}, "currency"),
        ({"currency": "XYZ"}, "currency"),
        ({"indicator": "  "}, "indicator"),
        ({"indicator": "../latest"}, "indicator"),
        ({"start_date": "2026-02-30"}, "real calendar date"),
        ({"start_date": "20260101"}, "YYYY-MM-DD"),
        ({"start_date": "2026-09-01", "end_date": "2026-01-01"}, "after"),
        ({"limit": 0}, "between 1 and 100"),
        ({"limit": 101}, "between 1 and 100"),
        ({"limit": True}, "integer"),
    ],
)
def test_invalid_inputs_are_rejected(keyless, mock_requests_get, kwargs, message):
    arguments = {"currency": "USD", "indicator": "inflation", **kwargs}

    with pytest.raises(FXMacroDataError, match=message):
        fxmacrodata_indicator_history(**arguments)

    mock_requests_get.assert_not_called()


def test_release_calendar(keyless, mock_requests_get):
    body = {
        "currency": "USD",
        "data": [
            {
                "announcement_datetime": 1791289800,
                "release": "trade_balance",
                "name": "Trade Balance",
                "date": "2026-08-31",
                "event_importance": "medium",
            },
            {
                "announcement_datetime": 1791385200,
                "release": "consumer_confidence",
                "name": "Consumer Confidence",
                "event_importance": "high",
            },
        ],
    }
    mock_requests_get.return_value = _response(body)

    view = fxmacrodata_release_calendar("USD", limit=1)

    args, _ = mock_requests_get.call_args
    assert args[0] == f"{FXMACRODATA_BASE_URL}/calendar/usd"
    assert (
        "| 2026-10-06 12:30 UTC | trade_balance | Trade Balance | 2026-08-31 | "
        "medium |" in view
    )
    assert "consumer_confidence" not in view


def test_data_catalogue(keyless, mock_requests_get):
    body = {
        "inflation": {
            "name": "Inflation (CPI)",
            "unit": "%YoY",
            "frequency": "Monthly",
        },
        "policy_rate": {"name": "Policy Rate", "unit": "%", "frequency": "Irregular"},
        "freemium_delay": {"applied": True, "message": "Delayed."},
    }
    mock_requests_get.return_value = _response(body)

    view = fxmacrodata_data_catalogue("eur")

    args, _ = mock_requests_get.call_args
    assert args[0] == f"{FXMACRODATA_BASE_URL}/data_catalogue/eur"
    assert "| inflation | Inflation (CPI) | %YoY | Monthly |" in view
    assert "| policy_rate | Policy Rate | % | Irregular |" in view
    assert "| freemium_delay |" not in view


def test_redirect_is_not_followed(with_key, mock_requests_get):
    mock_requests_get.return_value = _response({}, status_code=302)

    with pytest.raises(FXMacroDataError, match="redirect"):
        fxmacrodata_latest_releases("USD")

    _, kwargs = mock_requests_get.call_args
    assert kwargs["allow_redirects"] is False


def test_api_key_required_error(keyless, mock_requests_get):
    body = {"error": "api_key_required", "detail": "This endpoint requires a key."}
    mock_requests_get.return_value = _response(body, status_code=401)

    with pytest.raises(FXMacroDataError) as error:
        fxmacrodata_latest_releases("EUR")

    message = str(error.value)
    assert "HTTP 401" in message
    assert "This endpoint requires a key." in message
    assert "FXMACRODATA_API_KEY" in message


def test_error_text_never_contains_the_key(with_key, mock_requests_get):
    body = {"detail": f"Key {TEST_KEY} is not valid."}
    mock_requests_get.return_value = _response(body, status_code=401)

    with pytest.raises(FXMacroDataError) as error:
        fxmacrodata_latest_releases("USD")

    assert TEST_KEY not in str(error.value)
    assert "***" in str(error.value)


def test_output_never_contains_the_key(with_key, mock_requests_get):
    body = {"data": [{"indicator": "inflation", "name": f"echo {TEST_KEY}"}]}
    mock_requests_get.return_value = _response(body)

    view = fxmacrodata_latest_releases("USD")

    assert TEST_KEY not in view


def test_network_error_is_clean(with_key, mock_requests_get):
    mock_requests_get.side_effect = requests.ConnectionError(f"boom {TEST_KEY}")

    with pytest.raises(FXMacroDataError, match="ConnectionError") as error:
        fxmacrodata_latest_releases("USD")

    assert TEST_KEY not in str(error.value)


@pytest.mark.parametrize(
    "response",
    [
        _response(json_error=True),
        _response(["not", "an", "object"]),
        _response({"error": "internal", "detail": "Something failed."}),
        _response({"data": "not a list"}),
        _response({"data": ["not an object"]}),
    ],
)
def test_bad_success_bodies_are_clean_errors(keyless, mock_requests_get, response):
    mock_requests_get.return_value = response

    with pytest.raises(FXMacroDataError):
        fxmacrodata_latest_releases("USD")


def test_empty_catalogue_is_an_error(keyless, mock_requests_get):
    mock_requests_get.return_value = _response({})

    with pytest.raises(FXMacroDataError, match="empty"):
        fxmacrodata_data_catalogue("USD")
