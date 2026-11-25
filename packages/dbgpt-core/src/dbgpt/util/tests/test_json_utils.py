import json

import pytest

from dbgpt.util.json_utils import find_json_objects

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


@pytest.mark.parametrize("newline", ["\n", "\r", "\r\n"])
def test_find_json_objects_preserves_raw_line_endings(newline):
    content = "first" + newline + "second"
    text = '```json\n{"content":"' + content + '"}\n```'

    assert find_json_objects(text) == [{"content": content}]


@pytest.mark.parametrize("content", ["first\r\nsecond", r"first\r\nsecond"])
def test_find_json_objects_preserves_escaped_line_endings(content):
    text = json.dumps({"content": content})

    assert find_json_objects(text) == [{"content": content}]


def test_find_json_objects_accepts_crlf_whitespace_outside_strings():
    text = '\r\n{\r\n"content": "value"\r\n}\r\n'

    assert find_json_objects(text) == [{"content": "value"}]
