import pytest
from datetime import datetime, timedelta

import asyncio
from dbgpt.model.base import ModelInstance
from dbgpt.model.cluster.registry import EmbeddedModelRegistry


@pytest.fixture
def model_registry():
    return EmbeddedModelRegistry()


@pytest.fixture
def model_instance():
    return ModelInstance(
        model_name="test_model",
        host="192.168.1.1",
        port=5000,
    )


# Async function to test the registry
@pytest.mark.asyncio
async def test_register_instance(model_registry, model_instance):
    """
    Test if an instance can be registered correctly
    """
    assert await model_registry.register_instance(model_instance) == True
    assert len(model_registry.registry[model_instance.model_name]) == 1


@pytest.mark.asyncio
async def test_deregister_instance(model_registry, model_instance):
    """
    Test if an instance can be deregistered correctly
    """
    await model_registry.register_instance(model_instance)
    assert await model_registry.deregister_instance(model_instance) == True
    assert not model_registry.registry[model_instance.model_name][0].healthy


@pytest.mark.asyncio
async def test_get_all_instances(model_registry, model_instance):
    """
    Test if all instances can be retrieved, with and without the healthy_only filter
    """
    await model_registry.register_instance(model_instance)
    assert len(await model_registry.get_all_instances(model_instance.model_name)) == 1
    assert (
        len(
            await model_registry.get_all_instances(
                model_instance.model_name, healthy_only=True
            )
        )
        == 1
    )
    model_instance.healthy = False
    assert (
        len(
            await model_registry.get_all_instances(
                model_instance.model_name, healthy_only=True
            )
        )
        == 0
    )


@pytest.mark.asyncio
async def test_select_one_health_instance(model_registry, model_instance):
    """
    Test if a single healthy instance can be selected
    """
    await model_registry.register_instance(model_instance)
    selected_instance = await model_registry.select_one_health_instance(
        model_instance.model_name
    )
    assert selected_instance is not None
    assert selected_instance.healthy
    assert selected_instance.enabled


@pytest.mark.asyncio
async def test_send_heartbeat(model_registry, model_instance):
    """
    Test if a heartbeat can be sent and that it correctly updates the last_heartbeat timestamp
    """
    await model_registry.register_instance(model_instance)
    last_heartbeat = datetime.now() - timedelta(seconds=10)
    model_instance.last_heartbeat = last_heartbeat
    assert await model_registry.send_heartbeat(model_instance) == True
    assert (
        model_registry.registry[model_instance.model_name][0].last_heartbeat
        > last_heartbeat
    )
    assert model_registry.registry[model_instance.model_name][0].healthy == True


@pytest.mark.asyncio
async def test_heartbeat_timeout(model_registry, model_instance):
    """
    Test if an instance is marked as unhealthy when the heartbeat is not sent within the timeout
    """
    model_registry = EmbeddedModelRegistry(1, 1)
    await model_registry.register_instance(model_instance)
    model_registry.registry[model_instance.model_name][
        0
    ].last_heartbeat = datetime.now() - timedelta(
        seconds=model_registry.heartbeat_timeout_secs + 1
    )
    await asyncio.sleep(model_registry.heartbeat_interval_secs + 1)
    assert not model_registry.registry[model_instance.model_name][0].healthy


@pytest.mark.asyncio
async def test_multiple_instances(model_registry, model_instance):
    """
    Test if multiple instances of the same model are handled correctly
    """
    model_instance2 = ModelInstance(
        model_name="test_model",
        host="192.168.1.2",
        port=5000,
    )
    await model_registry.register_instance(model_instance)
    await model_registry.register_instance(model_instance2)
    assert len(await model_registry.get_all_instances(model_instance.model_name)) == 2


@pytest.mark.asyncio
async def test_same_model_name_different_ip_port(model_registry):
    """
    Test if instances with the same model name but different IP and port are handled correctly
    """
    instance1 = ModelInstance(model_name="test_model", host="192.168.1.1", port=5000)
    instance2 = ModelInstance(model_name="test_model", host="192.168.1.2", port=6000)
    await model_registry.register_instance(instance1)
    await model_registry.register_instance(instance2)
    instances = await model_registry.get_all_instances("test_model")
    assert len(instances) == 2
    assert instances[0].host != instances[1].host
    assert instances[0].port != instances[1].port
