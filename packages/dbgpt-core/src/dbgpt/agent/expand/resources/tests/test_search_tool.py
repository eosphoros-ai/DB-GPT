"""Tests for the search tools."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from dbgpt.agent.resource.tool.exceptions import ToolExecutionException
from dbgpt.agent.resource.tool.pack import ToolPack

from ..search_tool import searchapi_search, serply_search


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


def _searchapi_response(num_results: int) -> MagicMock:
    response = MagicMock()
    response.ok = True
    response.status_code = 200
    response.json.return_value = {
        "organic_results": [
            {
                "position": i + 1,
                "title": f"Title {i}",
                "link": f"https://example.com/{i}",
                "snippet": f"Snippet {i}",
                "source": "Example",
            }
            for i in range(num_results)
        ]
    }
    return response


def test_searchapi_search(monkeypatch, mock_requests_get):
    monkeypatch.setenv("SEARCHAPI_API_KEY", "test_key")
    # Google ignores `num`, so a page carries about 10 results whatever was asked.
    mock_requests_get.return_value = _searchapi_response(10)

    view = searchapi_search("what is dbgpt", num_results=8)

    args, kwargs = mock_requests_get.call_args
    assert args[0] == "https://www.searchapi.io/api/v1/search"
    assert kwargs["headers"]["Authorization"] == "Bearer test_key"
    assert kwargs["params"] == {"engine": "google", "q": "what is dbgpt"}
    assert "num" not in kwargs["params"]
    # The key travels in the header only, never in the URL or the query string.
    assert "test_key" not in args[0]
    assert "test_key" not in str(kwargs["params"])
    assert view.startswith("### [Title 0](https://example.com/0)\nSnippet 0")
    assert "Title 7" in view
    assert "Title 8" not in view


def test_searchapi_search_minimum_number_of_results(monkeypatch, mock_requests_get):
    monkeypatch.setenv("SEARCHAPI_API_KEY", "test_key")
    mock_requests_get.return_value = _searchapi_response(10)

    view = searchapi_search("what is dbgpt", num_results=3)

    _, kwargs = mock_requests_get.call_args
    # The minimum is applied client-side, so nothing about the count is sent.
    assert "num" not in kwargs["params"]
    assert "Title 7" in view
    assert "Title 8" not in view


def test_searchapi_search_without_api_key(monkeypatch, mock_requests_get):
    monkeypatch.delenv("SEARCHAPI_API_KEY", raising=False)

    with pytest.raises(ValueError, match="SEARCHAPI_API_KEY"):
        searchapi_search("what is dbgpt")

    mock_requests_get.assert_not_called()


def test_searchapi_search_api_error(monkeypatch, mock_requests_get):
    monkeypatch.setenv("SEARCHAPI_API_KEY", "bad_key")
    response = MagicMock()
    response.ok = False
    response.status_code = 401
    response.reason = "Unauthorized"
    response.json.return_value = {"error": "Invalid API key."}
    mock_requests_get.return_value = response

    with pytest.raises(requests.HTTPError, match="HTTP 401.*Invalid API key"):
        searchapi_search("what is dbgpt")


def test_searchapi_search_api_error_without_json_body(monkeypatch, mock_requests_get):
    monkeypatch.setenv("SEARCHAPI_API_KEY", "test_key")
    response = MagicMock()
    response.ok = False
    response.status_code = 502
    response.reason = "Bad Gateway"
    response.json.side_effect = ValueError("not json")
    mock_requests_get.return_value = response

    with pytest.raises(requests.HTTPError, match="HTTP 502.*Bad Gateway"):
        searchapi_search("what is dbgpt")


def test_searchapi_search_api_error_with_non_object_json_body(
    monkeypatch, mock_requests_get
):
    monkeypatch.setenv("SEARCHAPI_API_KEY", "test_key")
    response = MagicMock()
    response.ok = False
    response.status_code = 502
    response.reason = "Bad Gateway"
    # Valid JSON that is not an object must still end up as an HTTPError.
    response.json.return_value = []
    mock_requests_get.return_value = response

    with pytest.raises(requests.HTTPError, match="HTTP 502 .* Bad Gateway"):
        searchapi_search("what is dbgpt")


def test_searchapi_search_more_results_than_the_page_holds(
    monkeypatch, mock_requests_get
):
    monkeypatch.setenv("SEARCHAPI_API_KEY", "test_key")
    mock_requests_get.return_value = _searchapi_response(10)

    view = searchapi_search("what is dbgpt", num_results=20)

    # One request, one page: asking for more returns what the page holds.
    assert mock_requests_get.call_count == 1
    assert view.count("### [") == 10


def test_searchapi_search_non_object_success_body(monkeypatch, mock_requests_get):
    monkeypatch.setenv("SEARCHAPI_API_KEY", "test_key")
    response = MagicMock()
    response.ok = True
    response.status_code = 200
    response.json.return_value = []
    mock_requests_get.return_value = response

    assert searchapi_search("what is dbgpt") == ""


@pytest.mark.asyncio
async def test_searchapi_search_through_tool_pack(monkeypatch, mock_requests_get):
    monkeypatch.setenv("SEARCHAPI_API_KEY", "test_key")
    mock_requests_get.return_value = _searchapi_response(10)
    pack = ToolPack([searchapi_search._tool])

    # Discovery by the registered name, then execution the way agents do it.
    assert "searchapi_search" in pack._resources
    view = await pack.async_execute(
        resource_name="searchapi_search", query="what is dbgpt", num_results=8
    )

    assert view.startswith("### [Title 0](https://example.com/0)\nSnippet 0")
    assert view.count("### [") == 8
    _, kwargs = mock_requests_get.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer test_key"


@pytest.mark.asyncio
async def test_searchapi_search_error_through_tool_pack(monkeypatch, mock_requests_get):
    monkeypatch.setenv("SEARCHAPI_API_KEY", "test_key")
    response = MagicMock()
    response.ok = False
    response.status_code = 401
    response.reason = "Unauthorized"
    response.json.return_value = {"error": "Invalid API key."}
    mock_requests_get.return_value = response
    pack = ToolPack([searchapi_search._tool])

    # The agent sees the API message inside the ToolExecutionException.
    with pytest.raises(ToolExecutionException, match="Invalid API key."):
        await pack.async_execute(
            resource_name="searchapi_search", query="what is dbgpt"
        )
