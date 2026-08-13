"""Utilities for rendering the restricted HTML template syntax."""

import re
from typing import Any, Mapping

_PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")


def render_template_placeholders(template: str, replacements: Mapping[str, Any]) -> str:
    """Replace simple ``{{ key }}`` placeholders without evaluating code."""

    def _replace_placeholder(match: re.Match) -> str:
        key = match.group(1)
        return str(replacements.get(key, ""))

    return _PLACEHOLDER_PATTERN.sub(_replace_placeholder, template)
