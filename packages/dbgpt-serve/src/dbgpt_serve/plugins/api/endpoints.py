import logging
from functools import cache
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer

from dbgpt.component import SystemApp
from dbgpt_serve.core import Result

from ..config import SERVE_SERVICE_COMPONENT_NAME, ServeConfig
from ..service.service import Service
from .schemas import SuiteEventResponse, SuiteResponse, SuiteSyncSummary

router = APIRouter()

global_system_app: Optional[SystemApp] = None
logger = logging.getLogger(__name__)


def get_service() -> Service:
    """Get the service instance."""
    return global_system_app.get_component(SERVE_SERVICE_COMPONENT_NAME, Service)


get_bearer_token = HTTPBearer(auto_error=False)


@cache
def _parse_api_keys(api_keys: str) -> List[str]:
    if not api_keys:
        return []
    return [key.strip() for key in api_keys.split(",")]


async def check_api_key(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(get_bearer_token),
    service: Service = Depends(get_service),
) -> Optional[str]:
    """Check the api key; when unset, allow all (same policy as other serves)."""
    if service.config.api_keys:
        api_keys = _parse_api_keys(service.config.api_keys)
        if auth is None or (token := auth.credentials) not in api_keys:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": {
                        "message": "",
                        "type": "invalid_request_error",
                        "param": None,
                        "code": "invalid_api_key",
                    }
                },
            )
        return token
    return None


@router.get("", response_model=Result[List[SuiteResponse]])
async def list_suites(
    workspace_id: Optional[str] = Query(None, description="instance scope"),
    service: Service = Depends(get_service),
) -> Result[List[SuiteResponse]]:
    """List installed suites (enabled first); home tabs render from here."""
    return Result.succ(service.list_suites(workspace_id=workspace_id))


@router.get("/sync", response_model=Result[SuiteSyncSummary])
@router.post("/sync", response_model=Result[SuiteSyncSummary])
async def sync_suites(
    service: Service = Depends(get_service),
) -> Result[SuiteSyncSummary]:
    """Re-scan the suites dir and upsert official packages (ops / dev helper)."""
    return Result.succ(service.sync_official_on_start())


@router.get("/{name}", response_model=Result[SuiteResponse])
async def get_suite(
    name: str,
    workspace_id: Optional[str] = Query(None),
    service: Service = Depends(get_service),
) -> Result[SuiteResponse]:
    suite = service.get(name, workspace_id=workspace_id)
    if suite is None:
        raise HTTPException(status_code=404, detail=f"suite not installed: {name}")
    return Result.succ(suite)


@router.get("/{name}/events", response_model=Result[List[SuiteEventResponse]])
async def list_suite_events(
    name: str,
    limit: int = Query(default=100, ge=1, le=500),
    service: Service = Depends(get_service),
) -> Result[List[SuiteEventResponse]]:
    """Audit trail: install/enable/disable/upgrade/switch/pin events."""
    return Result.succ(service.list_events(name, limit=limit))


@router.post("/{name}/enable", response_model=Result[SuiteResponse])
async def enable_suite(
    name: str,
    workspace_id: Optional[str] = Query(None),
    user_name: Optional[str] = Query(None),
    service: Service = Depends(get_service),
) -> Result[SuiteResponse]:
    try:
        return Result.succ(
            service.enable(name, workspace_id=workspace_id, user_name=user_name)
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{name}/disable", response_model=Result[SuiteResponse])
async def disable_suite(
    name: str,
    workspace_id: Optional[str] = Query(None),
    user_name: Optional[str] = Query(None),
    service: Service = Depends(get_service),
) -> Result[SuiteResponse]:
    try:
        return Result.succ(
            service.disable(name, workspace_id=workspace_id, user_name=user_name)
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/{name}", response_model=Result[bool])
async def uninstall_suite(
    name: str,
    user_name: Optional[str] = Query(None),
    service: Service = Depends(get_service),
) -> Result[bool]:
    """Uninstall a suite (registry row removed; package files stay on disk)."""
    try:
        service.uninstall(name, user_name=user_name)
        return Result.succ(True)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


_MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # design §5.7: zip <= 50MB


@router.post("/upload", response_model=Result[SuiteResponse])
async def upload_suite(
    file: UploadFile = File(...),
    user_name: Optional[str] = Query(None),
    service: Service = Depends(get_service),
) -> Result[SuiteResponse]:
    """Upload an enterprise suite zip (root must contain suite.yaml)."""
    from pathlib import Path

    from dbgpt_serve.plugins.loader import load_suite_dir, resolve_suites_dir

    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="only .zip packages are accepted")
    payload = await file.read()
    if len(payload) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="package exceeds 50MB limit")

    root = resolve_suites_dir(service.config.suites_dir)
    if root is None:
        raise HTTPException(status_code=500, detail="suites dir is not configured")
    import io
    import zipfile

    target: Optional[Path] = None
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        names = zf.namelist()
        if not names:
            raise HTTPException(status_code=400, detail="empty zip")
        # suite.yaml at zip root, or inside a single top-level directory
        tops = {n.split("/", 1)[0] for n in names}
        prefix = ""
        if "suite.yaml" not in names:
            candidates = [t for t in tops if f"{t}/suite.yaml" in names]
            if len(candidates) != 1:
                raise HTTPException(
                    status_code=400, detail="zip must contain suite.yaml at root"
                )
            prefix = candidates[0] + "/"
        slug = None
        with zf.open(f"{prefix}suite.yaml") as fh:
            import yaml

            manifest = yaml.safe_load(fh.read().decode("utf-8")) or {}
        slug = str(manifest.get("name") or "").strip()
        if not slug or "/" in slug or slug in (".", ".."):
            raise HTTPException(status_code=400, detail="manifest name is invalid")
        target = root / slug
        target.mkdir(parents=True, exist_ok=True)
        for member in names:
            if member.endswith("/"):
                continue
            rel = (
                member[len(prefix) :]
                if prefix and member.startswith(prefix)
                else member
            )
            if not rel:
                continue
            dest = (target / rel).resolve()
            if not str(dest).startswith(str(target.resolve())):  # zip-slip guard
                raise HTTPException(
                    status_code=400, detail=f"unsafe zip path: {member}"
                )
            dest.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, open(dest, "wb") as out:
                out.write(src.read())
    pkg = load_suite_dir(target) if target else None
    if pkg is None:
        raise HTTPException(
            status_code=400, detail="uploaded package failed validation"
        )
    owner = user_name or file.filename or "enterprise"
    return Result.succ(service.install_package(pkg, user_name=owner))


def init_endpoints(system_app: SystemApp, config: ServeConfig) -> None:
    """Initialize the endpoints."""
    global global_system_app
    system_app.register(Service, config=config)
    global_system_app = system_app
