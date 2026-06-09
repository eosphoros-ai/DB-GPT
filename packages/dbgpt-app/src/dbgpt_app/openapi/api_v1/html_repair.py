"""HTML validation and repair helpers for generated report artifacts."""

from __future__ import annotations

import html as html_lib
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import List, Optional

_VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}

_OPTIONAL_CLOSE_TAGS = {"li", "p", "td", "th", "tr"}
_RAW_TEXT_TAGS = {"script", "style", "textarea", "title"}
_TRACKED_TAGS = {
    "html",
    "head",
    "body",
    "main",
    "section",
    "article",
    "header",
    "footer",
    "nav",
    "aside",
    "div",
    "span",
    "p",
    "table",
    "thead",
    "tbody",
    "tfoot",
    "tr",
    "td",
    "th",
    "ul",
    "ol",
    "li",
    "script",
    "style",
    "canvas",
    "svg",
}


@dataclass
class HtmlValidationResult:
    """Structured result for report HTML integrity checks."""

    is_valid: bool
    missing_required_tags: List[str] = field(default_factory=list)
    unclosed_tags: List[str] = field(default_factory=list)
    mismatched_tags: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)


HtmlAiRepair = Callable[[str, HtmlValidationResult], Awaitable[Optional[str]]]


class _TagBalanceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.stack: List[str] = []
        self.mismatched_tags: List[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        tag = tag.lower()
        if tag in _VOID_TAGS or tag not in _TRACKED_TAGS:
            return
        if tag in _OPTIONAL_CLOSE_TAGS and self.stack and self.stack[-1] == tag:
            self.stack.pop()
        self.stack.append(tag)

    def handle_startendtag(self, tag: str, attrs) -> None:  # noqa: ANN001
        return

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag not in _TRACKED_TAGS:
            return
        if tag not in self.stack:
            self.mismatched_tags.append(tag)
            return
        while self.stack:
            current = self.stack.pop()
            if current == tag:
                return
            self.mismatched_tags.append(current)


def validate_html_integrity(html: str) -> HtmlValidationResult:
    """Validate that generated HTML has the minimum structure for rendering."""

    text = (html or "").strip()
    missing: List[str] = []
    issues: List[str] = []
    if not text:
        return HtmlValidationResult(
            is_valid=False,
            missing_required_tags=["html", "head", "body"],
            issues=["empty_html"],
        )

    lower = text.lower()
    required_patterns = {
        "doctype": r"^\s*<!doctype\s+html\b",
        "html": r"<html\b",
        "/html": r"</html\s*>",
        "head": r"<head\b",
        "/head": r"</head\s*>",
        "body": r"<body\b",
        "/body": r"</body\s*>",
    }
    for label, pattern in required_patterns.items():
        if not re.search(pattern, lower, flags=re.IGNORECASE):
            missing.append(label)

    if re.search(r"<\\+\s*/\s*[a-z][a-z0-9:-]*\s*>", text, flags=re.IGNORECASE):
        issues.append("escaped_closing_tag")

    parser = _TagBalanceParser()
    parser.feed(text)
    parser.close()
    unclosed = [tag for tag in parser.stack if tag in _TRACKED_TAGS]
    all_issues = issues[:]
    all_issues.extend(f"missing:{tag}" for tag in missing)
    all_issues.extend(f"unclosed:{tag}" for tag in unclosed)
    all_issues.extend(f"mismatched:{tag}" for tag in parser.mismatched_tags)

    return HtmlValidationResult(
        is_valid=not missing and not unclosed and not parser.mismatched_tags,
        missing_required_tags=missing,
        unclosed_tags=unclosed,
        mismatched_tags=parser.mismatched_tags,
        issues=all_issues,
    )


def prepare_renderable_html(html: str, title: str = "Report") -> str:
    """Repair generated HTML enough to be safely rendered in the report iframe."""

    fixed = _strip_markdown_fence((html or "").strip())
    fixed = _remove_control_chars(fixed)
    fixed = _normalize_escaped_closing_tags(fixed)
    fixed = _ensure_document_shell(fixed, title)
    fixed = _append_missing_closing_tags(fixed)
    fixed = _ensure_required_tail(fixed)
    return fixed


async def repair_html_if_needed(
    html: str,
    title: str = "Report",
    ai_repair: Optional[HtmlAiRepair] = None,
) -> str:
    """Validate generated HTML and repair it when it is not renderable.

    AI repair is attempted first when provided. If the AI result is missing or
    still invalid, deterministic repair is used as the final fallback.
    """

    raw_html = (html or "").strip()
    validation = validate_html_integrity(raw_html)
    if validation.is_valid:
        return raw_html

    if ai_repair:
        try:
            ai_result = await ai_repair(raw_html, validation)
        except Exception:
            ai_result = None
        ai_html = _extract_html_from_ai_response(ai_result or "")
        if ai_html:
            ai_validation = validate_html_integrity(ai_html)
            if ai_validation.is_valid:
                return ai_html
            ai_fallback = prepare_renderable_html(ai_html, title)
            if validate_html_integrity(ai_fallback).is_valid:
                return ai_fallback

    return prepare_renderable_html(raw_html, title)


def _strip_markdown_fence(text: str) -> str:
    match = re.fullmatch(r"\s*```(?:html)?\s*(.*?)\s*```\s*", text, re.I | re.S)
    if match:
        return match.group(1).strip()
    return text


def _extract_html_from_ai_response(text: str) -> str:
    """Extract HTML when the model wraps the repaired document in prose."""

    text = (text or "").strip()
    if not text:
        return ""

    fenced = _strip_markdown_fence(text)
    if fenced != text:
        return fenced

    for match in re.finditer(
        r"```(?:html)?\s*(.*?)```",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        candidate = match.group(1).strip()
        if re.search(r"<html\b|<!doctype\s+html\b", candidate, flags=re.IGNORECASE):
            return candidate

    match = re.search(
        r"(?is)(<!doctype\s+html\b.*?</html>|<html\b.*?</html>)",
        text,
    )
    if match:
        return match.group(1).strip()
    return text


def _remove_control_chars(text: str) -> str:
    return "".join(ch for ch in text if ch in "\n\r\t" or ord(ch) >= 32)


def _normalize_escaped_closing_tags(text: str) -> str:
    return re.sub(
        r"<\\+\s*/\s*([A-Za-z][A-Za-z0-9:-]*)\s*>",
        r"</\1>",
        text,
        flags=re.IGNORECASE,
    )


def _ensure_document_shell(text: str, title: str) -> str:
    escaped_title = html_lib.escape(title or "Report", quote=False)
    lower = text.lower()

    if not re.search(r"<html\b", lower):
        body = text
        return (
            "<!DOCTYPE html><html><head>"
            f"<meta charset=\"utf-8\"><title>{escaped_title}</title>"
            f"</head><body>{body}</body></html>"
        )

    fixed = text
    if not re.search(r"^\s*<!doctype\s+html\b", fixed, flags=re.I):
        fixed = "<!DOCTYPE html>" + fixed

    if not re.search(r"<head\b", fixed, flags=re.I):
        fixed = re.sub(
            r"(<html\b[^>]*>)",
            r"\1<head><meta charset=\"utf-8\"></head>",
            fixed,
            count=1,
            flags=re.I,
        )
    if not re.search(r"<title\b", fixed, flags=re.I):
        fixed = re.sub(
            r"(</head\s*>)",
            f"<title>{escaped_title}</title>" + r"\1",
            fixed,
            count=1,
            flags=re.I,
        )
    if not re.search(r"<body\b", fixed, flags=re.I):
        if re.search(r"</head\s*>", fixed, flags=re.I):
            fixed = re.sub(
                r"(</head\s*>)",
                r"\1<body>",
                fixed,
                count=1,
                flags=re.I,
            )
        else:
            fixed = re.sub(
                r"(<html\b[^>]*>)",
                r"\1<body>",
                fixed,
                count=1,
                flags=re.I,
            )
    return fixed


def _append_missing_closing_tags(text: str) -> str:
    parser = _TagBalanceParser()
    parser.feed(text)
    parser.close()
    closers = []
    closers.extend(f"</{tag}>" for tag in parser.mismatched_tags)
    for tag in reversed(parser.stack):
        if tag in _RAW_TEXT_TAGS and re.search(
            rf"</{re.escape(tag)}\s*>", text, flags=re.I
        ):
            continue
        closers.append(f"</{tag}>")
    if not closers:
        return text

    closing_text = "".join(closers)
    if re.search(r"</body\s*>", text, flags=re.I):
        return re.sub(
            r"(</body\s*>)",
            closing_text + r"\1",
            text,
            count=1,
            flags=re.I,
        )
    return text + closing_text


def _ensure_required_tail(text: str) -> str:
    fixed = text
    if not re.search(r"</body\s*>", fixed, flags=re.I):
        fixed += "</body>"
    if not re.search(r"</html\s*>", fixed, flags=re.I):
        fixed += "</html>"
    return fixed
