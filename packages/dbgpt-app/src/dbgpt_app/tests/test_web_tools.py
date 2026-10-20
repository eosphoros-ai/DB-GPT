"""Unit tests for the web_search / web_fetch built-in tools."""

import json

import pytest

from dbgpt_app.openapi.api_v1.tools import web_tools


def test_ssrf_guard_rejects_non_public():
    for bad in (
        "http://127.0.0.1/secret",
        "http://10.1.2.3/x",
        "http://192.168.1.1/",
        "http://169.254.169.254/latest/meta-data",
        "file:///etc/passwd",
        "ftp://example.com/x",
    ):
        with pytest.raises(ValueError):
            web_tools.assert_public_url(bad)


def test_normalize_url_upgrades_and_rewrites():
    assert web_tools._normalize_url("http://example.com/a").startswith("https://")
    assert (
        web_tools._normalize_url("https://github.com/o/r/blob/main/f.py")
        == "https://raw.githubusercontent.com/o/r/main/f.py"
    )


def test_html_to_markdown_extracts_main_content():
    html = """
    <html><head><title>T</title><script>var x=1;</script></head>
    <body><nav>menu</nav><main>
      <h2>Section</h2><p>Hello <b>world</b>.</p>
      <ul><li>one</li><li>two</li></ul>
    </main></body></html>"""
    title, md = web_tools.html_to_markdown(html)
    assert title == "T"
    assert "## Section" in md
    assert "Hello world." in md
    assert "- one" in md
    assert "var x=1" not in md
    assert "menu" not in md


def test_build_search_envelope_shape():
    env = json.loads(
        web_tools.build_search_envelope(
            "q", [{"title": "T1", "url": "https://a/", "snippet": "s1"}]
        )
    )
    assert env["chunks"][0]["output_type"] == "text"
    assert "1. T1" in env["chunks"][0]["content"]
    assert env["chunks"][1]["output_type"] == "search_results"
    assert env["chunks"][1]["items"][0]["url"] == "https://a/"


def test_build_fetch_envelope_truncation_note():
    env = json.loads(
        web_tools.build_fetch_envelope(
            {
                "title": "P",
                "final_url": "https://p/",
                "markdown": "body",
                "truncated": True,
                "chars": 99999,
            }
        )
    )
    assert "[content truncated]" in env["chunks"][0]["content"]
    assert env["chunks"][1]["output_type"] == "web_page"


def test_web_search_unknown_provider_returns_error(monkeypatch):
    monkeypatch.setenv("DBGPT_WEB_SEARCH_PROVIDER", "nope")
    tool = web_tools.make_web_search()
    out = tool(query="x")
    assert "unknown search provider" in str(out)


def test_web_search_uses_provider_and_envelope(monkeypatch):
    monkeypatch.setenv("DBGPT_WEB_SEARCH_PROVIDER", "duckduckgo")
    monkeypatch.setitem(
        web_tools._PROVIDERS,
        "duckduckgo",
        lambda q, n: [{"title": "A", "url": "https://a/", "snippet": "s"}],
    )
    tool = web_tools.make_web_search()
    out = json.loads(tool(query="q"))
    assert out["chunks"][1]["output_type"] == "search_results"


def test_web_fetch_error_envelope(monkeypatch):
    def boom(url):
        raise ValueError("blocked non-public address")

    monkeypatch.setattr(web_tools, "fetch_page", boom)
    tool = web_tools.make_web_fetch()
    out = str(tool(url="http://127.0.0.1/"))
    assert "fetch failed" in out
