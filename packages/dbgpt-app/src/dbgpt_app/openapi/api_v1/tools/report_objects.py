"""Compile model-selected captured objects into the existing report contract."""

import asyncio
import hashlib
import json
import re
from collections import deque
from copy import deepcopy
from itertools import islice
from threading import Lock

from dbgpt.agent.resource.tool.base import tool
from dbgpt.core.interface.report_capture import (
    normalize_artifact_result_selector,
    read_artifact_result,
    select_artifact_result,
)

MAX_OBJECTS = 8192
MAX_NESTING_DEPTH = 32
_DEPTH_ERROR = (
    f"REPORT_OBJECT_DEPTH_EXCEEDED: maximum nesting depth is {MAX_NESTING_DEPTH}"
)


class _ReportObjectDepthError(ValueError):
    """An unsupported value that must not be treated as ordinary prose."""


def _load_report_json(value):
    # Bound nesting before json.loads recurses. Brackets inside quoted strings
    # (including escaped quotes/backslashes) do not contribute to JSON depth.
    depth, quoted, escaped = 0, False, False
    for char in value:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > MAX_NESTING_DEPTH:
                raise _ReportObjectDepthError(_DEPTH_ERROR)
        elif char in "]}":
            depth -= 1
    try:
        return json.loads(value)
    except RecursionError as error:
        raise _ReportObjectDepthError(_DEPTH_ERROR) from error


VALUE_FORMATS = [
    "text",
    "raw",
    "int",
    "num0",
    "num1",
    "num2",
    "money",
    "money2",
    "percent",
    "pct",
    "pct0",
    "pct1",
    "pct2",
    "百分比",
    "percentage",
    "亿元",
    "万元",
]


def report_author_contract(contract, captured_fields):
    """Expose authored prose and metadata; the engine owns data placeholders."""
    fields = (
        set(contract["fields"])
        - set(captured_fields)
        - set(contract.get("verified_fields", []))
    )
    if contract.get("prose_fields"):
        fields &= set(contract["prose_fields"])
    fields = {
        field for field in fields if not field.startswith(("ARTIFACT_ID_", "CHART_"))
    }
    return {
        **contract,
        "template_fields": contract["fields"],
        "fields": sorted(fields),
        "interpretation_only": contract["mode"] != "spec"
        and "CHART_DATA_JSON" in captured_fields,
    }


def report_object_schema(contract):
    def obj(properties, required=()):
        return {
            "type": "object",
            "properties": properties,
            "required": list(required),
            "additionalProperties": False,
        }

    def array(items):
        return {"type": "array", "items": items}

    text = {"type": "string"}
    scalar_id = {
        "type": "string",
        "pattern": "^reference-[a-f0-9]{24}$"
        if contract.get("interpretation_only")
        else "^(value|reference)-[a-f0-9]{24}$",
    }
    visual_id = {"type": "string", "pattern": "^(table|chart)-[a-f0-9]{24}$"}
    ref = obj(
        {"object_id": scalar_id, "format": {"enum": VALUE_FORMATS}}, ["object_id"]
    )
    part = {"anyOf": [text, ref]}
    parts = array(part)
    paragraphs = array(parts)
    selection = obj(
        {
            "object_id": visual_id,
            "limit": {"type": "integer", "minimum": 1, "maximum": 200},
        },
        ["object_id"],
    )
    if contract["mode"] != "spec":
        narrative = {"anyOf": [text, ref, parts, paragraphs]}
        return obj(
            {
                key: (
                    obj({"object_id": visual_id}, ["object_id"])
                    if key.startswith("CHART_")
                    else narrative
                )
                for key in contract["fields"]
                if not key.startswith("ARTIFACT_ID_")
            }
        )
    kpi = obj(
        {"label": text, "object_id": scalar_id, "format": {"enum": VALUE_FORMATS}},
        ["label", "object_id"],
    )
    recommendation = obj({"title": text, "lines": paragraphs, "goal": text}, ["title"])
    section = obj(
        {
            "heading": text,
            "intro": paragraphs,
            "bullets": paragraphs,
            "kpis": array(kpi),
            "table": selection,
            "chart": selection,
            "recommendations": array(recommendation),
            "note": parts,
        },
        ["heading"],
    )
    report = obj(
        {
            "title": text,
            "subtitle": text,
            "scope": {"anyOf": [text, parts]},
            "note": parts,
            "kpis": array(kpi),
            "sections": array(section),
        },
        ["sections"],
    )

    return {"anyOf": [report, obj({"REPORT_SPEC": report}, ["REPORT_SPEC"])]}


