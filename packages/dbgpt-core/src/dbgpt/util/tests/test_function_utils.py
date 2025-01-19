from typing import Any, Dict, List, Optional, Tuple

import pytest

from dbgpt.util.function_utils import rearrange_args_by_type, type_to_string


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


def test_base_type_to_string():
    assert type_to_string(int) == ("integer", []), "Failed with base type"
    assert type_to_string(str) == ("string", []), "Failed with base type"
    assert type_to_string(float) == ("number", []), "Failed with base type"
    assert type_to_string(bool) == ("boolean", []), "Failed with base type"
    assert type_to_string(None) == ("null", []), "Failed with base type"


def test_list_type_to_string():
    assert type_to_string(List[int]) == ("array", ["integer"]), "Failed with list type"
    assert type_to_string(List[str]) == ("array", ["string"]), "Failed with list type"
    assert type_to_string(List[float]) == ("array", ["number"]), "Failed with list type"
    assert type_to_string(List[bool]) == ("array", ["boolean"]), "Failed with list type"
    assert type_to_string(List[None]) == ("array", ["null"]), "Failed with list type"
    assert type_to_string(List[List[int]]) == (
        "array",
        ["array"],
    ), "Failed with list type"
    assert type_to_string(List[List[str]]) == (
        "array",
        ["array"],
    ), "Failed with list type"
    assert type_to_string(List[List[float]]) == (
        "array",
        ["array"],
    ), "Failed with list type"
    assert type_to_string(List[List[bool]]) == (
        "array",
        ["array"],
    ), "Failed with list type"
    assert type_to_string(List[List[None]]) == (
        "array",
        ["array"],
    ), "Failed with list type"


def test_dict_type_to_string():
    assert type_to_string(Dict[str, int]) == ("object", []), "Failed with dict type"
    assert type_to_string(Dict[str, str]) == ("object", []), "Failed with dict type"
    assert type_to_string(Dict[str, float]) == ("object", []), "Failed with dict type"
    assert type_to_string(Dict[str, bool]) == ("object", []), "Failed with dict type"
    assert type_to_string(Dict[str, None]) == ("object", []), "Failed with dict type"
    assert type_to_string(Dict[str, List[int]]) == (
        "object",
        [],
    ), "Failed with dict type"
    assert type_to_string(Dict[str, List[str]]) == (
        "object",
        [],
    ), "Failed with dict type"
    assert type_to_string(Dict[str, List[float]]) == (
        "object",
        [],
    ), "Failed with dict type"
    assert type_to_string(Dict[str, List[bool]]) == (
        "object",
        [],
    ), "Failed with dict type"
    assert type_to_string(Dict[str, List[None]]) == (
        "object",
        [],
    ), "Failed with dict type"
    assert type_to_string(Dict[str, Dict[str, int]]) == (
        "object",
        [],
    ), "Failed with dict type"
    assert type_to_string(Dict[str, Dict[str, str]]) == (
        "object",
        [],
    ), "Failed with dict type"
    assert type_to_string(Dict[str, Dict[str, float]]) == (
        "object",
        [],
    ), "Failed with dict type"
    assert type_to_string(Dict[str, Dict[str, bool]]) == (
        "object",
        [],
    ), "Failed with dict type"
    assert type_to_string(Dict[str, Dict[str, None]]) == (
        "object",
        [],
    ), "Failed with dict type"
    assert type_to_string(Dict[str, Dict[str, List[int]]]) == (
        "object",
        [],
    ), "Failed with dict type"
    assert type_to_string(Dict[str, Dict[str, List[str]]]) == (
        "object",
        [],
    ), "Failed with dict type"
    assert type_to_string(Dict[str, Dict[str, List[float]]]) == (
        "object",
        [],
    ), "Failed with dict type"
    assert type_to_string(Dict[str, Dict[str, List[bool]]]) == (
        "object",
        [],
    ), "Failed with dict type"
    assert type_to_string(Dict[str, Dict[str, List[None]]]) == (
        "object",
        [],
    ), "Failed with dict type"


