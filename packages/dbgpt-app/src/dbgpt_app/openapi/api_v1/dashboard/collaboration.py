"""Safe, revisioned collaboration for Dashboard drafts.

This module deliberately avoids whole-document last-write-wins updates. Clients send
small JSON Patch operations against an expected revision; the server authorizes,
applies, validates, persists, and broadcasts the accepted operation.
"""

import asyncio
import copy
import hashlib
import json
import os
import secrets
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple

from pydantic import ValidationError

from .identity import dashboard_production_mode
from .lineage import enrich_schema_lineage
from .models import DashboardConflictError, DashboardOperationEntity
from .schemas import (
    DashboardAction,
    DashboardCollaborationTicket,
    DashboardOperationLogRecord,
    DashboardOperationRequest,
    DashboardOperationResponse,
    DashboardPatchOp,
    DashboardPatchOperation,
    DashboardSchemaV1,
    DashboardStatus,
    ValidationIssue,
    model_dump_compat,
    model_validate_compat,
)
from .service import (
    DashboardSchemaValidationError,
    DashboardService,
    _json_dumps,
)


class DashboardPatchError(ValueError):
    """Raised when an operation is unsafe or cannot be applied."""


_PROTECTED_EXACT_PATHS = {
    "/dashboard/id",
    "/dashboard/status",
    "/dashboard/created_at",
    "/dashboard/updated_at",
    "/metadata/conversation_id",
    "/metadata/agent",
}
_PROTECTED_SEGMENTS = {"last_execution", "refresh_time"}
_ALLOWED_ROOTS = {
    # Clients may atomically upgrade a legacy schema when an edit introduces
    # presentation fields from a newer supported version.  The fully patched
    # document is still validated before it is persisted, so unsupported or
    # incompatible version changes fail closed and roll back.
    "schema_version",
    "dashboard",
    "metric_context",
    "filters",
    "widgets",
    "layouts",
    "metadata",
}


def _decode_pointer(path: str) -> List[str]:
    if not path.startswith("/") or path == "/":
        raise DashboardPatchError("Patch paths must address a schema field.")
    parts = path[1:].split("/")
    decoded: List[str] = []
    for part in parts:
        index = 0
        value = ""
        while index < len(part):
            if part[index] != "~":
                value += part[index]
                index += 1
                continue
            if index + 1 >= len(part) or part[index + 1] not in {"0", "1"}:
                raise DashboardPatchError(
                    "Patch path contains invalid JSON Pointer escaping."
                )
            value += "~" if part[index + 1] == "0" else "/"
            index += 2
        decoded.append(value)
    return decoded


def _authorize_path(path: str, parts: List[str]) -> None:
    if parts[0] not in _ALLOWED_ROOTS:
        raise DashboardPatchError(f"Schema root '{parts[0]}' is not editable.")
    if path in _PROTECTED_EXACT_PATHS:
        raise DashboardPatchError(f"Server-managed field '{path}' cannot be patched.")
    if any(part in _PROTECTED_SEGMENTS for part in parts):
        raise DashboardPatchError(
            f"Server-managed execution field '{path}' cannot be patched."
        )
    if parts[0] == "dashboard":
        # Replacing the descriptor root could smuggle protected fields such as
        # the dashboard id, status, or data-source binding past the exact-path
        # checks above.  Data-source changes must go through a separately
        # authorized workflow; ordinary collaboration edits are presentation
        # only.
        if len(parts) < 2 or parts[1] not in {"title", "description", "theme"}:
            raise DashboardPatchError(f"Dashboard field '{path}' is not editable.")
    if parts[0] == "metadata" and (len(parts) < 2 or parts[1] != "compatibility"):
        raise DashboardPatchError(f"Metadata field '{path}' is not editable.")


def _list_index(value: str, length: int, *, allow_end: bool) -> int:
    if value == "-" and allow_end:
        return length
    if not value.isdigit():
        raise DashboardPatchError(f"List index '{value}' is invalid.")
    index = int(value)
    maximum = length if allow_end else length - 1
    if index < 0 or index > maximum:
        raise DashboardPatchError(f"List index {index} is out of bounds.")
    return index


