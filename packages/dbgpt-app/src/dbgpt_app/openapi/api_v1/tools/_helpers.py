"""Shared helper utilities for built-in tools."""

import re
from typing import Dict, Tuple

_AUTO_DATA_MARKER_PATTERN = re.compile(
    r"###([A-Z0-9_]+)_START###\s*(.*?)\s*###\1_END###", re.DOTALL
)


def _extract_auto_data_markers(text: str) -> Tuple[str, Dict[str, str]]:
    """Extract AUTO_DATA markers from text and return (cleaned_text, data_dict)."""
    extracted: Dict[str, str] = {}

    def _replacer(m: re.Match) -> str:
        extracted[m.group(1)] = m.group(2)
        return ""

    cleaned = _AUTO_DATA_MARKER_PATTERN.sub(_replacer, text)
    return cleaned.strip(), extracted
