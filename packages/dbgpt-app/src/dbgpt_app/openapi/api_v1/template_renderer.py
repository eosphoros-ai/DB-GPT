"""Utilities for rendering the restricted HTML template syntax."""

import re
from typing import Any, Mapping

_PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")


def render_template_placeholders(template: str, replacements: Mapping[str, Any]) -> str:
    """Replace simple ``{{ key }}`` placeholders without evaluating code.

    Contract:
    - Whitespace around the identifier is allowed (``{{ key }}``) and keys are
      matched case-sensitively.
    - Only identifiers present in ``replacements`` are substituted.
    - Unknown placeholders are left untouched instead of being emptied, so
      template authors who intentionally keep literal double-brace text (e.g.
      frontend framework interpolation) are not silently affected.
    - Template expressions are never evaluated.
    """

    def _replace_placeholder(match: re.Match) -> str:
        key = match.group(1)
        if key in replacements:
            return str(replacements[key])
        return match.group(0)

    return _PLACEHOLDER_PATTERN.sub(_replace_placeholder, template)
