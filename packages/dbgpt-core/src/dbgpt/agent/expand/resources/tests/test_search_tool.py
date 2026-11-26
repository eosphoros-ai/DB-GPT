"""Tests for the search tools."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from dbgpt.agent.resource.tool.exceptions import ToolExecutionException
from dbgpt.agent.resource.tool.pack import ToolPack

from ..search_tool import serply_search, specstream_search


@pytest.fixture
def mock_requests_get():
    with patch("requests.get") as mock_get:
        yield mock_get


def _response(num_results: int) -> MagicMock:
    response = MagicMock()
    response.json.return_value = {
        "results": [
            {
                "title": f"Title {i}",
                "link": f"https://example.com/{i}",
                "description": f"Snippet {i}",
            }
            for i in range(num_results)
        ]
    }
    return response


def test_serply_search(monkeypatch, mock_requests_get):
    monkeypatch.setenv("SERPLY_API_KEY", "test_key")
    # The API can answer with a couple more results than asked for.
    mock_requests_get.return_value = _response(10)

    view = serply_search("what is dbgpt", num_results=8)

    _, kwargs = mock_requests_get.call_args
    assert kwargs["headers"]["X-Api-Key"] == "test_key"
    assert kwargs["params"] == {"q": "what is dbgpt", "num": 8}
    assert view.startswith("### [Title 0](https://example.com/0)\nSnippet 0")
    assert "Title 7" in view
    assert "Title 8" not in view


def test_serply_search_minimum_number_of_results(monkeypatch, mock_requests_get):
    monkeypatch.setenv("SERPLY_API_KEY", "test_key")
    mock_requests_get.return_value = _response(8)

    serply_search("what is dbgpt", num_results=3)

    _, kwargs = mock_requests_get.call_args
    assert kwargs["params"]["num"] == 8


def test_serply_search_without_api_key(monkeypatch, mock_requests_get):
    monkeypatch.delenv("SERPLY_API_KEY", raising=False)

    with pytest.raises(ValueError, match="SERPLY_API_KEY"):
        serply_search("what is dbgpt")

    mock_requests_get.assert_not_called()


def _specstream_response(num_results: int) -> MagicMock:
    response = MagicMock()
    response.ok = True
    response.status_code = 200
    response.json.return_value = {
        "data": {
            "query": "what is dbgpt",
            "sources": [
                {
                    "url": f"https://example.com/{i}",
                    "title": f"Title {i}",
                    "site": "example.com",
                    "snippet": f"Snippet {i}",
                    "read_at": "2026-11-26T06:00:00Z",
                }
                for i in range(num_results)
            ],
        }
    }
    return response


def _specstream_error(status_code: int, reason: str, message: str) -> MagicMock:
    response = MagicMock()
    response.ok = False
    response.status_code = status_code
    response.reason = reason
    response.json.return_value = {
        "error": {"code": "invalid_token", "message": message, "details": {}}
    }
    return response


def test_specstream_search(monkeypatch, mock_requests_get):
    monkeypatch.setenv("SPECSTREAM_API_KEY", "test_key")
    mock_requests_get.return_value = _specstream_response(10)

    view = specstream_search("what is dbgpt", num_results=8)

    args, kwargs = mock_requests_get.call_args
    assert args[0] == "https://api.specstream.ai/v1/web-search"
    assert kwargs["headers"]["Authorization"] == "Bearer test_key"
    assert kwargs["params"] == {"q": "what is dbgpt", "num": 8, "speed": "fast"}
    # The key travels in the header only, never in the query string.
    assert "test_key" not in str(kwargs["params"])
    assert view.startswith("### [Title 0](https://example.com/0)\nSnippet 0")
    assert view.count("### [") == 8


def test_specstream_search_number_of_results_bounds(monkeypatch, mock_requests_get):
    monkeypatch.setenv("SPECSTREAM_API_KEY", "test_key")
    mock_requests_get.return_value = _specstream_response(8)

    specstream_search("what is dbgpt", num_results=3)
    assert mock_requests_get.call_args[1]["params"]["num"] == 8

    specstream_search("what is dbgpt", num_results=500)
    assert mock_requests_get.call_args[1]["params"]["num"] == 100


def test_specstream_search_without_api_key(monkeypatch, mock_requests_get):
    monkeypatch.delenv("SPECSTREAM_API_KEY", raising=False)

    with pytest.raises(ValueError, match="SPECSTREAM_API_KEY"):
        specstream_search("what is dbgpt")

    mock_requests_get.assert_not_called()


def test_specstream_search_api_error(monkeypatch, mock_requests_get):
    monkeypatch.setenv("SPECSTREAM_API_KEY", "bad_key")
    mock_requests_get.return_value = _specstream_error(
        401, "Unauthorized", "SpecStream didn't accept this API key or token."
    )

    with pytest.raises(requests.HTTPError, match="HTTP 401.*didn't accept"):
        specstream_search("what is dbgpt")


def test_specstream_search_api_error_without_json_body(monkeypatch, mock_requests_get):
    monkeypatch.setenv("SPECSTREAM_API_KEY", "test_key")
    response = MagicMock()
    response.ok = False
    response.status_code = 502
    response.reason = "Bad Gateway"
    response.json.side_effect = ValueError("not json")
    mock_requests_get.return_value = response

    with pytest.raises(requests.HTTPError, match="HTTP 502.*Bad Gateway"):
        specstream_search("what is dbgpt")


def test_specstream_search_non_object_success_body(monkeypatch, mock_requests_get):
    monkeypatch.setenv("SPECSTREAM_API_KEY", "test_key")
    response = MagicMock()
    response.ok = True
    response.status_code = 200
    response.json.return_value = []
    mock_requests_get.return_value = response

    assert specstream_search("what is dbgpt") == ""


@pytest.mark.asyncio
async def test_specstream_search_through_tool_pack(monkeypatch, mock_requests_get):
    monkeypatch.setenv("SPECSTREAM_API_KEY", "test_key")
    mock_requests_get.return_value = _specstream_response(10)
    pack = ToolPack([specstream_search._tool])

    # Discovery by the registered name, then execution the way agents do it.
    assert "specstream_search" in pack._resources
    view = await pack.async_execute(
        resource_name="specstream_search", query="what is dbgpt", num_results=8
    )

    assert view.startswith("### [Title 0](https://example.com/0)\nSnippet 0")
    assert view.count("### [") == 8


@pytest.mark.asyncio
async def test_specstream_search_error_through_tool_pack(
    monkeypatch, mock_requests_get
):
    monkeypatch.setenv("SPECSTREAM_API_KEY", "bad_key")
    mock_requests_get.return_value = _specstream_error(
        401, "Unauthorized", "SpecStream didn't accept this API key or token."
    )
    pack = ToolPack([specstream_search._tool])

    # The agent sees the API message inside the ToolExecutionException.
    with pytest.raises(ToolExecutionException, match="didn't accept"):
        await pack.async_execute(
            resource_name="specstream_search", query="what is dbgpt"
        )
