"""One HTML attribute parser for report validation and persistence."""

import json
import re
from html import escape
from html.parser import HTMLParser
from typing import Any

EVIDENCE_TAG_PATTERN = re.compile(
    r"<(?P<tag>[a-zA-Z][\w:-]*)\b(?P<attrs>"
    r"(?:[^>\"']|\"[^\"]*\"|'[^']*')*?\bdata-dbgpt-artifacts\s*=\s*"
    r"(?P<quote>['\"])(?P<ids>[^'\"]*)(?P=quote)"
    r"(?:[^>\"']|\"[^\"]*\"|'[^']*')*)>",
    re.IGNORECASE,
)


class BindingAttributeError(ValueError):
    """A recoverable error at a particular report container."""

    def __init__(self, message, *, html=None):
        super().__init__(message)
        self.html = html


def validate_template_fragment(value: str) -> str:
    """Allow formatted prose, but never executable markup from template data."""

    class Fragment(HTMLParser):
        def handle_starttag(self, tag, attrs):
            if tag in {
                "script",
                "style",
                "iframe",
                "object",
                "embed",
                "base",
                "meta",
                "link",
                "form",
            }:
                raise ValueError("REPORT_TEMPLATE_DATA_UNSAFE: executable prose markup")
            for key, content in attrs:
                if key.startswith("on") or key == "srcdoc":
                    raise ValueError(
                        "REPORT_TEMPLATE_DATA_UNSAFE: executable prose attribute"
                    )
                if (
                    key in {"href", "src", "xlink:href", "action", "formaction"}
                    and content
                ):
                    url = re.sub(r"[\x00-\x20]", "", content).lower()
                    if url.startswith(("javascript:", "vbscript:", "data:text/html")):
                        raise ValueError(
                            "REPORT_TEMPLATE_DATA_UNSAFE: executable prose URL"
                        )

        handle_startendtag = handle_starttag

    Fragment().feed(value)
    return value


def html_tokens(html):
    """Keep original markup while respecting comments and raw script/style text."""
    offsets = [0, *(match.end() for match in re.finditer("\n", html))]
    ranges = []

    class Markup(HTMLParser):
        def record(self, length):
            line, column = self.getpos()
            start = offsets[line - 1] + column
            ranges.append((start, start + length))

        def handle_starttag(self, tag, attrs):
            self.record(len(self.get_starttag_text()))

        handle_startendtag = handle_starttag

        def handle_endtag(self, tag):
            line, column = self.getpos()
            start = offsets[line - 1] + column
            self.record(html.index(">", start) + 1 - start)

        def handle_comment(self, data):
            self.record(len(data) + 7)

        def handle_decl(self, data):
            self.record(len(data) + 3)

    parser = Markup(convert_charrefs=False)
    parser.feed(html)
    previous = 0
    for start, end in ranges:
        if start > previous:
            yield html[previous:start]
        yield html[start:end]
        previous = end
    if previous < len(html):
        yield html[previous:]


def iter_binding_tags(html):
    """Validation and persistence see only real DOM elements, never JS examples."""
    offsets = [0, *(match.end() for match in re.finditer("\n", html))]
    matches = []

    class Bindings(HTMLParser):
        def handle_starttag(self, tag, attrs):
            line, column = self.getpos()
            offset = offsets[line - 1] + column
            names = {key for key, _ in attrs}
            match = EVIDENCE_TAG_PATTERN.match(html, offset)
            if "data-dbgpt-artifacts" in names and not match:
                raise BindingAttributeError(
                    "REPORT_ATTRIBUTE_INVALID: attribute=data-dbgpt-artifacts; "
                    "container=HTML offset "
                    f"{offset}"
                    "; expected a quoted artifact ID "
                    "list"
                )
            if match and "data-dbgpt-artifacts" in names:
                matches.append(match)

        handle_startendtag = handle_starttag

    parser = Bindings(convert_charrefs=True)
    parser.feed(html)
    return iter(matches)


def replace_binding_tags(html, replace):
    parts, previous = [], 0
    for match in iter_binding_tags(html):
        parts.extend((html[previous : match.start()], replace(match)))
        previous = match.end()
    parts.append(html[previous:])
    return "".join(parts)


