"""Connector contract for external datasources.

Mirrors WeKnora's Go ``Connector`` interface (see
``internal/datasource/connector.go``):

- ``validate``          — credential test, no side effects
- ``list_resources``    — lazy, parent-driven resource tree for the picker
- ``fetch_all``         — full fetch with per-item streaming callback
- ``fetch_incremental`` — cursor-based delta fetch (cursor is a complete
  resumable snapshot, NOT a delta)
- ``fetch_resource``    — single-resource refetch (update detection)

Items are delivered through a callback instead of big return lists so a
100k-document wiki stays O(1) in memory and mid-sync checkpoints work.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Awaitable, Callable, ClassVar, Dict, List, Optional


class ConnectorError(Exception):
    """Raised by source connectors on auth/filter/validation failures."""


@dataclass
class ConnectorAuthField:
    """One credential form field. The frontend renders the binding form
    from ``meta.auth_fields`` — community connectors need zero UI code."""

    key: str
    label: str
    required: bool = False
    secret: bool = False  # rendered as password input; encrypted at rest
    placeholder: str = ""
    hint: str = ""


@dataclass
class ConnectorMeta:
    name: str
    auth_fields: List[ConnectorAuthField] = field(default_factory=list)
    icon: str = ""
    description: str = ""
    supports_incremental: bool = False
    resource_noun: str = "docs"  # e.g. "spaces"/"feeds"/"pages" for toasts


@dataclass
class ResourceInfo:
    """A node in the (possibly lazy) resource tree shown in the picker."""

    external_id: str
    title: str
    parent_id: Optional[str] = None
    has_children: bool = False
    resource_type: str = "doc"  # wiki_space | node | page | folder | doc | feed


@dataclass
class FetchedItem:
    """One document fetched from the platform. ``content`` is Markdown;
    binary/attachment-heavy payloads may instead set ``content_url``."""

    external_id: str
    title: str
    content: str = ""
    content_format: str = "markdown"  # markdown | html | url
    source_url: str = ""
    updated_at: Optional[datetime] = None
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class SyncCursor:
    """Complete resumable snapshot of sync progress (WeKnora #2136):
    serde must reproduce all progress so a timed-out sync resumes from
    the last checkpoint instead of restarting."""

    cursor: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, str]:
        return dict(self.cursor)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, str]]) -> "SyncCursor":
        if not data:
            return cls()
        return cls(cursor={str(k): str(v) for k, v in data.items()})

    def get(self, key: str, default: str = "") -> str:
        return self.cursor.get(key, default)

    def set(self, key: str, value: str) -> None:
        self.cursor[key] = value


ItemHandler = Callable[[FetchedItem], Awaitable[None]]


class BaseKnowledgeSourceConnector(ABC):
    """Implement this to integrate a new external platform.

    Register with ``@register_source_connector`` (or package entry-points group
    ``dbgpt.knowledge_sources``) — see registry.py.
    """

    type: ClassVar[str] = ""
    """Unique connector type identifier, e.g. ``"feishu_wiki"``."""

    meta: ClassVar[ConnectorMeta] = ConnectorMeta(name="")

    @abstractmethod
    async def validate(self, config: Dict[str, str]) -> None:
        """Verify credentials/connectivity. Raise ConnectorError on failure.
        Must have no side effects (no writes on the platform)."""

    @abstractmethod
    async def list_resources(
        self, config: Dict[str, str], parent_id: str = ""
    ) -> List[ResourceInfo]:
        """List the resource tree for the picker.

        ``parent_id == ""`` → top-level resources (e.g. wiki spaces).
        ``parent_id != ""`` → direct children of that resource.
        Connectors with a flat/single-call tree may ignore parent_id and
        return [] for non-empty parent_id.
        """

    @abstractmethod
    async def fetch_all(
        self,
        config: Dict[str, str],
        resource_ids: List[str],
        on_item: ItemHandler,
        cursor: Optional[SyncCursor] = None,
    ) -> SyncCursor:
        """Fetch every document under the given resource ids, emitting each
        item through ``on_item``. Return the final cursor snapshot."""

    async def fetch_incremental(
        self,
        config: Dict[str, str],
        resource_ids: List[str],
        cursor: SyncCursor,
        on_item: ItemHandler,
    ) -> SyncCursor:
        """Fetch items changed since ``cursor``. Default: full refetch
        (the sync engine then dedupes by content hash). Override when the
        platform exposes edit times / change feeds."""

    async def fetch_resource(
        self, config: Dict[str, str], resource_id: str
    ) -> Optional[FetchedItem]:
        """Refetch a single resource (update detection). Default: None →
        the sync engine will use fetch_all paths instead."""
        return None
