"""Utilities for the json_fixes package."""
import json
from datetime import date, datetime
import os.path
import re
import logging

from jsonschema import Draft7Validator

logger = logging.getLogger(__name__)

LLM_DEFAULT_RESPONSE_FORMAT = "llm_response_format_1"



def serialize(obj):
    if isinstance(obj, date):
        return obj.isoformat()


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
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


