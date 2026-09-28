"""Feishu (Lark) OpenAPI client.

Covers the knowledge-base sync surface: wiki space/node listing, docx
blocks/raw content, sheet & bitable export, drive folder listing.
Tenant access token is cached until 5 minutes before expiry.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional

from dbgpt_ext.knowledge_source.clients.http import RateLimitedClient

FEISHU_BASE = "https://open.feishu.cn/open-apis"

# 频控/错误码：命中则退避重试（app 频控 99991400/99991401、资源频控 230020）
_RETRY_CODES = {99991400, 99991401, 230020}


class FeishuAPIError(Exception):
    def __init__(self, code: int, msg: str):
        super().__init__(f"feishu api error {code}: {msg}")
        self.code = code
        self.msg = msg


class FeishuClient:
    def __init__(self, app_id: str, app_secret: str, concurrency: int = 3):
        self._app_id = app_id
        self._app_secret = app_secret
        self._http = RateLimitedClient(concurrency=concurrency)
        self._token: Optional[str] = None
        self._token_expire_at: float = 0.0
        self._token_lock = asyncio.Lock()

    # ---------------------------------------------------------------- auth
    async def _token_header(self) -> Dict[str, str]:
        async with self._token_lock:
            if self._token and time.time() < self._token_expire_at:
                return {"Authorization": f"Bearer {self._token}"}
            data = await self._http.post_json(
                f"{FEISHU_BASE}/auth/v3/tenant_access_token/internal",
                payload={"app_id": self._app_id, "app_secret": self._app_secret},
            )
            if data.get("code") not in (0, None):
                raise FeishuAPIError(int(data.get("code", -1)), str(data.get("msg")))
            self._token = data["tenant_access_token"]
            # expire(秒) 提前 5 分钟过期
            self._token_expire_at = time.time() + max(
                60, int(data.get("expire", 7200)) - 300
            )
            return {"Authorization": f"Bearer {self._token}"}

    async def _call(self, method: str, path: str, **kw) -> Dict[str, Any]:
        headers = await self._token_header()
        # 顶层业务码重试（频控类）
        for attempt in range(1, 4):
            data = await self._http.request_json(
                method,
                f"{FEISHU_BASE}{path}",
                headers=headers,
                payload=kw.get("payload"),
                params=kw.get("params"),
            )
            code = int(data.get("code", 0) or 0)
            if (
                code == 0
                or data.get("success") is True
                or ("data" in data and code in (0,))
            ):
                return data.get("data", data)
            if code in _RETRY_CODES and attempt < 3:
                await asyncio.sleep(2**attempt)
                continue
            raise FeishuAPIError(code, str(data.get("msg")))
        raise FeishuAPIError(-1, "unreachable")

    # ---------------------------------------------------------------- wiki
    async def wiki_spaces(self, page_token: str = "") -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"page_size": 50}
        if page_token:
            params["page_token"] = page_token
        data = await self._call("GET", "/wiki/v2/spaces", params=params)
        return self._collect(data, "items")

    async def wiki_nodes(
        self, space_id: str, parent_node_token: str = "", page_token: str = ""
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"page_size": 50}
        if parent_node_token:
            params["parent_node_token"] = parent_node_token
        if page_token:
            params["page_token"] = page_token
        data = await self._call(
            "GET", f"/wiki/v2/spaces/{space_id}/nodes", params=params
        )
        return self._collect(data, "items")

    # ---------------------------------------------------------------- docx
    async def docx_blocks(self, doc_token: str) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        page_token = ""
        while True:
            params: Dict[str, Any] = {"page_size": 500}
            if page_token:
                params["page_token"] = page_token
            data = await self._call(
                "GET", f"/docx/v1/documents/{doc_token}/blocks", params=params
            )
            items.extend(data.get("items", []))
            if not data.get("has_more"):
                break
            page_token = data.get("page_token", "")
        return items

    async def docx_raw_content(self, doc_token: str) -> str:
        data = await self._call("GET", f"/docx/v1/documents/{doc_token}/raw_content")
        return str(data.get("content", "") or "")

    # ------------------------------------------------------------- bitable
    async def bitable_tables(self, app_token: str) -> List[Dict[str, Any]]:
        data = await self._call(
            "GET", f"/bitable/v1/apps/{app_token}/tables", params={"page_size": 100}
        )
        return self._collect(data, "items")

    # -------------------------------------------------------------- export
    async def export_file(
        self, token: str, file_extension: str, obj_type: str
    ) -> Optional[bytes]:
        """Submit an export task, poll for the ticket, download the file."""
        ticket = await self._create_export(token, file_extension, obj_type)
        file_token = await self._poll_export(ticket)
        if not file_token:
            return None
        headers = await self._token_header()
        import httpx

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(
                f"{FEISHU_BASE}/drive/v1/medias/{file_token}/download",
                headers=headers,
            )
            resp.raise_for_status()
            return resp.content

    async def _create_export(
        self, token: str, file_extension: str, obj_type: str
    ) -> str:
        data = await self._call(
            "POST",
            "/drive/v1/export_tasks",
            payload={
                "file_extension": file_extension,
                "token": token,
                "type": obj_type,
            },
        )
        return str(data.get("ticket", ""))

    async def _poll_export(self, ticket: str, max_wait: float = 60) -> Optional[str]:
        waited = 0.0
        interval = 1.5
        while waited < max_wait:
            result = (await self._call("GET", f"/drive/v1/export_tasks/{ticket}")).get(
                "result", {}
            )
            status = int(result.get("job_status", 0) or 0)
            if status == 0:  # success
                return result.get("file_token")
            if status in (1, 2):  # pending / processing
                await asyncio.sleep(interval)
                waited += interval
                interval = min(interval * 1.5, 5.0)
                continue
            raise FeishuAPIError(-1, f"export job failed, status={status}")
        return None  # timeout: caller may retry later

    # -------------------------------------------------------------- drive
    async def drive_folder_files(self, folder_token: str) -> List[Dict[str, Any]]:
        data = await self._call(
            "GET",
            "/drive/v1/files",
            params={"folder_token": folder_token, "page_size": 200},
        )
        return self._collect(data, "files")

    # --------------------------------------------------------------- util
    @staticmethod
    def _collect(data: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
        if isinstance(data, dict):
            return list(data.get(key, []) or [])
        return []