def is_document_number(value, suffix, prefix, non_metric_prefix, *, heading=False):
    """Share label exclusions; negative/scientific values are never dates."""
    year = r"[12]\d{3}"
    separator = r"(?:[-–—~～]|至|到)"
    return bool(
        # Positional arguments in a SQL date-grouping example are not metrics.
        (
            re.fullmatch(r"\d+", value)
            and re.search(
                r"\b(?:substr|substring)\(\s*[A-Za-z_][\w.]*\s*,\s*"
                r"(?:\d+\s*,\s*)?$",
                prefix,
                re.I,
            )
            and re.match(r"\s*[,)]", suffix)
        )
        or (
            heading
            and re.fullmatch(r"\d+(?:\.\d+)+", value)
            and not prefix.strip()
            and re.match(r"\s+[^\d\W]", suffix, re.UNICODE)
        )
        or re.fullmatch(r"[12]\d{3}[-/]\d{1,2}(?:[-/]\d{1,2})?", value)
        or (re.fullmatch(year, value) and re.match(r"\s*年", suffix))
        or (
            re.match(r"\s*(?:月|日)", suffix)
            and re.search(r"(?:[12]\d{3}\s*年|\d{1,2}\s*月)\s*$", prefix)
        )
        or (
            re.fullmatch(r"\d{1,2}", value)
            and re.search(rf"{year}[-/]\d{{1,2}}\s*(?:→|{separator})\s*$", prefix)
            and 1 <= int(value) <= 12
        )
        or (
            re.fullmatch(r"\d+", value)
            and re.search(
                r"(?:最近|过去|未来|近|\b(?:last|past|next))\s*$", prefix, re.I
            )
            and re.match(
                r"\s*(?:个\s*)?(?:(?:完整|自然|工作)\s*)?"
                r"(?:月|季度|年|周|天|日|months?\b|quarters?\b|years?\b|weeks?\b|days?\b)",
                suffix,
                re.I,
            )
        )
        # "2010–2012" / "2017 至 2018": a year range is a document label, not a
        # measured value, even when the model binds the surrounding element.
        or (re.fullmatch(year, value) and re.match(rf"\s*{separator}\s*{year}", suffix))
        or (
            re.fullmatch(year, value)
            and re.search(rf"{year}\s*{separator}\s*$", prefix)
        )
        or (
            re.fullmatch(r"\d+", value.strip())
            and non_metric_prefix
            and non_metric_prefix.search(prefix)
        )
    )


class _Attributes(HTMLParser):
    def handle_starttag(self, tag, attrs):
        self.attributes = attrs