class ReportObjects:
    """A deterministic view of immutable results; identifiers survive recovery."""

    def __init__(self, artifacts, *, eager=True, kind=None, query="", match_token=None):
        self.artifacts = {
            a.artifact_id: a for a in artifacts if a.status == "succeeded"
        }
        self.objects = {}
        self.per_artifact = 512
        self.truncated = False
        self._kind = kind
        self._query = query.casefold()
        self._match_token = match_token
        if eager:
            for artifact in self.artifacts.values():
                self._index_artifact(artifact)

    def _index_artifact(self, artifact):
        self.artifact_start = len(self.objects)
        if artifact.type in {"sql", "python"} and artifact.result is not None:
            try:
                self._visit(artifact, read_artifact_result(artifact), [], 0)
            except RecursionError:
                self.truncated = True
            except (ValueError, OSError):
                return
        elif artifact.type == "chart" and artifact.output and artifact.output.uri:
            self._add(artifact, "chart", {}, artifact.name, artifact.output.uri)
        elif artifact.type == "reference" and artifact.excerpt:
            self._add(artifact, "reference", {}, artifact.name, artifact.excerpt)

    def _add(self, artifact, kind, selector, label, preview, columns=None):
        label = str(label or artifact.name or kind)
        if (self._kind and kind != self._kind) or self._query not in label.casefold():
            return
        identity = [artifact.artifact_id, kind, selector]
        token = (
            kind
            + "-"
            + hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[
                :24
            ]
        )
        if self._match_token and token != self._match_token:
            return
        if len(self.objects) >= MAX_OBJECTS or (
            len(self.objects) - self.artifact_start >= self.per_artifact
        ):
            self.truncated = True
            return
        self.objects[token] = {
            "kind": kind,
            "artifact_id": artifact.artifact_id,
            "selector": selector,
            "label": label,
            "preview": preview,
            "columns": columns,
        }

    def _visit(self, artifact, value, path, depth):
        # Breadth first keeps summary fields and table objects visible before
        # large tables consume the bounded scalar catalogue.
        pending = deque([(value, path, depth)])
        visited = 0
        while pending and visited < MAX_OBJECTS:
            if self._match_token and self.objects:
                break
            if (
                len(self.objects) >= MAX_OBJECTS
                or len(self.objects) - self.artifact_start >= self.per_artifact
            ):
                self.truncated = True
                break
            value, path, depth = pending.popleft()
            visited += 1
            if depth > 12:
                self.truncated = True
                continue
            selector = {"path": path}
            label = ".".join(map(str, path)) or artifact.name
            if isinstance(value, str) and value.lstrip().startswith(("{", "[")):
                try:
                    decoded = _load_report_json(value)
                except _ReportObjectDepthError:
                    self.truncated = True
                    continue
                except ValueError:
                    decoded = None
                if isinstance(decoded, (dict, list)):
                    pending.appendleft((decoded, path, depth + 1))
                    continue
            if isinstance(value, dict):
                rows = value.get("rows")
                header = value.get("columns", value.get("headers"))
                if (
                    isinstance(rows, list)
                    and isinstance(header, list)
                    and header
                    and all(isinstance(k, str) for k in header)
                ):
                    self._add(artifact, "table", selector, label, rows[:2], header)
                if len(value) > MAX_OBJECTS:
                    self.truncated = True
                pending.extend(
                    (child, [*path, key], depth + 1)
                    for key, child in islice(value.items(), MAX_OBJECTS)
                )
            elif isinstance(value, list):
                if value and all(isinstance(row, dict) for row in value):
                    columns = list(dict.fromkeys(k for row in value for k in row))
                    if columns and all(all(k in row for k in columns) for row in value):
                        self._add(
                            artifact, "table", selector, label, value[:2], columns
                        )
                if len(value) > self.per_artifact:
                    self.truncated = True
                pending.extend(
                    (child, [*path, index], depth + 1)
                    for index, child in enumerate(value[: self.per_artifact])
                )
            elif isinstance(value, (str, int, float)) and not isinstance(value, bool):
                self._add(artifact, "value", selector, label, value)
        if pending:
            self.truncated = True

    def manifest(self, *, kind=None, query="", artifact_ids=None, offset=0, limit=40):
        # Scope and filter before applying the output budget. Older results
        # cannot consume the slots reserved for an explicitly requested source.
        items, artifact_index = [], []
        truncated = False
        for artifact_id, artifact in self.artifacts.items():
            if artifact_ids and artifact_id not in artifact_ids:
                continue
            scoped = ReportObjects([artifact], kind=kind, query=query)
            truncated = truncated or scoped.truncated
            fields = []
            for token, item in scoped.objects.items():
                if not any(
                    isinstance(p, int) for p in item["selector"].get("path", [])
                ):
                    fields.append(item["label"])
                if (kind and item["kind"] != kind) or query.casefold() not in item[
                    "label"
                ].casefold():
                    continue
                if len(items) < MAX_OBJECTS:
                    items.append({"object_id": token, **item})
                else:
                    truncated = True
            artifact_index.append(
                {
                    "artifact_id": artifact_id,
                    "name": artifact.name,
                    "fields": list(dict.fromkeys(fields))[:60],
                }
            )
        priority = {"table": 0, "reference": 1, "chart": 2, "value": 3}
        items.sort(
            key=lambda item: (
                priority[item["kind"]],
                len(item["selector"].get("path", [])),
                item["artifact_id"],
                item["label"],
            )
        )
        page = items[offset : offset + limit]
        for item in page:
            item.pop("selector")
            item["preview"] = str(item["preview"])[:500]
        return {
            "total": len(items),
            "offset": offset,
            "objects": page,
            "bounded": True,
            "truncated": truncated,
            "total_is_lower_bound": truncated,
            "artifact_index": artifact_index,
            **(
                {
                    "instruction": (
                        "Catalogue size or nesting limits were reached. "
                        "Narrow artifact_ids, kind or query; "
                        "an empty page is not proof of missing data."
                    )
                }
                if truncated
                else {}
            ),
        }

    def get(self, token, kind=None):
        item = self.objects.get(token)
        if item is None:
            # Resolve issued handles on demand, including after a checkpoint
            # restore. The bounded cache is not an evidence availability limit.
            for artifact in self.artifacts.values():
                scoped = ReportObjects([artifact], match_token=token)
                item = scoped.objects.get(token)
                if item is not None:
                    if len(self.objects) >= MAX_OBJECTS:
                        self.objects.pop(next(iter(self.objects)))
                    self.objects[token] = item
                    break
        if item is None or (kind and item["kind"] != kind):
            raise ValueError(
                f"REPORT_OBJECT_INVALID: unknown {token!r} or wrong object kind; "
                "copy an object_id from list_report_objects"
            )
        return item

    def reference(self, token, format=None):
        item = self.get(token)
        if item["kind"] not in {"value", "reference"}:
            examples = [
                {"object_id": key, "label": child["label"]}
                for key, child in self.objects.items()
                if child["kind"] == "value"
                and child["artifact_id"] == item["artifact_id"]
            ][:8]
            raise ValueError(
                f"REPORT_OBJECT_INVALID: {token} is a {item['kind']} object. "
                "Prose requires a value or reference object. Example scalar objects: "
                + json.dumps(examples, ensure_ascii=False)
            )
        node = {"artifact_id": item["artifact_id"], **item["selector"]}
        if item["kind"] == "value":
            artifact = self.artifacts[item["artifact_id"]]
            node.update(normalize_artifact_result_selector(artifact, item["selector"]))
            select_artifact_result(artifact, node)
        if format is not None:
            if format not in VALUE_FORMATS:
                raise ValueError("REPORT_OBJECT_INVALID: unsupported value format")
            node["format"] = format
        return node

    def table(self, token, limit=20):
        item = self.get(token, "table")
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError("REPORT_OBJECT_INVALID: table limit must be 1–200")
        return {
            "artifact_id": item["artifact_id"],
            **item["selector"],
            "columns": item["columns"],
            "limit": limit,
        }


