"""Two-phase dashboard planning tools for the ReAct agent."""

import asyncio
import json
import logging
import re
import uuid
from typing import Any, Callable, Dict, List, Optional

from pydantic import ValidationError

from dbgpt.agent.resource.tool.base import tool

from ..dashboard.annotations import DashboardAnnotationService
from ..dashboard.chart_selection import normalize_plan_chart_selection
from ..dashboard.collaboration import (
    DashboardCollaborationService,
    apply_dashboard_patch,
)
from ..dashboard.confirmation import (
    observe_generation_event,
    record_generation_result,
    require_current_confirmation,
)
from ..dashboard.demo_contracts import verified_olist_plan_for_request
from ..dashboard.generation_budget import (
    DashboardGenerationTimeout,
    check_generation_deadline,
)
from ..dashboard.planner import DashboardPlannerService
from ..dashboard.release_features import layout_templates_enabled
from ..dashboard.schemas import (
    DashboardAction,
    DashboardChangeProposalRequest,
    DashboardOperationRequest,
    DashboardPatchOperation,
    DashboardPlan,
    DashboardQueryDraftRequest,
    DashboardSchemaV1,
    DashboardTargetResolutionStatus,
    model_dump_compat,
    model_validate_compat,
)
from ..dashboard.service import DashboardSchemaValidationError, DashboardService
from ..dashboard.target_resolution import resolve_dashboard_target
from ..dashboard.temporal_discovery import collect_temporal_evidence
from .dashboard_contracts import DashboardProposalToolInput, model_tool_parameters

logger = logging.getLogger(__name__)

_FUZZY_TARGET_CUES = (
    "这个图",
    "这张图",
    "这个组件",
    "当前图",
    "选中的图",
    "右边",
    "右侧",
    "左边",
    "左侧",
    "上面",
    "下面",
    "顶部",
    "底部",
    "this chart",
    "this widget",
    "rightmost",
    "leftmost",
    "on the right",
    "on the left",
)


def _normalized_prompt_text(value: str) -> str:
    return re.sub(r"\s+", "", value).casefold()


def _reference_is_in_prompt(reference: str, prompt: str) -> bool:
    normalized_reference = _normalized_prompt_text(reference)
    normalized_prompt = _normalized_prompt_text(prompt)
    return bool(normalized_reference) and normalized_reference in normalized_prompt


def _requires_fuzzy_target_resolution(prompt: str) -> bool:
    normalized = prompt.casefold()
    return any(cue in normalized for cue in _FUZZY_TARGET_CUES)


def _validate_target_scoped_operations(
    schema: DashboardSchemaV1,
    widget_id: str,
    operations: List[DashboardPatchOperation],
) -> None:
    widget_index = next(
        (
            index
            for index, widget in enumerate(schema.widgets)
            if widget.id == widget_id
        ),
        None,
    )
    if widget_index is None:
        raise ValueError("The resolved widget no longer exists. Reload the dashboard.")
    allowed_prefixes = [f"/widgets/{widget_index}"]
    allowed_prefixes.extend(
        f"/layouts/desktop/{index}"
        for index, item in enumerate(schema.layouts.desktop)
        if item.widget_id == widget_id
    )
    for operation in operations:
        if not any(
            operation.path == prefix or operation.path.startswith(f"{prefix}/")
            for prefix in allowed_prefixes
        ):
            raise ValueError(
                "A fuzzy-reference edit may change only the uniquely resolved "
                f'widget "{widget_id}" and its layout item; rejected path '
                f'"{operation.path}".'
            )


def _tool_result(content: str, **metadata: Any) -> str:
    return json.dumps(
        {
            "chunks": [{"output_type": "text", "content": content}],
            **metadata,
        },
        ensure_ascii=False,
    )


def _decode(value: Any) -> Any:
    if isinstance(value, str):
        return json.loads(value)
    return value


def _proposal_array(value: Any, name: str, *, optional=False) -> List[Any]:
    """Decode a legacy array without hiding the parameter or discarding keys."""
    if value is None and optional:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"{name}: expected a JSON array, not an operation name or free text. "
                f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}."
            ) from None
    if name == "operations" and isinstance(value, dict) and set(value) == {name}:
        value = value[name]
    if not isinstance(value, list):
        raise ValueError(
            f"{name}: expected a JSON array; received {type(value).__name__}. "
            "Pass operation objects inside operations: [{op, path, value}], "
            "not as top-level arguments or a single operation object."
        )
    return value


def _proposal_validation_message(exc: ValidationError) -> str:
    details = []
    for error in exc.errors(include_input=False, include_url=False)[:8]:
        path = ".".join(str(part) for part in error.get("loc", ())) or "proposal"
        details.append(f"{path}: {error['msg']}")
    return "Dashboard change proposal rejected: " + "; ".join(details)


def _plan_validation_message(exc: ValidationError) -> str:
    """Return bounded, model-actionable feedback instead of a huge Pydantic dump."""

    errors = exc.errors()
    details = []
    for item in errors[:8]:
        path = ".".join(str(part) for part in item.get("loc", ())) or "plan"
        details.append(f"- {path}: {item.get('msg', 'invalid value')}")
    remaining = len(errors) - len(details)
    if remaining > 0:
        details.append(f"- ... and {remaining} more validation issue(s).")
    contract = (
        'Required shape: {"title":"...","description":"...",'
        '"business_theme":"...","audience":"...",'
        '"decision_goal":"...","analysis_logic":["..."],'
        '"layout_rationale":"...","filter_strategy":"...",'
        '"metrics":["..."],'
        '"dimensions":["..."],"filters":[{"id":"...",'
        '"type":"date_range|select|multi_select|text|number_range",'
        '"label":"...","field":"real_database_field","default":..., '
        '"options":[{"label":"...","value":...}]}],'
        '"widgets":[{"id":"...","type":"kpi|line|bar|pie|table",'
        '"title":"...","business_question":"...","metric":"...",'
        '"dimensions":["..."],"analysis_level":1,'
        '"rationale":"...","layout":{"width":"quarter|third|half|full",'
        '"height":"compact|standard|tall"}}]}'
    )
    return (
        "Dashboard plan validation failed. Fix the listed fields and call "
        "plan_dashboard again without running more discovery unless a real field "
        "or option value is still unknown.\n" + "\n".join(details) + "\n" + contract
    )


def _draft_validation_message(
    exc: ValidationError, action_name: str = "create_dashboard_draft"
) -> str:
    """Return bounded feedback for model-produced widget query payloads."""

    errors = exc.errors()
    details = []
    for item in errors[:10]:
        path = ".".join(str(part) for part in item.get("loc", ())) or "draft"
        details.append(f"- {path}: {item.get('msg', 'invalid value')}")
    remaining = len(errors) - len(details)
    if remaining > 0:
        details.append(f"- ... and {remaining} more validation issue(s).")
    return (
        "Dashboard draft validation failed. Fix the payload and call "
        f"{action_name} again. Do not rerun data discovery. "
        "filter_parameters must map each Dashboard filter id to a named SQL "
        "parameter string (or start_parameter/end_parameter for a range); output "
        "field types are string|number|integer|boolean|date|datetime|unknown; and "
        "every widget in a filtered dashboard requires a publication contract.\n"
        + "\n".join(details)
    )


def _schema_validation_message(exc: DashboardSchemaValidationError) -> str:
    details = "; ".join(
        f"{issue.path} [{issue.code}]: {issue.message}" for issue in exc.issues
    )
    codes = {issue.code for issue in exc.issues}
    guidance = []
    if any(
        code.startswith("publication_") or code.startswith("unknown_publication")
        for code in codes
    ):
        guidance.append(
            "Publication contract: publication.query must be a bounded unfiltered "
            "SELECT with at most 5000 complete rows. It may aggregate at the full "
            "filter/grouping grain when that preserves the measure. Its "
            "output_fields must declare every field named by "
            "filter_fields, group_by, and measures.source_field. filter_fields keys "
            "are saved Dashboard filter ids and values are fields returned by that "
            "publication query. group_by plus measures.output_field must produce "
            "exactly output_columns. Do not send schema_version; the server upgrades "
            "the Dashboard to 1.3 when a valid publication binding is present."
        )
    if "unbound_sql_parameter" in codes:
        guidance.append(
            "Repeat filter_parameters on every repaired widget: map each saved filter "
            "id to the named SQL parameter (or range start/end parameters). A "
            "multi-select parameter may appear only in IN or NOT IN; do not add an "
            "IS NULL guard."
        )
    suffix = " " + " ".join(guidance) if guidance else ""
    return f"Dashboard schema validation failed: {details}.{suffix}".strip()


def _repair_metadata(
    exc: DashboardSchemaValidationError,
    widget_ids_by_index: Optional[List[str]] = None,
) -> Dict[str, Any]:
    widget_ids = []
    for issue in exc.issues:
        matched = re.match(r"widgets\.([^.]+)\.", issue.path)
        if not matched:
            continue
        widget_id = matched.group(1)
        if widget_id.isdigit() and widget_ids_by_index is not None:
            index = int(widget_id)
            if index < len(widget_ids_by_index):
                widget_id = widget_ids_by_index[index]
        if widget_id not in widget_ids:
            widget_ids.append(widget_id)
    return {
        "status": "repair_required",
        "component_ids": widget_ids,
        "issues": [model_dump_compat(issue) for issue in exc.issues],
    }


