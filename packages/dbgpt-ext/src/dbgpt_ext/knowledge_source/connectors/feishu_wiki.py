"""Feishu wiki (knowledge base) connector.

Resource tree: wiki spaces → node trees (lazy, parent_node_token driven).
Content dispatch by node.obj_type:
- docx   → blocks → Markdown (converters/feishu_docx), tables included
- sheet  → export csv → Markdown table per sheet is P1; P0 links the doc
- bitable→ export csv similar (P0: link-out)
- doc (old editor) / file → link-out placeholder (binary parse is P1)

Incremental: {node_token: obj_edit_time} snapshot — changed nodes are
refetched, new nodes created, removed nodes simply disappear from the
snapshot (engine's sync_deletions handles local cleanup).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional

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
from dbgpt_ext.knowledge_source.clients.feishu import FeishuAPIError, FeishuClient
from dbgpt_ext.knowledge_source.converters.feishu_docx import (
    feishu_blocks_to_markdown,
)
from dbgpt_ext.knowledge_source.registry import register_source_connector

logger = logging.getLogger(__name__)

ItemCB = Callable[[FetchedItem], Awaitable[None]]

_FETCHABLE = {"docx", "sheet", "bitable"}


@register_source_connector
class FeishuWikiConnector(BaseKnowledgeSourceConnector):
    type = "feishu_wiki"
    meta = ConnectorMeta(
        name="飞书知识库",
        icon="feishu",
        description="同步飞书知识库（Wiki）的 docx/sheet/bitable 文档到当前知识空间",
        auth_fields=[
            ConnectorAuthField(
                key="app_id",
                label="App ID",
                required=True,
                hint="飞书开放平台企业自建应用",
            ),
            ConnectorAuthField(
                key="app_secret", label="App Secret", required=True, secret=True
            ),
        ],
        supports_incremental=True,
        resource_noun="wiki",
    )

    def __init__(self, client: Optional[FeishuClient] = None):
        self._client = client  # injected for tests

    def _get_client(self, config: Dict[str, str]) -> FeishuClient:
        if self._client is not None:
            return self._client
        app_id = (config.get("app_id") or "").strip()
        app_secret = (config.get("app_secret") or "").strip()
        if not app_id or not app_secret:
            raise ConnectorError("app_id / app_secret are required")
        return FeishuClient(app_id, app_secret)

    # ------------------------------------------------------------- validate
    async def validate(self, config: Dict[str, str]) -> None:
        try:
            await self._get_client(config)._token_header()
        except FeishuAPIError as exc:
            raise ConnectorError(f"飞书验证失败：{exc}") from exc

    # ------------------------------------------------------- list_resources
    async def list_resources(
        self, config: Dict[str, str], parent_id: str = ""
    ) -> List[ResourceInfo]:
        client = self._get_client(config)
        if not parent_id:
            spaces = await client.wiki_spaces()
            return [
                ResourceInfo(
                    external_id=f"space:{s['space_id']}",
                    title=s.get("name", s["space_id"]),
                    parent_id=None,
                    has_children=True,
                    resource_type="wiki_space",
                )
                for s in spaces
            ]
        # parent_id formats: "space:<space_id>" or "node:<space_id>/<node_token>"
        kind, _, rest = parent_id.partition(":")
        if kind == "space":
            space_id, parent_token = rest, ""
            ui_parent = None
        elif kind == "node":
            space_id, parent_token = rest.split("/", 1)
            ui_parent = parent_id
        else:
            raise ConnectorError(f"invalid parent_id: {parent_id}")
        nodes = await self._paginate_nodes(client, space_id, parent_token)
        return [
            ResourceInfo(
                external_id=f"node:{space_id}/{n['node_token']}",
                title=n.get("title") or n["node_token"],
                parent_id=ui_parent,
                has_children=bool(n.get("has_child")),
                resource_type="node",
            )
            for n in nodes
        ]

    # -------------------------------------------------------------- fetch
    async def fetch_all(
        self,
        config: Dict[str, str],
        resource_ids: List[str],
        on_item: ItemHandler,
        cursor: Optional[SyncCursor] = None,
    ) -> SyncCursor:
        client = self._get_client(config)
        state = SyncCursor.from_dict(cursor.to_dict() if cursor else {})
        sem = asyncio.Semaphore(3)

        async def handle_node(space_id: str, node: Dict[str, Any]) -> None:
            node_token = node["node_token"]
            obj_edit = str(node.get("obj_edit_time", "") or "")
            if state.get(node_token) == obj_edit and obj_edit:
                return  # unchanged since last sync
            item = await self._build_item(client, node)
            if item is not None:
                async with sem:
                    await on_item(item)
            state.set(node_token, obj_edit)

        async def walk(space_id: str, parent_token: str = "") -> None:
            nodes = await self._paginate_nodes(client, space_id, parent_token)
            tasks: List[asyncio.Task] = []
            for node in nodes:
                if node.get("obj_type") in _FETCHABLE:
                    tasks.append(asyncio.create_task(handle_node(space_id, node)))
                if node.get("has_child"):
                    await walk(space_id, node["node_token"])
            if tasks:
                await asyncio.gather(*tasks)

        for resource_id in resource_ids:
            kind, _, rest = resource_id.partition(":")
            if kind == "space":
                await walk(rest)
            elif kind == "node":
                space_id, node_token = rest.split("/", 1)
                node = await self._find_node(client, space_id, node_token)
                if node is None:
                    continue
                if node.get("obj_type") in _FETCHABLE:
                    await handle_node(space_id, node)
                if node.get("has_child"):
                    await walk(space_id, node_token)
            else:
                raise ConnectorError(f"invalid resource id: {resource_id}")
        return state

    async def fetch_incremental(
        self,
        config: Dict[str, str],
        resource_ids: List[str],
        cursor: SyncCursor,
        on_item: ItemHandler,
    ) -> SyncCursor:
        # tree-walk with edit_time comparison is inherent to fetch_all
        return await self.fetch_all(config, resource_ids, on_item, cursor)

    # ------------------------------------------------------------ helpers
    async def _paginate_nodes(
        self, client: FeishuClient, space_id: str, parent_token: str
    ) -> List[Dict[str, Any]]:
        return await client.wiki_nodes(space_id, parent_node_token=parent_token)

    async def _find_node(
        self, client: FeishuClient, space_id: str, node_token: str
    ) -> Optional[Dict[str, Any]]:
        """Locate a node by token scanning the bare tree (small wikis OK)."""

        async def scan(parent_token: str) -> Optional[Dict[str, Any]]:
            for node in await self._paginate_nodes(client, space_id, parent_token):
                if node["node_token"] == node_token:
                    return node
                if node.get("has_child"):
                    found = await scan(node["node_token"])
                    if found:
                        return found
            return None

        return await scan("")

    async def _build_item(
        self, client: FeishuClient, node: Dict[str, Any]
    ) -> Optional[FetchedItem]:
        obj_type = node.get("obj_type")
        obj_token = node.get("obj_token", "")
        title = node.get("title") or obj_token
        common = dict(
            external_id=f"feishu:{node['node_token']}",
            title=title,
            source_url=f"https://feishu.cn/wiki/{node['node_token']}",
            updated_at=None,
            metadata={"obj_type": obj_type or "", "obj_token": obj_token},
        )
        try:
            if obj_type == "docx":
                try:
                    blocks = await client.docx_blocks(obj_token)
                    content = feishu_blocks_to_markdown(blocks)
                except FeishuAPIError as exc:
                    logger.warning(f"docx blocks failed ({exc}); fallback raw_content")
                    content = await client.docx_raw_content(obj_token)
                return FetchedItem(content=content, content_format="markdown", **common)
            if obj_type == "sheet":
                # export csv → markdown table is P1; register with link for now
                return FetchedItem(
                    content=f"[电子表格：{title}](https://feishu.cn/wiki/{node['node_token']})",
                    content_format="markdown",
                    **common,
                )
            if obj_type == "bitable":
                return FetchedItem(
                    content=f"[多维表格：{title}](https://feishu.cn/wiki/{node['node_token']})",
                    content_format="markdown",
                    **common,
                )
        except FeishuAPIError as exc:
            logger.error(f"feishu fetch node {node['node_token']} failed: {exc}")
            return None
        return None  # doc(file) / file: binary parse is a P1 concern
