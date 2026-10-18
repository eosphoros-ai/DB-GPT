"""Feishu drive (cloud files) connector.

Simple folder-token listing: credentials come with an optional
``folder_tokens`` (comma separated) list of drive folders; the tree loads
lazily from those roots. docx files (new editor) sync via the same blocks
converter as the wiki; other types render as link placeholders.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

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
from dbgpt_ext.knowledge_source.connectors.feishu_wiki import _FETCHABLE
from dbgpt_ext.knowledge_source.converters.feishu_docx import (
    feishu_blocks_to_markdown,
)
from dbgpt_ext.knowledge_source.registry import register_source_connector

logger = logging.getLogger(__name__)


@register_source_connector
class FeishuDriveConnector(BaseKnowledgeSourceConnector):
    type = "feishu_drive"
    meta = ConnectorMeta(
        name="飞书云盘",
        icon="drive",
        description="同步飞书云盘指定文件夹中的 docx 等文档",
        auth_fields=[
            ConnectorAuthField(key="app_id", label="App ID", required=True),
            ConnectorAuthField(
                key="app_secret", label="App Secret", required=True, secret=True
            ),
            ConnectorAuthField(
                key="folder_tokens",
                label="文件夹 Token（多个用英文逗号分隔）",
                required=True,
                placeholder="fldcnXXXXXXXX,fldcnYYYYYYYY",
                hint="文件夹链接末段即 token",
            ),
        ],
        supports_incremental=False,  # drive listing has no edit_time field in P0
        resource_noun="folders",
    )

    def __init__(self, client: Optional[FeishuClient] = None):
        self._client = client

    def _get_client(self, config: Dict[str, str]) -> FeishuClient:
        if self._client is not None:
            return self._client
        app_id = (config.get("app_id") or "").strip()
        app_secret = (config.get("app_secret") or "").strip()
        if not app_id or not app_secret:
            raise ConnectorError("app_id / app_secret are required")
        return FeishuClient(app_id, app_secret)

    @staticmethod
    def _folder_tokens(config: Dict[str, str]) -> List[str]:
        raw = (config.get("folder_tokens") or "").strip()
        return [t.strip() for t in raw.split(",") if t.strip()]

    async def validate(self, config: Dict[str, str]) -> None:
        if not self._folder_tokens(config):
            raise ConnectorError("至少需要配置一个 folder_token")
        try:
            await self._get_client(config)._token_header()
        except FeishuAPIError as exc:
            raise ConnectorError(f"飞书验证失败：{exc}") from exc

    async def list_resources(
        self, config: Dict[str, str], parent_id: str = ""
    ) -> List[ResourceInfo]:
        client = self._get_client(config)
        if not parent_id:
            return [
                ResourceInfo(
                    external_id=f"folder:{t}",
                    title=t,
                    parent_id=None,
                    has_children=True,
                    resource_type="folder",
                )
                for t in self._folder_tokens(config)
            ]
        folder = parent_id.removeprefix("folder:")
        files = await client.drive_folder_files(folder)
        out: List[ResourceInfo] = []
        for f in files:
            ftype = f.get("type", "")
            if ftype == "folder":
                out.append(
                    ResourceInfo(
                        external_id=f"folder:{f['token']}",
                        title=f.get("name", f["token"]),
                        parent_id=parent_id,
                        has_children=True,
                        resource_type="folder",
                    )
                )
            elif ftype in _FETCHABLE:
                out.append(
                    ResourceInfo(
                        external_id=f"file:{f['token']}",
                        title=f.get("name", f["token"]),
                        parent_id=parent_id,
                        has_children=False,
                        resource_type="file",
                    )
                )
        return out

    async def _walk(
        self,
        client: FeishuClient,
        folder_token: str,
        on_item: ItemHandler,
        depth: int = 0,
    ) -> None:
        if depth > 8:
            return
        try:
            files = await client.drive_folder_files(folder_token)
        except FeishuAPIError as exc:
            logger.error(f"drive folder {folder_token} listing failed: {exc}")
            return
        subfolders: List[Dict[str, Any]] = []
        for f in files:
            if f.get("type") == "folder":
                subfolders.append(f)
                continue
            if f.get("type") == "docx":
                try:
                    blocks = await client.docx_blocks(f["token"])
                    await on_item(
                        FetchedItem(
                            external_id=f"feishu-drive:{f['token']}",
                            title=f.get("name") or f["token"],
                            content=feishu_blocks_to_markdown(blocks),
                            content_format="markdown",
                            source_url=f"https://feishu.cn/file/{f['token']}",
                            metadata={"obj_type": "docx"},
                        )
                    )
                except FeishuAPIError as exc:
                    logger.error(f"drive docx {f['token']} fetch failed: {exc}")
            else:
                await on_item(
                    FetchedItem(
                        external_id=f"feishu-drive:{f['token']}",
                        title=f.get("name") or f["token"],
                        content=f"[飞书云盘文件：{f.get('name', f['token'])}]"
                        f"(https://feishu.cn/file/{f['token']})",
                        content_format="markdown",
                        source_url=f"https://feishu.cn/file/{f['token']}",
                        metadata={"obj_type": f.get("type", "file")},
                    )
                )
        for folder in subfolders:
            await self._walk(client, folder["token"], on_item, depth + 1)

    async def fetch_all(
        self,
        config: Dict[str, str],
        resource_ids: List[str],
        on_item: ItemHandler,
        cursor: Optional[SyncCursor] = None,
    ) -> SyncCursor:
        client = self._get_client(config)
        sem = asyncio.Semaphore(3)

        async def guarded(item: FetchedItem) -> None:
            async with sem:
                await on_item(item)

        roots = resource_ids or [f"folder:{t}" for t in self._folder_tokens(config)]
        for rid in roots:
            folder = rid.removeprefix("folder:")
            await self._walk(client, folder, guarded)
        return SyncCursor({})  # drive full re-fetch; hashing dedupes on the engine
