"""Yuque connector — flat repo (book) listing, markdown-first content.

Endpoints (aligned with WeKnora's yuque client):
- GET /api/v2/user                          → current user (validate)
- GET /api/v2/users/{login}/repos           → personal books
- GET /api/v2/users/{id}/groups             → joined groups
- GET /api/v2/groups/{login}/repos          → group books
- GET /api/v2/repos/{book_id}/docs          → doc list
- GET /api/v2/repos/docs/{doc_id}           → detail (body: markdown when
  format is "markdown"/"lake"; other formats skipped defensively)

Auth:``X-Auth-Token`` header. Docs are fetched per-book; cursor snapshots
{doc_id: content_updated_at}.
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
from dbgpt_ext.knowledge_source.clients.http import RateLimitedClient
from dbgpt_ext.knowledge_source.registry import register_source_connector

logger = logging.getLogger(__name__)

YUQUE_BASE = "https://www.yuque.com/api/v2"


class YuqueConnector(BaseKnowledgeSourceConnector):
    type = "yuque"
    meta = ConnectorMeta(
        name="语雀",
        icon="yuque",
        description="同步语雀知识库（个人 + 团队仓库）中的文档",
        auth_fields=[
            ConnectorAuthField(
                key="token",
                label="语雀 Token",
                required=True,
                secret=True,
                hint="语雀「个人设置 → Token（开发者）」新建，勾选仓库读取权限",
            ),
        ],
        supports_incremental=True,
        resource_noun="repos",
    )

    def __init__(self, http: Optional[RateLimitedClient] = None):
        self._http = http or RateLimitedClient(concurrency=2)

    # ------------------------------------------------------------- plumbing
    async def _get(self, token: str, path: str, params: Optional[Dict] = None) -> Any:
        data = await self._http.get_json(
            f"{YUQUE_BASE}{path}",
            headers={"X-Auth-Token": token},
            params=params,
        )
        return data.get("data") if isinstance(data, dict) else data

    async def _paged_list(
        self, token: str, path: str, item_key: str = ""
    ) -> List[Dict[str, Any]]:
        """Page through a Yuque list endpoint (page/per_page, max 100)."""
        out: List[Dict[str, Any]] = []
        page = 1
        while True:
            batch = (
                await self._get(
                    token,
                    path,
                    {"page": page, "per_page": 100},
                )
                or []
            )
            out.extend([b for b in batch if isinstance(b, dict)])
            if len(batch) < 100 or page >= 50:  # 50页 = 5000 项保护上限
                break
            page += 1
        return out

    # ------------------------------------------------------------- validate
    async def validate(self, config: Dict[str, str]) -> None:
        token = (config.get("token") or "").strip()
        if not token:
            raise ConnectorError("token 不能为空")
        try:
            user = await self._get(token, "/user")
        except RuntimeError as exc:
            msg = str(exc)
            if "CERTIFICATE_VERIFY_FAILED" in msg or "SSL" in msg:
                raise ConnectorError(
                    "HTTPS 证书校验失败（公司代理/网关拦截所致）。"
                    "设置 env DB_GPT_KS_CA_BUNDLE=企业根证书路径，"
                    "或临时 DB_GPT_KS_INSECURE=1 后重启服务重试"
                ) from exc
            if "HTTP 429" in msg:
                raise ConnectorError(
                    "语雀限流（429）：请稍等 1-2 分钟再重试；"
                    "若持续出现，检查该 Token 是否被语雀平台限流或与"
                    "其他脚本共用"
                ) from exc
            raise
        if not user or not user.get("id"):
            raise ConnectorError("token 验证失败：未获取到当前用户")

    # ------------------------------------------------------- list_resources
    async def list_resources(
        self, config: Dict[str, str], parent_id: str = ""
    ) -> List[ResourceInfo]:
        if parent_id:
            return []  # flat list, per WeKnora
        token = (config.get("token") or "").strip()
        me = await self._get(token, "/user")
        repos: Dict[int, Dict[str, Any]] = {}

        async def collect(base_path: str) -> None:
            try:
                for r in await self._paged_list(token, base_path):
                    repos[r["id"]] = r
            except Exception as exc:
                logger.warning(f"yuque collect {base_path} failed: {exc}")

        if me.get("type") == "Group":
            # team token: list the group's own repos directly
            await collect(f"/groups/{me['login']}/repos")
        else:
            await collect(f"/users/{me['login']}/repos")
            groups = await self._get(token, f"/users/{me['id']}/groups") or []
            for g in groups:
                await collect(f"/groups/{g['login']}/repos")

        items: List[ResourceInfo] = []
        for r in sorted(repos.values(), key=lambda x: x.get("id", 0)):
            owner = r.get("user", {}).get("name") or ""
            suffix = f"（{owner}）" if owner else ""
            items.append(
                ResourceInfo(
                    external_id=f"repo:{r.get('namespace') or r['id']}",
                    title=(r.get("name") or r.get("slug") or "") + suffix,
                    parent_id=None,
                    has_children=False,
                    resource_type="repo",
                )
            )
        return items

    # ---------------------------------------------------------------- fetch
    async def fetch_all(
        self,
        config: Dict[str, str],
        resource_ids: List[str],
        on_item: ItemHandler,
        cursor: Optional[SyncCursor] = None,
    ) -> SyncCursor:
        token = (config.get("token") or "").strip()
        state = SyncCursor.from_dict(cursor.to_dict() if cursor else {})
        sem = asyncio.Semaphore(2)

        for resource_id in resource_ids:
            namespace_or_id = resource_id.removeprefix("repo:")
            # docs list needs the numeric book id
            book_id = namespace_or_id
            if "/" in namespace_or_id:  # namespace "user/slug" → resolve via list
                docs0 = await self._get(
                    token,
                    f"/repos/{namespace_or_id}/docs",
                    {"per_page": 100},
                )
                if docs0:
                    book_id = str(docs0[0].get("book_id", namespace_or_id))
                else:
                    continue
            docs = (
                await self._get(token, f"/repos/{book_id}/docs", {"per_page": 100})
                or []
            )
            for d in docs:
                doc_id = str(d.get("id"))
                updated = str(d.get("content_updated_at") or "")
                if state.get(doc_id) == updated and updated:
                    continue
                detail = await self._get(token, f"/repos/docs/{doc_id}")
                body, fmt = (
                    (detail or {}).get("body") or "",
                    (detail or {}).get("format", ""),
                )
                if fmt and fmt not in ("markdown", "lake"):
                    logger.info(f"yuque doc {doc_id} skipped: format={fmt}")
                    state.set(doc_id, updated)
                    continue
                if not body:
                    state.set(doc_id, updated)
                    continue
                book_ns = (detail or {}).get("book", {}).get(
                    "namespace"
                ) or namespace_or_id
                slug = (detail or {}).get("slug") or doc_id
                item = FetchedItem(
                    external_id=f"yuque:{doc_id}",
                    title=(detail or {}).get("title") or d.get("title") or str(doc_id),
                    content=body,
                    content_format="markdown",
                    source_url=f"https://www.yuque.com/{book_ns}/{slug}",
                    updated_at=updated or None,
                    metadata={"book": book_ns, "format": fmt or "markdown"},
                )
                async with sem:
                    await on_item(item)
                state.set(doc_id, updated)
        return state

    async def fetch_incremental(
        self,
        config: Dict[str, str],
        resource_ids: List[str],
        cursor: SyncCursor,
        on_item: ItemHandler,
    ) -> SyncCursor:
        # content_updated_at comparison is inherent to fetch_all
        return await self.fetch_all(config, resource_ids, on_item, cursor)


register_source_connector(YuqueConnector)
