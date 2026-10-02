"""Tests for the search tools."""

from unittest.mock import MagicMock, patch

import pytest

from ..search_tool import serply_search


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
