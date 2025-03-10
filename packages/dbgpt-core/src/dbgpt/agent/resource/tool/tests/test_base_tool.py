import asyncio
import json
from typing import Dict, List, Optional

import pytest
from typing_extensions import Annotated, Doc

from dbgpt._private.pydantic import BaseModel, Field

from ..base import BaseTool, FunctionTool, ToolParameter, tool


class TestBaseTool(BaseTool):
    @property
    def name(self):
        return "test_tool"

    @property
    def description(self):
        return "This is a test tool."

    @property
    def args(self):
        return {}

    def execute(self, *args, **kwargs):
        return "executed"

    async def async_execute(self, *args, **kwargs):
        return "async executed"


def test_base_tool():
    tool = TestBaseTool()
    assert tool.name == "test_tool"
    assert tool.description == "This is a test tool."
    assert tool.execute() == "executed"
    assert asyncio.run(tool.async_execute()) == "async executed"


def test_function_tool_sync() -> None:
    def two_sum(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    ft = FunctionTool(name="sample", func=two_sum)
    assert ft.execute(1, 2) == 3
    with pytest.raises(ValueError):
        asyncio.run(ft.async_execute(1, 2))


@pytest.mark.asyncio
async def test_function_tool_async() -> None:
    async def sample_async_func(a: int, b: int) -> int:
        """Add two numbers asynchronously."""
        return a + b

    ft = FunctionTool(name="sample_async", func=sample_async_func)
    with pytest.raises(ValueError):
        ft.execute(1, 2)
    assert await ft.async_execute(1, 2) == 3


@pytest.mark.asyncio
async def test_function_tool_sync_with_args() -> None:
    def two_sum(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    ft = FunctionTool(
        name="sample",
        func=two_sum,
        args={
            "a": {"type": "integer", "name": "a", "description": "The first number."},
            "b": {"type": "integer", "name": "b", "description": "The second number."},
        },
    )
    ft1 = FunctionTool(
        name="sample",
        func=two_sum,
        args={
            "a": ToolParameter(
                type="integer", name="a", description="The first number."
            ),
            "b": ToolParameter(
                type="integer", name="b", description="The second number."
            ),
        },
    )
    assert ft.description == "Add two numbers."
    assert ft.args.keys() == {"a", "b"}
    assert ft.args["a"].type == "integer"
    assert ft.args["a"].name == "a"
    assert ft.args["a"].description == "The first number."
    assert ft.args["a"].title == "A"
    dict_params = [
        {
            "name": "a",
            "type": "integer",
            "description": "The first number.",
            "required": True,
        },
        {
            "name": "b",
            "type": "integer",
            "description": "The second number.",
            "required": True,
        },
    ]
    json_params = json.dumps(dict_params, ensure_ascii=False)
    expected_prompt = (
        f"sample: Call this tool to interact with the sample API. What is the "
        f"sample API useful for? Add two numbers. Parameters: {json_params}"
    )
    pmt, info = await ft.get_prompt()
    pmt1, info1 = await ft1.get_prompt()
    assert pmt == expected_prompt
    assert pmt1 == expected_prompt
    assert ft.execute(1, 2) == 3
    with pytest.raises(ValueError):
        await ft.async_execute(1, 2)


def test_function_tool_sync_with_complex_types() -> None:
    @tool
    def complex_func(
        a: int,
        b: Annotated[int, Doc("The second number.")],
        c: Annotated[str, Doc("The third string.")],
        d: List[int],
        e: Annotated[Dict[str, int], Doc("A dictionary of integers.")],
        f: Optional[float] = None,
        g: str | None = None,
    ) -> int:
        """A complex function."""
        return (
            a + b + len(c) + sum(d) + sum(e.values()) + (f or 0) + (len(g) if g else 0)
        )

    ft: FunctionTool = complex_func._tool
    assert ft.description == "A complex function."
    assert ft.args.keys() == {"a", "b", "c", "d", "e", "f", "g"}
    assert ft.args["a"].type == "integer"
    assert ft.args["a"].description == "A"
    assert ft.args["b"].type == "Annotated"
    assert ft.args["b"].description == "The second number."
    assert ft.args["c"].type == "Annotated"
    assert ft.args["c"].description == "The third string."
    assert ft.args["d"].type == "array"
    assert ft.args["d"].description == "D"
    assert ft.args["e"].type == "object"
    assert ft.args["e"].description == "A dictionary of integers."
    assert ft.args["f"].type == "number"
    assert ft.args["f"].description == "F"
    assert ft.args["g"].type == "string"
    assert ft.args["g"].description == "G"


def test_function_tool_sync_with_args_schema() -> None:
    class ArgsSchema(BaseModel):
        a: int = Field(description="The first number.")
        b: int = Field(description="The second number.")
        c: Optional[str] = Field(None, description="The third string.")
        d: List[int] = Field(description="Numbers.")

    @tool(args_schema=ArgsSchema)
    def complex_func(a: int, b: int, c: Optional[str] = None) -> int:
        """A complex function."""
        return a + b + len(c) if c else 0

    ft: FunctionTool = complex_func._tool
    assert ft.description == "A complex function."
    assert ft.args.keys() == {"a", "b", "c", "d"}
    assert ft.args["a"].type == "integer"
    assert ft.args["a"].description == "The first number."
    assert ft.args["b"].type == "integer"
    assert ft.args["b"].description == "The second number."
    assert ft.args["c"].type == "string"
    assert ft.args["c"].description == "The third string."
    assert ft.args["d"].type == "array"
    assert ft.args["d"].description == "Numbers."


def test_tool_decorator() -> None:
    @tool(description="Add two numbers")
    def add(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    assert add(1, 2) == 3
    assert add._tool.name == "add"
    assert add._tool.description == "Add two numbers"


@pytest.mark.asyncio
async def test_tool_decorator_async() -> None:
    @tool
    async def async_add(a: int, b: int) -> int:
        """Asynchronously add two numbers."""
        return a + b

    assert await async_add(1, 2) == 3