def test_optional_type_to_string():
    assert type_to_string(Optional[int]) == ("integer", []), "Failed with optional type"
    assert type_to_string(Optional[str]) == ("string", []), "Failed with optional type"
    assert type_to_string(Optional[float]) == (
        "number",
        [],
    ), "Failed with optional type"
    assert type_to_string(Optional[bool]) == (
        "boolean",
        [],
    ), "Failed with optional type"
    assert type_to_string(Optional[None]) == ("null", []), "Failed with optional type"


def test_complex_optional_type_to_string():
    assert type_to_string(Optional[List[int]]) == (
        "array",
        ["integer"],
    ), "Failed with optional type"
    assert type_to_string(Optional[List[str]]) == (
        "array",
        ["string"],
    ), "Failed with optional type"
    assert type_to_string(Optional[List[float]]) == (
        "array",
        ["number"],
    ), "Failed with optional type"
    assert type_to_string(Optional[List[bool]]) == (
        "array",
        ["boolean"],
    ), "Failed with optional type"
    assert type_to_string(Optional[List[None]]) == (
        "array",
        ["null"],
    ), "Failed with optional type"
    assert type_to_string(Optional[Dict[str, int]]) == (
        "object",
        [],
    ), "Failed with optional type"
    assert type_to_string(Optional[Dict[str, str]]) == (
        "object",
        [],
    ), "Failed with optional type"
    assert type_to_string(Optional[Dict[str, float]]) == (
        "object",
        [],
    ), "Failed with optional type"
    assert type_to_string(Optional[Dict[str, bool]]) == (
        "object",
        [],
    ), "Failed with optional type"
    assert type_to_string(Optional[Dict[str, None]]) == (
        "object",
        [],
    ), "Failed with optional type"
    assert type_to_string(Optional[Dict[str, List[int]]]) == (
        "object",
        [],
    ), "Failed with optional type"
    assert type_to_string(Optional[Dict[str, List[str]]]) == (
        "object",
        [],
    ), "Failed with optional type"
    assert type_to_string(Optional[Dict[str, List[float]]]) == (
        "object",
        [],
    ), "Failed with optional type"
    assert type_to_string(Optional[Dict[str, List[bool]]]) == (
        "object",
        [],
    ), "Failed with optional type"
    assert type_to_string(Optional[Dict[str, List[None]]]) == (
        "object",
        [],
    ), "Failed with optional type"
    assert type_to_string(Optional[Dict[str, Dict[str, int]]]) == (
        "object",
        [],
    ), "Failed with optional type"


def test_new_optional_type_to_string():
    assert type_to_string(int | None) == ("integer", []), "Failed with optional type"
    assert type_to_string(str | None) == ("string", []), "Failed with optional type"
    assert type_to_string(float | None) == ("number", []), "Failed with optional type"
    assert type_to_string(bool | None) == ("boolean", []), "Failed with optional type"
    assert type_to_string(List[int] | None) == (
        "array",
        ["integer"],
    ), "Failed with optional type"
    assert type_to_string(Dict[str, int] | None) == (
        "object",
        [],
    ), "Failed with optional type"


def test_tuple_type_to_string():
    assert type_to_string(Tuple[int, str, float]) == (
        "array",
        ["integer", "string", "number"],
    ), "Failed with tuple type"
    assert type_to_string(Tuple[str, int, float]) == (
        "array",
        ["string", "integer", "number"],
    ), "Failed with tuple type"
    assert type_to_string(Tuple[float, str, int]) == (
        "array",
        ["number", "string", "integer"],
    ), "Failed with tuple type"
    assert type_to_string(Tuple[bool, int, str]) == (
        "array",
        ["boolean", "integer", "string"],
    ), "Failed with tuple type"
    assert type_to_string(Tuple[None, str, int]) == (
        "array",
        ["null", "string", "integer"],
    ), "Failed with tuple type"


def test_new_tuple_type_to_string():
    assert type_to_string(tuple) == ("array", []), "Failed with tuple type"
