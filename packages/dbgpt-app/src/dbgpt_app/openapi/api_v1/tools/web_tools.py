"""web_search / web_fetch built-in tools — the "search then fetch" pair.

Mainstream agent products converge on two complementary tools: a search
tool that *discovers* candidate pages (title/url/snippet list) and a
fetch tool that *retrieves* one page as normalized markdown. This
module implements both server-side so every engine (dbgpt ReAct and
the pi harness bridge) shares one contained implementation:

- ``web_search``: pluggable keyless-first providers — duckduckgo
  (default, HTML lite), baidu (CN fallback), searxng (self-hosted);
  results return as a numbered text chunk plus a structured
  ``search_results`` chunk for UI citation chips.
- ``web_fetch``: httpx GET with timeout/redirect/size caps, HTTP→HTTPS
  upgrade, GitHub blob→raw rewrite, SSRF guard (resolved IPs must be
  public), bs4+lxml main-text→markdown extraction and a char cap.

Configuration is environment driven (no toml section required):
``DBGPT_WEB_SEARCH_PROVIDER`` (duckduckgo|baidu|searxng),
``DBGPT_WEB_SEARXNG_URL``, ``DBGPT_WEB_FETCH_MAX_CHARS``.
"""

import ipaddress
import json
import logging
import os
import re
import socket
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from dbgpt.agent.resource.tool.base import tool

logger = logging.getLogger(__name__)

_UA = "Mozilla/5.0 (compatible; DB-GPT-Agent/1.0; +https://github.com/eosphoros-ai/DB-GPT)"
_MAX_FETCH_BYTES = 5 * 1024 * 1024
_DROP_TAGS = [
    "script",
    "style",
    "nav",
    "header",
    "footer",
    "aside",
    "form",
    "noscript",
    "svg",
    "iframe",
    "button",
]


def _env_provider() -> str:
    return os.getenv("DBGPT_WEB_SEARCH_PROVIDER", "duckduckgo").strip().lower()


def _env_max_chars() -> int:
    try:
        return max(2000, int(os.getenv("DBGPT_WEB_FETCH_MAX_CHARS", "24000")))
    except ValueError:
        return 24000


def _envelope_text(content: str) -> Dict[str, Any]:
    return {"output_type": "text", "content": content}


def _envelope(extra: Dict[str, Any]) -> Dict[str, Any]:
    return {"chunks": [extra]}


