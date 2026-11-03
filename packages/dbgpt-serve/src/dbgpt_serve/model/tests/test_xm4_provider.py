from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from dbgpt.core import ModelMetadata
from dbgpt.model.cluster.storage import ModelProviderConfigItem
from dbgpt.model.proxy.llms.xm4 import XM4_API_BASE, Xm4DeployModelParameters
from dbgpt_serve.model.api.endpoints import (
    _finish_connect,
    _start_provider_model,
    enable_provider_model,
)
from dbgpt_serve.model.api.schemas import ProviderModelRequest


@pytest.mark.asyncio
async def test_connect_uses_authorized_models_and_stops_old_group(monkeypatch):
    monkeypatch.setattr(
        "dbgpt.model.utils.provider_test.test_provider_connection",
        AsyncMock(return_value=(True, "")),
    )
    monkeypatch.setattr(
        "dbgpt.model.proxy.llms.xm4.list_xm4_models",
        AsyncMock(
            return_value=[
                ModelMetadata(model="deepseek-v4.1-flash"),
                ModelMetadata(model="glm-5.3-flash"),
            ]
        ),
    )
    storage = MagicMock()
    storage.get.return_value = ModelProviderConfigItem(
        provider="proxy/xm4", api_key="old-key", enabled_models=["gpt-6"]
    )
    manager = MagicMock()
    manager.model_startup = AsyncMock()
    manager.model_shutdown = AsyncMock()
    ok, reason, enabled = await _finish_connect(
        storage, manager, "proxy/xm4", "test-key", None
    )
    assert ok and not reason
    assert enabled == ["deepseek-v4.1-flash", "glm-5.3-flash"]
    assert [
        call.args[0].model for call in manager.model_startup.call_args_list
    ] == enabled
    assert manager.model_shutdown.call_args.args[0].model == "gpt-6"
    assert storage.save_or_update.call_args.args[0].enabled_models == enabled


@pytest.mark.asyncio
async def test_empty_authorized_catalog_does_not_save_or_start(monkeypatch):
    monkeypatch.setattr(
        "dbgpt.model.utils.provider_test.test_provider_connection",
        AsyncMock(return_value=(True, "")),
    )
    monkeypatch.setattr(
        "dbgpt.model.proxy.llms.xm4.list_xm4_models", AsyncMock(return_value=[])
    )
    storage = MagicMock()
    storage.get.return_value = None
    manager = MagicMock()
    ok, reason, enabled = await _finish_connect(
        storage, manager, "proxy/xm4", "test-key", None
    )
    assert not ok and "no models" in reason and not enabled
    storage.save_or_update.assert_not_called()
    manager.model_startup.assert_not_called()


def _duplicate_manager(*, api_key="test-key", stopped=False, provider="proxy/xm4"):
    manager = MagicMock()
    manager.model_startup = AsyncMock(
        side_effect=Exception("Add worker glm-5.3-flash, worker instances is exist")
    )
    manager.model_shutdown = AsyncMock()
    manager.get_model_instances = AsyncMock(
        return_value=[
            SimpleNamespace(
                stopped=stopped,
                model_params=Xm4DeployModelParameters(
                    name="glm-5.3-flash",
                    provider=provider,
                    api_key=api_key,
                    api_base=XM4_API_BASE,
                ),
            )
        ]
    )
    return manager


@pytest.mark.asyncio
async def test_enable_existing_worker_repairs_empty_enabled_list():
    storage = MagicMock()
    storage.get.return_value = ModelProviderConfigItem(
        provider="proxy/xm4", api_key="test-key", api_base=XM4_API_BASE
    )
    manager = _duplicate_manager()
    result = await enable_provider_model(
        ProviderModelRequest(provider="proxy/xm4", model="glm-5.3-flash"),
        storage,
        manager,
    )
    assert result.success
    assert storage.save_or_update.call_args.args[0].enabled_models == ["glm-5.3-flash"]
    manager.model_shutdown.assert_not_awaited()


@pytest.mark.asyncio
async def test_reconnect_keeps_existing_worker_enabled(monkeypatch):
    monkeypatch.setattr(
        "dbgpt.model.utils.provider_test.test_provider_connection",
        AsyncMock(return_value=(True, "")),
    )
    monkeypatch.setattr(
        "dbgpt.model.proxy.llms.xm4.list_xm4_models",
        AsyncMock(return_value=[ModelMetadata(model="glm-5.3-flash")]),
    )
    storage = MagicMock()
    storage.get.return_value = ModelProviderConfigItem(
        provider="proxy/xm4",
        api_key="test-key",
        api_base=XM4_API_BASE,
        enabled_models=["glm-5.3-flash"],
    )
    manager = _duplicate_manager()
    ok, reason, enabled = await _finish_connect(
        storage, manager, "proxy/xm4", "test-key", XM4_API_BASE
    )
    assert ok and not reason and enabled == ["glm-5.3-flash"]
    assert storage.save_or_update.call_args.args[0].enabled_models == enabled
    manager.model_shutdown.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("api_key,stopped", [("old-key", False), ("test-key", True)])
async def test_existing_worker_refreshes_changed_key_or_stopped_state(api_key, stopped):
    manager = _duplicate_manager(api_key=api_key, stopped=stopped)
    manager.model_startup.side_effect = [
        Exception("worker instances is exist"),
        None,
    ]
    item = ModelProviderConfigItem(
        provider="proxy/xm4", api_key="test-key", api_base=XM4_API_BASE
    )
    await _start_provider_model(manager, item, "glm-5.3-flash")
    manager.model_shutdown.assert_awaited_once()
    assert manager.model_startup.await_count == 2
    assert manager.model_startup.call_args.args[0].params["api_key"] == "test-key"


@pytest.mark.asyncio
async def test_duplicate_from_another_provider_is_not_adopted():
    manager = _duplicate_manager(provider="proxy/zhipu")
    item = ModelProviderConfigItem(provider="proxy/xm4", api_key="test-key")
    with pytest.raises(Exception, match="worker instances is exist"):
        await _start_provider_model(manager, item, "glm-5.3-flash")
    manager.model_shutdown.assert_not_awaited()


@pytest.mark.asyncio
async def test_startup_failure_is_not_treated_as_enabled():
    manager = _duplicate_manager()
    manager.model_startup.side_effect = ValueError("invalid configuration")
    item = ModelProviderConfigItem(provider="proxy/xm4", api_key="test-key")
    with pytest.raises(ValueError, match="invalid configuration"):
        await _start_provider_model(manager, item, "glm-5.3-flash")
    manager.get_model_instances.assert_not_awaited()
