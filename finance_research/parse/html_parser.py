"""HTML page fetching, table and text extraction."""

import io
import ipaddress
import socket
from typing import List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:112.0) "
        "Gecko/20100101 Firefox/112.0"
    )
}

# Bound the size of untrusted responses before parsing.
MAX_HTML_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_PDF_BYTES = 20 * 1024 * 1024  # 20 MB
_MAX_REDIRECTS = 5

_BLOCKED_HOSTS = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "::",
}


def _check_hostname(hostname: str, port: Optional[int]) -> None:
    """Reject loopback, private, link-local, and reserved destinations."""
    if hostname.lower() in _BLOCKED_HOSTS:
        raise ValueError(f"Blocked host: {hostname!r}")
    try:
        infos = socket.getaddrinfo(hostname, port or 0)
    except socket.gaierror as exc:
        raise ValueError(f"Cannot resolve host {hostname!r}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_loopback
            or ip.is_private
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise ValueError(f"Blocked private/reserved destination: {ip}")


def _validate_url(url: str) -> None:
    """Allow only http/https and reject suspicious destinations."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsupported URL scheme: {parsed.scheme!r}")
    if not parsed.hostname:
        raise ValueError("URL has no host")
    _check_hostname(parsed.hostname, parsed.port)


def _request_bounded(
    url: str, timeout: int = 20, max_bytes: int = MAX_HTML_BYTES
) -> Tuple[bytes, str]:
    """Fetch ``url``, revalidating every redirect, streaming with a byte cap.

    Returns ``(content, encoding_hint)``. Raises on non-http(s) URLs, private
    destinations, redirect loops, or responses over ``max_bytes``.
    """
    current_url = url
    for _ in range(_MAX_REDIRECTS):
        _validate_url(current_url)
        resp = requests.get(
            current_url,
            headers=HEADERS,
            timeout=timeout,
            stream=True,
            allow_redirects=False,
        )
        if resp.is_redirect:
            location = resp.headers.get("Location")
            resp.close()
            if not location:
                raise ValueError(f"Redirect without Location from {current_url}")
            current_url = urljoin(current_url, location)
            continue
        try:
            resp.raise_for_status()
            encoding = resp.encoding or "utf-8"
            chunks = []
            total = 0
            for chunk in resp.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError(
                        f"Response from {current_url} exceeds {max_bytes} bytes"
                    )
                chunks.append(chunk)
            return b"".join(chunks), encoding
        finally:
            resp.close()
    raise ValueError(f"Too many redirects for {url}")


def fetch_html(url: str, timeout: int = 20) -> str:
    """Fetch the raw HTML content of a URL, bounded and SSRF-safe."""
    content, encoding = _request_bounded(
        url, timeout=timeout, max_bytes=MAX_HTML_BYTES
    )
    return content.decode(encoding, errors="replace")


def fetch_pdf_bytes(url: str, timeout: int = 20) -> bytes:
    """Download a remote PDF into memory, bounded and SSRF-safe."""
    content, _ = _request_bounded(url, timeout=timeout, max_bytes=MAX_PDF_BYTES)
    return content


def extract_tables(html: str) -> List[pd.DataFrame]:
    """Extract all ``<table>`` elements from HTML as DataFrames."""
    try:
        # StringIO avoids the pandas 2.1+ deprecation for literal HTML input.
        return pd.read_html(io.StringIO(html))
    except (ValueError, ImportError):
        return []


def extract_text(html: str) -> str:
    """Extract readable text from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    return soup.get_text("\n", strip=True)