def compile_report_objects(
    data, objects, *, spec_mode, fields, interpretation_only=False
):
    """Resolve handles before the renderer can see any authored content."""
    if isinstance(data, str):
        try:
            data = _load_report_json(data)
        except _ReportObjectDepthError:
            raise
        except ValueError as error:
            raise ValueError("REPORT_OBJECT_INVALID: invalid JSON object") from error
    if not isinstance(data, dict):
        raise ValueError("REPORT_OBJECT_INVALID: data must be an object")
    literal_errors = []

    def validate_literals():
        if literal_errors:
            raise ValueError(
                "REPORT_OBJECT_LITERAL: replace measured literals with captured "
                "value objects; capture derived calculations before writing results. "
                + json.dumps(literal_errors, ensure_ascii=False)
            )

    def prose(value, location, depth=0):
        if depth > MAX_NESTING_DEPTH:
            raise _ReportObjectDepthError(f"{_DEPTH_ERROR} at {location}")
        if isinstance(value, str):
            if value.lstrip().startswith(("[", "{")):
                try:
                    decoded = _load_report_json(value)
                except _ReportObjectDepthError:
                    raise
                except ValueError:
                    decoded = None
                if isinstance(decoded, (list, dict)):
                    return prose(decoded, location, depth + 1)
            if re.search(r"<\s*[A-Za-z!/?]", value) or "{artifact_id" in value:
                raise ValueError(
                    f"REPORT_OBJECT_INVALID: plain text required at {location}"
                )
            # Model-authored measured numbers must be submitted as object references.
            from .html_interpreter import (
                _NON_METRIC_NUMBER_PREFIX,
                _NUMERIC_CLAIM_PATTERN,
            )
            from .report_binding import is_document_number

            literals = [
                m[0]
                for m in _NUMERIC_CLAIM_PATTERN.finditer(value)
                if not is_document_number(
                    m[0],
                    value[m.end() :],
                    value[: m.start()],
                    _NON_METRIC_NUMBER_PREFIX,
                )
            ]
            if literals:
                literal_errors.append(
                    {"location": location, "literals": literals, "text": value[:300]}
                )
            return value
        if isinstance(value, list):
            return [
                prose(child, f"{location}[{i}]", depth + 1)
                for i, child in enumerate(value)
            ]
        if (
            isinstance(value, dict)
            and set(value) <= {"object_id", "format"}
            and "object_id" in value
        ):
            if (
                interpretation_only
                and objects.get(value["object_id"])["kind"] != "reference"
            ):
                raise ValueError(
                    "REPORT_OBJECT_INTERPRETATION_ONLY: statistics are already "
                    "rendered by the template. Write qualitative interpretation "
                    "without numeric references or measured literals."
                )
            return objects.reference(value["object_id"], value.get("format"))
        raise ValueError(
            f"REPORT_OBJECT_INVALID: expected text or object_id at {location}"
        )

    if not spec_mode:
        if set(data) - set(fields):
            raise ValueError("REPORT_OBJECT_INVALID: use listed template fields")
        result = {}
        for key, value in data.items():
            if isinstance(value, dict) and set(value) == {"object_id"}:
                item = objects.get(value["object_id"])
                if item["kind"] == "chart" and key.startswith("CHART_"):
                    result[key] = item["preview"]
                    continue
            result[key] = prose(value, key)
        validate_literals()
        return result

    if set(data) == {"REPORT_SPEC"} and isinstance(data["REPORT_SPEC"], dict):
        data = data["REPORT_SPEC"]
    allowed = {"title", "subtitle", "scope", "note", "kpis", "sections"}
    if set(data) - allowed:
        raise ValueError(
            "REPORT_OBJECT_INVALID: unsupported report fields "
            f"{sorted(set(data) - allowed)}; "
            f"allowed fields are {sorted(allowed)}; data is the report itself"
        )
    spec = {k: prose(data[k], k) for k in ("title", "subtitle", "scope") if k in data}

    def kpis(items):
        result = []
        for item in items:
            if not isinstance(item, dict) or set(item) - {
                "label",
                "object_id",
                "format",
            }:
                raise ValueError(
                    "REPORT_OBJECT_INVALID: KPI requires label and object_id"
                )
            result.append(
                {
                    "label": prose(item["label"], "kpi.label"),
                    "ref": objects.reference(item["object_id"], item.get("format")),
                }
            )
        return result

    spec["kpis"] = kpis(data.get("kpis", []))
    spec["sections"] = []
    if isinstance(data.get("scope"), list):
        spec.pop("scope", None)
        spec["sections"].append(
            {
                "source_field": "scope",
                "heading": "数据范围",
                "intro": [prose(data["scope"], "scope")],
            }
        )
    if "note" in data:
        spec["sections"].append(
            {
                "heading": "口径说明",
                "note": {"label": "知识库口径", "parts": prose(data["note"], "note")},
            }
        )
    for index, source in enumerate(data.get("sections", [])):
        if not isinstance(source, dict) or set(source) - {
            "heading",
            "intro",
            "bullets",
            "kpis",
            "table",
            "chart",
            "recommendations",
            "note",
        }:
            raise ValueError("REPORT_OBJECT_INVALID: unsupported section field")
        section = {
            k: prose(source[k], f"sections[{index}].{k}")
            for k in ("heading", "intro", "bullets")
            if k in source
        }
        section["kpis"] = kpis(source.get("kpis", []))
        if "note" in source:
            section["note"] = {
                "label": "知识库口径",
                "parts": prose(source["note"], "note"),
            }
        for key in ("table", "chart"):
            if key not in source:
                continue
            node = source[key]
            if not isinstance(node, dict) or set(node) - {"object_id", "limit"}:
                raise ValueError(
                    "REPORT_OBJECT_INVALID: table/chart requires object_id"
                )
            item = objects.get(node["object_id"])
            if key == "chart" and item["kind"] == "chart":
                section["chart"] = {"refs": [item["artifact_id"]]}
            else:
                selection = objects.table(node["object_id"], node.get("limit", 20))
                if key == "table":
                    section["table"] = selection
                else:
                    # A chart has its own source and projection. Keep a selected
                    # table intact; chart-only sections retain their data table.
                    section.setdefault("table", selection)
                    section["chart"] = {
                        "refs": [item["artifact_id"]],
                        "source_table": selection,
                    }
        section["recommendations"] = []
        for recommendation in source.get("recommendations", []):
            if set(recommendation) - {"title", "lines", "goal"}:
                raise ValueError("REPORT_OBJECT_INVALID: unsupported recommendation")
            lines = [
                {"parts": prose(parts, "recommendation.lines")}
                for parts in recommendation.get("lines", [])
            ]
            if "goal" in recommendation:
                goal = recommendation["goal"]
                if not isinstance(goal, str) or "<" in goal:
                    raise ValueError("REPORT_OBJECT_INVALID: goal must be plain text")
                lines.append({"parts": [{"proposal": goal}]})
            section["recommendations"].append(
                {
                    "title": prose(recommendation["title"], "recommendation.title"),
                    "lines": lines,
                }
            )
        spec["sections"].append(section)
    from .report_spec import validate_report_spec

    validate_literals()
    return {"REPORT_SPEC": validate_report_spec(spec)}


