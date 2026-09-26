import logging
from functools import cache
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer

from dbgpt.component import SystemApp
from dbgpt.model.base import SupportedModel
from dbgpt.model.cluster import (
    WorkerManager,
    WorkerManagerFactory,
    WorkerStartupRequest,
)
from dbgpt.model.cluster.controller.controller import BaseModelController
from dbgpt.model.cluster.storage import (
    ModelProviderConfigItem,
    ModelProviderConfigStorage,
    ModelStorage,
)
from dbgpt.model.parameter import WorkerType
from dbgpt_serve.core import Result

from ..config import SERVE_SERVICE_COMPONENT_NAME, ServeConfig
from ..service.service import Service
from .schemas import (
    ModelResponse,
    ProviderConfigRequest,
    ProviderCustomRequest,
    ProviderModelRequest,
    ProviderModelsRequest,
    ProviderRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Add your API endpoints here

global_system_app: Optional[SystemApp] = None


def get_service() -> Service:
    """Get the service instance"""
    return global_system_app.get_component(SERVE_SERVICE_COMPONENT_NAME, Service)


def get_worker_manager() -> WorkerManager:
    """Get the worker manager instance"""
    return WorkerManagerFactory.get_instance(global_system_app).create()


def get_model_controller() -> BaseModelController:
    """Get the model controller instance"""
    return BaseModelController.get_instance(global_system_app)


def get_model_storage() -> ModelStorage:
    """Get the model storage instance"""
    from ..serve import Serve as ModelServe

    model_serve = ModelServe.get_instance(global_system_app)
    # Persistent model storage
    model_storage = ModelStorage(model_serve.model_storage)
    return model_storage


def get_provider_config_storage() -> ModelProviderConfigStorage:
    """Get the provider config storage instance"""
    from ..serve import Serve as ModelServe

    model_serve = ModelServe.get_instance(global_system_app)
    return ModelProviderConfigStorage(model_serve.provider_config_storage)


get_bearer_token = HTTPBearer(auto_error=False)


@cache
def _parse_api_keys(api_keys: str) -> List[str]:
    """Parse the string api keys to a list

    Args:
        api_keys (str): The string api keys

    Returns:
        List[str]: The list of api keys
    """
    if not api_keys:
        return []
    return [key.strip() for key in api_keys.split(",")]


async def check_api_key(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(get_bearer_token),
    service: Service = Depends(get_service),
) -> Optional[str]:
    """Check the api key

    If the api key is not set, allow all.

    Your can pass the token in you request header like this:

    .. code-block:: python

        import requests

        client_api_key = "your_api_key"
        headers = {"Authorization": "Bearer " + client_api_key}
        res = requests.get("http://test/hello", headers=headers)
        assert res.status_code == 200

    """
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
    else:
        # api_keys not set; allow all
        return None


@router.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok"}


@router.get("/test_auth", dependencies=[Depends(check_api_key)])
async def test_auth():
    """Test auth endpoint"""
    return {"status": "ok"}


@router.get("/model-types")
async def model_params(worker_manager: WorkerManager = Depends(get_worker_manager)):
    try:
        params = []
        workers = await worker_manager.supported_models()
        for worker in workers:
            for model in worker.models:
                model_dict = model.__dict__
                model_dict["host"] = worker.host
                model_dict["port"] = worker.port
                params.append(model_dict)
        return Result.succ(params)
    except Exception as e:
        return Result.failed(err_code="E000X", msg=f"model stop failed {e}")


# How many of each provider's (most recently updated) models are enabled by
# default when connecting a provider.
DEFAULT_ENABLE_MODEL_COUNT = 5


_PROVIDER_NAME_OVERRIDES = {
    "hf": "Hugging Face",
    "vllm": "vLLM",
    "mlx": "Apple MLX",
    "llama.cpp": "llama.cpp",
    "vercel": "Vercel AI Gateway",
    "xai": "xAI",
    "wenxin": "Baidu Qianfan",
    "spark": "iFlytek Spark",
    "yi": "Yi (01.AI)",
    "gitee": "Gitee AI",
    "aimlapi": "AIML API",
    "tongyi": "Tongyi Qwen",
    "zhipu": "Zhipu AI",
    "orcarouter": "OrcaRouter",
}


def _provider_display_name(provider: Optional[str]) -> str:
    """Derive a human-friendly name from the provider id."""
    if not provider:
        return "Unknown"
    if provider in _PROVIDER_NAME_OVERRIDES:
        return _PROVIDER_NAME_OVERRIDES[provider]
    name = provider.rsplit("/", 1)[-1]
    return name[:1].upper() + name[1:] if name else provider


def _to_provider_model(m: SupportedModel) -> Dict[str, Any]:
    """Convert a supported model to a provider-facing dict."""
    return {
        "model": m.model,
        "label": m.label or m.model,
        "context_length": m.context_length,
        "max_output_length": m.max_output_length,
        "function_calling": m.function_calling,
        "link": m.link,
        "description": m.description,
        "enabled": m.enabled,
    }


def _model_startup_params(item: ModelProviderConfigItem, model: str) -> Dict[str, Any]:
    """Build startup params for a model, routing custom providers through the
    OpenAI-compatible client."""
    provider = "proxy/openai" if item.is_custom else item.provider
    params: Dict[str, Any] = {
        "name": model,
        "provider": provider,
        "api_key": item.api_key,
    }
    if provider == "proxy/wenxin" and item.api_key:
        # Wenxin stores an "AK:SK" pair in the api_key column; the Qianfan
        # client expects them as separate api_key / api_secret params.
        ak, _, sk = item.api_key.partition(":")
        params["api_key"] = ak
        params["api_secret"] = sk
    if item.api_base:
        params["api_base"] = item.api_base
    return params


def _default_enable_model_names(provider: str) -> List[str]:
    """Pick the default set of models to enable for a provider.

    Prefer the models.dev snapshot ordered by ``last_updated`` (most recent
    first) and take the top N; fall back to the full registry for providers
    without a snapshot.
    """
    from dbgpt.model.utils.llm_utils import list_supported_models
    from dbgpt.model.utils.models_dev import get_models_dev_models

    dev_models = get_models_dev_models(provider)
    if dev_models:
        return [m["model"] for m in dev_models[:DEFAULT_ENABLE_MODEL_COUNT]]
    return [
        m.model
        for m in list_supported_models()
        if m.provider == provider and m.worker_type == WorkerType.LLM.value
    ]


async def _start_provider_models(
    worker_manager: WorkerManager,
    item: ModelProviderConfigItem,
    model_names: List[str],
) -> List[str]:
    """Start the proxy workers for the given models; return the ones started."""
    enabled: List[str] = []
    for model in model_names:
        try:
            await worker_manager.model_startup(
                WorkerStartupRequest(
                    host="",
                    port=0,
                    model=model,
                    worker_type=WorkerType.LLM,
                    params=_model_startup_params(item, model),
                )
            )
            enabled.append(model)
        except Exception as e:
            logger.warning(f"enable model {model} under {item.provider} failed: {e}")
    return enabled


@router.get("/providers")
async def model_providers(
    worker_type: Optional[str] = None,
    worker_manager: WorkerManager = Depends(get_worker_manager),
    storage: ModelProviderConfigStorage = Depends(get_provider_config_storage),
):
    """List model providers and their supported models.

    Returns a two-level catalog grouped by (provider, worker_type), where each
    provider carries the default deploy params (api_key/api_base etc.) shared by
    all of its models.
    """
    try:
        providers: Dict[str, Dict[str, Any]] = {}
        workers = await worker_manager.supported_models()
        for worker in workers:
            for model in worker.models:
                if worker_type and model.worker_type != worker_type:
                    continue
                key = f"{model.provider}__{model.worker_type}"
                if key not in providers:
                    providers[key] = {
                        "provider": model.provider,
                        "name": _provider_display_name(model.provider),
                        "worker_type": model.worker_type,
                        "proxy": model.proxy,
                        "params": model.params,
                        "models": [],
                    }
                providers[key]["models"].append(_to_provider_model(model))

        # Merge user-defined (custom OpenAI-compatible) providers into the catalog.
        for item in storage.list_all():
            if not item.is_custom:
                continue
            providers[item.provider] = {
                "provider": item.provider,
                "name": item.label or item.provider,
                "worker_type": WorkerType.LLM.value,
                "proxy": True,
                "params": [],
                "models": [
                    {
                        "model": m,
                        "label": m,
                        "context_length": None,
                        "max_output_length": None,
                        "function_calling": None,
                        "link": None,
                        "description": None,
                        "enabled": True,
                    }
                    for m in item.enabled_models
                ],
            }

        # Reconcile connected providers that have no enabled models yet (e.g.
        # connected before default-enable existed): start their default models
        # so the enabled state matches the connection state.
        if worker_type in (None, WorkerType.LLM.value):
            for item in storage.list_all():
                if item.is_custom or not item.connected or item.enabled_models:
                    continue
                enabled = await _start_provider_models(
                    worker_manager, item, _default_enable_model_names(item.provider)
                )
                if enabled:
                    storage.save_or_update(
                        ModelProviderConfigItem(
                            provider=item.provider,
                            label=item.label,
                            api_key=item.api_key,
                            api_base=item.api_base,
                            enabled_models=enabled,
                        )
                    )

        result = sorted(providers.values(), key=lambda p: p["name"].lower())
        return Result.succ(result)
    except Exception as e:
        logger.error(f"list model providers failed {e}")
        return Result.failed(err_code="E000X", msg=f"list model providers failed {e}")


@router.get("/providers/config")
async def get_provider_config(
    provider: str,
    storage: ModelProviderConfigStorage = Depends(get_provider_config_storage),
):
    """Get the stored provider configuration (connection state + enabled models)."""
    try:
        item = storage.get(provider)
        return Result.succ(
            {
                "provider": provider,
                "connected": item.connected if item else False,
                "api_base": item.api_base if item else None,
                "enabled_models": item.enabled_models if item else [],
            }
        )
    except Exception as e:
        logger.error(f"get provider config failed {e}")
        return Result.failed(err_code="E000X", msg=f"get provider config failed {e}")


@router.put("/providers/config")
async def save_provider_config(
    request: ProviderConfigRequest,
    storage: ModelProviderConfigStorage = Depends(get_provider_config_storage),
):
    """Save provider credentials. Missing fields keep their existing value."""
    try:
        provider = request.provider
        existing = storage.get(provider)
        item = ModelProviderConfigItem(
            provider=provider,
            api_key=request.api_key
            if request.api_key is not None
            else (existing.api_key if existing else None),
            api_base=request.api_base
            if request.api_base is not None
            else (existing.api_base if existing else None),
            enabled_models=existing.enabled_models if existing else [],
        )
        storage.save_or_update(item)
        return Result.succ(True)
    except Exception as e:
        logger.error(f"save provider config failed {e}")
        return Result.failed(err_code="E000X", msg=f"save provider config failed {e}")


@router.post("/providers/connect")
async def connect_provider(
    request: ProviderConfigRequest,
    storage: ModelProviderConfigStorage = Depends(get_provider_config_storage),
    worker_manager: WorkerManager = Depends(get_worker_manager),
):
    """Connect a provider and enable its default (popular) models."""
    from dbgpt.model.utils.provider_test import NO_API_KEY_REQUIRED_PROVIDERS

    provider = request.provider
    existing = storage.get(provider)
    api_key = request.api_key
    if not api_key and provider not in NO_API_KEY_REQUIRED_PROVIDERS:
        return Result.failed(err_code="E000X", msg="api_key is required")
    api_base = (
        request.api_base
        if request.api_base is not None
        else (existing.api_base if existing else None)
    )

    # Verify the credentials against the provider before persisting anything.
    ok, reason, enabled = await _finish_connect(
        storage, worker_manager, provider, api_key, api_base
    )
    if not ok:
        return Result.failed(err_code="E000X", msg=f"connect failed: {reason}")
    return Result.succ({"connected": True, "enabled_models": enabled})


@router.post("/providers/github_copilot/auth/start")
async def copilot_auth_start():
    """Begin the GitHub OAuth device flow for GitHub Copilot.

    Returns the user code to enter at github.com/login/device plus the
    device code used when polling.
    """
    from dbgpt.model.utils.copilot_auth import start_device_flow

    ok, msg, data = await start_device_flow()
    if not ok:
        return Result.failed(err_code="E000X", msg=msg)
    return Result.succ(data)


@router.get("/providers/github_copilot/auth/poll")
async def copilot_auth_poll(
    device_code: str,
    storage: ModelProviderConfigStorage = Depends(get_provider_config_storage),
    worker_manager: WorkerManager = Depends(get_worker_manager),
):
    """Poll the GitHub device flow once.

    While the user has not authorized yet, returns ``{"status": "pending"}``
    (or ``slow_down``). Once authorized, the GitHub OAuth token becomes the
    provider api_key and the default Copilot models are started.
    """
    from dbgpt.model.utils.copilot_auth import poll_device_flow

    status, github_token = await poll_device_flow(device_code)
    if status == "pending":
        return Result.succ({"status": "pending"})
    if status == "slow_down":
        return Result.succ({"status": "slow_down"})
    if status != "success":
        return Result.failed(
            err_code="E000X",
            msg="device flow expired or failed, please restart the login",
        )
    provider = "proxy/github_copilot"
    existing = storage.get(provider)
    ok, reason, enabled = await _finish_connect(
        storage,
        worker_manager,
        provider,
        github_token,
        existing.api_base if existing else None,
    )
    if not ok:
        return Result.failed(err_code="E000X", msg=f"connect failed: {reason}")
    return Result.succ({"status": "success", "enabled_models": enabled})


async def _finish_connect(
    storage: ModelProviderConfigStorage,
    worker_manager: WorkerManager,
    provider: str,
    api_key: str,
    api_base: Optional[str],
) -> Tuple[bool, str, List[str]]:
    """Verify credentials, start default models and persist the provider.

    Shared by the plain connect endpoint and the GitHub Copilot device flow.
    """
    from dbgpt.model.utils.provider_test import test_provider_connection

    existing = storage.get(provider)
    ok, reason = await test_provider_connection(provider, api_key, api_base)
    if not ok:
        return False, reason, []
    item = ModelProviderConfigItem(
        provider=provider,
        label=existing.label if existing else None,
        api_key=api_key,
        api_base=api_base,
    )
    enabled = await _start_provider_models(
        worker_manager, item, _default_enable_model_names(provider)
    )
    item.enabled_models = enabled
    storage.save_or_update(item)
    return True, "", enabled


@router.put("/providers/models")
async def save_provider_models(
    request: ProviderModelsRequest,
    storage: ModelProviderConfigStorage = Depends(get_provider_config_storage),
):
    """Save the enabled model list under a provider (model enable/disable)."""
    try:
        provider = request.provider
        existing = storage.get(provider)
        item = ModelProviderConfigItem(
            provider=provider,
            api_key=existing.api_key if existing else None,
            api_base=existing.api_base if existing else None,
            enabled_models=request.enabled_models,
        )
        storage.save_or_update(item)
        return Result.succ(True)
    except Exception as e:
        logger.error(f"save provider models failed {e}")
        return Result.failed(err_code="E000X", msg=f"save provider models failed {e}")


@router.post("/providers/models/enable")
async def enable_provider_model(
    request: ProviderModelRequest,
    storage: ModelProviderConfigStorage = Depends(get_provider_config_storage),
    worker_manager: WorkerManager = Depends(get_worker_manager),
):
    """Enable a model: start its proxy worker with the stored provider key."""
    try:
        item = storage.get(request.provider)
        if not item or not item.api_key:
            return Result.failed(err_code="E000X", msg="provider not connected")
        startup_req = WorkerStartupRequest(
            host="",
            port=0,
            model=request.model,
            worker_type=WorkerType.LLM,
            params=_model_startup_params(item, request.model),
        )
        await worker_manager.model_startup(startup_req)
        enabled = list(item.enabled_models)
        if request.model not in enabled:
            enabled.append(request.model)
        storage.save_or_update(
            ModelProviderConfigItem(
                provider=request.provider,
                label=item.label,
                api_key=item.api_key,
                api_base=item.api_base,
                enabled_models=enabled,
            )
        )
        return Result.succ(True)
    except Exception as e:
        logger.error(f"enable provider model failed {e}")
        return Result.failed(err_code="E000X", msg=f"enable provider model failed {e}")


@router.post("/providers/models/disable")
async def disable_provider_model(
    request: ProviderModelRequest,
    storage: ModelProviderConfigStorage = Depends(get_provider_config_storage),
    worker_manager: WorkerManager = Depends(get_worker_manager),
):
    """Disable a model: stop its proxy worker and drop it from the enabled list."""
    item = storage.get(request.provider)
    try:
        shutdown_req = WorkerStartupRequest(
            host="",
            port=0,
            model=request.model,
            worker_type=WorkerType.LLM,
            delete_after=True,
            params={},
        )
        await worker_manager.model_shutdown(shutdown_req)
    except Exception as e:
        # The worker may not be running (e.g. failed to start); still update the
        # enabled list so the toggle reaches the desired state.
        logger.warning(
            f"shutdown worker {request.model} failed (maybe not running): {e}"
        )

    enabled = [m for m in (item.enabled_models if item else []) if m != request.model]
    storage.save_or_update(
        ModelProviderConfigItem(
            provider=request.provider,
            label=item.label if item else None,
            api_key=item.api_key if item else None,
            api_base=item.api_base if item else None,
            enabled_models=enabled,
        )
    )
    return Result.succ(True)


@router.post("/providers/disconnect")
async def disconnect_provider(
    request: ProviderRequest,
    storage: ModelProviderConfigStorage = Depends(get_provider_config_storage),
    worker_manager: WorkerManager = Depends(get_worker_manager),
):
    """Disconnect a provider: stop its enabled models and clear its key."""
    item = storage.get(request.provider)
    if item:
        for model in item.enabled_models:
            try:
                await worker_manager.model_shutdown(
                    WorkerStartupRequest(
                        host="",
                        port=0,
                        model=model,
                        worker_type=WorkerType.LLM,
                        delete_after=True,
                        params={},
                    )
                )
            except Exception as e:
                logger.warning(f"shutdown model {model} on disconnect failed: {e}")
    # Remove the stored configuration entirely: the SQLAlchemy update path skips
    # None fields, so clearing api_key via save_or_update would not take effect.
    # No config record == not connected.
    if item:
        storage.delete(request.provider)
    return Result.succ(True)


@router.post("/providers/custom")
async def create_custom_provider(
    request: ProviderCustomRequest,
    storage: ModelProviderConfigStorage = Depends(get_provider_config_storage),
    worker_manager: WorkerManager = Depends(get_worker_manager),
):
    """Create (or update) a custom OpenAI-compatible provider and start its models."""
    import re
    from uuid import uuid4

    from dbgpt.model.utils.provider_test import test_provider_connection

    # Custom providers are OpenAI-compatible; verify the base url + key first.
    ok, reason = await test_provider_connection(
        "proxy/openai", request.api_key, request.api_base
    )
    if not ok:
        return Result.failed(err_code="E000X", msg=f"connect failed: {reason}")

    slug = re.sub(r"[^a-z0-9]+", "-", request.label.strip().lower()).strip("-")
    provider_id = f"custom/{slug or uuid4().hex[:8]}"

    item = ModelProviderConfigItem(
        provider=provider_id,
        label=request.label,
        api_key=request.api_key,
        api_base=request.api_base,
        enabled_models=request.models,
    )
    storage.save_or_update(item)

    enabled = []
    for model in request.models:
        try:
            await worker_manager.model_startup(
                WorkerStartupRequest(
                    host="",
                    port=0,
                    model=model,
                    worker_type=WorkerType.LLM,
                    params=_model_startup_params(item, model),
                )
            )
            enabled.append(model)
        except Exception as e:
            logger.warning(f"enable custom model {model} failed: {e}")

    item.enabled_models = enabled
    storage.save_or_update(item)
    return Result.succ(
        {"provider": provider_id, "label": request.label, "enabled_models": enabled}
    )


@router.get("/models")
async def model_list(controller: BaseModelController = Depends(get_model_controller)):
    try:
        responses = []
        managers = await controller.get_all_instances(
            model_name="WorkerManager@service", healthy_only=True
        )
        manager_map = dict(map(lambda manager: (manager.host, manager), managers))
        models = await controller.get_all_instances()
        for model in models:
            worker_name, worker_type = model.model_name.split("@")
            if worker_type in WorkerType.values():
                manager_host = model.host if manager_map.get(model.host) else ""
                manager_port = (
                    manager_map[model.host].port if manager_map.get(model.host) else -1
                )
                response = ModelResponse(
                    model_name=worker_name,
                    worker_type=worker_type,
                    host=model.host,
                    port=model.port,
                    manager_host=manager_host,
                    manager_port=manager_port,
                    healthy=model.healthy,
                    check_healthy=model.check_healthy,
                    last_heartbeat=model.str_last_heartbeat,
                    prompt_template=model.prompt_template,
                )
                responses.append(response)
        return Result.succ(responses)

    except Exception as e:
        return Result.failed(err_code="E000X", msg=f"model list error {e}")


@router.post("/models/stop")
async def model_stop(
    request: WorkerStartupRequest,
    worker_manager: WorkerManager = Depends(get_worker_manager),
):
    try:
        request.params = {}
        await worker_manager.model_shutdown(request)
        return Result.succ(True)
    except Exception as e:
        return Result.failed(err_code="E000X", msg=f"model stop failed {e}")


@router.post("/models")
async def create_model(
    request: WorkerStartupRequest,
    worker_manager: WorkerManager = Depends(get_worker_manager),
):
    """Create a model.

    Must provide the full information of the model, including the host, port,
    model name, worker type, and params.
    """
    try:
        await worker_manager.model_startup(request)
        return Result.succ(True)
    except Exception as e:
        logger.error(f"model start failed {e}")
        return Result.failed(err_code="E000X", msg=f"model start failed {e}")


@router.post("/models/start")
async def start_model(
    request: WorkerStartupRequest,
    worker_manager: WorkerManager = Depends(get_worker_manager),
    model_storage: ModelStorage = Depends(get_model_storage),
):
    """Start an existing model."""

    try:
        models = model_storage.query_models(
            request.model,
            worker_type=request.worker_type.value,
            user_name=request.user_name,
            sys_code=request.sys_code,
            host=request.host,
            port=request.port,
        )
        if not models:
            return Result.failed(err_code="E000X", msg="model not found")
        if len(models) > 1:
            return Result.failed(err_code="E000X", msg="multiple models found")
        await worker_manager.model_startup(models[0])
        return Result.succ(True)
    except Exception as e:
        logger.error(f"model start failed {e}")
        return Result.failed(err_code="E000X", msg=f"model start failed {e}")


def init_endpoints(system_app: SystemApp, config: ServeConfig) -> None:
    """Initialize the endpoints"""
    global global_system_app
    system_app.register(Service, config=config)
    global_system_app = system_app
