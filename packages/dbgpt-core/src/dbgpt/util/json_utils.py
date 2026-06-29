"""Utilities for the json_fixes package."""

import json
import logging
import re
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, time

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
        if isinstance(obj, time):
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


def find_json_objects(text: str):
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


def parse_or_raise_error(text: str, is_array: bool = False):
    if not text:
        return None
    parsed_objs = find_json_objects(text)
    if not parsed_objs:
        # Use json.loads to raise raw error
        return json.loads(text)
    return parsed_objs if is_array else parsed_objs[0]


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


def _strip_json_code_fence(text: str) -> str:
    """Strip a leading/trailing Markdown code fence from a JSON string.

    LLMs frequently wrap JSON payloads in fenced code blocks such as
    ``` ```json ... ``` ```. This helper removes a single surrounding fence
    (optionally tagged with a language such as ``json``) so the inner payload
    can be parsed. If no fence is detected the text is returned unchanged.
    """
    stripped = text.strip()
    if not stripped.startswith("```"):
        return text
    # Drop the opening fence line (``` or ```json etc.)
    lines = stripped.split("\n")
    lines = lines[1:]
    # Drop the closing fence line if present.
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines)


def _strip_json_comments(text: str) -> str:
    """Remove ``//`` and ``/* */`` comments that live outside of strings.

    Comments are not valid JSON but are commonly emitted by language models.
    Characters inside double-quoted strings (respecting escapes) are preserved.
    """
    result = []
    inside_string = False
    escape = False
    i = 0
    n = len(text)
    while i < n:
        char = text[i]
        if inside_string:
            result.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                inside_string = False
            i += 1
            continue
        # Not inside a string.
        if char == '"':
            inside_string = True
            result.append(char)
            i += 1
            continue
        if char == "/" and i + 1 < n and text[i + 1] == "/":
            # Line comment: skip until end of line.
            i += 2
            while i < n and text[i] != "\n":
                i += 1
            continue
        if char == "/" and i + 1 < n and text[i + 1] == "*":
            # Block comment: skip until closing */.
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue
        result.append(char)
        i += 1
    return "".join(result)


def _remove_trailing_commas(text: str) -> str:
    """Remove trailing commas before ``}`` or ``]`` that live outside strings.

    Example: ``{"a": 1,}`` becomes ``{"a": 1}``. Commas inside double-quoted
    strings (respecting escapes) are preserved.
    """
    result = []
    inside_string = False
    escape = False
    for char in text:
        if inside_string:
            result.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                inside_string = False
            continue
        if char == '"':
            inside_string = True
            result.append(char)
            continue
        if char in "}]":
            # Walk back over any whitespace, dropping a trailing comma.
            j = len(result) - 1
            while j >= 0 and result[j] in " \t\r\n":
                j -= 1
            if j >= 0 and result[j] == ",":
                del result[j]
        result.append(char)
    return "".join(result)


def repair_json(text: str) -> str:
    """Best-effort repair of common JSON defects in LLM output.

    Applies, in order:

    1. Strips a surrounding Markdown code fence (e.g. ```` ```json ... ``` ````).
    2. Removes ``//`` line comments and ``/* */`` block comments.
    3. Removes trailing commas before ``}`` or ``]``.

    All transformations preserve the contents of double-quoted strings. The
    result is a string that is more likely to parse with ``json.loads`` but is
    not guaranteed to be valid JSON.

    Args:
        text (str): The raw text to repair.

    Returns:
        str: The repaired text.
    """
    if not text:
        return text
    repaired = _strip_json_code_fence(text)
    repaired = _strip_json_comments(repaired)
    repaired = _remove_trailing_commas(repaired)
    return repaired.strip()


def loads_robust(text: str, **kwargs):
    """Parse JSON, falling back to a repaired version on failure.

    First attempts a strict ``json.loads``. If that raises
    ``json.JSONDecodeError``, the text is run through :func:`repair_json`
    (stripping code fences, comments and trailing commas) and parsed again.
    This is convenient for tolerating the small defects commonly present in
    language-model JSON output without giving up strictness on well-formed
    input.

    Args:
        text (str): The JSON text to parse.
        **kwargs: Extra keyword arguments forwarded to ``json.loads``.

    Returns:
        The parsed Python object.

    Raises:
        json.JSONDecodeError: If the text cannot be parsed even after repair.
    """
    try:
        return json.loads(text, **kwargs)
    except json.JSONDecodeError:
        return json.loads(repair_json(text), **kwargs)


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
