"""Utilities for the json_fixes package."""
import json
import os.path
import re
import json
import logging
from datetime import datetime

from jsonschema import Draft7Validator

from pilot.configs.config import Config

logger = logging.getLogger(__name__)

CFG = Config()
LLM_DEFAULT_RESPONSE_FORMAT = "llm_response_format_1"


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


def validate_json(json_object: object, schema_name: str) -> dict | None:
    """
    :type schema_name: object
    :param schema_name: str
    :type json_object: object
    """
    scheme_file = os.path.join(os.path.dirname(__file__), f"{schema_name}.json")
    with open(scheme_file, "r") as f:
        schema = json.load(f)
    validator = Draft7Validator(schema)

    if errors := sorted(validator.iter_errors(json_object), key=lambda e: e.path):
        logger.error("The JSON object is invalid.")
        if CFG.debug_mode:
            logger.error(
                json.dumps(json_object, indent=4)
            )  # Replace 'json_object' with the variable containing the JSON data
            logger.error("The following issues were found:")

            for error in errors:
                logger.error(f"Error: {error.message}")
    else:
        logger.debug("The JSON object is valid.")

    return json_object


def validate_json_string(json_string: str, schema_name: str) -> dict | None:
    """
    :type schema_name: object
    :param schema_name: str
    :type json_object: object
    """

    try:
        json_loaded = json.loads(json_string)
        return validate_json(json_loaded, schema_name)
    except:
        return None


def is_string_valid_json(json_string: str, schema_name: str) -> bool:
    """
    :type schema_name: object
    :param schema_name: str
    :type json_object: object
    """

    return validate_json_string(json_string, schema_name) is not None




def find_json_objects(text):
    json_objects = []
    inside_string = False
    escape_character = False
    stack = []
    start_index = -1

    for i, char in enumerate(text):
        # Handle escape characters
        if char == "\\" and not escape_character:
            escape_character = True
            continue

        # Toggle inside_string flag
        if char == '"' and not escape_character:
            inside_string = not inside_string

        if not inside_string and char == "\n":
            continue
        if inside_string and char == "\n":
            char = "\\n"
        if inside_string and char == "\t":
            char = "\\t"

        # Handle opening brackets
        if char in '{[' and not inside_string:
            stack.append(char)
            if len(stack) == 1:
                start_index = i
        # Handle closing brackets
        if char in '}]' and not inside_string and stack:
            if (char == '}' and stack[-1] == '{') or (char == ']' and stack[-1] == '['):
                stack.pop()
                if not stack:
                    end_index = i + 1
                    try:
                        json_obj = json.loads(text[start_index:end_index])
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
    """
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


if __name__ == "__main__":
    # 示例文本，包含多个JSON对象和数组
    text = """

        """
    # 使用函数查找和解析文本中的所有JSON对象和数组
    json_objects = find_json_objects(text)
    print(json_objects)


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)