def _merge_query_identity(
    widget_queries: Any,
    dashboard_id: Optional[str],
    expected_revision: Optional[int],
) -> Any:
    """Support both the documented nested payload and explicit tool arguments."""

    payload = _decode(widget_queries)
    if isinstance(payload, list):
        payload = {"widgets": payload}
    if not isinstance(payload, dict):
        return payload
    payload = dict(payload)
    for key, explicit in (
        ("dashboard_id", dashboard_id),
        ("expected_revision", expected_revision),
    ):
        nested = payload.get(key)
        if explicit is not None and nested is not None and nested != explicit:
            raise ValueError(f"Conflicting {key} values were supplied.")
        if explicit is not None:
            payload[key] = explicit
    return payload


def _select_query_payload(widget_queries: Any, draft: Any) -> Any:
    """Accept the documented payload and the bounded wrapper used by some models."""

    if widget_queries is None and draft is None:
        raise ValueError("widget_queries is required after plan confirmation.")
    if widget_queries is not None and draft is not None:
        decoded_queries = _decode(widget_queries)
        decoded_draft = _decode(draft)
        if decoded_queries != decoded_draft:
            raise ValueError(
                "Supply either widget_queries or its legacy draft alias, not both."
            )
        return decoded_queries
    return widget_queries if widget_queries is not None else draft


