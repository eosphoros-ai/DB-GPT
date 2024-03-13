from typing import Any, Dict, List

import pytest

from dbgpt.util.function_utils import rearrange_args_by_type


class ChatPromptTemplate:
    pass


class BaseMessage:
    pass


class ModelMessage:
    pass


class DummyClass:
    @rearrange_args_by_type
    async def class_method(self, a: int, b: str, c: float):
        return a, b, c

    @rearrange_args_by_type
    async def merge_history(
        self,
        prompt: ChatPromptTemplate,
        history: List[BaseMessage],
        prompt_dict: Dict[str, Any],
    ) -> List[ModelMessage]:
        return [type(prompt), type(history), type(prompt_dict)]

    @rearrange_args_by_type
    def sync_class_method(self, a: int, b: str, c: float):
        return a, b, c


@rearrange_args_by_type
def sync_regular_function(a: int, b: str, c: float):
    return a, b, c


@rearrange_args_by_type
async def regular_function(a: int, b: str, c: float):
    return a, b, c


@pytest.mark.asyncio
async def test_class_method_correct_order():
    instance = DummyClass()
    result = await instance.class_method(1, "b", 3.0)
    assert result == (1, "b", 3.0), "Class method failed with correct order"


@pytest.mark.asyncio
async def test_class_method_incorrect_order():
    instance = DummyClass()
    result = await instance.class_method("b", 3.0, 1)
    assert result == (1, "b", 3.0), "Class method failed with incorrect order"


@pytest.mark.asyncio
async def test_regular_function_correct_order():
    result = await regular_function(1, "b", 3.0)
    assert result == (1, "b", 3.0), "Regular function failed with correct order"


@pytest.mark.asyncio
async def test_regular_function_incorrect_order():
    result = await regular_function("b", 3.0, 1)
    assert result == (1, "b", 3.0), "Regular function failed with incorrect order"


@pytest.mark.asyncio
async def test_merge_history_correct_order():
    instance = DummyClass()
    result = await instance.merge_history(
        ChatPromptTemplate(), [BaseMessage()], {"key": "value"}
    )
    assert result == [ChatPromptTemplate, list, dict], "Failed with correct order"


@pytest.mark.asyncio
async def test_merge_history_incorrect_order_1():
    instance = DummyClass()
    result = await instance.merge_history(
        [BaseMessage()], ChatPromptTemplate(), {"key": "value"}
    )
    assert result == [ChatPromptTemplate, list, dict], "Failed with incorrect order 1"


@pytest.mark.asyncio
async def test_merge_history_incorrect_order_2():
    instance = DummyClass()
    result = await instance.merge_history(
        {"key": "value"}, [BaseMessage()], ChatPromptTemplate()
    )
    assert result == [ChatPromptTemplate, list, dict], "Failed with incorrect order 2"


def test_sync_class_method_correct_order():
    instance = DummyClass()
    result = instance.sync_class_method(1, "b", 3.0)
    assert result == (1, "b", 3.0), "Sync class method failed with correct order"


def test_sync_class_method_incorrect_order():
    instance = DummyClass()
    result = instance.sync_class_method("b", 3.0, 1)
    assert result == (1, "b", 3.0), "Sync class method failed with incorrect order"


def test_sync_regular_function_correct_order():
    result = sync_regular_function(1, "b", 3.0)
    assert result == (1, "b", 3.0), "Sync regular function failed with correct order"


def test_sync_regular_function_incorrect_order():
    result = sync_regular_function("b", 3.0, 1)
    assert result == (1, "b", 3.0), "Sync regular function failed with incorrect order"
