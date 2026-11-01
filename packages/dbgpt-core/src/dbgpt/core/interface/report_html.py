"""Normalize model serialization errors without rewriting report content."""

import json as _json
import re
from html import escape as _escape

_TAG = r"""<[a-zA-Z][\w:-]*\b(?:[^>"']|"[^"]*"|'[^']*')*>"""
_TOKENS = re.compile(
    r"""<!--.*?-->|<(?P<raw>script|style|textarea|title)\b"""
    r"""(?:[^>"']|"[^"]*"|'[^']*')*>.*?</(?P=raw)\s*>|"""
    + _TAG
    + r"""|(?<=>)"\s*\+\s*"(?=<)""",
    re.IGNORECASE | re.DOTALL,
)
_ATTRIBUTES = re.compile(
    r"""(?P<prefix>\s[\w:.-]+\s*=\s*)(?:\\(?P<quote>["'])"""
    r"""(?P<value>.*?)\\(?P=quote)(?=\s|/?>)|"[^"]*"|'[^']*'|[^\s>]+)""",
    re.DOTALL,
)
# ``data-dbgpt-artifact-selectors="{"id":{...}}"``: the model forgot that the
# inner JSON quotes also close a double-quoted HTML attribute.
_SELECTOR_JSON_ATTRIBUTE = re.compile(
    r"""(?P<prefix>\bdata-dbgpt-artifact-selectors\s*=\s*)"(?=\s*\{)""",
    re.IGNORECASE,
)


def _json_object_end(value: str, start: int):
    """Return the index just past the balanced JSON object, or ``None``."""
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(value)):
        char = value[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index + 1
        elif char == ">" and depth:
            return None
    return None


def _repair_unescaped_attribute_json(value: str) -> str:
    """Re-escape selector JSON written with raw double quotes in the attribute.

    Only a balanced JSON object that both parses and is immediately closed by
    the attribute quote is rewritten, and only into the escaped form the
    binding writer already produces. Everything else keeps its original bytes.
    """
    output = []
    search_index = 0
    output_index = 0
    repaired = False
    while True:
        match = _SELECTOR_JSON_ATTRIBUTE.search(value, search_index)
        if match is None:
            break
        start = value.index("{", match.end() - 1)
        end = _json_object_end(value, start)
        if end is None or end >= len(value) or value[end] != '"':
            search_index = match.end()
            continue
        raw = value[start:end]
        try:
            _json.loads(raw)
        except ValueError:
            search_index = match.end()
            continue
        output.append(value[output_index : match.end()])
        output.append(_escape(raw, quote=True))
        output.append('"')
        search_index = end + 1
        output_index = end + 1
        repaired = True
    if not repaired:
        return value
    output.append(value[output_index:])
    return "".join(output)


def normalize_report_html(value: str) -> str:
    """Repair escaped attribute delimiters before binding or DOM parsing.

    HTML has no backslash escape for attribute quotes. Only attributes whose
    opening and closing delimiters both carry an extra backslash are repaired.
    Selector JSON that closes its own attribute is re-escaped instead. Valid
    attributes, text, comments and raw element contents retain their original
    escaping. This is normalization, not sanitization.
    """
    if not value:
        return value
    value = _repair_unescaped_attribute_json(value)

    def attribute(match):
        quote = match["quote"]
        if not quote:
            return match[0]
        body = re.sub(r"""\\(["'])""", r"\1", match["value"])
        body = body.replace(quote, "&quot;" if quote == '"' else "&#39;")
        return f"{match['prefix']}{quote}{body}{quote}"

    def token(match):
        text = match[0]
        if not text.startswith("<"):
            return ""
        if text.startswith("<!--"):
            return text
        if match["raw"]:
            opening = re.match(_TAG, text)
            end = opening.end()
            return _ATTRIBUTES.sub(attribute, text[:end]) + text[end:]
        return _ATTRIBUTES.sub(attribute, text)

    return _TOKENS.sub(token, value)