# ---------------------------------------------------------------------------
# SSRF guard + fetch
# ---------------------------------------------------------------------------
def assert_public_url(url: str) -> None:
    """Reject non-http(s) schemes and privately-routed hosts."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"unsupported scheme: {parsed.scheme!r}")
    host = parsed.hostname
    if not host:
        raise ValueError("url has no host")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise ValueError(f"dns resolve failed for {host}: {e}") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise ValueError(f"blocked non-public address for {host}: {ip}")


def _normalize_url(url: str) -> str:
    url = url.strip()
    if url.startswith("http://"):
        url = "https://" + url[len("http://") :]
    # GitHub blob pages render via JS; the raw endpoint carries the text.
    m = re.match(r"^https://github\.com/([^/]+/[^/]+)/blob/(.+)$", url)
    if m:
        url = f"https://raw.githubusercontent.com/{m.group(1)}/{m.group(2)}"
    return url


def html_to_markdown(html_text: str) -> Tuple[str, str]:
    """Extract (title, markdown) main content from an HTML document."""
    soup = BeautifulSoup(html_text, "lxml")
    for tag in list(soup(_DROP_TAGS)):
        tag.decompose()
    title = soup.title.get_text(strip=True) if soup.title else ""
    root = soup.find("main") or soup.find("article") or soup.body or soup
    lines: List[str] = []
    for el in root.find_all(
        ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "pre", "blockquote", "td", "th"]
    ):
        text = re.sub(r"\s+", " ", el.get_text(" ", strip=True))
        text = re.sub(r"\s+([.,;:!?%)])", r"\1", text)
        if not text:
            continue
        name = el.name
        if name.startswith("h"):
            lines.append(f"{'#' * int(name[1])} {text}")
        elif name == "li":
            lines.append(f"- {text}")
        elif name == "pre":
            lines.append("```\n" + el.get_text() + "\n```")
        elif name == "blockquote":
            lines.append(f"> {text}")
        elif name in ("td", "th"):
            continue  # tables collapse into their cell text via p/li walks
        else:
            lines.append(text)
    # de-duplicate consecutive identical lines (nested matches)
    out: List[str] = []
    for line in lines:
        if not out or out[-1] != line:
            out.append(line)
    return title, "\n\n".join(out)


def fetch_page(url: str) -> Dict[str, Any]:
    """Fetch one public URL and normalize it to markdown."""
    url = _normalize_url(url)
    assert_public_url(url)
    with httpx.Client(
        follow_redirects=True,
        max_redirects=5,
        timeout=20.0,
        headers={
            "User-Agent": _UA,
            "Accept": "text/markdown, text/html, text/plain, */*",
        },
    ) as client:
        resp = client.get(url)
        resp.raise_for_status()
        raw = resp.content
        if len(raw) > _MAX_FETCH_BYTES:
            raw = raw[:_MAX_FETCH_BYTES]
        ctype = (resp.headers.get("content-type") or "").lower()
        text = raw.decode("utf-8", errors="replace")
        if "html" in ctype or text.lstrip()[:15].lower().startswith(
            ("<!doctype", "<html")
        ):
            title, markdown = html_to_markdown(text)
        else:
            title, markdown = "", text
    cap = _env_max_chars()
    truncated = len(markdown) > cap
    return {
        "title": title,
        "final_url": str(resp.url),
        "markdown": markdown[:cap],
        "truncated": truncated,
        "chars": len(markdown),
    }


# ---------------------------------------------------------------------------
# search providers
# ---------------------------------------------------------------------------
def _search_duckduckgo(query: str, num: int) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    with httpx.Client(
        follow_redirects=True,
        timeout=15.0,
        headers={"User-Agent": _UA},
    ) as client:
        resp = client.post(
            "https://lite.duckduckgo.com/lite/",
            data={"q": query},
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        for a in soup.select("a.result-link, a[rel='nofollow']"):
            href = a.get("href") or ""
            title = a.get_text(strip=True)
            if not href.startswith("http") or not title:
                continue
            snippet = ""
            row = a.find_parent("tr")
            if row is not None:
                nxt = row.find_next_sibling("tr")
                if nxt is not None:
                    snippet = re.sub(r"\s+", " ", nxt.get_text(" ", strip=True))
            results.append({"title": title, "url": href, "snippet": snippet[:300]})
            if len(results) >= num:
                break
    return results


def _search_baidu(query: str, num: int) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    with httpx.Client(
        follow_redirects=True,
        timeout=15.0,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        },
    ) as client:
        resp = client.get(
            "https://www.baidu.com/s",
            params={"wd": query, "rn": str(max(num, 10))},
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        for block in soup.select("div.result, div.c-container"):
            a = block.find("h3")
            if a is None:
                a = block.find("a")
            if a is None:
                continue
            href = a.get("href") or ""
            title = a.get_text(strip=True)
            if not href.startswith("http") or not title:
                continue
            abs_el = block.select_one(
                ".c-abstract, .content-right_8Ts1Q, span.content-right_2nO83"
            )
            snippet = (
                re.sub(r"\s+", " ", abs_el.get_text(" ", strip=True)) if abs_el else ""
            )
            results.append({"title": title, "url": href, "snippet": snippet[:300]})
            if len(results) >= num:
                break
    return results


def _search_searxng(query: str, num: int) -> List[Dict[str, str]]:
    base = os.getenv("DBGPT_WEB_SEARXNG_URL", "").rstrip("/")
    if not base:
        raise ValueError("searxng provider needs DBGPT_WEB_SEARXNG_URL")
    with httpx.Client(
        follow_redirects=True, timeout=15.0, headers={"User-Agent": _UA}
    ) as client:
        resp = client.get(f"{base}/search", params={"q": query, "format": "json"})
        resp.raise_for_status()
        data = resp.json()
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": (r.get("content") or "")[:300],
        }
        for r in (data.get("results") or [])[:num]
    ]


_PROVIDERS = {
    "duckduckgo": _search_duckduckgo,
    "baidu": _search_baidu,
    "searxng": _search_searxng,
}


def build_search_envelope(query: str, items: List[Dict[str, str]]) -> str:
    """Serialize search results into the tool envelope (text + structured)."""
    lines = [
        f"{i + 1}. {it['title']}\n   {it['url']}\n   {it['snippet']}"
        for i, it in enumerate(items)
    ]
    body = f"Web search results for: {query}\n\n" + "\n".join(lines)
    return json.dumps(
        {
            "chunks": [
                _envelope_text(body),
                {"output_type": "search_results", "items": items},
            ]
        },
        ensure_ascii=False,
    )


def build_fetch_envelope(page: Dict[str, Any]) -> str:
    """Serialize a fetched page into the tool envelope."""
    head = (
        f"# {page['title']}\nsource: {page['final_url']}\n\n"
        if page["title"]
        else f"source: {page['final_url']}\n\n"
    )
    note = "\n\n[content truncated]" if page["truncated"] else ""
    return json.dumps(
        {
            "chunks": [
                _envelope_text(head + page["markdown"] + note),
                {
                    "output_type": "web_page",
                    "title": page["title"],
                    "url": page["final_url"],
                    "chars": page["chars"],
                },
            ]
        },
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# tool factories
# ---------------------------------------------------------------------------
def make_web_search() -> Any:
    @tool(
        description=(
            "Search the web and return candidate pages. Use this to DISCOVER "
            "sources; then call web_fetch on the most relevant url to read "
            "full content. Parameter: query (string), max_results (int, <=10)."
        )
    )
    def web_search(query: str, max_results: int = 8) -> str:
        provider = _env_provider()
        fn = _PROVIDERS.get(provider)
        if fn is None:
            return json.dumps(
                {
                    "chunks": [
                        _envelope_text(f"Error: unknown search provider {provider!r}")
                    ]
                },
                ensure_ascii=False,
            )
        try:
            items = fn(query, min(int(max_results or 8), 10))
        except Exception as e:
            logger.warning("web_search provider %s failed: %s", provider, e)
            return json.dumps(
                {
                    "chunks": [
                        _envelope_text(f"Error: search provider {provider} failed: {e}")
                    ]
                },
                ensure_ascii=False,
            )
        if not items:
            return json.dumps(
                {"chunks": [_envelope_text(f"No results for query: {query}")]},
                ensure_ascii=False,
            )
        return build_search_envelope(query, items)

    return web_search


def make_web_fetch() -> Any:
    @tool(
        description=(
            "Fetch one web page and return its main content as markdown. "
            "Use after web_search to READ a specific url. "
            "Parameter: url (string, http/https, public hosts only)."
        )
    )
    def web_fetch(url: str) -> str:
        try:
            page = fetch_page(url)
        except Exception as e:
            return json.dumps(
                {"chunks": [_envelope_text(f"Error: fetch failed for {url}: {e}")]},
                ensure_ascii=False,
            )
        return build_fetch_envelope(page)

    return web_fetch
