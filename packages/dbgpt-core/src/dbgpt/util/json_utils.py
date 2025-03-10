"""Utilities for the json_fixes package."""

import json
import logging
import re
from dataclasses import asdict, is_dataclass
from datetime import date, datetime

logger = logging.getLogger(__name__)

LLM_DEFAULT_RESPONSE_FORMAT = "llm_response_format_1"


def serialize(obj):
    if isinstance(obj, date):
        return obj.isoformat()


class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if is_dataclass(obj):
            return asdict(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, date):
            return obj.isoformat()
        return super().default(obj)


def extract_char_position(error_message: str) -> int:
    """Extract the character position from the JSONDecodeError message.

    Args:
        error_message (str): The error message from the JSONDecodeError
          exception.

    Returns:
        int: The character position.
    """

    char_pattern = re.compile(r"\(char (\d+)\)")
    if match := char_pattern.search(error_message):
        return int(match[1])
    else:
        raise ValueError("Character position not found in the error message.")


def find_json_objects(text):
    json_objects = []
    inside_string = False
    escape_character = False
    stack = []
    start_index = -1
    modified_text = list(text)  # Convert text to a list for easy modification

    for i, char in enumerate(text):
        # Handle escape characters
        if char == "\\" and not escape_character:
            escape_character = True
            continue

        # Toggle inside_string flag
        if char == '"' and not escape_character:
            inside_string = not inside_string

        # Replace newline and tab characters inside strings
        if inside_string:
            if char == "\n":
                modified_text[i] = "\\n"
            elif char == "\t":
                modified_text[i] = "\\t"

        # Handle opening brackets
        if char in "{[" and not inside_string:
            stack.append(char)
            if len(stack) == 1:
                start_index = i
        # Handle closing brackets
        if char in "}]" and not inside_string and stack:
            if (char == "}" and stack[-1] == "{") or (char == "]" and stack[-1] == "["):
                stack.pop()
                if not stack:
                    end_index = i + 1
                    try:
                        json_str = "".join(modified_text[start_index:end_index])
                        json_obj = json.loads(json_str)
                        json_objects.append(json_obj)
                    except json.JSONDecodeError:
                        pass
        # Reset escape_character flag
        escape_character = False if escape_character else escape_character

    return json_objects


@staticmethod
def _format_json_str(jstr):
    """Remove newlines outside of quotes, and handle JSON escape sequences.

    1. this function removes the newline in the query outside of quotes otherwise json.loads(s) will fail.
        Ex 1:
        "{\n"tool": "python",\n"query": "print('hello')\nprint('world')"\n}" -> "{"tool": "python","query": "print('hello')\nprint('world')"}"
        Ex 2:
        "{\n  \"location\": \"Boston, MA\"\n}" -> "{"location": "Boston, MA"}"

    2. this function also handles JSON escape sequences inside quotes,
        Ex 1:
        '{"args": "a\na\na\ta"}' -> '{"args": "a\\na\\na\\ta"}'
    """  # noqa
    result = []
    inside_quotes = False
    last_char = " "
    for char in jstr:
        if last_char != "\\" and char == '"':
            inside_quotes = not inside_quotes
        last_char = char
        if not inside_quotes and char == "\n":
            continue
        if inside_quotes and char == "\n":
            char = "\\n"
        if inside_quotes and char == "\t":
            char = "\\t"
        result.append(char)
    return "".join(result)


def compare_json_properties(json1, json2):
    """
    Check whether the attributes of two json are consistent
    """
    obj1 = json.loads(json1)
    obj2 = json.loads(json2)

    # 检查两个对象的键集合是否相同
    if set(obj1.keys()) == set(obj2.keys()):
        return True

    return False


def compare_json_properties_ex(json1, json2):
    """
    Check whether the attributes of two json are consistent
    """
    # 检查两个对象的键集合是否相同
    if set(json1.keys()) == set(json2.keys()):
        return True

    return False
