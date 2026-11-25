import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any, List, Optional, Set, Tuple

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response
from fastapi.security.http import HTTPAuthorizationCredentials
from starlette.concurrency import run_in_threadpool

from dbgpt.configs.model_config import PILOT_PATH
from dbgpt_app.openapi.api_v1.dashboard import identity as dashboard_identity
from dbgpt_app.openapi.api_v1.dashboard.identity import (
    DashboardIdentityError,
    DBGPTUserIdentityProvider,
    dashboard_production_mode,
)
from dbgpt_app.openapi.api_v1.feedback.feed_back_db import ChatFeedBackDao
from dbgpt_app.openapi.api_v1.feedback.feed_back_model import FeedBackBody
from dbgpt_app.openapi.api_view_model import Result
from dbgpt_serve.feedback.api import endpoints as feedback_serve_endpoints
from dbgpt_serve.feedback.config import SERVE_SERVICE_COMPONENT_NAME
from dbgpt_serve.feedback.service.service import Service as FeedbackService
from dbgpt_serve.utils.auth import UserRequest

TRUSTED_GATEWAY_SECRET_ENV = "DBGPT_TRUSTED_GATEWAY_SECRET"
TRUSTED_GATEWAY_SIG_HEADER = "x-dbgpt-gateway-signature"
AUTH_USER_HEADER = "x-authenticated-user"
DEV_FALLBACK_ENV = "DBGPT_FEEDBACK_ALLOW_DEV_FALLBACK"
SESSION_SECRET_ENV = "DBGPT_FEEDBACK_SESSION_SECRET"
SESSION_KEY_FILE_ENV = "DBGPT_FEEDBACK_SESSION_KEY_FILE"
DEFAULT_SESSION_KEY_FILE = str(Path(PILOT_PATH) / "meta_data" / "feedback-session.key")
SESSION_COOKIE_NAME = "dbgpt_feedback_session"
SESSION_RECOVERY_HEADER = "x-dbgpt-feedback-session"
SESSION_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 400
_SESSION_DOMAIN_PREFIX = "dbgpt-feedback-session-v1:"


@dataclass(frozen=True)
class _ApiKeyAuthResult:
    authenticated: bool = False
    bound_owner: Optional[str] = None


@dataclass(frozen=True)
class _ResolvedFeedbackActor:
    actor_id: str
    is_session_actor: bool = False
    can_reclaim_session_row: bool = False


def compute_gateway_signature(secret: str, actor_id: str) -> str:
    """Compute the hex HMAC-SHA256 attestation for ``actor_id``."""
    return hmac.new(
        secret.encode("utf-8"),
        actor_id.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _session_signing_secret() -> str:
    """Return a persistent signing key shared across restarts and worker processes."""
    configured = os.getenv(SESSION_SECRET_ENV, "").strip()
    if configured:
        return configured
    key_path = Path(
        os.getenv(SESSION_KEY_FILE_ENV, DEFAULT_SESSION_KEY_FILE).strip()
        or DEFAULT_SESSION_KEY_FILE
    )
    try:
        key_path.parent.mkdir(parents=True, exist_ok=True)
        if not key_path.exists():
            tmp_path = key_path.with_name(f"{key_path.name}.{secrets.token_hex(8)}.tmp")
            try:
                with os.fdopen(
                    os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600),
                    "wb",
                ) as handle:
                    handle.write(secrets.token_hex(32).encode("ascii"))
                    handle.flush()
                    os.fsync(handle.fileno())
                try:
                    os.link(tmp_path, key_path)
                except FileExistsError:
                    pass
            finally:
                tmp_path.unlink(missing_ok=True)
        persisted = key_path.read_text(encoding="ascii").strip()
    except (OSError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Feedback session signing key is unavailable; configure "
                f"{SESSION_SECRET_ENV} or a writable {SESSION_KEY_FILE_ENV}."
            ),
        ) from exc
    if len(persisted) < 32:
        raise HTTPException(
            status_code=503,
            detail="Feedback session key file must be at least 32 ASCII chars.",
        )
    return persisted


def _compute_session_signature(secret: str, actor_id: str) -> str:
    """Compute a domain-separated HMAC-SHA256 signature for session cookies."""
    return hmac.new(
        secret.encode("utf-8"),
        f"{_SESSION_DOMAIN_PREFIX}{actor_id}".encode("ascii"),
        hashlib.sha256,
    ).hexdigest()


def _format_session_token(actor_id: str) -> str:
    sig = _compute_session_signature(_session_signing_secret(), actor_id)
    return f"{actor_id}.{sig}"


def _mint_session_cookie_value() -> str:
    return _format_session_token(f"session:{secrets.token_hex(16)}")


