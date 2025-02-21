import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pytest

from dbgpt.core.interface.storage import InMemoryStorage
from dbgpt.util.serialization.json_serialization import JsonSerializer

from ...registry_impl.storage import (
    ModelInstance,
    ModelInstanceStorageItem,
    StorageModelRegistry,
)


@pytest.fixture
def in_memory_storage():
    return InMemoryStorage(serializer=JsonSerializer())


@pytest.fixture
def thread_pool_executor():
    return ThreadPoolExecutor(max_workers=2)


@pytest.fixture
def registry(in_memory_storage, thread_pool_executor):
    return StorageModelRegistry(
        storage=in_memory_storage,
        executor=thread_pool_executor,
        heartbeat_interval_secs=1,
        heartbeat_timeout_secs=2,
    )


@pytest.fixture
def model_instance():
    return ModelInstance(
        model_name="test_model",
        host="localhost",
        port=8080,
        weight=1.0,
        check_healthy=True,
        healthy=True,
        enabled=True,
        prompt_template=None,
        last_heartbeat=datetime.now(),
    )


@pytest.fixture
def model_instance_2():
    return ModelInstance(
        model_name="test_model",
        host="localhost",
        port=8081,
        weight=1.0,
        check_healthy=True,
        healthy=True,
        enabled=True,
        prompt_template=None,
        last_heartbeat=datetime.now(),
    )


@pytest.fixture
def model_instance_3():
    return ModelInstance(
        model_name="test_model_2",
        host="localhost",
        port=8082,
        weight=1.0,
        check_healthy=True,
        healthy=True,
        enabled=True,
        prompt_template=None,
        last_heartbeat=datetime.now(),
    )


@pytest.fixture
def model_instance_storage_item(model_instance):
    return ModelInstanceStorageItem.from_model_instance(model_instance)


@pytest.mark.asyncio
async def test_register_instance_new(registry, model_instance):
    """Test registering a new model instance."""
    result = await registry.register_instance(model_instance)

    assert result is True
    instances = await registry.get_all_instances(model_instance.model_name)
    assert len(instances) == 1
    saved_instance = instances[0]
    assert saved_instance.model_name == model_instance.model_name
    assert saved_instance.host == model_instance.host
    assert saved_instance.port == model_instance.port
    assert saved_instance.healthy is True
    assert saved_instance.last_heartbeat is not None


@pytest.mark.asyncio
async def test_register_instance_existing(
    registry, model_instance, model_instance_storage_item
):
    """Test registering an existing model instance and updating it."""
    await registry.register_instance(model_instance)

    # Register the instance again with updated heartbeat
    result = await registry.register_instance(model_instance)

    assert result is True
    instances = await registry.get_all_instances(model_instance.model_name)
    assert len(instances) == 1
    updated_instance = instances[0]
    assert updated_instance.model_name == model_instance.model_name
    assert updated_instance.host == model_instance.host
    assert updated_instance.port == model_instance.port
    assert updated_instance.healthy is True
    assert updated_instance.last_heartbeat is not None


@pytest.mark.asyncio
async def test_deregister_instance(registry, model_instance):
    """Test deregistering a model instance."""
    await registry.register_instance(model_instance)

    result = await registry.deregister_instance(model_instance)

    assert result is True
    instances = await registry.get_all_instances(model_instance.model_name)
    assert len(instances) == 1
    deregistered_instance = instances[0]
    assert deregistered_instance.healthy is False


@pytest.mark.asyncio
async def test_get_all_instances(registry, model_instance):
    """Test retrieving all model instances."""
    await registry.register_instance(model_instance)

    result = await registry.get_all_instances(
        model_instance.model_name, healthy_only=True
    )

    assert len(result) == 1
    assert result[0].model_name == model_instance.model_name


def test_sync_get_all_instances(registry, model_instance):
    """Test synchronously retrieving all model instances."""
    registry.sync_get_all_instances(model_instance.model_name, healthy_only=True)
    registry._storage.save(ModelInstanceStorageItem.from_model_instance(model_instance))

    result = registry.sync_get_all_instances(
        model_instance.model_name, healthy_only=True
    )

    assert len(result) == 1
    assert result[0].model_name == model_instance.model_name


@pytest.mark.asyncio
async def test_send_heartbeat_new_instance(registry, model_instance):
    """Test sending a heartbeat for a new instance."""
    result = await registry.send_heartbeat(model_instance)

    assert result is True
    instances = await registry.get_all_instances(model_instance.model_name)
    assert len(instances) == 1
    saved_instance = instances[0]
    assert saved_instance.model_name == model_instance.model_name


@pytest.mark.asyncio
async def test_send_heartbeat_existing_instance(registry, model_instance):
    """Test sending a heartbeat for an existing instance."""
    await registry.register_instance(model_instance)

    # Send heartbeat to update the instance
    result = await registry.send_heartbeat(model_instance)

    assert result is True
    instances = await registry.get_all_instances(model_instance.model_name)
    assert len(instances) == 1
    updated_instance = instances[0]
    assert updated_instance.last_heartbeat > model_instance.last_heartbeat


@pytest.mark.asyncio
async def test_heartbeat_checker(
    in_memory_storage, thread_pool_executor, model_instance
):
    """Test the heartbeat checker mechanism."""
    heartbeat_timeout_secs = 1
    registry = StorageModelRegistry(
        storage=in_memory_storage,
        executor=thread_pool_executor,
        heartbeat_interval_secs=0.1,
        heartbeat_timeout_secs=heartbeat_timeout_secs,
    )

    async def check_heartbeat(model_name: str, expected_healthy: bool):
        instances = await registry.get_all_instances(model_name)
        assert len(instances) == 1
        updated_instance = instances[0]
        assert updated_instance.healthy == expected_healthy

    await registry.register_instance(model_instance)
    # First heartbeat should be successful
    await check_heartbeat(model_instance.model_name, True)
    # Wait heartbeat timeout
    await asyncio.sleep(heartbeat_timeout_secs + 0.5)
    await check_heartbeat(model_instance.model_name, False)

    # Send heartbeat again
    await registry.send_heartbeat(model_instance)
    # Should be healthy again
    await check_heartbeat(model_instance.model_name, True)
