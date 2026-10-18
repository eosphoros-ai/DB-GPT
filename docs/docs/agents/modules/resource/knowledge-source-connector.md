---
sidebar_position: 5
title: Custom Knowledge Source Connector
---

# Custom Knowledge Source Connector

This guide shows how to integrate a new external document platform (like the
built-in **Feishu**, **Yuque**, **RSS** connectors) so its documents flow into
a DB-GPT knowledge space automatically — chunking, retrieval, and LLM-Wiki
updates all work without extra code.

Everything you implement lives behind one interface. The frontend credential
form, encrypted credential storage, the lazy resource picker, incremental
syncing, and the ingestion pipeline are provided by the framework.

## Architecture in one picture

```
Your connector (validate / list_resources / fetch_*)
        │  registered via entry-points, config modules, or decorator
        ▼
Knowledge Source Sync Engine (schedule / cursor checkpoints / conflict rules)
        │  FetchedItem (Markdown) → knowledge_document
        ▼
Standard knowledge pipeline (chunk → index → retrieve → LLM-Wiki)
```

Contract layer (read alongside this guide):

- `packages/dbgpt-ext/src/dbgpt_ext/knowledge_source/base.py` — the interface
- `packages/dbgpt-ext/src/dbgpt_ext/knowledge_source/registry.py` — discovery & registration
- `packages/dbgpt-ext/src/dbgpt_ext/knowledge_source/connectors/rss.py` — smallest reference connector

## Quick start (a complete connector)

```python
# my_connector.py — an OpenAPI-style wiki platform
from typing import Dict, List, Optional
from datetime import datetime

from dbgpt_ext.knowledge_source.base import (
    BaseKnowledgeSourceConnector,
    ConnectorAuthField,
    ConnectorError,
    ConnectorMeta,
    FetchedItem,
    ResourceInfo,
    SyncCursor,
)
from dbgpt_ext.knowledge_source.registry import register_source_connector


@register_source_connector
class MyWikiConnector(BaseKnowledgeSourceConnector):
    type = "my_wiki"  # globally unique, becomes the binding's type
    meta = ConnectorMeta(
        name="My Wiki",
        icon="mywiki",
        description="Sync pages from our internal wiki",
        auth_fields=[
            ConnectorAuthField(key="base_url", label="API URL", required=True),
            ConnectorAuthField(
                key="token", label="Token", required=True, secret=True
            ),
        ],
        supports_incremental=True,
    )

    async def validate(self, config: Dict[str, str]) -> None:
        """Runs when the user clicks Validate in the binding wizard."""
        me = await api_get(config, "/user")
        if not me:
            raise ConnectorError("invalid token")

    async def list_resources(
        self, config: Dict[str, str], parent_id: str = ""
    ) -> List[ResourceInfo]:
        """Return the resource tree for the scope picker.

        parent_id == ""  -> top-level rows (e.g. spaces)
        parent_id != ""  -> direct children of that row (lazy loading)
        """
        parent = parent_id or "root"
        return [
            ResourceInfo(
                external_id=page_id,          # stable platform id
                title=page_title,
                parent_id=parent if parent_id else None,
                has_children=False,
                resource_type="page",
            )
            for page_id, page_title in await api_list_pages(config, parent)
        ]

    async def fetch_all(
        self,
        config: Dict[str, str],
        resource_ids: List[str],
        on_item,                       # async callback — emit items one by one
        cursor: Optional[SyncCursor] = None,
    ) -> SyncCursor:
        cursor = cursor or SyncCursor()
        for doc in await api_fetch_docs(config, resource_ids):
            await on_item(
                FetchedItem(
                    external_id=doc["id"],        # stable forever, do NOT use titles
                    title=doc["title"],
                    content=doc["markdown"],      # Markdown goes to the pipeline
                    source_url=doc["url"],
                    updated_at=doc["updated_at"],  # drives incremental sync
                )
            )
            cursor.set(doc["id"], doc["updated_at"])
        return cursor

    async def fetch_resource(
        self, config: Dict[str, str], resource_id: str
    ) -> Optional[FetchedItem]:
        return await api_get_doc(config, resource_id)  # None = fall back to fetch_all
```

That is the whole connector. Register it (below), restart DB-GPT, and it
appears in **Knowledge Base → Sources → Bind source** with a credential form
generated from `meta.auth_fields` — zero frontend code.

## The five methods in detail