def _verify_signed_session_token(raw_token: Optional[str]) -> Optional[str]:
    if not raw_token or not raw_token.isascii():
        return None
    actor_part, sep, sig_part = raw_token.strip().partition(".")
    if sep != "." or not actor_part.startswith("session:") or not sig_part:
        return None
    session_hex = actor_part[len("session:") :]
    if len(session_hex) < 16 or any(ch not in "0123456789abcdef" for ch in session_hex):
        return None
    expected_sig = _compute_session_signature(_session_signing_secret(), actor_part)
    if not hmac.compare_digest(
        sig_part.lower().encode("ascii"), expected_sig.encode("ascii")
    ):
        return None
    return actor_part


def _verify_session_cookie(request: Request) -> Optional[str]:
    cookie_actor = _verify_signed_session_token(
        request.cookies.get(SESSION_COOKIE_NAME)
    )
    raw_recovery = _single_header(request, SESSION_RECOVERY_HEADER)
    if raw_recovery is not None:
        recovered_actor = _verify_signed_session_token(raw_recovery)
        if recovered_actor is None:
            raise HTTPException(
                status_code=401, detail="Invalid feedback session recovery token"
            )
        if cookie_actor is not None and cookie_actor != recovered_actor:
            raise HTTPException(
                status_code=403, detail="Conflicting feedback session credentials"
            )
        return recovered_actor
    return cookie_actor


def _enforce_cookie_mutation_guards(request: Request) -> None:
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    if request.headers.get("sec-fetch-site", "").strip().lower() == "cross-site":
        raise HTTPException(
            status_code=403, detail="Cross-site feedback mutation is not allowed"
        )
    media_type = request.headers.get("content-type", "").partition(";")[0].strip()
    if media_type.lower() != "application/json":
        raise HTTPException(
            status_code=415, detail="Content-Type must be application/json"
        )


def _is_https_request(request: Request) -> bool:
    if request.url.scheme == "https":
        return True
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    first_hop = forwarded_proto.split(",")[0].strip().lower()
    return first_hop == "https"


def _feedback_cookie_path(request: Request) -> str:
    raw_path = request.url.path or "/"
    for suffix in ("/select", "/find", "/commit"):
        if raw_path.endswith(suffix):
            return raw_path[: -len(suffix)] or "/"
    return "/"


def _set_session_cookie(request: Request, response: Response, actor_id: str) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=_format_session_token(actor_id),
        max_age=SESSION_COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=_is_https_request(request),
        path=_feedback_cookie_path(request),
    )


def _parse_api_key_entries(
    raw_keys: str,
) -> Tuple[bool, List[Tuple[Optional[str], str]]]:
    """Parse comma-separated API keys supporting optional ``owner:token`` bindings."""
    entries: List[Tuple[Optional[str], str]] = []
    has_non_empty_entry = False
    for raw_item in raw_keys.split(","):
        item = raw_item.strip()
        if not item:
            continue
        has_non_empty_entry = True
        if ":" in item:
            owner_part, _, token_part = item.partition(":")
            owner = owner_part.strip()
            token = token_part.strip()
            if owner and token:
                entries.append((owner, token))
        else:
            entries.append((None, item))
    return has_non_empty_entry, entries