def _resolve_parent(document: Any, parts: List[str]) -> Tuple[Any, str]:
    current = document
    for part in parts[:-1]:
        if isinstance(current, dict):
            if part not in current:
                raise DashboardPatchError(
                    f"Patch parent '/{'/'.join(parts[:-1])}' does not exist."
                )
            current = current[part]
        elif isinstance(current, list):
            current = current[_list_index(part, len(current), allow_end=False)]
        else:
            raise DashboardPatchError("Patch path traverses a scalar value.")
    return current, parts[-1]


def apply_dashboard_patch(
    document: Dict[str, Any], operations: List[DashboardPatchOperation]
) -> Dict[str, Any]:
    """Apply a constrained RFC 6902 subset to a defensive copy."""

    result = copy.deepcopy(document)
    for operation in operations:
        parts = _decode_pointer(operation.path)
        _authorize_path(operation.path, parts)
        parent, key = _resolve_parent(result, parts)
        if isinstance(parent, dict):
            exists = key in parent
            if operation.op == DashboardPatchOp.REMOVE:
                if not exists:
                    raise DashboardPatchError(
                        f"Patch target '{operation.path}' does not exist."
                    )
                del parent[key]
            elif operation.op == DashboardPatchOp.REPLACE:
                if not exists:
                    raise DashboardPatchError(
                        f"Patch target '{operation.path}' does not exist."
                    )
                parent[key] = copy.deepcopy(operation.value)
            else:
                parent[key] = copy.deepcopy(operation.value)
        elif isinstance(parent, list):
            if operation.op == DashboardPatchOp.ADD:
                parent.insert(
                    _list_index(key, len(parent), allow_end=True),
                    copy.deepcopy(operation.value),
                )
            else:
                index = _list_index(key, len(parent), allow_end=False)
                if operation.op == DashboardPatchOp.REMOVE:
                    parent.pop(index)
                else:
                    parent[index] = copy.deepcopy(operation.value)
        else:
            raise DashboardPatchError("Patch target parent is not a collection.")
    return result


def _validation_issues(exc: ValidationError) -> List[ValidationIssue]:
    return [
        ValidationIssue(
            path=".".join(str(part) for part in item.get("loc", [])),
            code=str(item.get("type", "invalid_schema")),
            message=str(item.get("msg", "Invalid schema value.")),
        )
        for item in exc.errors()
    ]


