import json

import pytest

from dbgpt.util.json_utils import find_json_objects, loads_robust, repair_json

# 定义参数化测试数据
test_data = [
    (
        """
        ```json

          {
            "serial_number": "1",
            "agent": "CodeOptimizer",
            "content": "```json
select * 
from table
where column = 'value'
``` optimize the code above.",
            "rely": ""
          }
        ```
        """,
        [
            {
                "serial_number": "1",
                "agent": "CodeOptimizer",
                "content": "```json\nselect * \nfrom table\nwhere column = 'value'\n```"
                " optimize the code above.",
                "rely": "",
            }
        ],
        "Test case with nested code block",
    ),
    (
        """
        {
            "key": "value"
        }
        """,
        [{"key": "value"}],
        "Test case with simple JSON",
    ),
    (
        """
        {
            "key1": "value1"
        }
        {
            "key2": "value2"
        }
        """,
        [{"key1": "value1"}, {"key2": "value2"}],
        "Test case with multiple JSON objects",
    ),
    ("", [], "Test case with empty input"),
    ("This is not a JSON string", [], "Test case with non-JSON input"),
]


@pytest.mark.parametrize("text, expected, description", test_data)
def test_find_json_objects(text, expected, description):
    result = find_json_objects(text)
    assert result == expected, (
        f"Test failed: {description}\nExpected: {expected}\nGot: {result}"
    )


repair_data = [
    (
        '{"a": 1, "b": 2,}',
        {"a": 1, "b": 2},
        "Trailing comma in object",
    ),
    (
        '{"a": [1, 2, 3,]}',
        {"a": [1, 2, 3]},
        "Trailing comma in array",
    ),
    (
        '```json\n{"a": 1}\n```',
        {"a": 1},
        "Fenced json code block",
    ),
    (
        '```\n{"a": 1}\n```',
        {"a": 1},
        "Fenced code block without language",
    ),
    (
        '{\n  // a comment\n  "a": 1\n}',
        {"a": 1},
        "Line comment",
    ),
    (
        '{"a": 1 /* inline */, "b": 2}',
        {"a": 1, "b": 2},
        "Block comment",
    ),
    (
        '```json\n{\n  "a": 1, // trailing\n  "b": [1, 2,],\n}\n```',
        {"a": 1, "b": [1, 2]},
        "Combined fence + comment + trailing commas",
    ),
    (
        '{"a": "value, with comma,", "b": "http://x.com"}',
        {"a": "value, with comma,", "b": "http://x.com"},
        "Defect-like characters inside strings are preserved",
    ),
]


@pytest.mark.parametrize("text, expected, description", repair_data)
def test_loads_robust(text, expected, description):
    result = loads_robust(text)
    assert result == expected, (
        f"Test failed: {description}\nExpected: {expected}\nGot: {result}"
    )


def test_loads_robust_passthrough_valid_json():
    """Well-formed JSON must parse identically to json.loads."""
    text = '{"a": 1, "b": [1, 2, 3], "c": "x"}'
    assert loads_robust(text) == json.loads(text)


def test_loads_robust_raises_on_unrepairable():
    with pytest.raises(json.JSONDecodeError):
        loads_robust("{not valid at all")


def test_repair_json_preserves_string_contents():
    text = '{"note": "keep // this and , this"}'
    # No structural defects outside strings -> unchanged content semantics.
    assert json.loads(repair_json(text)) == {"note": "keep // this and , this"}


def test_repair_json_empty():
    assert repair_json("") == ""