def make_report_object_tools(state, renderer, template_path, contract):
    fields_lock = Lock()
    repair_lock = asyncio.Lock()
    required_fields = set(contract.get("prose_fields", contract["fields"])) & set(
        contract["fields"]
    )
    if state.get("_report_object_template") != template_path:
        state["_report_object_template"] = template_path
        state["_report_object_fields"] = {}
    else:
        state["_report_object_fields"] = {
            field: value
            for field, value in state.get("_report_object_fields", {}).items()
            if field in contract["fields"]
        }

    def selection_failure(error):
        from .report_repair import record_report_object_failure

        return record_report_object_failure(
            state, _DEPTH_ERROR if isinstance(error, RecursionError) else str(error)
        )

    def catalogue(*, eager=True):
        sink = state.get("_report_artifact_sink")
        return ReportObjects(sink.snapshot() if sink else [], eager=eager)

    @tool(
        description=(
            "List captured objects for compose_report. Filter by artifact_ids, "
            "kind or query; use offset for pagination."
        )
    )
    def list_report_objects(
        artifact_ids: list[str] | None = None,
        kind: str | None = None,
        query: str = "",
        offset: int = 0,
        limit: int = 40,
    ) -> str:
        if offset < 0 or not 1 <= limit <= 100:
            raise ValueError("REPORT_OBJECT_INVALID: invalid pagination")
        registry = catalogue(eager=False)
        return json.dumps(
            {
                **registry.manifest(
                    kind=kind
                    or (
                        "reference"
                        if contract.get("interpretation_only")
                        else "value"
                        if contract["mode"] != "spec"
                        else None
                    ),
                    query=query,
                    artifact_ids=artifact_ids,
                    offset=offset,
                    limit=limit,
                ),
                "template_fields": contract["fields"],
            },
            ensure_ascii=False,
        )

    @tool(
        description=(
            "Assemble captured objects into a report. "
            "Use plain text and {object_id,format?} "
            "parts only. Business data uses title,kpis[{label,object_id}],sections "
            "[{heading,intro:[[text,{object_id}]],table:{object_id},chart:{object_id},"
            "recommendations:[{title,lines:[[parts]],goal:plain proposed target}]}]. "
            "Named templates use listed template fields. No artifact IDs, selectors, "
            "HTML, measured literals or chart options."
        )
    )
    async def compose_report(data: dict | None = None, title: str = "Report") -> str:
        try:
            if contract["mode"] == "spec" and saved_spec() is not None:
                raise ValueError(
                    "REPORT_OBJECT_REPAIR_REQUIRED: use patch_report to modify "
                    "the saved report; omitted content must be preserved"
                )
            if data is None:
                data = state.get("_report_object_fields")
                if not data or contract["mode"] == "spec":
                    raise ValueError(
                        "REPORT_OBJECT_INVALID: submit data, or stage named "
                        "template fields with set_report_field before composing"
                    )
                missing = required_fields - set(data)
                if missing:
                    raise ValueError(
                        "REPORT_OBJECT_INVALID: stage the remaining fields: "
                        + json.dumps(sorted(missing))
                    )
            compiled = compile_report_objects(
                data,
                catalogue(),
                spec_mode=contract["mode"] == "spec",
                fields=contract["fields"],
                interpretation_only=contract.get("interpretation_only", False),
            )
            if contract["mode"] != "spec":
                template_fields = contract.get("template_fields", [])
                if "REPORT_TITLE" in template_fields:
                    compiled.update(
                        compile_report_objects(
                            {"REPORT_TITLE": title},
                            catalogue(),
                            spec_mode=False,
                            fields=["REPORT_TITLE"],
                        )
                    )
                if "LANG" in template_fields:
                    compiled["LANG"] = state.get("_report_language", "zh")
        except (ValueError, TypeError, KeyError, RecursionError) as error:
            return selection_failure(error)
        return await renderer(template_path=template_path, title=title, data=compiled)

    for name, schema in {
        "offset": {"type": "integer", "minimum": 0, "default": 0},
        "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 40},
        "kind": {
            "type": ["string", "null"],
            "enum": ["value", "table", "chart", "reference", None],
        },
    }.items():
        parameter = list_report_objects._tool.args[name]
        parameter.json_schema = schema
        parameter.type = json.dumps(schema)
    schema = report_object_schema(contract)
    parameter = compose_report._tool.args["data"]
    parameter.json_schema = schema
    parameter.type = json.dumps(schema, ensure_ascii=False)
    parameter.required = contract["mode"] == "spec"
    result = [list_report_objects, compose_report]

    def saved_spec():
        saved = state.get("_report_saved_arguments") or {}
        if saved.get("template_path") != template_path:
            return None
        data = saved.get("data") or {}
        if isinstance(data, str):
            data = _load_report_json(data)
        spec = data.get("REPORT_SPEC") if isinstance(data, dict) else None
        if isinstance(spec, str):
            spec = _load_report_json(spec)
        return spec if isinstance(spec, dict) else None

    if contract["mode"] == "spec":

        @tool(
            description=(
                "Repair the saved report without replacing untouched content. "
                "section_index is zero-based. section changes only supplied fields; "
                "append_recommendations adds to that section; append_sections adds "
                "new sections. report edits top-level title, subtitle, scope or kpis. "
                "remove_fields removes obsolete top-level fields, except sections. "
                "remove_section_fields removes named fields from section_index. "
                "A non-object legacy section can be replaced using section, or "
                "deleted with remove_invalid_section=true and section_index. "
                "replace_invalid_sections supplies a corrected list only when "
                "the saved sections field is not a list. Other root fields remain. "
                "When editing scope in an old report without compiler provenance, "
                "scope_section_index explicitly identifies its old scope section. "
                "All new content uses the compose_report object grammar."
            )
        )
        async def patch_report(
            section_index: int | None = None,
            section: dict | None = None,
            append_recommendations: list[dict] | None = None,
            append_sections: list[dict] | None = None,
            report: dict | None = None,
            remove_fields: list[str] | None = None,
            remove_section_fields: list[str] | None = None,
            scope_section_index: int | None = None,
            remove_invalid_section: bool = False,
            replace_invalid_sections: list[dict] | None = None,
        ) -> str:
            async with repair_lock:
                try:
                    previous = saved_spec()
                    if previous is None:
                        raise ValueError(
                            "REPORT_OBJECT_INVALID: no saved report to repair"
                        )
                    repaired = deepcopy(previous)
                    scope_sections = None
                    if "scope" in (remove_fields or []):
                        scope_sections = []
                    if remove_fields:
                        if "sections" in remove_fields:
                            raise ValueError("REPORT_OBJECT_INVALID: preserve sections")
                        for field in remove_fields:
                            # The renderer merges root objects. An explicit null
                            # deletes a field; omission would restore the old one.
                            repaired[field] = None
                    if report is not None:
                        if set(report) - {"title", "subtitle", "scope", "kpis"}:
                            raise ValueError(
                                "REPORT_OBJECT_INVALID: report edits accept "
                                "title, subtitle, scope and kpis"
                            )
                        root = compile_report_objects(
                            report, catalogue(), spec_mode=True, fields=[]
                        )["REPORT_SPEC"]
                        for field in report:
                            if field in root:
                                repaired[field] = root[field]
                            else:
                                repaired[field] = None
                        # Structured scope parts are compiled into a source-bound
                        # section rather than an unsupported scalar scope.
                        if "scope" in report:
                            scope_sections = root["sections"]
                    sections = repaired.setdefault("sections", [])
                    if replace_invalid_sections is not None:
                        if isinstance(sections, list):
                            raise ValueError(
                                "REPORT_OBJECT_INVALID: preserve valid section lists"
                            )
                        sections = repaired["sections"] = compile_report_objects(
                            {"sections": replace_invalid_sections},
                            catalogue(),
                            spec_mode=True,
                            fields=[],
                        )["REPORT_SPEC"]["sections"]
                    if sections is None or sections == "" or sections == {}:
                        # Empty malformed legacy drafts contain no sections to
                        # preserve. Normalize them before applying public edits.
                        sections = repaired["sections"] = []
                    if not isinstance(sections, list):
                        raise ValueError(
                            "REPORT_OBJECT_INVALID: saved sections must be a list"
                        )
                    if remove_invalid_section:
                        if (
                            type(section_index) is not int
                            or not 0 <= section_index < len(sections)
                            or isinstance(sections[section_index], dict)
                            or section is not None
                            or append_recommendations is not None
                            or remove_section_fields
                            or scope_section_index is not None
                        ):
                            raise ValueError(
                                "REPORT_OBJECT_INVALID: remove_invalid_section "
                                "requires a non-object saved section and no "
                                "other indexed edits"
                            )
                        del sections[section_index]
                    if scope_section_index is not None:
                        if (
                            scope_sections is None
                            or type(scope_section_index) is not int
                            or not 0 <= scope_section_index < len(sections)
                            or not isinstance(sections[scope_section_index], dict)
                        ):
                            raise ValueError(
                                "REPORT_OBJECT_INVALID: scope_section_index requires "
                                "a scope edit and a valid saved section index"
                            )
                        sections[scope_section_index]["source_field"] = "scope"
                    if (
                        section is not None
                        or append_recommendations is not None
                        or remove_section_fields
                    ):
                        if type(
                            section_index
                        ) is not int or not 0 <= section_index < len(sections):
                            raise ValueError(
                                "REPORT_OBJECT_INVALID: invalid section_index"
                            )
                        if not isinstance(sections[section_index], dict):
                            if section is None or not section.get("heading"):
                                raise ValueError(
                                    "REPORT_OBJECT_INVALID: replace a non-object "
                                    "section with a section containing heading"
                                )
                            sections[section_index] = {}
                        source = dict(section or {})
                        if set(remove_section_fields or []) & (
                            set(source)
                            | (
                                {"recommendations"}
                                if append_recommendations is not None
                                else set()
                            )
                        ):
                            raise ValueError(
                                "REPORT_OBJECT_INVALID: cannot edit and remove "
                                "the same field"
                            )
                        if "source_field" in (remove_section_fields or []):
                            raise ValueError(
                                "REPORT_OBJECT_INVALID: preserve compiler provenance"
                            )
                        for field in remove_section_fields or []:
                            sections[section_index].pop(field, None)
                        if append_recommendations is not None:
                            if "recommendations" in source:
                                raise ValueError(
                                    "REPORT_OBJECT_INVALID: replace or append "
                                    "recommendations, not both"
                                )
                            source["recommendations"] = append_recommendations
                        compiled = compile_report_objects(
                            {"sections": [source]},
                            catalogue(),
                            spec_mode=True,
                            fields=[],
                        )["REPORT_SPEC"]["sections"][0]
                        for key in source:
                            if (
                                key == "recommendations"
                                and append_recommendations is not None
                            ):
                                sections[section_index].setdefault(key, []).extend(
                                    compiled[key]
                                )
                            else:
                                sections[section_index][key] = compiled[key]
                    if scope_sections is not None:
                        # Apply after indexed edits so callers' section indices
                        # still refer to the saved report. Preserve user sections
                        # even when they happen to share the generated heading.
                        position = next(
                            (
                                i
                                for i, item in enumerate(sections)
                                if isinstance(item, dict)
                                and item.get("source_field") == "scope"
                            ),
                            0,
                        )
                        sections[:] = [
                            item
                            for item in sections
                            if not isinstance(item, dict)
                            or item.get("source_field") != "scope"
                        ]
                        sections[position:position] = scope_sections
                    if append_sections:
                        sections.extend(
                            compile_report_objects(
                                {"sections": append_sections},
                                catalogue(),
                                spec_mode=True,
                                fields=[],
                            )["REPORT_SPEC"]["sections"]
                        )
                    if (
                        section is None
                        and not append_recommendations
                        and not append_sections
                        and not report
                        and not remove_fields
                        and not remove_section_fields
                        and not remove_invalid_section
                        and replace_invalid_sections is None
                    ):
                        raise ValueError(
                            "REPORT_OBJECT_INVALID: supply a report change"
                        )
                    saved = state["_report_saved_arguments"]
                    data = saved.get("data") or {}
                    if isinstance(data, str):
                        data = _load_report_json(data)
                    updated = {**deepcopy(data), "REPORT_SPEC": repaired}
                except (ValueError, TypeError, KeyError, RecursionError) as error:
                    return selection_failure(error)
                return await renderer(
                    template_path=template_path,
                    title=saved.get("title", "Report"),
                    data=updated,
                )

        section_schema = schema["anyOf"][0]["properties"]["sections"]["items"]
        for name, value in {
            "report": {
                "type": "object",
                "properties": {
                    key: schema["anyOf"][0]["properties"][key]
                    for key in ("title", "subtitle", "scope", "kpis")
                },
                "additionalProperties": False,
            },
            "section": {**section_schema, "required": []},
            "append_sections": {"type": "array", "items": section_schema},
            "replace_invalid_sections": {"type": "array", "items": section_schema},
            "append_recommendations": section_schema["properties"]["recommendations"],
        }.items():
            parameter = patch_report._tool.args[name]
            parameter.json_schema = {"anyOf": [value, {"type": "null"}]}
            parameter.type = json.dumps(parameter.json_schema)
        result.append(patch_report)
    if contract["mode"] != "spec":

        @tool(
            description=(
                "Validate and stage one named template field at a time. "
                "Content is plain text, an object reference, or paragraph parts. "
                "Other staged fields are retained. After all fields are staged, "
                "call compose_report without data to render the complete report."
            )
        )
        def set_report_field(field: str, content: str | list | dict) -> str:
            try:
                compile_report_objects(
                    {field: content},
                    catalogue(),
                    spec_mode=False,
                    fields=contract["fields"],
                    interpretation_only=contract.get("interpretation_only", False),
                )
            except (ValueError, TypeError, KeyError, RecursionError) as error:
                return selection_failure(error)
            from .report_repair import _save_checkpoint

            with fields_lock:
                draft = state.setdefault("_report_object_fields", {})
                draft[field] = content
                _save_checkpoint(
                    state,
                    state.get("_report_saved_arguments") or {},
                    "REPORT_DRAFT_STAGED: stage remaining fields, then compose_report",
                )
                return json.dumps(
                    {
                        "status": "staged",
                        "remaining_fields": sorted(required_fields - set(draft)),
                    }
                )

        field_schema = {"type": "string", "enum": contract["fields"]}
        parameter = set_report_field._tool.args["field"]
        parameter.json_schema = field_schema
        parameter.type = json.dumps(field_schema)
        # Every field uses the same object-based prose grammar as compose_report.
        if schema["properties"]:
            parameter = set_report_field._tool.args["content"]
            parameter.json_schema = {"anyOf": list(schema["properties"].values())}
            parameter.type = json.dumps(parameter.json_schema)
        result.append(set_report_field)
    return result


