"""Rate-limited HTTP JSON helper shared by platform clients."""

from __future__ import annotations

import asyncio
import logging
import os
import ssl
from typing import Any, Dict, Optional, Union

import httpx

logger = logging.getLogger(__name__)

# Sentry-ish WAFs (Yuque among them) rate-limit default script UAs hard.
# Always send a recognisable product UA unless the caller overrides it.
DEFAULT_UA = "DB-GPT-KnowledgeSource/1.0"

_warned_insecure = False


def _verify_arg() -> Union[str, bool, ssl.SSLContext]:
    """TLS verification strategy for platform calls (corporate proxy CAs):

    1. ``DB_GPT_KS_CA_BUNDLE`` — path to a CA bundle / PEM (recommended for
       TLS-intercepting proxies; get the corp root CA from IT)
    2. ``DB_GPT_KS_INSECURE=1`` — disable verification (last resort, logs a
       loud warning; never enable in production)
    3. default: strict verification (httpx/certifi trust store)
    """
    global _warned_insecure
    bundle = os.environ.get("DB_GPT_KS_CA_BUNDLE", "").strip()
    if bundle:
        return bundle
    insecure = os.environ.get("DB_GPT_KS_INSECURE", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    if insecure:
        if not _warned_insecure:
            logger.warning(
                "DB_GPT_KS_INSECURE is enabled: platform TLS verification is "
                "OFF. This is a security risk — switch to DB_GPT_KS_CA_BUNDLE "
                "with the corporate root CA as soon as possible."
            )
            _warned_insecure = True
        return False
    return True


class RateLimitedClient:
    """Concurrency-capped async client with exponential backoff on
    transient errors / provider rate limiting."""

    RETRY_STATUS = {429, 500, 502, 503, 504}

    def __init__(self, concurrency: int = 3, max_retries: int = 3, timeout: float = 20):
        self._semaphore = asyncio.Semaphore(concurrency)
        self._max_retries = max_retries
        self._timeout = timeout

    async def request_json(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        payload: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        last_error: Optional[str] = None
        for attempt in range(1, self._max_retries + 1):
            async with self._semaphore:
                try:
                    async with httpx.AsyncClient(
                        timeout=self._timeout, verify=_verify_arg()
                    ) as client:
                        resp = await client.request(
                            method,
                            url,
                            headers=headers or {},
                            json=payload,
                            params=params,
                        )
                    if resp.status_code in self.RETRY_STATUS:
                        last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                    else:
                        return resp.json()
                except (httpx.HTTPError, ValueError) as exc:
                    last_error = str(exc)
            await asyncio.sleep(2**attempt * 0.5)
        raise RuntimeError(f"{method} {url} failed after retries: {last_error}")

    async def get_json(self, url: str, headers=None, params=None) -> Any:
        return await self.request_json("GET", url, headers=headers, params=params)

    async def post_json(self, url: str, headers=None, payload=None) -> Any:
        return await self.request_json("POST", url, headers=headers, payload=payload)
