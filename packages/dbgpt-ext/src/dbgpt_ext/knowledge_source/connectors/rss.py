"""RSS connector — the reference example for community datasource plugins.

A complete, dependency-free connector showing every contract method:
validate / list_resources / fetch_all / fetch_incremental / fetch_resource.
Copy this file, rename the type, swap the API calls — that's a new
datasource integration.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Dict, List, Optional

import httpx

from dbgpt_ext.knowledge_source.base import (
    BaseKnowledgeSourceConnector,
    ConnectorAuthField,
    ConnectorError,
    ConnectorMeta,
    FetchedItem,
    ItemHandler,
    ResourceInfo,
    SyncCursor,
)
from dbgpt_ext.knowledge_source.registry import register_source_connector

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")
_ITEM_XPATH = ".//item"
_NS = {"atom": "http://www.w3.org/2005/Atom", "dc": "http://purl.org/dc/elements/1.1/"}


def _text(node: Optional[ET.Element], path: str) -> str:
    if node is None:
        return ""
    found = node.find(path, _NS)
    return (found.text or "").strip() if found is not None and found.text else ""


def _parse_ts(raw: str) -> Optional[datetime]:
    raw = (raw or "").strip()
    if not raw:
        return None
    from email.utils import parsedate_to_datetime

    try:
        return parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None


def _entry_to_markdown(title: str, link: str, content_html: str, published: str) -> str:
    """Minimal HTML→Markdown for feed bodies (paragraph/heading-agnostic)."""
    body = content_html.strip()
    if not body:
        body = ""
    text = body.replace("<p>", "").replace("</p>", "\n\n")
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = _TAG_RE.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    header = f"[原文]({link})\n\n" if link else ""
    meta_line = f"> {published}\n\n" if published else ""
    return f"{header}{meta_line}{text}"


@register_source_connector
class RSSConnector(BaseKnowledgeSourceConnector):
    """One fetch = one feed; incremental via per-entry id dedup cursor."""

    type = "rss"
    meta = ConnectorMeta(
        name="RSS",
        icon="rss",
        description="Subscribe and sync an RSS/Atom feed into the knowledge space.",
        auth_fields=[
            ConnectorAuthField(
                key="feed_url",
                label="Feed URL",
                required=True,
                placeholder="https://blog.example.com/feed.xml",
            )
        ],
        supports_incremental=True,
        resource_noun="feeds",
    )

    async def validate(self, config: Dict[str, str]) -> None:
        feed_url = (config.get("feed_url") or "").strip()
        if not feed_url.startswith(("http://", "https://")):
            raise ConnectorError("feed_url must be a valid http(s) URL")
        await self._fetch_xml(feed_url)  # raises ConnectorError on failure

    async def list_resources(
        self, config: Dict[str, str], parent_id: str = ""
    ) -> List[ResourceInfo]:
        """Flat datasource: single feed resource, ignore children requests."""
        if parent_id:
            return []
        feed_url = (config.get("feed_url") or "").strip()
        # per-row display hides the raw URL: prefer the feed's own channel
        # title; fallback is host+path (scheme stripped), not the full URL
        from urllib.parse import urlparse

        root = await self._fetch_xml(feed_url)
        channel_title = _text(root, ".//channel/title") or _text(
            root, ".//atom:feed/atom:title"
        )
        if channel_title:
            title = f"RSS · {channel_title}"
        else:
            parsed = urlparse(feed_url)
            title = f"RSS · {parsed.netloc}{parsed.path}".rstrip("/")
        return [
            ResourceInfo(
                external_id=feed_url,
                title=title,
                parent_id=None,
                has_children=False,
                resource_type="feed",
            )
        ]

    async def fetch_all(
        self,
        config: Dict[str, str],
        resource_ids: List[str],
        on_item: ItemHandler,
        cursor: Optional[SyncCursor] = None,
    ) -> SyncCursor:
        state = SyncCursor.from_dict(cursor.to_dict() if cursor else {})
        for feed_url in resource_ids or [(config.get("feed_url") or "").strip()]:
            if not feed_url:
                continue
            root = await self._fetch_xml(feed_url)
            for item in root.findall(_ITEM_XPATH, _NS) or root.findall(
                ".//atom:entry", _NS
            ):
                external_id = (
                    _text(item, "guid")
                    or _text(item, ".//atom:entry/atom:id")
                    or _text(item, "link")
                )
                if not external_id:
                    continue
                title = _text(item, "title") or _text(item, ".//atom:title")
                link = _text(item, "link")
                content_html = _text(item, "encoded") or ""
                if not content_html:
                    desc = _text(item, "description") or _text(item, ".//atom:content")
                    if desc:
                        content_html = desc
                published = (
                    _text(item, "pubDate")
                    or _text(item, ".//atom:updated")
                    or _text(item, "date")
                )
                updated_at = _parse_ts(published)
                await on_item(
                    FetchedItem(
                        external_id=f"rss:{external_id}",
                        title=title or external_id[:80],
                        content=_entry_to_markdown(
                            title, link, content_html, published
                        ),
                        content_format="markdown",
                        source_url=link,
                        updated_at=updated_at,
                        metadata={"feed_url": feed_url},
                    )
                )
                ts = updated_at or datetime.now(timezone.utc)
                state.set(external_id, ts.isoformat())
        return state

    async def fetch_incremental(
        self,
        config: Dict[str, str],
        resource_ids: List[str],
        cursor: SyncCursor,
        on_item: ItemHandler,
    ) -> SyncCursor:
        """Feed semantics: refetch and rely on the engine's content-hash
        dedupe; we keep the id map so future feeds can skip unchanged."""

        return await self.fetch_all(config, resource_ids, on_item, cursor)

    async def fetch_resource(
        self, config: Dict[str, str], resource_id: str
    ) -> Optional[FetchedItem]:
        """``resource_id`` is ``rss:<guid>`` — find it in the feed."""
        feed_url = (config.get("feed_url") or "").strip()
        wanted = resource_id.removeprefix("rss:")
        try:
            root = await self._fetch_xml(feed_url)
        except ConnectorError:
            return None
        for item in root.iter("item"):
            guid = _text(item, "guid") or _text(item, "link")
            if guid == wanted:
                return FetchedItem(
                    external_id=resource_id,
                    title=_text(item, "title") or wanted[:80],
                    content=_entry_to_markdown(
                        "", _text(item, "link"), _text(item, "encoded") or "", ""
                    ),
                    source_url=_text(item, "link"),
                )
        return None

    async def _fetch_xml(self, feed_url: str) -> ET.Element:
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(feed_url, headers={"User-Agent": "DB-GPT/1.0"})
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ConnectorError(f"RSS fetch failed: {exc}") from exc
        try:
            return ET.fromstring(resp.text)
        except ET.ParseError as exc:
            raise ConnectorError(f"invalid RSS/Atom XML: {exc}") from exc