class DashboardCollaborationService:
    """Revisioned patch service shared by REST and WebSocket transports."""

    def __init__(self, dashboard_service: Optional[DashboardService] = None) -> None:
        self.dashboard_service = dashboard_service or DashboardService()

    @staticmethod
    def _to_operation(entity: DashboardOperationEntity) -> DashboardOperationLogRecord:
        return DashboardOperationLogRecord(
            dashboard_id=entity.dashboard_id,
            operation_id=entity.operation_id,
            client_id=entity.client_id,
            actor_id=entity.actor_id,
            base_revision=entity.base_revision,
            applied_revision=entity.applied_revision,
            operations=[
                model_validate_compat(DashboardPatchOperation, item)
                for item in json.loads(entity.patch_json)
            ],
            created_at=entity.gmt_created,
        )

    def apply_operation(
        self,
        dashboard_id: str,
        request: DashboardOperationRequest,
        actor_id: str,
        *,
        promote_to_asset: Optional[bool] = None,
        version_source: Optional[str] = None,
    ) -> DashboardOperationResponse:
        self.dashboard_service.require_permission(
            dashboard_id, actor_id, DashboardAction.EDIT
        )
        patch_payload = [model_dump_compat(item) for item in request.operations]
        patch_json = _json_dumps(patch_payload)

        def transform(schema_json: str) -> Tuple[str, str, str, str]:
            current = json.loads(schema_json)
            patched = apply_dashboard_patch(current, request.operations)
            try:
                schema = model_validate_compat(DashboardSchemaV1, patched)
            except ValidationError as exc:
                raise DashboardSchemaValidationError(_validation_issues(exc)) from exc
            enrich_schema_lineage(schema)
            schema.dashboard.status = DashboardStatus.DRAFT
            schema.dashboard.updated_at = datetime.now()
            self.dashboard_service.require_permission(
                dashboard_id, actor_id, DashboardAction.QUERY, schema
            )
            validation = self.dashboard_service.validate_schema(
                schema, execute_queries=False
            )
            if not validation.valid:
                raise DashboardSchemaValidationError(validation.issues)
            return (
                self.dashboard_service._serialize_schema(schema),
                schema.dashboard.title,
                schema.dashboard.description,
                schema.dashboard.data_source_id,
            )

        dashboard, operation, replayed = self.dashboard_service.dao.apply_operation(
            dashboard_id,
            request.expected_revision,
            operation_id=request.operation_id,
            client_id=request.client_id,
            actor_id=actor_id,
            patch_json=patch_json,
            transform=transform,
            promote_to_asset=(
                request.promote_to_asset
                if promote_to_asset is None
                else promote_to_asset
            ),
            version_source=version_source,
        )
        if (
            operation.actor_id != actor_id
            or operation.client_id != request.client_id
            or operation.patch_json != patch_json
        ):
            raise DashboardConflictError(
                "The operation id was already used for a different edit."
            )
        if not replayed:
            self.dashboard_service.record_audit(
                dashboard_id,
                actor_id,
                "collaboration.operation.applied",
                target_type="operation",
                target_id=request.operation_id,
                details={
                    "client_id": request.client_id,
                    "base_revision": request.expected_revision,
                    "applied_revision": operation.applied_revision,
                    "operation_count": len(request.operations),
                },
            )
        return DashboardOperationResponse(
            dashboard=self.dashboard_service._to_record(dashboard),
            operation=self._to_operation(operation),
            replayed=replayed,
        )

    def list_operations(
        self,
        dashboard_id: str,
        actor_id: str,
        *,
        after_revision: int = 0,
        limit: int = 200,
    ) -> List[DashboardOperationLogRecord]:
        self.dashboard_service.require_permission(
            dashboard_id, actor_id, DashboardAction.VIEW
        )
        return [
            self._to_operation(item)
            for item in self.dashboard_service.dao.list_operations(
                dashboard_id, after_revision=after_revision, limit=limit
            )
        ]


@dataclass(frozen=True)
class CollaborationClaim:
    dashboard_id: str
    actor_id: str
    client_id: str
    expires_at_epoch: float


class DashboardTicketStore(Protocol):
    """Shared one-time ticket contract for WebSocket authentication."""

    def issue(
        self, dashboard_id: str, actor_id: str, client_id: str
    ) -> DashboardCollaborationTicket: ...

    def consume(self, ticket: str, dashboard_id: str) -> CollaborationClaim: ...