def _invalid_api_key_error() -> HTTPException:
    return HTTPException(
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


async def check_feedback_api_key(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(
        feedback_serve_endpoints.get_bearer_token
    ),
) -> _ApiKeyAuthResult:
    """Enforce configured feedback service API keys and extract bound principal."""
    sys_app = feedback_serve_endpoints.global_system_app
    if sys_app is None:
        return _ApiKeyAuthResult()
    service = sys_app.get_component(
        SERVE_SERVICE_COMPONENT_NAME,
        FeedbackService,
        default_component=None,
    )
    if service is None or not service.config.api_keys:
        return _ApiKeyAuthResult()
    has_configured_key, entries = _parse_api_key_entries(service.config.api_keys)
    if not has_configured_key:
        return _ApiKeyAuthResult()
    if not entries or auth is None or not auth.credentials:
        raise _invalid_api_key_error()

    provided = auth.credentials.encode("utf-8")
    matched_owners: Set[Optional[str]] = set()
    for owner, expected_token in entries:
        if hmac.compare_digest(provided, expected_token.encode("utf-8")):
            matched_owners.add(owner)
    if len(matched_owners) != 1:
        raise _invalid_api_key_error()
    bound_owner = next(iter(matched_owners))
    return _ApiKeyAuthResult(authenticated=True, bound_owner=bound_owner)


def _extract_principal_id(principal: Any) -> Optional[str]:
    if principal is None:
        return None
    if getattr(principal, "is_authenticated", True) is False:
        return None
    if isinstance(principal, str):
        return principal.strip() or None
    if isinstance(principal, UserRequest):
        if DBGPTUserIdentityProvider._is_development_fallback(principal):
            return None
        return (principal.user_id or principal.user_name or "").strip() or None
    for attr in ("user_id", "username", "identity", "display_name", "id"):
        value = getattr(principal, attr, None)
        if isinstance(value, (str, int)):
            text = str(value).strip()
            if text:
                return text
    return None


def _extract_request_principal(request: Request) -> Optional[str]:
    """Read a verified principal populated by upstream ASGI/FastAPI auth middleware."""
    for state_attr in ("authenticated_user", "user"):
        candidate = _extract_principal_id(getattr(request.state, state_attr, None))
        if candidate:
            return candidate
    if "user" in request.scope:
        return _extract_principal_id(request.scope.get("user"))
    return None


def _resolve_custom_provider(
    request: Request, verified_hint: Optional[str]
) -> Optional[str]:
    provider = dashboard_identity._identity_provider
    if provider is None and os.getenv("DBGPT_DASHBOARD_IDENTITY_PROVIDER", "").strip():
        provider = dashboard_identity.get_dashboard_identity_provider()
    if provider is None or isinstance(provider, DBGPTUserIdentityProvider):
        return None
    try:
        resolve_req = getattr(provider, "resolve_request", None)
        if callable(resolve_req):
            resolved_value = resolve_req(request)
        else:
            resolved_value = provider.resolve(UserRequest(user_id=verified_hint))
    except (DashboardIdentityError, PermissionError) as exc:
        raise HTTPException(
            status_code=401, detail=str(exc) or "Authentication required"
        ) from exc
    if not isinstance(resolved_value, str):
        raise HTTPException(status_code=401, detail="Authentication required")
    resolved = resolved_value.strip()
    if not resolved:
        raise HTTPException(status_code=401, detail="Authentication required")
    return resolved


def _allow_dev_feedback_fallback() -> bool:
    if dashboard_production_mode():
        return False
    return os.getenv(DEV_FALLBACK_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _single_header(request: Request, name: str) -> Optional[str]:
    values = request.headers.getlist(name)
    if len(values) > 1:
        raise HTTPException(
            status_code=400, detail=f"Duplicate {name} header is not allowed"
        )
    return values[0] if values else None


def _resolve_feedback_actor_context(
    request: Request,
    api_key_auth: _ApiKeyAuthResult = Depends(check_feedback_api_key),
) -> _ResolvedFeedbackActor:
    """Resolve a verified caller principal without trusting raw ``user-id`` headers.

    Accepted identity sources:
    1. Upstream ASGI/FastAPI middleware principals (`request.state` / `request.scope`);
    2. Trusted gateway HMAC-SHA256 attestations (`DBGPT_TRUSTED_GATEWAY_SECRET`);
    3. Unambiguous principal-bound feedback API keys (`owner:token`);
    4. Custom non-default `DashboardIdentityProvider` adapters;
    5. When neither a gateway secret nor API keys nor upstream principals are active,
       an isolated per-browser `dbgpt_feedback_session` cookie signed by a persistent
       shared key (supporting the built-in browser UI in default and production modes
       while rejecting stateless anonymous calls and raw header spoofing);
    6. Explicit non-production opt-in `DBGPT_FEEDBACK_ALLOW_DEV_FALLBACK` (`"001"`).
    """
    raw_user_id = _single_header(request, "user-id")
    raw_auth_user = _single_header(request, AUTH_USER_HEADER)
    raw_gateway_sig = _single_header(request, TRUSTED_GATEWAY_SIG_HEADER)
    has_identity_header = (
        raw_user_id is not None
        or raw_auth_user is not None
        or raw_gateway_sig is not None
    )
    if (
        raw_user_id is not None
        and raw_auth_user is not None
        and raw_user_id.strip() != raw_auth_user.strip()
    ):
        raise HTTPException(status_code=403, detail="Conflicting identity headers")

    claimed_header_user = (
        raw_auth_user if raw_auth_user is not None else (raw_user_id or "")
    ).strip()

    state_owner = _extract_request_principal(request)
    gateway_secret = os.getenv(TRUSTED_GATEWAY_SECRET_ENV, "").strip()
    gateway_owner: Optional[str] = None
    if gateway_secret and has_identity_header:
        provided_sig = (raw_gateway_sig or "").strip().lower()
        if not claimed_header_user or not provided_sig or not provided_sig.isascii():
            raise HTTPException(
                status_code=401,
                detail="Invalid or missing trusted gateway signature",
            )
        expected_sig = compute_gateway_signature(gateway_secret, claimed_header_user)
        if not hmac.compare_digest(
            provided_sig.encode("ascii"), expected_sig.encode("ascii")
        ):
            raise HTTPException(
                status_code=401,
                detail="Invalid or missing trusted gateway signature",
            )
        gateway_owner = claimed_header_user

    provider_owner = _resolve_custom_provider(
        request, state_owner or gateway_owner or api_key_auth.bound_owner
    )
    candidates = [
        c
        for c in (
            state_owner,
            gateway_owner,
            api_key_auth.bound_owner,
            provider_owner,
        )
        if c
    ]
    if len(set(candidates)) > 1:
        raise HTTPException(
            status_code=403, detail="Conflicting authenticated principals"
        )
    verified_owner = candidates[0] if candidates else None
    is_session_actor = False

    if verified_owner is None and not gateway_secret and not api_key_auth.authenticated:
        session_owner = _verify_session_cookie(request)
        if session_owner is not None:
            verified_owner = session_owner
            is_session_actor = True

    if has_identity_header and gateway_owner is None:
        if raw_gateway_sig is not None:
            raise HTTPException(
                status_code=401, detail="Trusted gateway boundary is not configured"
            )
        if verified_owner is None:
            raise HTTPException(
                status_code=401, detail="Unverified user-id header is not accepted"
            )
        if not claimed_header_user or claimed_header_user != verified_owner:
            raise HTTPException(
                status_code=403,
                detail="Forged user-id header does not match authenticated principal",
            )

    if verified_owner:
        if is_session_actor:
            _enforce_cookie_mutation_guards(request)
        return _ResolvedFeedbackActor(
            actor_id=verified_owner,
            is_session_actor=is_session_actor,
            can_reclaim_session_row=not is_session_actor,
        )

    if (
        not api_key_auth.authenticated
        and not gateway_secret
        and _allow_dev_feedback_fallback()
    ):
        return _ResolvedFeedbackActor(
            actor_id="001",
            is_session_actor=False,
            can_reclaim_session_row=False,
        )

    raise HTTPException(status_code=401, detail="Authentication required")


def _resolve_feedback_actor(
    actor: _ResolvedFeedbackActor = Depends(_resolve_feedback_actor_context),
) -> str:
    return actor.actor_id


router = APIRouter(dependencies=[Depends(check_feedback_api_key)])
chat_feed_back = ChatFeedBackDao()


@router.get("/v1/feedback/find", response_model=Result[FeedBackBody])
async def feed_back_find(
    request: Request,
    conv_uid: str,
    conv_index: int,
    response: Response,
    actor: _ResolvedFeedbackActor = Depends(_resolve_feedback_actor_context),
):
    response.headers["Cache-Control"] = "no-store"
    if actor.is_session_actor:
        _set_session_cookie(request, response, actor.actor_id)
    rt = await run_in_threadpool(
        chat_feed_back.get_chat_feed_back,
        conv_uid,
        conv_index,
        user_name=actor.actor_id,
    )
    if rt is not None:
        return Result.succ(
            FeedBackBody(
                conv_uid=rt.conv_uid,
                conv_index=rt.conv_index,
                question=rt.question,
                knowledge_space=rt.knowledge_space,
                score=rt.score,
                ques_type=rt.ques_type,
                user_name=rt.user_name,
                messages=rt.messages,
            )
        )
    return Result.succ(None)


@router.post("/v1/feedback/commit", response_model=Result[bool])
async def feed_back_commit(
    request: Request,
    response: Response,
    feed_back_body: FeedBackBody = Body(),
    actor: _ResolvedFeedbackActor = Depends(_resolve_feedback_actor_context),
):
    response.headers["Cache-Control"] = "no-store"
    if not feed_back_body.conv_uid or feed_back_body.conv_index is None:
        raise HTTPException(
            status_code=422, detail="conv_uid and conv_index are required"
        )
    if actor.is_session_actor:
        _set_session_cookie(request, response, actor.actor_id)
    try:
        await run_in_threadpool(
            partial(
                chat_feed_back.create_or_update_chat_feed_back,
                feed_back_body,
                user_name=actor.actor_id,
                allow_default_conv_owner=actor.is_session_actor,
                can_reclaim_session_row=actor.can_reclaim_session_row,
            )
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return Result.succ(True)


@router.get("/v1/feedback/select", response_model=Result[dict])
async def feed_back_select(
    request: Request,
    response: Response,
    api_key_auth: _ApiKeyAuthResult = Depends(check_feedback_api_key),
):
    response.headers["Cache-Control"] = "no-store"
    if (
        not os.getenv(TRUSTED_GATEWAY_SECRET_ENV, "").strip()
        and not api_key_auth.authenticated
        and _extract_request_principal(request) is None
    ):
        existing_actor = _verify_session_cookie(request)
        actor_to_issue = existing_actor or f"session:{secrets.token_hex(16)}"
        _set_session_cookie(request, response, actor_to_issue)
    return Result.succ(
        {
            "information": "信息查询",
            "work_study": "工作学习",
            "just_fun": "互动闲聊",
            "others": "其他",
        }
    )