| Method | When it runs | Contract |
|---|---|---|
| `validate(config)` | "Validate & bind" in the wizard | Read-only probe; raise `ConnectorError` with a human-friendly message on failure |
| `list_resources(config, parent_id)` | Every time the user expands a tree node | `parent_id == ""` → top level; else direct children. Flat platforms: ignore `parent_id`, return one row |
| `fetch_all(config, resource_ids, on_item, cursor)` | Full sync (manual / scheduled / fallback) | Stream items through `await on_item(...)`; never accumulate the full corpus in memory. Return the final `SyncCursor` snapshot |
| `fetch_incremental(config, resource_ids, cursor, on_item)` | Scheduled incremental sync | Emit only changed items; return an updated cursor. Default implementation simply calls `fetch_all` (engine dedupes by content hash) |
| `fetch_resource(config, resource_id)` | Single-reso urce refresh | Return `None` to let the engine fall back to `fetch_all` |

## Data contract rules

- **`external_id` must be stable forever** — it maps platform items to local
  documents. Numeric ids/guids only; titles and slugs change.
- **`content` is Markdown** — convert platform payloads (blocks, XHTML, lake)
  before emitting; the pipeline chunks and embeds it as-is.
- **`updated_at` powers incremental sync** — populate it whenever the
  platform exposes edit times; otherwise keep the default full-refetch
  behavior.
- **`SyncCursor` is a resumable snapshot**, not a delta. Serialization must
  let a timed-out sync resume from the last checkpoint (typical shape:
  `{external_id: updated_at}` or `{next_page_token}`).
- Emit items **one by one** through `on_item` — the engine checkpoints the
  cursor after every item.

## Registration (three ways)

### A. pip entry-points (publish to PyPI — recommended)

```toml
# your package's pyproject.toml
[project.entry-points."dbgpt.knowledge_sources"]
my_wiki = "my_connector:MyWikiConnector"
```

Users `pip install your-connector` and restart DB-GPT.

### B. Config-declared module (local development)

```toml
[rag.knowledge_source]
extra_connector_modules = ["my_connector"]
```

### C. In-process decorator (tests / prototypes)

```python
from dbgpt_ext.knowledge_source.registry import register_source_connector
@register_source_connector
class MyConnector(...): ...
```

Registration validates that `type` is unique and `meta.name` is set, so a
broken plugin fails loudly at startup instead of mid-sync.

## Credential form without frontend code

`meta.auth_fields` drives the bind-wizard form:

```python
ConnectorAuthField(
    key="base_url", label="API URL", required=True,
    placeholder="https://wiki.example.com",
)
ConnectorAuthField(key="token", label="API Token", required=True, secret=True)
```

`secret=True` renders a password input and stores the value AES-256-GCM
encrypted. The form layout, validation display, and encryption are all handled
by the framework.

## Contract self-tests

Copy the pattern from `packages/dbgpt-ext/tests/knowledge_source/` (the Feishu
and Yuque suites): a fake API client + fixtures that exercise
`validate → list_resources (2 levels) → fetch_all (≥2 items) → cursor snapshot
→ fetch_incremental (1 changed item)`. Mock the platform API — no network
needed — and assert on emitted `FetchedItem`s plus the returned cursor.

## Reference implementations

| Connector | File | Good for learning |
|---|---|---|
| RSS | `.../knowledge_source/connectors/rss.py` | Flat scope, single fetch loop, HTML→Markdown |
| Yuque | `.../knowledge_source/connectors/yuque.py` | Personal+team repo merge, pagination, format guard |
| Feishu Wiki | `.../knowledge_source/connectors/feishu_wiki.py` | Two-level lazy tree, per-type content dispatch, edit-time incremental |
| Feishu Drive | `.../knowledge_source/connectors/feishu_drive.py` | Folder walking, docx blocks conversion |

## FAQ

- **Platform has no tree concept (feeds, monitoring)?** Return one top-level
  resource; the picker degrades to a single checkbox.
- **Pagination?** Loop inside `fetch_all`/`list_resources`, checkpoint the
  page token into `SyncCursor` between pages.
- **Rate limits?** Wrap calls with `asyncio.Semaphore`, retry 429s with
  exponential backoff, and raise `ConnectorError` after exhausting retries.
- **Attachment images?** Put platform URLs in `FetchedItem.metadata`; the
  engine's attachment handler downloads and rewrites them to local storage.
- **Broken plugin?** Import failures are logged and skipped at startup —
  the server still boots; fix and restart.

## Where your data goes

`FetchedItem → knowledge_document (doc_type=TEXT) → standard chunk/embed
pipeline`. Docs synced this way are identical to manual uploads for retrieval
and chat, and LLM-Wiki regenerates affected pages automatically when the
space has Wiki enabled.