def claim_target_texts(html: str) -> dict[str, str]:
    """Read actual claim text from the rendered DOM, independently of its label."""

    class Targets(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.stack = []
            self.texts = {}

        def handle_starttag(self, tag, attrs):
            target = dict(attrs).get("data-dbgpt-claim-id")
            if tag not in {
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
            }:
                self.stack.append((tag, target))
            if target:
                self.texts.setdefault(target, [])

        def handle_endtag(self, tag):
            for index in range(len(self.stack) - 1, -1, -1):
                if self.stack[index][0] == tag:
                    del self.stack[index:]
                    break

        def handle_data(self, text):
            for _, target in self.stack:
                if target:
                    self.texts[target].append(text)

    parser = Targets()
    parser.feed(html)
    return {key: "".join(parts).strip() for key, parts in parser.texts.items()}


def parse_binding(match: re.Match) -> dict[str, Any]:
    """Decode entities once, validate selectors, and identify the error location."""
    from dbgpt.core.interface.report import normalize_result_selector

    parser = _Attributes(convert_charrefs=True)
    parser.feed(match.group(0))
    pairs = getattr(parser, "attributes", [])
    attrs = dict(pairs)
    label = attrs.get("data-dbgpt-evidence-label") or attrs.get("id") or "unnamed"
    container = f"<{match.group('tag')}> {label!r}, HTML offset {match.start()}"

    def fail(name, reason):
        target = {
            "attribute": name,
            "container": container,
            "html_offset": match.start(),
            "html_line": match.string.count("\n", 0, match.start()) + 1,
            "old": match.group(0),
        }
        raise BindingAttributeError(
            f"REPORT_ATTRIBUTE_INVALID: attribute={name}; "
            f"container={container}; {reason}; repair_target="
            + json.dumps(target, ensure_ascii=False),
            html=match.string,
        )

    for name, _ in pairs:
        if name.startswith("data-dbgpt-") and sum(k == name for k, _ in pairs) > 1:
            fail(name, "duplicate attribute")
        if name in {"data-dbgpt-quote", "data-dbgpt-quote-selector"}:
            fail(name, "use data-dbgpt-artifact-selectors; quote is optional")
        if name in {"data-dbgpt-selector", "data-dbgpt-selectors"}:
            fail(name, "unknown selector attribute; use data-dbgpt-artifact-selectors")
    raw_ids = attrs.get("data-dbgpt-artifacts")
    if not raw_ids or not re.fullmatch(
        r"[A-Za-z0-9_.:-]+(?:(?:\s*,\s*|\s+)[A-Za-z0-9_.:-]+)*", raw_ids.strip()
    ):
        fail(
            "data-dbgpt-artifacts",
            "expected nonempty artifact IDs separated by commas or whitespace; "
            f"received={json.dumps(raw_ids, ensure_ascii=False)}",
        )
    ids = list(dict.fromkeys(re.split(r"\s*,\s*|\s+", raw_ids.strip())))
    attrs["data-dbgpt-artifacts"] = ",".join(ids)
    raw = attrs.get("data-dbgpt-artifact-selectors")
    selectors = {}
    if raw is not None:
        try:
            selectors = json.loads(raw)
        except json.JSONDecodeError as error:
            fail(
                "data-dbgpt-artifact-selectors",
                f"JSON line {error.lineno}, column {error.colno}, "
                f"offset {error.pos}: {error.msg}. Use HTML entities for quotes "
                "inside selector JSON (for example &#39; for a SQL literal inside "
                "a single-quoted attribute); decoded source text must stay exact",
            )
        if not isinstance(selectors, dict):
            fail(
                "data-dbgpt-artifact-selectors",
                "JSON path $ must be an object keyed by artifact ID",
            )
        for artifact_id, selector in selectors.items():
            if artifact_id not in ids:
                fail(
                    "data-dbgpt-artifact-selectors",
                    f"JSON path $.{artifact_id}: ID is not bound to this container",
                )
            if not isinstance(selector, dict):
                fail(
                    "data-dbgpt-artifact-selectors",
                    f"JSON path $.{artifact_id} must be an object",
                )
            if "quote" in selector and (
                not isinstance(selector["quote"], str) or not selector["quote"].strip()
            ):
                fail(
                    "data-dbgpt-artifact-selectors",
                    f"JSON path $.{artifact_id}.quote must be "
                    "a nonempty string when supplied",
                )
            if "field" in selector and (
                not isinstance(selector["field"], str) or not selector["field"]
            ):
                fail(
                    "data-dbgpt-artifact-selectors",
                    f"JSON path $.{artifact_id}.field must be a nonempty string",
                )
            try:
                selectors[artifact_id] = normalize_result_selector(selector)
            except ValueError as error:
                fail(
                    "data-dbgpt-artifact-selectors",
                    f"JSON path $.{artifact_id}.path: {error}",
                )
    return {
        "attributes": attrs,
        "artifact_ids": ids,
        "artifact_selectors": selectors,
        "container": container,
    }


def normalize_binding_attributes(html: str) -> str:
    """Serialize IDs and result paths using the existing browser protocol.

    This changes representations only. Artifact ownership and source identity are
    still checked by the renderer; no evidence IDs are inferred or inserted.
    """

    errors = []

    def replace(match):
        try:
            binding = parse_binding(match)
        except BindingAttributeError as error:
            errors.append(str(error))
            return match.group(0)
        start = match.start("ids") - match.start()
        end = match.end("ids") - match.start()
        opening = (
            match.group(0)[:start]
            + binding["attributes"]["data-dbgpt-artifacts"]
            + match.group(0)[end:]
        )
        raw_selectors = binding["attributes"].get("data-dbgpt-artifact-selectors")
        if (
            raw_selectors is not None
            and json.loads(raw_selectors) != binding["artifact_selectors"]
        ):
            # Scan whole attribute values so a quoted example in another
            # attribute cannot be mistaken for the actual selector attribute.
            for attribute in re.finditer(
                r"""(?P<name>[\w:-]+)\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)""", opening
            ):
                if attribute["name"].lower() == "data-dbgpt-artifact-selectors":
                    value = escape(
                        json.dumps(binding["artifact_selectors"], ensure_ascii=False),
                        quote=True,
                    )
                    opening = (
                        opening[: attribute.start()]
                        + f'data-dbgpt-artifact-selectors="{value}"'
                        + opening[attribute.end() :]
                    )
                    break
        return opening

    normalized = replace_binding_tags(html, replace)
    if errors:
        raise BindingAttributeError("\n".join(errors), html=html)
    return normalized


def validate_result_selectors(html: str, artifacts) -> str | None:
    """Check every selected field/cell against the captured result, loading once."""
    from dbgpt.core.interface.report_capture import (
        read_artifact_result,
        select_artifact_result,
        select_result_value,
    )

    by_id = {item.artifact_id: item for item in artifacts if item.status == "succeeded"}
    results = {}
    errors = []
    for match in iter_binding_tags(html):
        binding = parse_binding(match)
        for artifact_id, selector in binding["artifact_selectors"].items():
            artifact = by_id.get(artifact_id)
            if (
                not artifact
                or artifact.type not in {"sql", "python"}
                or not (
                    "field" in selector
                    or "path" in selector
                    or selector.get("kind") == "sql"
                )
            ):
                continue
            try:
                if selector.get("kind") == "sql":
                    select_artifact_result(artifact, selector)
                    continue
                if artifact_id not in results:
                    results[artifact_id] = read_artifact_result(artifact)
                value = results[artifact_id]
                field = selector.get("field")
                if (
                    selector.get("path")
                    and isinstance(value, dict)
                    and isinstance(value.get(field), str)
                ):
                    value = dict(value)
                    value[field] = json.loads(value[field])
                    results[artifact_id] = value
                select_result_value(value, selector)
            except (ValueError, TypeError, OSError) as error:
                errors.append(
                    {
                        "container": binding["container"],
                        "attribute": "data-dbgpt-artifact-selectors",
                        "json_path": f"$.{artifact_id}",
                        "selector": selector,
                        "reason": str(error),
                        "available_result_fields": list(results.get(artifact_id, {}))[
                            :25
                        ]
                        if isinstance(results.get(artifact_id), dict)
                        else [],
                        "html_offset": match.start(),
                        "html_line": html.count("\n", 0, match.start()) + 1,
                        "old": match[0],
                    }
                )
    if errors:
        return (
            "REPORT_RESULT_SELECTOR_INVALID: "
            + json.dumps(errors, ensure_ascii=False)
            + ". Fix the listed selectors only; reuse completed artifacts."
        )
    return None


def normalize_payload_selectors(html: str, artifacts) -> str:
    """Record the JSON result field a bare ``path`` selector resolves inside.

    Skill payloads expose their metrics as one JSON result field (for example
    ``CHART_DATA_JSON``). A selector that names only ``path`` is unambiguous
    when that path resolves inside the single field, so the field is recorded
    instead of failing every numeric target that shares the binding. A path
    that does not resolve is left untouched for the selector validator.
    """
    from dbgpt.core.interface.report_capture import (
        normalize_artifact_result_selector,
        read_artifact_result,
    )

    by_id = {
        item.artifact_id: item
        for item in artifacts
        if getattr(item, "status", None) == "succeeded"
        and getattr(item, "type", None) in {"sql", "python"}
    }
    results = {}

    def resolve(artifact_id, selector):
        artifact = by_id.get(artifact_id)
        if artifact is None or "path" not in selector or "field" in selector:
            return None
        if selector.get("kind") == "sql":
            return None
        if artifact_id not in results:
            try:
                results[artifact_id] = read_artifact_result(artifact)
            except (ValueError, TypeError, OSError):
                results[artifact_id] = None
        result = results[artifact_id]
        if not isinstance(result, dict) or len(result) != 1:
            return None
        try:
            candidate = normalize_artifact_result_selector(artifact, selector)
        except (ValueError, TypeError):
            return None
        return candidate if candidate != selector else None

    def replace(match):
        binding = parse_binding(match)
        updated = {}
        for artifact_id, selector in binding["artifact_selectors"].items():
            candidate = resolve(artifact_id, selector)
            if candidate is not None:
                updated[artifact_id] = candidate
        if not updated:
            return match.group(0)
        selectors = {**binding["artifact_selectors"], **updated}
        value = escape(json.dumps(selectors, ensure_ascii=False), quote=True)
        opening = match.group(0)
        for attribute in re.finditer(
            r"""(?P<name>[\w:-]+)\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)""", opening
        ):
            if attribute["name"].lower() == "data-dbgpt-artifact-selectors":
                return (
                    opening[: attribute.start()]
                    + f'data-dbgpt-artifact-selectors="{value}"'
                    + opening[attribute.end() :]
                )
        return opening

    return replace_binding_tags(html, replace)


def validate_report_targets(
    html: str,
    artifact_types: dict[str, str],
    *,
    numeric_pattern=None,
    numeric_skip_tags=(),
    non_metric_prefix=None,
    numeric_evidence=None,
    chart_evidence=None,
) -> str | None:
    """Require evidence on every data target, independently of page bindings."""
    offsets = [0, *(match.end() for match in re.finditer("\n", html))]
    missing = []
    void_tags = {
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

    data_types = {"sql", "python", "reference"}
    inline_tags = {"strong", "b", "span", "em", "mark", "a", "td", "th"}
    value_classes = {"value", "val", "metric-value", "kpi-value", "stat-value"}

    class Targets(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.stack = []
            self.recent_text = ""
            self.errors_by_target = {}
            self.heading = ""

        def reject(self, kind, attributes, offset, opening, **details):
            key = (kind, offset)
            if key in self.errors_by_target:
                previous = self.errors_by_target[key]
                if "value" in details:
                    values = previous.setdefault("values", [previous["value"]])
                    if details["value"] not in values:
                        values.append(details["value"])
                return
            anchor = opening
            missing.append(
                {
                    "kind": kind,
                    "container": f"<{attributes['tag']}> "
                    + (
                        attributes.get("data-dbgpt-evidence-label")
                        or attributes.get("id")
                        or self.heading
                        or "unnamed"
                    ),
                    "html_offset": offset,
                    "html_line": html.count("\n", 0, offset) + 1,
                    "attribute": "data-dbgpt-artifacts",
                    "old": anchor,
                    **details,
                }
            )
            self.errors_by_target[key] = missing[-1]

        def handle_starttag(self, tag, attrs):
            attributes = dict(attrs)
            attributes["tag"] = tag
            if re.fullmatch(r"h[1-6]", tag):
                self.recent_text = ""
            classes = set((attributes.get("class") or "").split())
            chart = (
                tag in {"canvas", "img", "svg", "figure"}
                or bool(
                    set((attributes.get("class") or "").split())
                    & {
                        "chart-box",
                        "chartbox",
                        "figbox",
                        "chart",
                        "chart-container",
                    }
                )
                or "data-dbgpt-chart-placeholder" in attributes
                or "_echarts_instance_" in attributes
                or "data-dbgpt-chart-renderer" in attributes
                or "data-dbgpt-chart-id" in attributes
                or "data-dbgpt-chart-key" in attributes
            )
            line, column = self.getpos()
            offset = offsets[line - 1] + column
            match = (
                EVIDENCE_TAG_PATTERN.match(html, offset)
                if "data-dbgpt-artifacts" in attributes
                else None
            )
            binding = parse_binding(match) if match else None
            # Only a dedicated enclosing figure/host can own a chart. Sections,
            # tables and the body never transfer their bindings to a chart.
            owner = binding or next(
                (
                    frame["binding"]
                    for frame in reversed(self.stack)
                    if frame["chart"] and frame["binding"]
                ),
                None,
            )
            if chart and not (
                owner
                and any(
                    artifact_types.get(item) == "chart"
                    for item in owner["artifact_ids"]
                )
            ):
                owner = next(
                    (
                        frame["binding"]
                        for frame in reversed(self.stack)
                        if frame["chart"]
                        and frame["binding"]
                        and any(
                            artifact_types.get(item) == "chart"
                            for item in frame["binding"]["artifact_ids"]
                        )
                    ),
                    owner,
                )
            covered = chart and bool(
                owner
                and any(
                    artifact_types.get(artifact_id) == "chart"
                    for artifact_id in owner["artifact_ids"]
                )
            )
            if covered and chart_evidence and not chart_evidence(attributes, owner):
                self.reject(
                    "chart_source_mismatch",
                    attributes,
                    offset,
                    self.get_starttag_text(),
                )
                covered = False
            if covered:
                for frame in self.stack:
                    if frame["chart"]:
                        frame["covered"] = True
            if chart and tag in void_tags and not covered:
                self.reject("chart", attributes, offset, self.get_starttag_text())
            unbound_table = tag == "table" and not (
                binding
                and any(
                    artifact_types.get(item) in data_types
                    for item in binding["artifact_ids"]
                )
            )
            if unbound_table:
                self.reject("table", attributes, offset, self.get_starttag_text())
            if tag not in void_tags:
                self.stack.append(
                    {
                        "tag": tag,
                        "attrs": attributes,
                        "binding": binding,
                        "chart": chart,
                        "offset": offset,
                        "covered": covered,
                        "opening": self.get_starttag_text(),
                        "classes": classes,
                        "unbound_table": unbound_table,
                        "heading_text": []
                        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}
                        else None,
                    }
                )

        def handle_startendtag(self, tag, attrs):
            self.handle_starttag(tag, attrs)
            if tag not in void_tags:
                self.handle_endtag(tag)

        def handle_endtag(self, tag):
            for index in range(len(self.stack) - 1, -1, -1):
                if self.stack[index]["tag"] == tag:
                    for frame in self.stack[index:]:
                        if frame["heading_text"] is not None:
                            self.heading = "".join(frame["heading_text"]).strip()
                        if frame["chart"] and not frame["covered"]:
                            self.reject(
                                "chart",
                                frame["attrs"],
                                frame["offset"],
                                frame["opening"],
                            )
                    del self.stack[index:]
                    break
            if tag in {"p", "li", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6"}:
                self.recent_text = ""

        def handle_data(self, text):
            for frame in self.stack:
                if frame["heading_text"] is not None:
                    frame["heading_text"].append(text)
            if not self.stack or any(
                frame["tag"] in numeric_skip_tags
                or frame["tag"] in {"svg", "canvas"}
                or "section-no" in frame["classes"]
                for frame in self.stack
            ):
                return
            if numeric_pattern is None:
                return
            # A numbered recommendation card uses its number as navigation,
            # just like a section ordinal. Its quantitative body stays checked.
            if (
                self.stack[-1]["classes"] & {"num", "number"}
                and any(
                    frame["classes"] & {"rec", "recommendation", "recommendation-card"}
                    for frame in self.stack[:-1]
                )
                and re.fullmatch(r"\s*\d+\s*", text)
            ):
                return
            # Fix the missing table source first. No cell is accepted for saving
            # until that table and all its numeric targets pass the next validation.
            if any(frame["unbound_table"] for frame in self.stack):
                return
            owner = next(
                (
                    frame
                    for frame in reversed(self.stack)
                    if frame["binding"]
                    and (
                        frame["tag"] in inline_tags
                        or frame["classes"] & value_classes
                        or frame["attrs"].get("data-dbgpt-target-kind") == "claim"
                    )
                ),
                None,
            )
            bound = owner and any(
                artifact_types.get(item) in data_types
                for item in owner["binding"]["artifact_ids"]
            )
            scalar = self.stack[-1]
            if (
                scalar["classes"] & value_classes
                and not bound
                and text.strip()
                and not re.fullmatch(
                    r"(?:--|—|[-/()%\s]+|R\$|BRL|USD|CNY|元|行|KB|"
                    r"天|小时|分钟|秒|单|笔|人|件|次|分|倍|个|r\s*=)",
                    text.strip(),
                    re.I,
                )
                and not numeric_pattern.search(text)
            ):
                self.reject(
                    "data_value",
                    scalar["attrs"],
                    scalar["offset"],
                    scalar["opening"],
                    value=text.strip()[:160],
                )
            for number in numeric_pattern.finditer(text):
                value = number[0]
                prefix = self.recent_text + text[: number.start()]
                if is_document_number(
                    value,
                    text[number.end() :],
                    prefix,
                    non_metric_prefix,
                    heading=any(
                        frame["heading_text"] is not None for frame in self.stack
                    ),
                ):
                    continue
                source_mismatch = (
                    bound
                    and numeric_evidence
                    and not (
                        owner["attrs"].get("data-dbgpt-value-role") == "proposal"
                        and (
                            owner["attrs"].get("data-dbgpt-evidence-label") or ""
                        ).startswith("建议目标（非观测值）：")
                        and owner["binding"]["artifact_selectors"]
                    )
                    and not numeric_evidence(value, owner["binding"], text)
                )
                if not bound or source_mismatch:
                    frame = self.stack[-1]
                    line, column = self.getpos()
                    text_offset = offsets[line - 1] + column
                    end = html.find("<", text_offset)
                    raw_text = html[text_offset : end if end >= 0 else len(html)]
                    self.reject(
                        "numeric_source_mismatch"
                        if source_mismatch
                        else "numeric_value",
                        frame["attrs"],
                        text_offset,
                        raw_text,
                        value=value,
                        **(
                            {
                                "source_artifact_ids": owner["binding"]["artifact_ids"],
                                "selectors": owner["binding"]["artifact_selectors"],
                            }
                            if source_mismatch
                            else {}
                        ),
                    )
            self.recent_text = (self.recent_text + text)[-80:]

    parser = Targets()
    parser.feed(html)
    for frame in parser.stack:
        if frame["chart"] and not frame["covered"]:
            parser.reject("chart", frame["attrs"], frame["offset"], frame["opening"])
    if missing:
        return (
            "REPORT_TARGET_BINDING_REQUIRED: "
            + json.dumps(missing, ensure_ascii=False)
            + ". Bind every chart host/figure to its own captured ChartArtifact, "
            "every table to its producing SQL/Python or captured reference, and "
            "each numeric value to a separate inline result/reference target. "
            "An SQL binding alone cannot capture a hand-drawn SVG. Reuse a "
            "captured chart, "
            "or declare an ECharts host with id, data-dbgpt-chart-renderer=echarts, "
            "producer ID and result field/path selector; the renderer "
            "supplies the chart ID. "
            "Metric thresholds may select an exact captured SQL predicate using "
            "kind=sql and quote; computed values must retain result selectors. "
            "For numeric_source_mismatch, correct the displayed value/source "
            "or capture "
            "only the missing derived calculation; never present a proposed "
            "target as an observed result. "
            "Page/section bindings do not satisfy these requirements. "
            "Declare dynamic data targets in the template before saving target IDs. "
            "Repair all listed targets together and reuse completed analysis."
            " Use each target's html_offset and exact old together; patches refer "
            "to the same saved HTML snapshot. For unbound tables, bind the table "
            "first; the next render will bind matching cells and validate every value."
        )
    return None


def capture_template_charts(html: str, sink) -> str:
    """Register explicitly declared template charts through the core collector."""
    if sink is None:
        return html
    from hashlib import sha256
    from html import escape
    from time import perf_counter

    from dbgpt.core.interface.report_capture import (
        capture_chart_execution,
        select_artifact_result,
        store_artifact_json,
    )

    artifacts = {item.artifact_id: item for item in sink.snapshot()}
    template_content = None
    scripts = re.findall(r"<script\b[^>]*>.*?</script\s*>", html, re.I | re.S)
    renderer_fingerprint = sha256("\n".join(scripts).encode("utf-8")).hexdigest()

    def bind(match):
        nonlocal template_content
        started = perf_counter()
        binding = parse_binding(match)
        attrs = binding["attributes"]
        if attrs.get("data-dbgpt-chart-renderer") != "echarts":
            return match.group(0)
        declared_chart = attrs.get("data-dbgpt-chart-id")
        if declared_chart:
            chart = artifacts.get(declared_chart)
            if (
                declared_chart not in binding["artifact_ids"]
                or getattr(chart, "type", None) != "chart"
                or chart.status != "succeeded"
                or chart.spec.get("renderer") != "echarts"
            ):
                raise BindingAttributeError(
                    f"CHART_BINDING_INVALID: container={binding['container']}; "
                    "expected a successful ECharts artifact bound to this container"
                )
        sources = [
            artifact_id
            for artifact_id in binding["artifact_ids"]
            if getattr(artifacts.get(artifact_id), "type", None) in {"python", "sql"}
            and artifact_id in binding["artifact_selectors"]
        ]
        authored = declared_chart and chart.spec.get("authored_option")
        if authored:
            if binding["artifact_selectors"] != chart.spec[
                "source_selectors"
            ] or not set(chart.input_artifact_ids).issubset(binding["artifact_ids"]):
                raise BindingAttributeError(
                    (
                        "CHART_BINDING_INVALID: retain all exact captured option "
                        "sources "
                        "and selectors"
                    )
                )
            source_id = chart.spec["source_artifact_id"]
        elif len(sources) != 1:
            raise BindingAttributeError(
                "CHART_SOURCE_SELECTOR_REQUIRED: "
                "attribute=data-dbgpt-artifact-selectors; "
                f"container={binding['container']}; "
                "declare one exact data source field/path"
            )
        else:
            source_id = sources[0]
        selector = binding["artifact_selectors"][source_id]
        if selector.get("kind", "result") != "result" or not (
            "field" in selector or "path" in selector
        ):
            raise BindingAttributeError(
                f"CHART_SOURCE_SELECTOR_INVALID: container={binding['container']}; "
                "select a captured result field/path"
            )
        try:
            dataset = select_artifact_result(artifacts[source_id], selector)
            if isinstance(dataset, str):
                dataset = json.loads(dataset)
        except (ValueError, TypeError) as error:
            raise BindingAttributeError(
                "CHART_SOURCE_SELECTOR_INVALID: "
                "attribute=data-dbgpt-artifact-selectors; "
                f"container={binding['container']}; JSON path $.{source_id}; {error}"
            ) from error
        if declared_chart and chart.spec.get("option") is not None:
            # Preparation owns the exact result and option; retries reuse its ID.
            try:
                option = json.loads(attrs.get("data-dbgpt-chart-option", "null"))
            except ValueError as error:
                raise BindingAttributeError(
                    "CHART_OPTION_INVALID: invalid captured option"
                ) from error
            if (
                chart.spec.get("source_artifact_id") != source_id
                or chart.spec.get("source_selector") != selector
                or chart.spec.get("data") != dataset
                or chart.spec["option"] != option
                or chart.spec.get("maps", {})
                != json.loads(attrs.get("data-dbgpt-chart-maps", "{}"))
            ):
                raise BindingAttributeError(
                    (
                        "CHART_BINDING_INVALID: prepared chart must retain its exact "
                        "captured data and "
                        "option"
                    )
                )
            return match.group(0)
        if template_content is None:
            template_content = store_artifact_json({"html": html})
        spec = {
            "renderer": "echarts",
            "source_artifact_id": source_id,
            "source_selector": selector,
            "data": dataset,
        }
        target_id = attrs.get("data-dbgpt-block-id") or attrs.get("id")
        if not target_id:
            raise BindingAttributeError(
                "CHART_TARGET_ID_REQUIRED: "
                + json.dumps(
                    [
                        {
                            "kind": "chart",
                            "attribute": "data-dbgpt-block-id",
                            "container": binding["container"],
                            "html_offset": match.start(),
                            "html_line": html.count("\n", 0, match.start()) + 1,
                            "old": match.group(0),
                        }
                    ],
                    ensure_ascii=False,
                )
                + ". Add a stable id or data-dbgpt-block-id on this exact bound "
                "figure/container. Keep the child chart host id. read_file offset "
                "is a zero-based line number; use html_line minus one."
            )
        metadata = {
            "target_id": target_id,
            "renderer_fingerprint": renderer_fingerprint,
            "renderer_template": template_content.model_dump(exclude_none=True),
        }
        existing = next(
            (
                item
                for item in artifacts.values()
                if getattr(item, "type", None) == "chart"
                and item.status == "succeeded"
                and item.spec == spec
                and item.metadata.get("target_id") == target_id
                and item.metadata.get("renderer_fingerprint") == renderer_fingerprint
            ),
            None,
        )
        chart_id = (
            existing.artifact_id
            if existing
            else capture_chart_execution(
                input_artifact_ids=[
                    item for item in binding["artifact_ids"] if item != declared_chart
                ],
                chart_type="echarts",
                spec=spec,
                output_inline=spec,
                action="template_chart.prepare",
                duration_ms=max(0, int((perf_counter() - started) * 1000)),
                name=attrs.get("data-dbgpt-evidence-label"),
                metadata=metadata,
                artifact_sink=sink,
            )
        )
        if existing is None:
            artifacts.update((item.artifact_id, item) for item in sink.snapshot())
        opening = match.group(0)
        start, end = (
            match.start("ids") - match.start(),
            match.end("ids") - match.start(),
        )
        opening = (
            opening[:start]
            + ",".join(
                dict.fromkeys(
                    [
                        *(
                            item
                            for item in binding["artifact_ids"]
                            if item != declared_chart
                        ),
                        chart_id,
                    ]
                )
            )
            + opening[end:]
        )
        opening = re.sub(
            r"\s+data-dbgpt-chart-id\s*=\s*(['\"])[^'\"]*\1", "", opening, flags=re.I
        )
        return opening[:-1] + f' data-dbgpt-chart-id="{escape(chart_id, quote=True)}">'

    return replace_binding_tags(html, bind)


def validate_knowledge_sources(html, references):
    """Check captured source IDs against persisted documents and canonical chunks."""
    from dbgpt_serve.rag.chunk_metadata import document_chunk_entries
    from dbgpt_serve.rag.tools.kb_file_tools import _get_all_file_paths, _get_chunk_dao

    files_by_space = {}
    chunks_by_document = {}
    for match in iter_binding_tags(html):
        binding = parse_binding(match)
        for artifact_id in set(binding["artifact_ids"]).intersection(references):
            artifact = references[artifact_id]
            locator = artifact.locator or {}
            space = str(locator.get("knowledge_id") or "")
            document_id = locator.get("document_id")
            chunk_id = locator.get("chunk_id")
            error = (
                "KB_CHUNK_IDENTITY_INVALID: attribute=data-dbgpt-artifacts; "
                f"container={binding['container']}; artifact={artifact_id}; "
                f"document_id={document_id}, chunk_id={chunk_id}; "
            )
            if (
                not space
                or document_id is None
                or not chunk_id
                or artifact.source_id != chunk_id
            ):
                return error + "missing or inconsistent captured source identity"
            if space not in files_by_space:
                files_by_space[space] = _get_all_file_paths(space)
            files = [
                file
                for file in files_by_space[space]
                if str(file["doc_id"]) == str(document_id)
            ]
            if len(files) != 1:
                return error + "document does not exist in this knowledge space"
            key = (space, str(document_id))
            if key not in chunks_by_document:
                dao, entity = _get_chunk_dao()
                chunks, page = [], 1
                while True:
                    batch = dao.get_document_chunks(
                        entity(document_id=files[0]["doc_id"]),
                        page=page,
                        page_size=1000,
                    )
                    chunks.extend(batch)
                    if len(batch) < 1000:
                        break
                    page += 1
                chunks_by_document[key] = document_chunk_entries(files[0], chunks)
            entries = [
                entry
                for entry in chunks_by_document[key]
                if entry[1]["chunk_id"] == chunk_id
            ]
            if len(entries) != 1:
                return error + "canonical chunk does not belong to this document"
            chunk, metadata = entries[0]
            for field in ("chunk_db_id", "chunk_index"):
                if locator.get(field) is not None and str(locator[field]) != str(
                    metadata[field]
                ):
                    return error + f"{field} does not match persisted source"
            excerpt = re.sub(r"\s+", " ", artifact.excerpt or "").strip()
            if not excerpt or excerpt not in re.sub(r"\s+", " ", chunk.content).strip():
                return error + "captured excerpt is not present in the source chunk"
    return None