def _snake_case(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", str(value)).strip("_")
    return normalized.casefold()


def _parameter_stems(filter_id: str, field: str) -> List[str]:
    """Return stable stems used only to match existing named placeholders."""

    stems: List[str] = []
    for raw in (field, filter_id):
        value = _snake_case(raw)
        if value and value not in stems:
            stems.append(value)
        for suffix in ("_multi_select", "_date_range", "_select", "_filter", "_multi"):
            if value.endswith(suffix):
                base = value[: -len(suffix)]
                if base and base not in stems:
                    stems.append(base)
    return stems


def _first_parameter(available: Dict[str, str], candidates: List[str]) -> Optional[str]:
    for candidate in candidates:
        matched = available.get(candidate.casefold())
        if matched:
            return matched
    return None


def _infer_filter_parameters(sql: str, plan: DashboardPlan) -> Dict[str, Any]:
    """Link plan filters to placeholders that the model already put in SQL.

    This compatibility step never modifies SQL and never inserts filter values.
    The regular schema validator and SQL security layer remain authoritative.
    """

    names = re.findall(r"(?<!:):([A-Za-z_][A-Za-z0-9_]*)", sql)
    available = {name.casefold(): name for name in names}
    inferred: Dict[str, Any] = {}
    for dashboard_filter in plan.filters:
        stems = _parameter_stems(dashboard_filter.id, dashboard_filter.field)
        if dashboard_filter.type.value in {"date_range", "number_range"}:
            start_candidates: List[str] = []
            end_candidates: List[str] = []
            for stem in stems:
                start_candidates.extend(
                    [
                        f"start_{stem}",
                        f"{stem}_start",
                        f"from_{stem}",
                        f"{stem}_from",
                        f"min_{stem}",
                        f"{stem}_min",
                    ]
                )
                end_candidates.extend(
                    [
                        f"end_{stem}",
                        f"{stem}_end",
                        f"to_{stem}",
                        f"{stem}_to",
                        f"max_{stem}",
                        f"{stem}_max",
                    ]
                )
            start = _first_parameter(available, start_candidates)
            end = _first_parameter(available, end_candidates)
            if start and end:
                inferred[dashboard_filter.id] = {
                    "start_parameter": start,
                    "end_parameter": end,
                }
            continue

        candidates: List[str] = []
        for stem in stems:
            if dashboard_filter.type.value == "multi_select":
                candidates.extend([f"{stem}_ids", f"{stem}_values"])
            candidates.extend([stem, f"{stem}_value"])
        parameter = _first_parameter(available, candidates)
        if parameter:
            inferred[dashboard_filter.id] = parameter
    return inferred


def _normalize_output_fields(value: Any) -> Any:
    aliases = {
        "float": "number",
        "double": "number",
        "decimal": "number",
        "numeric": "number",
        "int": "integer",
        "bigint": "integer",
        "smallint": "integer",
        "str": "string",
        "varchar": "string",
        "text": "string",
        "bool": "boolean",
        "timestamp": "datetime",
    }

    def normalize_item(item: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(item)
        raw_type = result.get("type")
        if isinstance(raw_type, str):
            result["type"] = aliases.get(raw_type.casefold(), raw_type.casefold())
        return result

    if isinstance(value, list):
        return [
            normalize_item(item) if isinstance(item, dict) else item for item in value
        ]
    if not isinstance(value, dict):
        return value
    normalized = []
    for name, definition in value.items():
        if isinstance(definition, str):
            normalized.append(normalize_item({"name": name, "type": definition}))
        elif isinstance(definition, dict):
            normalized.append(normalize_item({"name": name, **definition}))
        else:
            normalized.append({"name": name, "type": "string"})
    return normalized


def _normalize_filter_parameters(
    value: Any, sql: str, plan: DashboardPlan
) -> Dict[str, Any]:
    """Normalize only unambiguous model aliases into filter-id mappings."""

    result = _infer_filter_parameters(sql, plan)
    if not isinstance(value, dict):
        return result
    placeholders = {
        name.casefold(): name
        for name in re.findall(r"(?<!:):([A-Za-z_][A-Za-z0-9_]*)", sql)
    }
    filters_by_id = {item.id: item for item in plan.filters}
    filters_by_field: Dict[str, List[Any]] = {}
    for item in plan.filters:
        for raw in (item.field, item.field.rsplit(".", 1)[-1]):
            filters_by_field.setdefault(raw.casefold(), []).append(item)

    for key, binding in value.items():
        if key in filters_by_id:
            if isinstance(binding, str):
                result[key] = binding
            elif isinstance(binding, dict):
                recognized = {
                    name: binding[name]
                    for name in ("parameter", "start_parameter", "end_parameter")
                    if binding.get(name)
                }
                if recognized:
                    result[key] = recognized
            continue

        field = None
        if isinstance(binding, dict):
            field = binding.get("field")
        elif isinstance(binding, str):
            field = binding
        parameter = placeholders.get(str(key).casefold())
        matches = filters_by_field.get(str(field).casefold(), []) if field else []
        unique_matches = {item.id: item for item in matches}
        if parameter and len(unique_matches) == 1:
            filter_id = next(iter(unique_matches))
            result[filter_id] = parameter
    return result


def _connector_field_names(connector: Any, database_name: str) -> set[str]:
    """Best-effort physical field allowlist used for generated filter plans."""

    names: set[str] = set()
    try:
        tables = connector.get_table_names()
    except Exception:
        return names
    for table in tables or []:
        try:
            fields = connector.get_fields(table, database_name)
        except TypeError:
            try:
                fields = connector.get_fields(table)
            except Exception:
                continue
        except Exception:
            continue
        for field in fields or []:
            if isinstance(field, dict):
                raw_name = field.get("name") or field.get("field")
            elif isinstance(field, (list, tuple)) and field:
                raw_name = field[0]
            else:
                raw_name = getattr(field, "name", field)
            if raw_name is not None:
                names.add(str(raw_name).casefold())
    return names


def _validate_generated_filter_contract(
    plan: DashboardPlan, known_fields: set[str]
) -> None:
    """Require generated filters to be backed by real fields and legal defaults."""

    for dashboard_filter in plan.filters:
        physical_field = dashboard_filter.field.rsplit(".", 1)[-1].casefold()
        if known_fields and physical_field not in known_fields:
            raise ValueError(
                f"Filter '{dashboard_filter.id}' references unknown data field "
                f"'{dashboard_filter.field}'."
            )
        filter_type = dashboard_filter.type.value
        default = dashboard_filter.default
        if filter_type in {"date_range", "number_range"} and not (
            isinstance(default, (list, tuple)) and len(default) == 2
        ):
            raise ValueError(
                f"Range filter '{dashboard_filter.id}' requires a legal two-value "
                "default discovered from the data."
            )
        if filter_type not in {"select", "multi_select"}:
            continue
        if not dashboard_filter.options:
            raise ValueError(
                f"Filter '{dashboard_filter.id}' requires non-empty options "
                "discovered from the data."
            )
        option_values = [option.value for option in dashboard_filter.options]
        if all(value is None for value in option_values):
            raise ValueError(
                f"Filter '{dashboard_filter.id}' needs actual selectable values; "
                "a null/All option alone is not a data-backed choice. Discover "
                "distinct field values. Use an empty default for All."
            )

        def is_option(value: Any) -> bool:
            return any(value == candidate for candidate in option_values)

        if filter_type == "select" and default is not None and not is_option(default):
            raise ValueError(
                f"Filter '{dashboard_filter.id}' default is not one of its options."
            )
        if filter_type == "multi_select" and default is not None:
            if not isinstance(default, (list, tuple)):
                raise ValueError(
                    f"Filter '{dashboard_filter.id}' multi-select default must "
                    "be a list."
                )
            invalid = [value for value in default if not is_option(value)]
            if invalid:
                raise ValueError(
                    f"Filter '{dashboard_filter.id}' defaults are not present in "
                    f"its options: {invalid}."
                )


def _normalize_model_query_payload(payload: Any, plan: DashboardPlan) -> Any:
    """Normalize a small set of observed, unambiguous model wrapper variants."""

    if not isinstance(payload, dict):
        return payload
    normalized = dict(payload)
    # DashboardPlannerService derives Schema 1.3 whenever a publication contract
    # is present.  Some models nevertheless copy ``schema_version`` into this
    # query-only request even though it is not part of DashboardQueryDraftRequest.
    # Ignoring that redundant hint is unambiguous and prevents a valid widget
    # payload from failing StrictModel parsing before semantic validation.
    normalized.pop("schema_version", None)
    normalized.pop("publication_contract", None)
    normalized.pop("failed_widget_ids", None)
    global_filter_parameters = normalized.pop("filter_parameters", None)
    widgets = normalized.get("widgets")
    if widgets is None:
        nested = normalized.pop("widget_queries", None)
        query_map = (
            nested
            if isinstance(nested, dict)
            else {
                key: value
                for key, value in list(normalized.items())
                if key not in {"dashboard_id", "expected_revision"}
                and isinstance(value, dict)
            }
        )
        if query_map:
            for key in list(query_map):
                normalized.pop(key, None)
            widgets = [
                {"widget_id": widget_id, **dict(query)}
                for widget_id, query in query_map.items()
                if isinstance(query, dict)
            ]
            normalized["widgets"] = widgets
    elif isinstance(widgets, dict):
        normalized["widgets"] = [
            {"widget_id": widget_id, **dict(query)}
            for widget_id, query in widgets.items()
            if isinstance(query, dict)
        ]

    for widget in normalized.get("widgets") or []:
        if not isinstance(widget, dict):
            continue
        if widget.get("sql") is None and isinstance(widget.get("query"), str):
            widget["sql"] = widget.pop("query")
        encoding = widget.get("encoding")
        if isinstance(encoding, dict):
            encoding.pop("chart_type", None)
        legacy_fields = widget.pop("fields", None)
        role_dimensions: List[str] = []
        role_metrics: List[str] = []
        if widget.get("output_fields") is None and isinstance(legacy_fields, list):
            output_fields = []
            inferred_encoding: Dict[str, Any] = {}
            for item in legacy_fields:
                if not isinstance(item, dict):
                    output_fields.append(item)
                    continue
                field = dict(item)
                field_encoding = field.pop("encoding", None)
                output_fields.append(field)
                if isinstance(field_encoding, dict):
                    role = str(field_encoding.get("role") or "").casefold()
                    if role == "dimension" and field.get("name"):
                        role_dimensions.append(field["name"])
                    elif role == "metric" and field.get("name"):
                        role_metrics.append(field["name"])
                    channel = field_encoding.get("channel")
                    if channel in {
                        "x",
                        "y",
                        "value",
                        "series",
                        "category",
                        "angle",
                        "color",
                        "y2",
                        "row",
                        "column",
                        "target",
                    } and field.get("name"):
                        inferred_encoding[channel] = field["name"]
                    for inferred_channel in (
                        "x",
                        "y",
                        "value",
                        "series",
                        "category",
                        "angle",
                        "color",
                        "y2",
                        "row",
                        "column",
                        "target",
                    ):
                        if field_encoding.get(inferred_channel) is True and field.get(
                            "name"
                        ):
                            inferred_encoding[inferred_channel] = field["name"]
            widget["output_fields"] = output_fields
            plan_widget = next(
                (item for item in plan.widgets if item.id == widget.get("widget_id")),
                None,
            )
            widget_type = (
                getattr(plan_widget.type, "value", str(plan_widget.type))
                if plan_widget is not None
                else ""
            )
            # Some tool-capable models put semantic roles beside each field
            # instead of emitting the canonical top-level encoding. The approved
            # plan fixes the widget type, so this conversion is deterministic.
            if role_metrics:
                if widget_type == "kpi":
                    inferred_encoding["value"] = role_metrics[0]
                elif widget_type in {"line", "bar"} and role_dimensions:
                    inferred_encoding["x"] = role_dimensions[0]
                    inferred_encoding["y"] = role_metrics[0]
                elif widget_type == "pie" and role_dimensions:
                    inferred_encoding["category"] = role_dimensions[0]
                    inferred_encoding["angle"] = role_metrics[0]
                elif widget_type == "table":
                    inferred_encoding["columns"] = [
                        field.get("name")
                        for field in output_fields
                        if isinstance(field, dict) and field.get("name")
                    ]
            if not widget.get("encoding") and inferred_encoding:
                widget["encoding"] = inferred_encoding
        widget["output_fields"] = _normalize_output_fields(widget.get("output_fields"))
        if not widget.get("filter_parameters") and isinstance(
            global_filter_parameters, dict
        ):
            widget["filter_parameters"] = dict(global_filter_parameters)
        sql = str(widget.get("sql") or "")
        widget["filter_parameters"] = _normalize_filter_parameters(
            widget.get("filter_parameters"), sql, plan
        )
        publication = widget.get("publication")
        if isinstance(publication, dict):
            # ``type`` and ``title`` are presentation hints seen in legacy model
            # output, not a frozen-publication contract. Drop only those known
            # aliases; an empty remainder becomes a missing contract and goes
            # through the normal strict repair/validation path.
            publication.pop("type", None)
            publication.pop("title", None)
            if not publication:
                widget["publication"] = None
                publication = None
        if isinstance(publication, dict):
            publication_query = publication.get("query")
            if isinstance(publication_query, dict):
                legacy_publication_fields = publication_query.pop("fields", None)
                if (
                    publication_query.get("output_fields") is None
                    and legacy_publication_fields is not None
                ):
                    publication_query["output_fields"] = legacy_publication_fields
                legacy_parameters = publication_query.pop("params", None)
                if publication_query.get("default_parameters") is None and isinstance(
                    legacy_parameters, dict
                ):
                    publication_query["default_parameters"] = legacy_parameters
                publication_query["output_fields"] = _normalize_output_fields(
                    publication_query.get("output_fields")
                )
            filters_by_id = {item.id: item for item in plan.filters}
            parameter_to_filter: Dict[str, str] = {}
            raw_parameters = widget.get("filter_parameters")
            if isinstance(raw_parameters, dict):
                for filter_id, binding in raw_parameters.items():
                    if filter_id not in filters_by_id:
                        continue
                    if isinstance(binding, str):
                        parameter_to_filter[binding] = filter_id
                    elif isinstance(binding, dict):
                        for key in (
                            "parameter",
                            "start_parameter",
                            "end_parameter",
                        ):
                            if binding.get(key):
                                parameter_to_filter[str(binding[key])] = filter_id
            raw_filter_fields = publication.get("filter_fields")
            if isinstance(raw_filter_fields, dict):
                canonical_filter_fields: Dict[str, Any] = {}
                for key, value in raw_filter_fields.items():
                    if key in filters_by_id:
                        canonical_filter_fields[key] = value
                        continue
                    reverse_filter_id = None
                    if isinstance(value, str):
                        if value in filters_by_id:
                            # A common model alias is ``field -> filter_id``;
                            # canonical publication bindings are the reverse.
                            canonical_filter_fields[value] = key
                            continue
                        else:
                            reverse_filter_id = parameter_to_filter.get(
                                value
                            ) or parameter_to_filter.get(str(key))
                    if reverse_filter_id:
                        canonical_filter_fields[reverse_filter_id] = value
                publication["filter_fields"] = canonical_filter_fields
            for sort in publication.get("sort") or []:
                if (
                    isinstance(sort, dict)
                    and "direction" not in sort
                    and "order" in sort
                ):
                    sort["direction"] = sort.pop("order")
                if isinstance(sort, dict):
                    direction = sort.get("direction")
                    if isinstance(direction, str):
                        sort["direction"] = {
                            "asc": "ascending",
                            "desc": "descending",
                        }.get(direction.casefold(), direction.casefold())
            if publication.get("output_columns") is None:
                publication["output_columns"] = [
                    item.get("name")
                    for item in widget.get("output_fields") or []
                    if isinstance(item, dict) and item.get("name")
                ]
    return normalized


def _stage_dashboard_query_batch(
    react_state: Dict[str, Any],
    query_request: DashboardQueryDraftRequest,
    plan: DashboardPlan,
) -> tuple[DashboardQueryDraftRequest, List[str]]:
    """Accumulate bounded model tool calls before one atomic draft creation.

    Tool-capable models can truncate a single JSON argument when several widgets
    each carry a frozen-publication contract. Staging keeps every individual call
    small without weakening all-widget validation or exposing a partial asset.
    """

    if query_request.dashboard_id is None:
        raise ValueError("dashboard_id is required after plan confirmation.")
    if query_request.expected_revision is None:
        raise ValueError("expected_revision is required after plan confirmation.")

    plan_ids = [item.id for item in plan.widgets]
    batch_ids = [item.widget_id for item in query_request.widgets]
    if len(batch_ids) != len(set(batch_ids)):
        raise ValueError("Dashboard query widget ids must be unique within a batch.")
    extra = set(batch_ids).difference(plan_ids)
    if extra:
        raise ValueError(
            "Queries refer to widgets that are not in the confirmed plan: "
            + ", ".join(sorted(extra))
            + "."
        )

    identity = {
        "dashboard_id": query_request.dashboard_id,
        "expected_revision": query_request.expected_revision,
    }
    staging = react_state.get("dashboard_query_staging")
    if not isinstance(staging, dict) or any(
        staging.get(key) != value for key, value in identity.items()
    ):
        staging = {**identity, "widgets": {}}

    staged_widgets = staging.get("widgets")
    if not isinstance(staged_widgets, dict):
        staged_widgets = {}
    for widget in query_request.widgets:
        staged_widgets[widget.widget_id] = model_dump_compat(widget)
    staging["widgets"] = staged_widgets
    react_state["dashboard_query_staging"] = staging

    missing = [widget_id for widget_id in plan_ids if widget_id not in staged_widgets]
    combined = model_validate_compat(
        DashboardQueryDraftRequest,
        {
            **identity,
            "widgets": [
                staged_widgets[widget_id]
                for widget_id in plan_ids
                if widget_id in staged_widgets
            ],
        },
    )
    return combined, missing


def make_dashboard_planner_tools(
    react_state: Dict[str, Any],
    database_connector: Optional[Any],
    database_name: Optional[str],
    owner_id: Optional[str],
    user_prompt: str,
    model_name: Optional[str],
    stream_callback: Callable,
    planner_service: Optional[DashboardPlannerService] = None,
) -> List[Any]:
    """Return plan/query tools bound to the current user and selected database."""

    request_token = uuid.uuid4().hex
    original_stream_callback = stream_callback

    async def generation_stream_callback(event_type, payload):
        check_generation_deadline()
        observe_generation_event(react_state, event_type, payload)
        generation = react_state.get("dashboard_generation")
        if generation:
            payload = {
                **payload,
                "generation_id": generation["generation_id"],
                "dashboard_id": generation["dashboard_id"],
                "source_turn_id": generation["source_turn_id"],
            }
        await original_stream_callback(event_type, payload)

    stream_callback = generation_stream_callback

    def generation_stage(stage):
        check_generation_deadline()
        if react_state.get("dashboard_generation"):
            react_state["dashboard_generation"]["stage"] = stage

    def generation_contract_error(exc):
        if any("publication" in issue.path for issue in exc.issues):
            generation_stage("publication_validation")

    dialect = str(getattr(database_connector, "db_type", "unknown") or "unknown")
    dialect_hint = f"The selected SQL dialect is {dialect}."
    if dialect.casefold() == "sqlite":
        dialect_hint += (
            " Use SQLite syntax only: strftime for date parts; never use TO_CHAR, "
            "EXTRACT, or PostgreSQL :: casts."
        )

    def remember_dashboard(
        record: Any,
        workflow_status: str,
        *,
        plan: Optional[DashboardPlan] = None,
    ) -> Dict[str, Any]:
        """Keep compact task-history references without copying dashboard data."""

        reference = {
            "dashboard_id": record.id,
            "title": record.schema_payload.dashboard.title,
            "conversation_id": record.conversation_id,
            "source_turn_id": record.source_turn_id,
            "status": workflow_status,
            "data_source_id": record.schema_payload.dashboard.data_source_id,
            "total_widgets": len(record.schema_payload.widgets),
            "validated_widgets": sum(
                1 for widget in record.schema_payload.widgets if widget.error is None
            ),
            "failed_widgets": sum(
                1
                for widget in record.schema_payload.widgets
                if widget.error is not None
            ),
            "asset_state": (
                record.asset_state.value
                if hasattr(record.asset_state, "value")
                else str(record.asset_state)
            ),
            "current_revision": record.current_revision,
            "editor_path": f"/dashboards/{record.id}",
        }
        if workflow_status == "awaiting_confirmation" and plan is not None:
            # History replay needs enough SQL-free plan state to render the same
            # confirmation controls after a page refresh.  Keep this compact:
            # the editable Dashboard schema and every generated query remain in
            # the Dashboard asset rather than being copied into chat history.
            reference.update(
                {
                    "plan": model_dump_compat(plan),
                    "confirmation_prompt": (
                        f"[[confirm-dashboard:{record.id}]] I confirm this dashboard "
                        "plan at expected revision "
                        f"{record.current_revision}. Generate "
                        "and validate its SQL queries now."
                    ),
                    "revision_prompt": (
                        f"[[revise-dashboard-plan:{record.id}]] Revise this dashboard "
                        f"plan at expected revision {record.current_revision} as "
                        "follows: "
                    ),
                }
            )
        references = list(react_state.get("dashboard_refs") or [])
        references = [
            item for item in references if item.get("dashboard_id") != record.id
        ]
        references.append(reference)
        react_state["dashboard_refs"] = references
        if workflow_status == "created":
            record_generation_result(react_state, record)
        return reference

    if planner_service is None and database_connector is not None and database_name:

        def resolve_connector(requested: str):
            if requested != str(database_name):
                raise ValueError("Dashboard v1 supports only the selected data source.")
            return database_connector

        planner_service = DashboardPlannerService(
            DashboardService(connector_resolver=resolve_connector)
        )

    # A dashboard confirmation is intentionally handled in a later Agent turn.
    # That fresh turn does not inherit the in-memory plan from the planning turn,
    # so reload the authoritative persisted plan before the model writes SQL.  In
    # addition to preventing widget-id guessing, this keeps the prompt and the
    # backend validator anchored to the same revision.
    confirmation_match = re.search(
        r"\[\[confirm-dashboard:([A-Za-z0-9_-]{1,64})\]\]", user_prompt
    )
    if confirmation_match and planner_service is not None:
        confirmed_dashboard_id = confirmation_match.group(1)
        try:
            pending = planner_service.dashboard_service.get_dashboard(
                confirmed_dashboard_id, owner_id
            )
            confirmed_plan_revision = require_current_confirmation(
                pending, user_prompt, str(database_name)
            )
            workflow = pending.schema_payload.metadata.compatibility.get(
                "agent_dashboard_workflow", {}
            )
            stored_plan = workflow.get("plan")
            if stored_plan is not None:
                parsed_plan = model_validate_compat(DashboardPlan, stored_plan)
                normalized_plan = model_dump_compat(parsed_plan)
                react_state["dashboard_plan"] = normalized_plan
                react_state["dashboard_record_id"] = pending.id
                react_state["dashboard_generation"] = {
                    "status": "generating",
                    "generation_id": request_token,
                    "stage": "sql_generation",
                    "dashboard_id": pending.id,
                    "current_revision": confirmed_plan_revision,
                    "source_turn_id": pending.source_turn_id,
                    "title": parsed_plan.title,
                    "data_source_id": str(database_name),
                    "total_widgets": len(parsed_plan.widgets),
                }
                react_state["dashboard_confirmation_contract"] = {
                    "dashboard_id": pending.id,
                    "expected_revision": pending.current_revision,
                    "widgets": [
                        {
                            "widget_id": widget.id,
                            "type": widget.type.value,
                            "title": widget.title,
                            "metric": widget.metric,
                            "dimensions": list(widget.dimensions),
                        }
                        for widget in parsed_plan.widgets
                    ],
                    "filters": [
                        {
                            "filter_id": dashboard_filter.id,
                            "type": dashboard_filter.type.value,
                            "field": dashboard_filter.field,
                        }
                        for dashboard_filter in parsed_plan.filters
                    ],
                }
            else:
                raise ValueError("The saved plan metadata is unavailable.")
        except Exception:
            # Do not disclose whether another user's dashboard exists.  The
            # create tool performs the authoritative permission and revision
            # checks and will return a bounded failure to the Agent.
            react_state["dashboard_confirmation_error"] = (
                "无法继续生成：规划不可访问、已变更、已生成或数据源不匹配。"
                "请重新打开有权限的规划并确认当前修订。"
            )
    elif confirmation_match:
        react_state["dashboard_confirmation_error"] = (
            "无法继续生成：规划或数据源服务不可用。请检查数据源连接后重新打开规划。"
        )

    @tool(
        description=(
            "Load an existing editable dashboard before modifying it. This is a "
            "read-only operation: it returns the authoritative current revision "
            "and complete Dashboard Schema, and never creates a new dashboard. "
            "Call it in the same turn before resolve_dashboard_reference or "
            "modify_dashboard_draft."
        )
    )
    async def load_dashboard_draft(dashboard_id: str) -> str:
        if planner_service is None:
            return _tool_result("Dashboard service is unavailable.")
        known_ids = {
            str(item.get("dashboard_id"))
            for item in react_state.get("dashboard_refs") or []
            if isinstance(item, dict) and item.get("dashboard_id")
        }
        if dashboard_id not in user_prompt and dashboard_id not in known_ids:
            return _tool_result(
                "Dashboard load rejected: the dashboard must be identified by "
                "the current user message or an existing task reference."
            )
        try:
            record = planner_service.dashboard_service.get_dashboard(
                dashboard_id, owner_id
            )
        except Exception as exc:
            return _tool_result(f"Dashboard draft could not be loaded: {exc}")
        react_state["loaded_dashboard_context"] = {
            "dashboard_id": record.id,
            "current_revision": record.current_revision,
            "request_token": request_token,
        }
        react_state["dashboard_record_id"] = record.id
        reference = remember_dashboard(record, "loaded_for_edit")
        return _tool_result(
            "Existing dashboard loaded read-only. Resolve any ambiguous target, "
            "then submit a bounded modification against this exact revision.",
            __dashboard_draft__={
                "dashboard_id": record.id,
                "expected_revision": record.current_revision,
                "title": record.schema_payload.dashboard.title,
                "schema": model_dump_compat(record.schema_payload),
            },
            __dashboard_ref__=reference,
        )

    @tool(
        description=(
            "Resolve a natural reference such as 'this chart' or 'the one on the "
            "right' against the existing dashboard loaded in this turn. The "
            "reference must be copied from the current user message. The server "
            "uses deterministic title/id, layout-position, and explicit-selection "
            "rules. If the result needs clarification, stop and ask the returned "
            "question; do not modify the dashboard."
        )
    )
    async def resolve_dashboard_reference(
        dashboard_id: str,
        reference: str,
        selected_widget_id: Optional[str] = None,
    ) -> str:
        if planner_service is None:
            return _tool_result("Dashboard service is unavailable.")
        loaded = react_state.get("loaded_dashboard_context") or {}
        if (
            loaded.get("request_token") != request_token
            or loaded.get("dashboard_id") != dashboard_id
        ):
            return _tool_result(
                "Dashboard reference resolution rejected: call "
                "load_dashboard_draft for this dashboard in the current turn first."
            )
        if not _reference_is_in_prompt(reference, user_prompt):
            return _tool_result(
                "Dashboard reference resolution rejected: reference must be copied "
                "from the current user message."
            )
        try:
            record = planner_service.dashboard_service.get_dashboard(
                dashboard_id, owner_id
            )
            if record.current_revision != loaded.get("current_revision"):
                raise ValueError(
                    "The dashboard changed after it was loaded. Load it again."
                )
            resolution = resolve_dashboard_target(
                record.schema_payload,
                reference,
                selected_widget_id=selected_widget_id,
            )
        except Exception as exc:
            return _tool_result(f"Dashboard reference could not be resolved: {exc}")
        resolution_payload = model_dump_compat(resolution)
        react_state["dashboard_target_resolution"] = {
            "dashboard_id": dashboard_id,
            "current_revision": record.current_revision,
            "request_token": request_token,
            "reference": reference,
            "resolution": resolution_payload,
        }
        if resolution.status == DashboardTargetResolutionStatus.NEEDS_CLARIFICATION:
            return _tool_result(
                resolution.question
                or "The dashboard target is ambiguous. Ask the user to clarify.",
                __dashboard_target_resolution__=resolution_payload,
            )
        return _tool_result(
            "Dashboard target resolved uniquely. Any fuzzy-reference patch in this "
            "turn is restricted to this widget and its layout item.",
            __dashboard_target_resolution__=resolution_payload,
        )

    @tool(
        description=(
            "First phase for dashboard generation. Submit a DashboardPlan as JSON "
            "with no SQL. Required keys and allowed types are defined by the "
            "generated DashboardPlan shape below. Include useful audience, "
            "decision_goal, analysis_logic, layout_rationale and filter_strategy "
            "when supported by the request. metrics and dimensions are string "
            "arrays, never objects. filters may be empty. "
            + (
                "Optional layout_template: trend-focus (8:4 primary trend/support), "
                "metric-overview (equal comparison grid), operations-detail "
                "(compact KPIs then 8:4 table/support), or null for custom placement. "
                "Honor a user-selected template; it takes precedence over widget "
                "layout hints and supplies matching visual styling. "
                if layout_templates_enabled()
                else "Layout families are not released. Use individual widget "
                "layout width/height hints only. "
            )
            + "Each filter uses real source field names. Range filters require a "
            "two-value default; "
            "select/multi_select require non-empty label/value options discovered "
            "from the data. Each widget requires id, type "
            "(kpi|line|bar|pie|table), title, business_question, metric, and a "
            "dimensions string array. Include analysis_level (1 is the highest "
            "decision level), rationale, and layout width/height intent when "
            "useful; the schema supplies defaults when omitted. Example widget: "
            "{id: sales_trend, type: "
            "line, title: Sales trend, business_question: How did sales change?, "
            "metric: sales, dimensions: [month], analysis_level: 2, rationale: "
            "explains the primary KPI, layout: {width: full, height: standard}}. "
            "The server validates and stores this plan for the current ReAct run. "
            'Parameter: {"plan": "JSON object or JSON string"}'
        ),
        args={
            "plan": {
                "type": "object",
                "description": (
                    "Complete SQL-free DashboardPlan object. A JSON-encoded "
                    "string is also accepted for compatibility. See generated "
                    "DashboardPlan validation shape."
                ),
                "required": True,
            }
        },
    )
    async def plan_dashboard(plan: Optional[Any] = None, **plan_fields: Any) -> str:
        loaded = react_state.get("loaded_dashboard_context") or {}
        if loaded.get("request_token") == request_token or (
            "[[dashboard-annotation:" in user_prompt
        ):
            return _tool_result(
                "Dashboard planning rejected: this request is editing an existing "
                "dashboard. Load and modify that dashboard; do not create a duplicate."
            )
        if database_connector is None or not database_name:
            return _tool_result(
                "A data source must be selected before planning a dashboard."
            )
        # Some ReAct models emit the contents of the sole ``plan`` argument as
        # top-level Action Input fields.  Accept that wire shape while keeping
        # exactly the same validated DashboardPlan contract.
        raw_plan = plan if plan is not None else plan_fields
        if not raw_plan:
            return _tool_result(
                'Dashboard plan validation failed: required parameter "plan" is '
                "missing. Call plan_dashboard with the complete SQL-free plan."
            )
        try:
            verified_olist_plan = verified_olist_plan_for_request(
                user_prompt, str(database_name)
            )
            used_verified_olist_plan = verified_olist_plan is not None
            parsed = verified_olist_plan or model_validate_compat(
                DashboardPlan, _decode(raw_plan)
            )
            if "dashboard_selection_evidence" not in react_state:
                # Selected connector already has the caller's datasource scope.
                try:
                    react_state[
                        "dashboard_selection_evidence"
                    ] = await asyncio.to_thread(
                        collect_temporal_evidence, database_connector
                    )
                except Exception:
                    # Unknown profiling must not block planning or guess counts.
                    react_state["dashboard_selection_evidence"] = {"columns": []}
            parsed = normalize_plan_chart_selection(
                parsed, react_state["dashboard_selection_evidence"]
            )
            widget_ids = [item.id for item in parsed.widgets]
            filter_ids = [item.id for item in parsed.filters]
            if len(widget_ids) != len(set(widget_ids)):
                raise ValueError("Widget ids must be unique.")
            if len(filter_ids) != len(set(filter_ids)):
                raise ValueError("Filter ids must be unique.")
            _validate_generated_filter_contract(
                parsed, _connector_field_names(database_connector, str(database_name))
            )
        except ValidationError as exc:
            return _tool_result(_plan_validation_message(exc))
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            return _tool_result(f"Dashboard plan validation failed: {exc}")

        await stream_callback(
            "dashboard.plan.started",
            {
                "title": parsed.title,
                "conversation_id": react_state.get("conv_id"),
                "source_turn_id": request_token,
            },
        )
        await stream_callback(
            "dashboard.plan.completed",
            {
                "title": parsed.title,
                "source_turn_id": request_token,
                "total_widgets": len(parsed.widgets),
                "total_filters": len(parsed.filters),
            },
        )
        if planner_service is None:
            return _tool_result("Dashboard planning service is unavailable.")
        try:
            record = await planner_service.create_plan_draft(
                plan=parsed,
                data_source_id=str(database_name),
                owner_id=owner_id,
                conversation_id=react_state.get("conv_id"),
                prompt=user_prompt,
                model_name=model_name,
                request_token=request_token,
                event_callback=stream_callback,
            )
        except DashboardSchemaValidationError as exc:
            return _tool_result(_schema_validation_message(exc))
        except Exception as exc:
            return _tool_result(f"Dashboard plan could not be saved: {exc}")

        react_state["dashboard_plan"] = model_dump_compat(parsed)
        react_state["dashboard_record_id"] = record.id
        reference = remember_dashboard(record, "awaiting_confirmation", plan=parsed)
        return _tool_result(
            f"Dashboard plan saved for user review: {len(parsed.widgets)} widgets "
            f"and {len(parsed.filters)} filters. Stop this run and ask the user to "
            "confirm or revise the visible plan. Do not generate SQL in this turn.",
            __dashboard_plan__=model_dump_compat(parsed),
            __dashboard_plan_draft__={
                "dashboard_id": record.id,
                "expected_revision": record.current_revision,
                "status": "awaiting_confirmation",
                "source_turn_id": record.source_turn_id,
            },
            __dashboard_contract__=(
                {"source": "verified_olist_demo", "normalized": True}
                if used_verified_olist_plan
                else None
            ),
            __dashboard_ref__=reference,
        )

    @tool(
        description=(
            "Second phase for dashboard generation. Call only in a later user turn "
            "whose exact input contains [[confirm-dashboard:DASHBOARD_ID]]. Never "
            "call it in the same turn as plan_dashboard and never ask for another "
            "confirmation when that marker is present. Pass dashboard_id and "
            "expected_revision as explicit tool arguments. Pass widget_queries as "
            "a JSON object with exactly one top-level key, widgets. Each widget "
            "requires widget_id, sql, "
            "output_fields, encoding, and may include filter_parameters, "
            "default_parameters, timeout_seconds, max_rows, grain, publication, and "
            "anomaly_rules. anomaly_rules are deterministic server rules, not model "
            "opinions: each enabled rule must name a numeric value_field, optionally a "
            "time_field, choose previous_period, rolling_average, or target_value, and "
            "supply an explicit relative_change or absolute_change threshold. Never "
            "hard-code an unrequested percentage or claim an anomaly in prose. "
            "SQL must be a "
            "single read-only SELECT/CTE and all user filter values must use named "
            f"parameters such as :start_date. {dialect_hint} "
            "The server injects the selected data "
            "source, validates and test-runs each widget independently, preserves "
            "failed widgets as editable errors, and saves a draft. output_fields "
            "must be objects such as {name: total_sales, type: number}, not strings. "
            "Encoding examples: KPI {value: total_sales}; line/bar "
            "{x: month, y: sales}; pie {category: holiday, angle: sales}; "
            "table {columns: [store, sales]}. Every planned filter must be mapped "
            "by at least one widget. Example date mapping: filter_parameters "
            "{date_range: {start_parameter: start_date, end_parameter: end_date}} "
            "with :start_date and :end_date in SQL. number_range uses the same "
            "start_parameter/end_parameter pair (e.g. year_start/year_end) and "
            "BETWEEN :year_start AND :year_end, never a scalar equality binding. "
            "Example multi-select mapping: "
            "{store_filter: store_ids} with :store_ids in SQL. "
            "For multi-selects use only field IN (:parameter); do not add an IS NULL "
            "guard because the backend implements the empty/All semantics. Never "
            "use INSTR, LIKE or comma-delimited strings for a list parameter. "
            "For a dashboard with filters, add publication to every widget so the "
            "anonymous share page can filter a frozen dataset without querying the "
            "database. publication.query must be a bounded, unfiltered SELECT that "
            "returns all filter dimensions plus grouping and measure fields; "
            "do not include data_source_id because the server injects it. "
            "Map Dashboard "
            "filter ids with publication.filter_fields, define group_by and measures, "
            "and list the final widget fields in output_columns. Aggregated example: "
            "{publication: {query: {sql: 'SELECT store, sales FROM sales', "
            "output_fields: [{name: store, type: string}, "
            "{name: sales, type: number}]}, "
            "filter_fields: {store_filter: store}, group_by: [store], measures: "
            "[{source_field: sales, output_field: total_sales, aggregation: sum}], "
            "output_columns: [store, total_sales]}}. For a weighted ratio, use "
            "aggregation: ratio with denominator_field and scale (for example 100 "
            "for a percentage). Both query.max_rows and max_output_rows are at "
            "most 5000 (default 1000); truncated frozen data is rejected. If raw "
            "rows exceed the bound, pre-aggregate at the complete filter/grouping "
            "grain while preserving the measure (sum of sums, or numerator and "
            "denominator for a weighted ratio; never average averages). Do not "
            "silently LIMIT away source rows. Use row_mode only for bounded "
            "detail tables. Every widget requires publication when the plan has "
            "filters, including widgets unaffected by a particular filter. "
            "Submit at most two widgets per call. The server safely stages bounded "
            "batches in this Agent run and creates the Dashboard atomically only "
            "after every confirmed-plan widget has been received. When the tool "
            "reports missing widget ids, call it again with only those missing "
            "widgets; never repeat the whole payload. Parameters: dashboard_id "
            "(string), expected_revision (integer), "
            "widget_queries ({widgets: [...]} object or JSON string). The legacy "
            "draft alias is accepted for compatibility, but never send both."
        ),
        args={
            "dashboard_id": {
                "type": "string",
                "required": False,
                "description": "Confirmed Dashboard ID; supply explicitly.",
            },
            "expected_revision": {
                "type": "integer",
                "required": False,
                "description": "Confirmed plan revision; supply explicitly.",
            },
            "widget_queries": {
                "type": "object",
                "required": False,
                "description": (
                    "Required unless legacy draft is supplied: "
                    "{widgets: DashboardWidgetQueryDraft[]}. At most two widgets "
                    "per call; see generated validation shapes. JSON string "
                    "also accepted."
                ),
            },
            "draft": {
                "type": "object",
                "required": False,
                "description": "Legacy alias; prefer widget_queries and omit draft.",
            },
        },
    )
    async def create_dashboard_draft(
        widget_queries: Optional[Dict[str, Any]] = None,
        dashboard_id: Optional[str] = None,
        expected_revision: Optional[int] = None,
        draft: Optional[Dict[str, Any]] = None,
    ) -> str:
        check_generation_deadline()
        if planner_service is None or database_connector is None or not database_name:
            return _tool_result(
                "A data source must be selected before creating a dashboard."
            )
        try:
            if react_state.get("dashboard_confirmation_error"):
                raise ValueError(react_state["dashboard_confirmation_error"])
            stored_plan = react_state.get("dashboard_plan")
            if stored_plan is None:
                raise ValueError(
                    "The confirmed dashboard plan is unavailable; reopen the "
                    "plan from the task before generating SQL."
                )
            confirmed_plan = model_validate_compat(DashboardPlan, stored_plan)
            merged_payload = _merge_query_identity(
                _select_query_payload(widget_queries, draft),
                dashboard_id,
                expected_revision,
            )
            query_request = model_validate_compat(
                DashboardQueryDraftRequest,
                _normalize_model_query_payload(merged_payload, confirmed_plan),
            )
            resolved_dashboard_id = query_request.dashboard_id or react_state.get(
                "dashboard_record_id"
            )
            if not resolved_dashboard_id:
                raise ValueError("dashboard_id is required after plan confirmation.")
            marker = f"[[confirm-dashboard:{resolved_dashboard_id}]]"
            if marker not in user_prompt:
                raise ValueError(
                    "The current user turn did not explicitly confirm this plan."
                )
            pending = planner_service.dashboard_service.get_dashboard(
                str(resolved_dashboard_id), owner_id
            )
            if pending.schema_payload.dashboard.data_source_id != str(database_name):
                raise ValueError(
                    "Select the same data source that was used to create this plan "
                    "before confirming it."
                )
            resolved_expected_revision = query_request.expected_revision
            if resolved_expected_revision is None:
                confirmation_contract = (
                    react_state.get("dashboard_confirmation_contract") or {}
                )
                resolved_expected_revision = confirmation_contract.get(
                    "expected_revision"
                )
            bound_revision = require_current_confirmation(
                pending, user_prompt, str(database_name)
            )
            if resolved_expected_revision != bound_revision:
                raise ValueError("Use the exact revision confirmed by the user.")
            query_request = model_validate_compat(
                DashboardQueryDraftRequest,
                {
                    **model_dump_compat(query_request),
                    "dashboard_id": str(resolved_dashboard_id),
                    "expected_revision": resolved_expected_revision,
                },
            )
            query_request, missing_widget_ids = _stage_dashboard_query_batch(
                react_state, query_request, confirmed_plan
            )
            if missing_widget_ids:
                staged_widget_ids = [item.widget_id for item in query_request.widgets]
                return _tool_result(
                    f"Staged {len(staged_widget_ids)} of "
                    f"{len(confirmed_plan.widgets)} Dashboard widget queries. "
                    "Call create_dashboard_draft again with at most two of these "
                    "missing widget ids: "
                    + ", ".join(missing_widget_ids)
                    + ". Do not repeat already staged widgets or rerun discovery.",
                    __dashboard_generation_staging__={
                        "status": "collecting_queries",
                        "dashboard_id": str(resolved_dashboard_id),
                        "expected_revision": resolved_expected_revision,
                        "staged_widget_ids": staged_widget_ids,
                        "missing_widget_ids": missing_widget_ids,
                        "max_widgets_per_call": 2,
                    },
                )
            generation_stage("contract_validation")
            record, _ = await planner_service.complete_plan_draft(
                dashboard_id=str(resolved_dashboard_id),
                query_request=query_request,
                owner_id=owner_id,
                request_token=request_token,
                event_callback=stream_callback,
            )
        except DashboardGenerationTimeout:
            raise
        except DashboardSchemaValidationError as exc:
            generation_contract_error(exc)
            return _tool_result(
                _schema_validation_message(exc)
                + " Generation entered the repair stage automatically; correct "
                "the listed components and retry before reporting completion.",
                __dashboard_repair_required__=_repair_metadata(exc),
            )
        except ValidationError as exc:
            return _tool_result(_draft_validation_message(exc))
        except json.JSONDecodeError:
            return _tool_result(
                "Dashboard draft payload was truncated or malformed JSON. Do not "
                "retry the complete Dashboard payload. Call create_dashboard_draft "
                "again with dashboard_id, expected_revision, and at most two "
                "confirmed-plan widgets; the server will stage batches until all "
                "widgets are present."
            )
        except (TypeError, ValueError) as exc:
            return _tool_result(f"Dashboard draft validation failed: {exc}")
        except Exception as exc:
            return _tool_result(f"Dashboard draft could not be saved: {exc}")

        failed = sum(1 for item in record.schema_payload.widgets if item.error)
        react_state.pop("dashboard_query_staging", None)
        react_state["dashboard_record_id"] = record.id
        reference = remember_dashboard(record, "created")
        dashboard_payload = {
            "dashboard_id": record.id,
            "source_turn_id": record.source_turn_id,
            "title": record.schema_payload.dashboard.title,
            "editor_path": f"/dashboards/{record.id}",
            "total_widgets": len(record.schema_payload.widgets),
            "validated_widgets": len(record.schema_payload.widgets) - failed,
            "failed_widgets": failed,
            "asset_state": reference["asset_state"],
            "publishable": failed == 0,
        }
        next_step = (
            f" {failed} widget(s) failed. Call repair_dashboard_draft with corrected "
            "queries for only those widgets."
            if failed
            else ""
        )
        return _tool_result(
            "Dashboard draft created. Open it in the editor to review, refresh, "
            f"and publish.{next_step}",
            __dashboard__=dashboard_payload,
        )

    @tool(
        description=(
            "Repair selected widgets in the current dashboard draft after "
            "create_dashboard_draft reports failures. Submit "
            "{widgets: [{widget_id, sql, filter_parameters, output_fields, "
            "encoding, publication}]} and include only failed widgets; successful "
            "widgets remain unchanged. Repeat filter_parameters for every repaired "
            "widget. Keys are saved Dashboard filter ids and values are named SQL "
            "parameters (or start_parameter/end_parameter for a range). For a "
            "multi-select, use only field IN (:parameter), without an IS NULL "
            "guard. Every widget in a filtered plan also requires publication. "
            "publication.query must be a bounded, unfiltered SELECT (max_rows <= "
            "5000), optionally pre-aggregated at the complete filter/grouping "
            "grain while preserving the measure, with output_fields that "
            "declare every field referenced by publication.filter_fields, group_by, "
            "and measures.source_field. publication.filter_fields maps saved filter "
            "ids to those raw query field names. group_by plus each "
            "measures.output_field must produce exactly output_columns, which must "
            "also equal the editor widget output names. Example KPI publication: "
            "{query: {sql: 'SELECT store, sales FROM sales', output_fields: "
            "[{name: store, type: string}, {name: sales, type: number}]}, "
            "filter_fields: {store_filter: store}, group_by: [], measures: "
            "[{source_field: sales, output_field: total_sales, aggregation: sum}], "
            "output_columns: [total_sales], row_mode: false}. Do not send "
            "schema_version or invent dataset_fields; the server upgrades the "
            "Dashboard to Schema 1.3 after a valid publication contract. The "
            "object, list, and widget-id map wrappers accepted by "
            "create_dashboard_draft are also normalized here."
        ),
        args={
            "widget_queries": {
                "type": "object",
                "required": True,
                "description": (
                    "DashboardQueryDraftRequest object with widgets containing "
                    "only failed components. Put dashboard_id inside this object "
                    "for a later repair. JSON string also accepted; see generated "
                    "validation shapes."
                ),
            }
        },
    )
    async def repair_dashboard_draft(widget_queries: Any) -> str:
        generation_stage("repair")
        stored_plan = react_state.get("dashboard_plan")
        if planner_service is None:
            return _tool_result(
                "Create a dashboard draft before attempting a widget repair."
            )
        query_request: Optional[DashboardQueryDraftRequest] = None
        try:
            raw_payload = _decode(widget_queries)
            dashboard_id = (
                raw_payload.get("dashboard_id")
                if isinstance(raw_payload, dict)
                else None
            ) or react_state.get("dashboard_record_id")
            if not dashboard_id:
                raise ValueError("dashboard_id is required for a later repair.")
            if stored_plan is None:
                existing = planner_service.dashboard_service.get_dashboard(
                    str(dashboard_id), owner_id
                )
                workflow = existing.schema_payload.metadata.compatibility.get(
                    "agent_dashboard_workflow", {}
                )
                stored_plan = workflow.get("plan")
            if stored_plan is None:
                raise ValueError("The original dashboard plan is unavailable.")
            plan = model_validate_compat(DashboardPlan, stored_plan)
            query_request = model_validate_compat(
                DashboardQueryDraftRequest,
                _normalize_model_query_payload(raw_payload, plan),
            )
            record, _ = await planner_service.repair_draft(
                dashboard_id=str(dashboard_id),
                plan=plan,
                query_request=query_request,
                owner_id=owner_id,
                event_callback=stream_callback,
            )
        except DashboardGenerationTimeout:
            raise
        except DashboardSchemaValidationError as exc:
            generation_contract_error(exc)
            return _tool_result(
                _schema_validation_message(exc)
                + " Repair is still incomplete; do not report this dashboard as "
                "publishable.",
                __dashboard_repair_required__=_repair_metadata(
                    exc,
                    [item.widget_id for item in query_request.widgets]
                    if query_request is not None
                    else None,
                ),
            )
        except ValidationError as exc:
            return _tool_result(
                _draft_validation_message(exc, "repair_dashboard_draft")
            )
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            return _tool_result(f"Dashboard repair validation failed: {exc}")
        except Exception as exc:
            return _tool_result(f"Dashboard repair could not be saved: {exc}")

        failed = sum(1 for item in record.schema_payload.widgets if item.error)
        reference = remember_dashboard(record, "created")
        dashboard_payload = {
            "dashboard_id": record.id,
            "source_turn_id": record.source_turn_id,
            "title": record.schema_payload.dashboard.title,
            "editor_path": f"/dashboards/{record.id}",
            "total_widgets": len(record.schema_payload.widgets),
            "validated_widgets": len(record.schema_payload.widgets) - failed,
            "failed_widgets": failed,
            "asset_state": reference["asset_state"],
            "publishable": failed == 0,
        }
        return _tool_result(
            f"Dashboard repair saved. {failed} widget(s) still need attention.",
            __dashboard__=dashboard_payload,
        )

    @tool(
        description=(
            "Revise a saved SQL-free dashboard plan before confirmation. Call only "
            "when the current user input contains "
            "[[revise-dashboard-plan:DASHBOARD_ID]]. Parameters: dashboard_id, "
            "expected_revision, and plan (the complete replacement DashboardPlan "
            "JSON without SQL). The revised plan pauses for confirmation again."
        )
    )
    async def revise_dashboard_plan(
        dashboard_id: str, expected_revision: int, plan: str
    ) -> str:
        if planner_service is None:
            return _tool_result("Dashboard planning service is unavailable.")
        marker = f"[[revise-dashboard-plan:{dashboard_id}]]"
        if marker not in user_prompt:
            return _tool_result(
                "The current user turn did not explicitly request a plan revision."
            )
        try:
            parsed = model_validate_compat(DashboardPlan, _decode(plan))
            parsed = normalize_plan_chart_selection(parsed)
            record = await planner_service.revise_plan_draft(
                dashboard_id=dashboard_id,
                plan=parsed,
                expected_revision=expected_revision,
                owner_id=owner_id,
                request_token=request_token,
                prompt=user_prompt,
                model_name=model_name,
                event_callback=stream_callback,
            )
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
            return _tool_result(f"Dashboard plan revision failed: {exc}")
        except Exception as exc:
            return _tool_result(f"Dashboard plan could not be revised: {exc}")
        react_state["dashboard_plan"] = model_dump_compat(parsed)
        react_state["dashboard_record_id"] = record.id
        reference = remember_dashboard(record, "awaiting_confirmation", plan=parsed)
        return _tool_result(
            "Dashboard plan revised. Stop this run and ask the user to confirm the "
            "updated visible plan before generating SQL.",
            __dashboard_plan__=model_dump_compat(parsed),
            __dashboard_plan_draft__={
                "dashboard_id": record.id,
                "expected_revision": record.current_revision,
                "status": "awaiting_confirmation",
                "source_turn_id": record.source_turn_id,
            },
            __dashboard_ref__=reference,
        )

    @tool(
        description=(
            "Modify an existing editable dashboard when the user explicitly asks. "
            "You must call load_dashboard_draft for the same dashboard in this "
            "turn first. If the request uses a relative or deictic target, also "
            "call resolve_dashboard_reference and proceed only when it resolves "
            "uniquely. "
            "Submit dashboard_id and a JSON array of bounded "
            "RFC 6902 add/remove/replace operations. Prefer narrow paths such as "
            "/dashboard/title, /widgets/0/title, /widgets/0/type, "
            "/widgets/0/query/sql, /widgets/0/encoding, /filters, or /layouts. "
            "Identity, status, data-source bindings, execution metadata, and Agent "
            "metadata cannot be changed. The complete patched schema and every "
            "query are validated and test-run before the atomic save."
        )
    )
    async def modify_dashboard_draft(
        dashboard_id: str,
        operations: str,
        expected_revision: Optional[int] = None,
    ) -> str:
        if planner_service is None:
            return _tool_result("Dashboard service is unavailable.")
        if "[[dashboard-annotation:" in user_prompt:
            return _tool_result(
                "Selection-aware edits must use propose_dashboard_change so the "
                "user can preview and approve the change before it is saved."
            )
        if dashboard_id not in user_prompt:
            return _tool_result(
                "Dashboard modification rejected: the current user message must "
                "identify the dashboard being changed."
            )
        loaded = react_state.get("loaded_dashboard_context") or {}
        if (
            loaded.get("request_token") != request_token
            or loaded.get("dashboard_id") != dashboard_id
        ):
            return _tool_result(
                "Dashboard modification rejected: call load_dashboard_draft for "
                "this dashboard in the current turn before modifying it."
            )
        try:
            dashboard_service = planner_service.dashboard_service
            existing = dashboard_service.get_dashboard(dashboard_id, owner_id)
            if existing.current_revision != loaded.get("current_revision"):
                raise ValueError(
                    "The dashboard changed after it was loaded. Reload it before "
                    "retrying."
                )
            if expected_revision is not None and expected_revision != loaded.get(
                "current_revision"
            ):
                raise ValueError(
                    "expected_revision does not match the loaded dashboard revision."
                )
            raw_operations = _decode(operations)
            if isinstance(raw_operations, dict):
                raw_operations = raw_operations.get("operations")
            if not isinstance(raw_operations, list):
                raise ValueError("operations must be a JSON array.")
            parsed_operations = [
                model_validate_compat(DashboardPatchOperation, item)
                for item in raw_operations
            ]
            for operation in parsed_operations:
                path_segments = operation.path.split("/")
                if "data_source_id" in path_segments:
                    raise ValueError("Agent edits cannot change data-source bindings.")
                if "metadata" in path_segments:
                    raise ValueError("Agent edits cannot change dashboard metadata.")
            if _requires_fuzzy_target_resolution(user_prompt):
                resolved = react_state.get("dashboard_target_resolution") or {}
                resolution = resolved.get("resolution") or {}
                target = resolution.get("target") or {}
                if (
                    resolved.get("request_token") != request_token
                    or resolved.get("dashboard_id") != dashboard_id
                    or resolved.get("current_revision") != existing.current_revision
                    or resolution.get("status") != "resolved"
                    or not target.get("widget_id")
                ):
                    raise ValueError(
                        "The natural target is not uniquely resolved. Call "
                        "resolve_dashboard_reference and ask the user if it returns "
                        "needs_clarification."
                    )
                _validate_target_scoped_operations(
                    existing.schema_payload,
                    str(target["widget_id"]),
                    parsed_operations,
                )
            patched_payload = apply_dashboard_patch(
                model_dump_compat(existing.schema_payload), parsed_operations
            )
            patched_schema = model_validate_compat(DashboardSchemaV1, patched_payload)
            dashboard_service.require_permission(
                dashboard_id,
                owner_id,
                DashboardAction.QUERY,
                patched_schema,
            )
            validation = dashboard_service.validate_schema(
                patched_schema,
                execute_queries=True,
            )
            if not validation.valid:
                messages = "; ".join(item.message for item in validation.issues[:5])
                raise ValueError(f"Patched dashboard validation failed: {messages}")

            collaboration = DashboardCollaborationService(dashboard_service)
            response = collaboration.apply_operation(
                dashboard_id,
                DashboardOperationRequest(
                    operation_id=f"agent-{uuid.uuid4().hex}",
                    client_id="dashboard-agent",
                    expected_revision=existing.current_revision,
                    operations=parsed_operations,
                ),
                str(owner_id or existing.owner_id),
                promote_to_asset=False,
                version_source="ai_edit",
            )
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
            return _tool_result(f"Dashboard modification rejected: {exc}")
        except Exception as exc:
            return _tool_result(f"Dashboard modification could not be saved: {exc}")

        record = response.dashboard
        react_state["loaded_dashboard_context"] = {
            "dashboard_id": record.id,
            "current_revision": record.current_revision,
            "request_token": request_token,
        }
        react_state.pop("dashboard_target_resolution", None)
        reference = remember_dashboard(record, "updated")
        await stream_callback(
            "dashboard.updated",
            {
                "dashboard_id": record.id,
                "source_turn_id": record.source_turn_id,
                "title": record.schema_payload.dashboard.title,
                "editor_path": f"/dashboards/{record.id}",
                "total_widgets": len(record.schema_payload.widgets),
                "current_revision": record.current_revision,
                "asset_state": reference["asset_state"],
            },
        )
        return _tool_result(
            "Dashboard changes were validated, test-run, and saved atomically.",
            __dashboard__={
                "dashboard_id": record.id,
                "source_turn_id": record.source_turn_id,
                "title": record.schema_payload.dashboard.title,
                "editor_path": f"/dashboards/{record.id}",
                "current_revision": record.current_revision,
                "total_widgets": len(record.schema_payload.widgets),
                "asset_state": reference["asset_state"],
            },
        )

    @tool(
        description=(
            "Propose, but do not save, a modification for a persisted Dashboard "
            "annotation. Use only when the current message contains the exact "
            "[[dashboard-annotation:ID]] marker. Address widgets and filters by "
            "stable paths such as /widgets/by-id/total-sales/title, "
            "/widgets/by-id/store-ranking/presentation/visualization, or "
            "/filters/by-id/store/default. The server resolves ids, applies the "
            "patch in memory, validates the complete Schema and test-runs queries. "
            "The user must explicitly apply the returned proposal in the UI."
        ),
        args=model_tool_parameters(DashboardProposalToolInput),
    )
    async def propose_dashboard_change(
        dashboard_id: str,
        annotation_id: str,
        summary: str,
        operations: List[Dict[str, Any]],
        before: Optional[List[str]] = None,
        after: Optional[List[str]] = None,
    ) -> str:
        def failure_result(message: str) -> str:
            return _tool_result(
                message,
                __dashboard_tool_error__={
                    "tool": "propose_dashboard_change",
                    "stage": "annotation_proposal",
                    "code": "proposal_validation_failed",
                    "reason": message,
                    "retryable": True,
                },
            )

        if planner_service is None:
            return failure_result("Dashboard service is unavailable.")
        scoped_marker = f"[[dashboard-annotation:{dashboard_id}:{annotation_id}]]"
        legacy_marker = f"[[dashboard-annotation:{annotation_id}]]"
        if (
            scoped_marker not in user_prompt and legacy_marker not in user_prompt
        ) or dashboard_id not in user_prompt:
            return failure_result(
                "Dashboard proposal rejected: the current user message must "
                "identify both the dashboard and persisted annotation."
            )
        annotation_service = DashboardAnnotationService(
            planner_service.dashboard_service
        )

        def failed_proposal(message: str) -> str:
            try:
                annotation_service.invalidate_pending_proposal(
                    dashboard_id,
                    annotation_id,
                    str(owner_id or "001"),
                    reason=message,
                )
            except Exception:
                # Preserve the actionable tool failure even if the annotation was
                # concurrently removed or its status changed in another client.
                logger.exception(
                    "Failed to invalidate dashboard annotation %s after a rejected "
                    "proposal for dashboard %s.",
                    annotation_id,
                    dashboard_id,
                )
            return failure_result(message)

        try:
            request = DashboardProposalToolInput.model_validate(
                {
                    "dashboard_id": dashboard_id,
                    "annotation_id": annotation_id,
                    "summary": summary,
                    "operations": _proposal_array(operations, "operations"),
                    "before": _proposal_array(before, "before", optional=True),
                    "after": _proposal_array(after, "after", optional=True),
                }
            )
            await stream_callback(
                "dashboard.change.proposal.started",
                {
                    "dashboard_id": dashboard_id,
                    "annotation_id": annotation_id,
                },
            )
            annotation = annotation_service.propose_change(
                dashboard_id,
                annotation_id,
                DashboardChangeProposalRequest(
                    summary=request.summary,
                    operations=request.operations,
                    before=request.before,
                    after=request.after,
                ),
                str(owner_id or "001"),
            )
        except DashboardSchemaValidationError as exc:
            return failed_proposal(_schema_validation_message(exc))
        except ValidationError as exc:
            return failed_proposal(_proposal_validation_message(exc))
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            return failed_proposal(f"Dashboard change proposal rejected: {exc}")
        except Exception as exc:
            return failed_proposal(f"Dashboard change proposal failed: {exc}")

        proposal = annotation.proposal
        await stream_callback(
            "dashboard.change.proposed",
            {
                "dashboard_id": dashboard_id,
                "annotation_id": annotation_id,
                "base_revision": annotation.base_revision,
                "summary": proposal.summary if proposal else summary,
                "operation_count": len(proposal.operations) if proposal else 0,
            },
        )
        return _tool_result(
            "Dashboard change proposal validated. It has not been saved; wait "
            "for the user to apply or reject it in the Dashboard UI.",
            __dashboard_change_proposal__=model_dump_compat(annotation),
        )

    tools = [
        load_dashboard_draft,
        resolve_dashboard_reference,
        plan_dashboard,
        create_dashboard_draft,
        repair_dashboard_draft,
        revise_dashboard_plan,
        modify_dashboard_draft,
        propose_dashboard_change,
    ]
    read_only_annotation_turn = (
        "[[dashboard-annotation:" in user_prompt
        and "[修改组件]" not in user_prompt
        and ("[指标解释]" in user_prompt or "[异常分析]" in user_prompt)
    )
    if read_only_annotation_turn:
        return [load_dashboard_draft, resolve_dashboard_reference]
    return tools