def report_object_prompt(template_path, contract, injected_fields, language):
    instructions = [
        "你是报告作者。工具 JSON Schema 是唯一提交契约。"
        "旧任务中的底层引用不能直接提交。",
        "禁止 HTML、底层证据选择器、图片地址或图表 option。"
        "set_report_field.field 仅填列出的模板字段名。",
        "程序负责读取真实结果、格式化数值与生成表格图表。",
        "区分事实、推测与建议，按用户要求覆盖分析维度。",
        "模板：" + template_path,
    ]
    if contract["mode"] == "spec":
        instructions += [
            "先调用 list_report_objects 获取对象，"
            "再用 compose_report 提交完整业务报告。",
            "已有保存报告时使用 patch_report 局部修复或追加，"
            "section_index 为从零开始的章节索引；顶层 KPI、标题和范围使用 report 参数。"
            "删除章节内的错误字段使用 remove_section_fields，并指定 section_index。"
            "旧报告未标记范围章节时，修改范围须用 scope_section_index "
            "明确指定旧范围章节。"
            "引擎保留所有未修改内容。",
            "使用 title、kpis[{label,object_id}]、sections。"
            "正文段落为普通文字与 {object_id,format?} 组成的 parts 数组。",
            "表格选择 table={object_id:表格ID}，"
            "图表选择 chart={object_id:表格或图表ID}。",
            "知识库口径使用 note=[文字,{object_id:reference对象ID}]，"
            '程序采用 "label":"知识库口径"。',
            "建议目标放在独立 goal 字符串；不得在事实正文手写统计数字。",
        ]
    else:
        instructions += [
            "本模板采用的知识库口径放入相应正文。",
            "优先调用 set_report_field 逐字段提交，多个字段可并行；"
            "有效字段已保存，不要重发。",
            "remaining_fields 为空后调用 compose_report，不传 data；"
            "标题用 title 参数填写。",
            "正文只填写：" + json.dumps(contract["fields"]),
        ]
        if contract.get("interpretation_only"):
            instructions += [
                "本模板的完整统计、数据表和图表已由程序生成，正文只做定性解读。",
                "正文可使用普通文字、文字段落数组与知识库 reference 对象；"
                "禁止 value 数值对象和手写统计数字。",
                "不要为重复统计值逐项查询目录；直接解释趋势、差异、局限与行动建议。",
            ]
        else:
            instructions += [
                "正文使用普通文字与 {object_id,format?} 组成的段落数组；"
                "不得手写统计数字。",
                "只为直接支撑结论的少量数值查询对象，不要遍历全部统计。",
            ]
    instructions += [
        "目录只接受真实 object_id。先看 artifact_index 的真实字段再定向筛选，"
        "禁止猜测或重复相同查询。",
        "如缺少必要派生结果，使用 request_report_calculation 请求补算，不要编造。",
        "自动注入字段无需提交：" + json.dumps(injected_fields),
        "所有报告文字使用英文。" if language == "en" else "报告文字使用中文。",
    ]
    return "\n".join(instructions)