class InMemoryDashboardTicketStore:
    """Thread-safe, one-time, short-lived WebSocket ticket store."""

    def __init__(
        self,
        *,
        ttl_seconds: int = 60,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.ttl_seconds = ttl_seconds
        self._clock = clock
        self._claims: Dict[str, CollaborationClaim] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _digest(ticket: str) -> str:
        return hashlib.sha256(ticket.encode("utf-8")).hexdigest()

    def issue(
        self, dashboard_id: str, actor_id: str, client_id: str
    ) -> DashboardCollaborationTicket:
        ticket = secrets.token_urlsafe(32)
        expires_epoch = self._clock() + self.ttl_seconds
        claim = CollaborationClaim(
            dashboard_id=dashboard_id,
            actor_id=actor_id,
            client_id=client_id,
            expires_at_epoch=expires_epoch,
        )
        with self._lock:
            now = self._clock()
            self._claims = {
                key: value
                for key, value in self._claims.items()
                if value.expires_at_epoch > now
            }
            self._claims[self._digest(ticket)] = claim
        return DashboardCollaborationTicket(
            ticket=ticket,
            websocket_path=f"/api/v1/dashboards/{dashboard_id}/collaborate",
            expires_at=datetime.fromtimestamp(expires_epoch),
        )

    def consume(self, ticket: str, dashboard_id: str) -> CollaborationClaim:
        digest = self._digest(ticket)
        with self._lock:
            claim = self._claims.pop(digest, None)
        if claim is None:
            raise DashboardPatchError(
                "Collaboration ticket is invalid or already used."
            )
        if claim.expires_at_epoch <= self._clock():
            raise DashboardPatchError("Collaboration ticket has expired.")
        if claim.dashboard_id != dashboard_id:
            raise DashboardPatchError(
                "Collaboration ticket belongs to another dashboard."
            )
        return claim


# Keep the v2.4 public name while making the storage boundary explicit.
CollaborationTicketStore = InMemoryDashboardTicketStore


class RedisDashboardTicketStore:
    """Cross-process ticket store using Redis TTL and atomic consume."""

    _CONSUME_SCRIPT = """
    local value = redis.call('GET', KEYS[1])
    if value then
      redis.call('DEL', KEYS[1])
    end
    return value
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        *,
        client: Any = None,
        ttl_seconds: int = 60,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if client is None:
            if not redis_url:
                raise ValueError("A Redis URL or client is required.")
            try:
                from redis import Redis
            except ImportError as exc:  # pragma: no cover - optional adapter
                raise RuntimeError(
                    "Redis collaboration requires the optional 'redis' package."
                ) from exc
            client = Redis.from_url(redis_url, decode_responses=True)
        self._redis = client
        self.ttl_seconds = ttl_seconds
        self._clock = clock

    @staticmethod
    def _digest(ticket: str) -> str:
        return hashlib.sha256(ticket.encode("utf-8")).hexdigest()

    @classmethod
    def _key(cls, ticket: str) -> str:
        return f"dbgpt:dashboard:ticket:{cls._digest(ticket)}"

    def issue(
        self, dashboard_id: str, actor_id: str, client_id: str
    ) -> DashboardCollaborationTicket:
        expires_epoch = self._clock() + self.ttl_seconds
        payload = json.dumps(
            {
                "dashboard_id": dashboard_id,
                "actor_id": actor_id,
                "client_id": client_id,
                "expires_at_epoch": expires_epoch,
            },
            separators=(",", ":"),
        )
        for _ in range(3):
            ticket = secrets.token_urlsafe(32)
            if self._redis.set(
                self._key(ticket), payload, ex=self.ttl_seconds, nx=True
            ):
                return DashboardCollaborationTicket(
                    ticket=ticket,
                    websocket_path=f"/api/v1/dashboards/{dashboard_id}/collaborate",
                    expires_at=datetime.fromtimestamp(expires_epoch),
                )
        raise RuntimeError("Unable to allocate a unique collaboration ticket.")

    def consume(self, ticket: str, dashboard_id: str) -> CollaborationClaim:
        payload = self._redis.eval(self._CONSUME_SCRIPT, 1, self._key(ticket))
        if payload is None:
            raise DashboardPatchError(
                "Collaboration ticket is invalid or already used."
            )
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        raw = json.loads(payload)
        claim = CollaborationClaim(**raw)
        if claim.expires_at_epoch <= self._clock():
            raise DashboardPatchError("Collaboration ticket has expired.")
        if claim.dashboard_id != dashboard_id:
            raise DashboardPatchError(
                "Collaboration ticket belongs to another dashboard."
            )
        return claim

    def close(self) -> None:
        close = getattr(self._redis, "close", None)
        if callable(close):
            close()


def create_collaboration_ticket_store(
    redis_url: Optional[str] = None, *, production_mode: Optional[bool] = None
) -> DashboardTicketStore:
    redis_url = redis_url or os.getenv("DBGPT_DASHBOARD_COLLAB_REDIS_URL")
    if redis_url:
        return RedisDashboardTicketStore(redis_url)
    if production_mode is None:
        production_mode = dashboard_production_mode()
    if production_mode:
        raise RuntimeError(
            "Dashboard production collaboration requires "
            "DBGPT_DASHBOARD_COLLAB_REDIS_URL."
        )
    return InMemoryDashboardTicketStore()


@dataclass
class _Connection:
    websocket: Any
    actor_id: str
    client_id: str


class DashboardCollaborationHub:
    """In-process WebSocket fan-out with an optional Redis cross-worker bridge."""

    def __init__(self, redis_url: Optional[str] = None) -> None:
        self._connections: Dict[str, Dict[str, _Connection]] = {}
        self._lock = asyncio.Lock()
        self._instance_id = uuid.uuid4().hex
        self._redis_url = redis_url
        self._redis = None
        self._redis_listener: Optional[asyncio.Task] = None

    async def _ensure_redis(self) -> None:
        if not self._redis_url or self._redis is not None:
            return
        try:
            from redis.asyncio import from_url
        except ImportError as exc:  # pragma: no cover - optional production adapter
            raise RuntimeError(
                "Redis collaboration requires the optional 'redis' package."
            ) from exc
        self._redis = from_url(self._redis_url, decode_responses=True)
        self._redis_listener = asyncio.create_task(self._listen_redis())

    async def _listen_redis(self) -> None:  # pragma: no cover - Redis integration
        retry_seconds = 0.25
        while True:
            pubsub = None
            try:
                pubsub = self._redis.pubsub()
                await pubsub.psubscribe("dbgpt:dashboard:collaboration:*")
                retry_seconds = 0.25
                async for item in pubsub.listen():
                    if item.get("type") != "pmessage":
                        continue
                    payload = json.loads(item["data"])
                    if payload.get("origin") == self._instance_id:
                        continue
                    dashboard_id = item["channel"].rsplit(":", 1)[-1]
                    await self._broadcast_local(dashboard_id, payload["message"])
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(retry_seconds)
                retry_seconds = min(retry_seconds * 2, 5.0)
            finally:
                if pubsub is not None:
                    close = getattr(pubsub, "aclose", None) or getattr(
                        pubsub, "close", None
                    )
                    if callable(close):
                        result = close()
                        if asyncio.iscoroutine(result):
                            await result

    async def connect(
        self, dashboard_id: str, websocket: Any, actor_id: str, client_id: str
    ) -> str:
        await self._ensure_redis()
        connection_id = uuid.uuid4().hex
        async with self._lock:
            self._connections.setdefault(dashboard_id, {})[connection_id] = _Connection(
                websocket=websocket, actor_id=actor_id, client_id=client_id
            )
        return connection_id

    async def disconnect(self, dashboard_id: str, connection_id: str) -> None:
        async with self._lock:
            bucket = self._connections.get(dashboard_id, {})
            bucket.pop(connection_id, None)
            if not bucket:
                self._connections.pop(dashboard_id, None)

    async def presence(self, dashboard_id: str) -> List[Dict[str, str]]:
        async with self._lock:
            values = list(self._connections.get(dashboard_id, {}).values())
        unique = {(item.actor_id, item.client_id) for item in values}
        return [
            {"actor_id": actor_id, "client_id": client_id}
            for actor_id, client_id in sorted(unique)
        ]

    async def _broadcast_local(
        self, dashboard_id: str, message: Dict[str, Any]
    ) -> None:
        async with self._lock:
            items = list(self._connections.get(dashboard_id, {}).items())
        stale: List[str] = []
        for connection_id, connection in items:
            try:
                await connection.websocket.send_json(message)
            except Exception:
                stale.append(connection_id)
        for connection_id in stale:
            await self.disconnect(dashboard_id, connection_id)

    async def broadcast(self, dashboard_id: str, message: Dict[str, Any]) -> None:
        await self._broadcast_local(dashboard_id, message)
        if self._redis is not None:  # pragma: no cover - Redis integration
            await self._redis.publish(
                f"dbgpt:dashboard:collaboration:{dashboard_id}",
                json.dumps(
                    {"origin": self._instance_id, "message": message},
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            )

    async def close(self) -> None:
        if self._redis_listener is not None:
            self._redis_listener.cancel()
            await asyncio.gather(self._redis_listener, return_exceptions=True)
            self._redis_listener = None
        if self._redis is not None:
            close = getattr(self._redis, "aclose", None) or getattr(
                self._redis, "close", None
            )
            if callable(close):
                result = close()
                if asyncio.iscoroutine(result):
                    await result
            self._redis = None


ticket_store = create_collaboration_ticket_store()
collaboration_hub = DashboardCollaborationHub(
    os.getenv("DBGPT_DASHBOARD_COLLAB_REDIS_URL")
)
