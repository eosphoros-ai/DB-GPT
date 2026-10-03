"""Deterministic bridge from an Agent plan to an editable dashboard draft."""

import inspect
import re
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from .chart_selection import normalize_executed_chart, normalize_plan_chart_selection
from .demo_contracts import (
    repair_safe_static_publication_contracts,
    repair_verified_olist_generation_contract,
)
from .generation_budget import check_generation_deadline, generation_read
from .layout_templates import template_layout, template_theme
from .release_features import layout_templates_enabled
from .schemas import (
    AgentGenerationInfo,
    ChartEncoding,
    DashboardAction,
    DashboardCreateRequest,
    DashboardDescriptor,
    DashboardLayouts,
    DashboardMetadata,
    DashboardPlan,
    DashboardPlanWidget,
    DashboardPublicationBinding,
    DashboardQueryDraftRequest,
    DashboardRecord,
    DashboardSchemaV1,
    DashboardThemeMode,
    DashboardThemePreset,
    DashboardVisualTheme,
    DashboardWidget,
    DashboardWidgetQueryDraft,
    DimensionDefinition,
    LastExecution,
    LayoutItem,
    MetricContext,
    MetricDefinition,
    QueryOutputField,
    SemanticDefinitionSource,
    ValidationIssue,
    WidgetError,
    WidgetQueryBinding,
    WidgetQueryResult,
    WidgetType,
    model_dump_compat,
    model_validate_compat,
)
from .service import DashboardSchemaValidationError, DashboardService

DashboardEventCallback = Callable[[str, Dict[str, Any]], Optional[Awaitable[None]]]


def _semantic_id(prefix: str, label: str, index: int) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "-", label).strip("-").lower()
    # Distinct multilingual labels can collapse to the same ASCII slug (for
    # example two Chinese metrics containing Weekly_Sales). Keep the ordinal
    # before the slug so truncation cannot erase uniqueness within this plan.
    return f"{prefix}-{index + 1}-{normalized or 'item'}"[:128]


async def _emit(
    callback: Optional[DashboardEventCallback], event_type: str, payload: Dict[str, Any]
) -> None:
    if callback is None:
        return
    result = callback(event_type, payload)
    if inspect.isawaitable(result):
        await result


def _reject_empty_agent_result(
    result: WidgetQueryResult, *, expected_empty: bool = False
) -> WidgetQueryResult:
    """Keep unexpected empty results actionable; honor an approved empty table."""

    if result.error is not None or result.row_count > 0 or expected_empty:
        return result
    empty_error = WidgetError(
        code="planner_widget_empty_result",
        message=("查询执行成功但返回 0 行；请检查默认筛选条件、关联关系和字段后重试。"),
        retryable=True,
    )
    if hasattr(result, "model_copy"):
        return result.model_copy(update={"error": empty_error})
    return result.copy(update={"error": empty_error})


def _expects_empty_table(schema: DashboardSchemaV1, widget: DashboardWidget) -> bool:
    """Only the approved plan can permit a no-data detail table."""
    plan = schema.metadata.compatibility.get("dashboard_plan", {})
    return widget.type == WidgetType.TABLE and any(
        item.get("id") == widget.id and item.get("expected_data_points") == 0
        for item in plan.get("widgets", [])
    )


def _default_encoding(
    widget_type: WidgetType, fields: List[QueryOutputField]
) -> ChartEncoding:
    names = [item.name for item in fields]
    first = names[0] if names else "value"
    second = names[1] if len(names) > 1 else first
    if widget_type == WidgetType.KPI:
        return ChartEncoding(value=first)
    if widget_type in (WidgetType.LINE, WidgetType.BAR):
        return ChartEncoding(x=first, y=second)
    if widget_type == WidgetType.PIE:
        return ChartEncoding(category=first, color=first, angle=second)
    return ChartEncoding(columns=names)


def _canonical_encoding(
    widget_type: WidgetType,
    fields: List[QueryOutputField],
    proposed: ChartEncoding,
) -> ChartEncoding:
    """Keep only valid encoding slots for the approved widget type.

    Model output often mixes chart vocabularies (for example ``value`` on a
    table).  Carrying those irrelevant fields into the persisted schema makes
    an otherwise valid query fail cross-field validation.  Canonicalization is
    deliberately server-side and never invents executable SQL.
    """

    names = {item.name for item in fields}
    defaults = _default_encoding(widget_type, fields)

    def valid(name: Optional[str], fallback: Optional[str] = None) -> Optional[str]:
        return name if name in names else fallback

    if widget_type == WidgetType.KPI:
        return ChartEncoding(value=valid(proposed.value, defaults.value))
    if widget_type in (WidgetType.LINE, WidgetType.BAR):
        return ChartEncoding(
            x=valid(proposed.x, defaults.x),
            y=valid(proposed.y, defaults.y),
            series=valid(proposed.series),
            color=valid(proposed.color),
        )
    if widget_type == WidgetType.PIE:
        return ChartEncoding(
            category=valid(proposed.category, defaults.category),
            angle=valid(proposed.angle, defaults.angle),
            color=valid(proposed.color, defaults.color),
        )
    columns = [name for name in proposed.columns if name in names]
    return ChartEncoding(columns=columns or defaults.columns)


def _merge_plan_revision_context(
    original: DashboardPlan, revised: DashboardPlan
) -> DashboardPlan:
    """Keep decision context that a narrowly scoped model revision omitted.

    Plan revisions are commonly requests such as removing a filter or reducing the
    widget set. Model defaults turn omitted narrative fields into empty values,
    which previously erased the confirmed audience, decision goal, analysis logic,
    and layout rationale even though the user never asked to change them.
    """

    original_payload = model_dump_compat(original)
    revised_payload = model_dump_compat(revised)
    revised_fields = getattr(revised, "model_fields_set", None)
    if revised_fields is None:
        revised_fields = revised.__fields_set__
    if "layout_template" not in revised_fields:
        revised_payload["layout_template"] = original_payload.get("layout_template")
    for field in (
        "description",
        "audience",
        "decision_goal",
        "layout_rationale",
    ):
        value = revised_payload.get(field)
        if not isinstance(value, str) or not value.strip():
            revised_payload[field] = original_payload.get(field, "")
    if not revised_payload.get("analysis_logic"):
        revised_payload["analysis_logic"] = original_payload.get("analysis_logic", [])
    filter_strategy = revised_payload.get("filter_strategy")
    if not isinstance(filter_strategy, str) or not filter_strategy.strip():
        if revised_payload.get("filters") == original_payload.get("filters"):
            revised_payload["filter_strategy"] = original_payload.get(
                "filter_strategy", ""
            )
        elif revised_payload.get("filters"):
            revised_payload["filter_strategy"] = (
                "Use the revised global filters to constrain the approved analysis "
                "scope."
            )
        else:
            revised_payload["filter_strategy"] = (
                "No global filters are used in this revision; widgets show the "
                "full approved analysis scope."
            )

    original_widgets = {
        item.get("id"): item for item in original_payload.get("widgets", [])
    }
    for widget in revised_payload.get("widgets", []):
        previous = original_widgets.get(widget.get("id"))
        if not previous:
            continue
        if not str(widget.get("rationale") or "").strip():
            widget["rationale"] = previous.get("rationale", "")
        if widget.get("layout") is None and previous.get("layout") is not None:
            widget["layout"] = previous["layout"]
    return model_validate_compat(DashboardPlan, revised_payload)


def _placeholder_query(
    widget_type: WidgetType,
) -> Tuple[str, List[QueryOutputField], ChartEncoding]:
    if widget_type == WidgetType.KPI:
        fields = [QueryOutputField(name="value", type="number")]
        return "SELECT 0 AS value", fields, ChartEncoding(value="value")
    if widget_type == WidgetType.TABLE:
        fields = [QueryOutputField(name="message", type="string")]
        return (
            "SELECT 'Query generation failed' AS message",
            fields,
            ChartEncoding(columns=["message"]),
        )
    fields = [
        QueryOutputField(name="category", type="string"),
        QueryOutputField(name="value", type="number"),
    ]
    if widget_type == WidgetType.PIE:
        encoding = ChartEncoding(category="category", color="category", angle="value")
    else:
        encoding = ChartEncoding(x="category", y="value")
    return "SELECT 'Unavailable' AS category, 0 AS value", fields, encoding


def _layout_for(
    widgets: List[DashboardWidget],
    plan_widgets: Optional[List[DashboardPlanWidget]] = None,
) -> DashboardLayouts:
    items: List[LayoutItem] = []
    plan_by_id = {item.id: item for item in plan_widgets or []}
    width_by_name = {"quarter": 3, "third": 4, "half": 6, "full": 12}
    height_by_name = {"compact": 3, "standard": 5, "tall": 7}
    x = 0
    y = 0
    row_height = 0
    for widget in widgets:
        planned_layout = plan_by_id.get(widget.id)
        planned_layout = planned_layout.layout if planned_layout else None
        if planned_layout is not None:
            width = width_by_name[planned_layout.width.value]
            height = height_by_name[planned_layout.height.value]
        elif widget.type == WidgetType.KPI:
            width, height = 3, 3
        elif widget.type == WidgetType.TABLE:
            width, height = 12, 6
        else:
            width, height = 6, 5
        if width == 12 and x:
            y += row_height
            x = 0
            row_height = 0
        if x + width > 12:
            y += row_height
            x = 0
            row_height = 0
        items.append(LayoutItem(widget_id=widget.id, x=x, y=y, w=width, h=height))
        row_height = max(row_height, height)
        x += width
        if x == 12:
            y += row_height
            x = 0
            row_height = 0
    return DashboardLayouts(desktop=items)


class DashboardPlannerService:
    """Build, validate, execute, and persist one partial Agent dashboard draft."""

    def __init__(self, dashboard_service: DashboardService) -> None:
        self.dashboard_service = dashboard_service

    @staticmethod
    def _validate_plan_ids(plan: DashboardPlan) -> None:
        plan_ids = [item.id for item in plan.widgets]
        filter_ids = [item.id for item in plan.filters]
        if len(plan_ids) != len(set(plan_ids)):
            raise ValueError("Dashboard plan widget ids must be unique.")
        if len(filter_ids) != len(set(filter_ids)):
            raise ValueError("Dashboard plan filter ids must be unique.")

    @staticmethod
    def _validate_ids(
        plan: DashboardPlan, query_request: DashboardQueryDraftRequest
    ) -> Dict[str, DashboardWidgetQueryDraft]:
        DashboardPlannerService._validate_plan_ids(plan)
        plan_ids = [item.id for item in plan.widgets]
        query_ids = [item.widget_id for item in query_request.widgets]
        if len(query_ids) != len(set(query_ids)):
            raise ValueError("Dashboard query widget ids must be unique.")
        extra = set(query_ids).difference(plan_ids)
        if extra:
            raise ValueError(
                "Queries refer to widgets that are not in the plan: "
                + ", ".join(sorted(extra))
                + ". Expected widget ids: "
                + ", ".join(plan_ids)
            )
        return {item.widget_id: item for item in query_request.widgets}

    @staticmethod
    def _repair_generation_contract(
        plan: DashboardPlan,
        query_request: DashboardQueryDraftRequest,
        data_source_id: str,
    ) -> Tuple[DashboardPlan, DashboardQueryDraftRequest, List[str]]:
        """Apply only deterministic publication repairs before strict validation."""

        effective_plan, effective_request, verified = (
            repair_verified_olist_generation_contract(
                plan, query_request, data_source_id
            )
        )
        static: List[str] = []
        if effective_plan.filters:
            effective_request, static = repair_safe_static_publication_contracts(
                effective_request
            )
        repaired = [*verified, *static]
        return effective_plan, effective_request, list(dict.fromkeys(repaired))

    @staticmethod
    def _validate_filter_bindings(
        plan: DashboardPlan, query_request: DashboardQueryDraftRequest
    ) -> None:
        """Require every planned filter to reach at least one real SQL parameter."""

        planned = {item.id: item for item in plan.filters}
        if not planned:
            return
        mapped = set()
        for widget in query_request.widgets:
            unknown = set(widget.filter_parameters).difference(planned)
            if unknown:
                raise ValueError(
                    f"Widget '{widget.widget_id}' maps unknown filters: "
                    + ", ".join(sorted(unknown))
                )
            for filter_id, binding in widget.filter_parameters.items():
                dashboard_filter = planned[filter_id]
                if isinstance(binding, str):
                    names = [binding]
                    if dashboard_filter.type.value == "date_range":
                        raise ValueError(
                            f"Date filter '{filter_id}' must map start_parameter "
                            "and end_parameter."
                        )
                else:
                    names = binding.parameter_names()
                    if dashboard_filter.type.value == "date_range" and not (
                        binding.start_parameter and binding.end_parameter
                    ):
                        raise ValueError(
                            f"Date filter '{filter_id}' must map start_parameter "
                            "and end_parameter."
                        )
                    if dashboard_filter.type.value != "date_range" and not (
                        binding.parameter
                    ):
                        raise ValueError(
                            f"Filter '{filter_id}' must map one parameter."
                        )
                if not names:
                    raise ValueError(f"Filter '{filter_id}' has no SQL parameter.")
                missing = [name for name in names if f":{name}" not in widget.sql]
                if missing:
                    raise ValueError(
                        f"Widget '{widget.widget_id}' maps filter '{filter_id}' "
                        "but its SQL does not reference "
                        + ", ".join(f":{name}" for name in missing)
                        + "."
                    )
                mapped.add(filter_id)
        missing_filters = set(planned).difference(mapped)
        if missing_filters:
            raise ValueError(
                "Every planned filter must be mapped by at least one widget "
                "query. Missing filter ids: " + ", ".join(sorted(missing_filters))
            )

    @staticmethod
    def _normalized_widget(
        plan_widget,
        draft: Optional[DashboardWidgetQueryDraft],
        data_source_id: str,
    ) -> DashboardWidget:
        if draft is None:
            sql, output_fields, encoding = _placeholder_query(plan_widget.type)
            return DashboardWidget(
                id=plan_widget.id,
                type=plan_widget.type,
                title=plan_widget.title,
                description=plan_widget.business_question,
                query=WidgetQueryBinding(
                    data_source_id=data_source_id,
                    sql=sql,
                    output_fields=output_fields,
                    max_rows=10,
                ),
                encoding=encoding,
                error=WidgetError(
                    code="query_not_generated",
                    message="The Agent did not generate a query for this widget.",
                    retryable=True,
                ),
            )

        encoding = _canonical_encoding(
            plan_widget.type, draft.output_fields, draft.encoding
        )

        publication = None
        if draft.publication is not None:
            publication_draft = draft.publication
            publication = DashboardPublicationBinding(
                query=WidgetQueryBinding(
                    data_source_id=data_source_id,
                    sql=publication_draft.query.sql,
                    default_parameters=publication_draft.query.default_parameters,
                    output_fields=publication_draft.query.output_fields,
                    timeout_seconds=publication_draft.query.timeout_seconds,
                    max_rows=publication_draft.query.max_rows,
                ),
                filter_fields=publication_draft.filter_fields,
                group_by=publication_draft.group_by,
                measures=publication_draft.measures,
                output_columns=publication_draft.output_columns,
                row_mode=publication_draft.row_mode,
                sort=publication_draft.sort,
                max_output_rows=publication_draft.max_output_rows,
            )

        return DashboardWidget(
            id=plan_widget.id,
            type=plan_widget.type,
            title=plan_widget.title,
            description=plan_widget.business_question,
            query=WidgetQueryBinding(
                data_source_id=data_source_id,
                sql=draft.sql,
                filter_parameters=draft.filter_parameters,
                default_parameters=draft.default_parameters,
                output_fields=draft.output_fields,
                timeout_seconds=draft.timeout_seconds,
                max_rows=draft.max_rows,
                grain=draft.grain,
            ),
            encoding=encoding,
            publication=publication,
            anomaly_rules=draft.anomaly_rules,
        )

    @staticmethod
    def _normalize_filter_mappings(schema: DashboardSchemaV1) -> None:
        known_filters = {item.id for item in schema.filters}
        for widget in schema.widgets:
            valid = {}
            for filter_id, binding in widget.query.filter_parameters.items():
                if filter_id not in known_filters:
                    continue
                names = (
                    [binding] if isinstance(binding, str) else binding.parameter_names()
                )
                if names and all(f":{name}" in widget.query.sql for name in names):
                    valid[filter_id] = binding
            widget.query.filter_parameters = valid

    def _build_schema(
        self,
        *,
        plan: DashboardPlan,
        query_map: Dict[str, DashboardWidgetQueryDraft],
        data_source_id: str,
        conversation_id: Optional[str],
        prompt: Optional[str],
        model_name: Optional[str],
        user_confirmed: bool = False,
        compatibility: Optional[Dict[str, Any]] = None,
    ) -> DashboardSchemaV1:
        ordered_plan_widgets = [
            item
            for _, item in sorted(
                enumerate(plan.widgets),
                key=lambda pair: (pair[1].analysis_level, pair[0]),
            )
        ]
        widgets = [
            self._normalized_widget(item, query_map.get(item.id), data_source_id)
            for item in ordered_plan_widgets
        ]
        source = (
            SemanticDefinitionSource.USER_CONFIRMED
            if user_confirmed
            else SemanticDefinitionSource.MODEL_INFERRED
        )
        definition_prefix = "User-confirmed" if user_confirmed else "Agent-inferred"
        metrics = [
            MetricDefinition(
                id=_semantic_id("metric", name, index),
                name=name,
                business_definition=f"{definition_prefix} metric: {name}",
                definition_source=source,
            )
            for index, name in enumerate(plan.metrics)
        ]
        dimensions = [
            DimensionDefinition(
                id=_semantic_id("dimension", name, index),
                name=name,
                business_definition=f"{definition_prefix} dimension: {name}",
                definition_source=source,
            )
            for index, name in enumerate(plan.dimensions)
        ]
        metric_ids = {item.name.casefold(): item.id for item in metrics}
        dimension_ids = {item.name.casefold(): item.id for item in dimensions}
        for plan_widget, widget in zip(ordered_plan_widgets, widgets):
            metric_id = metric_ids.get(plan_widget.metric.casefold())
            widget.metric_ids = [metric_id] if metric_id else []
            widget.dimension_ids = [
                dimension_ids[name.casefold()]
                for name in plan_widget.dimensions
                if name.casefold() in dimension_ids
            ]
        effective_compatibility = dict(compatibility or {})
        effective_compatibility["dashboard_plan"] = model_dump_compat(plan)
        schema = DashboardSchemaV1(
            schema_version="1.4",
            dashboard=DashboardDescriptor(
                title=plan.title,
                description=plan.description,
                data_source_id=data_source_id,
                theme=(
                    template_theme(plan.layout_template.value)
                    if layout_templates_enabled() and plan.layout_template
                    else DashboardVisualTheme(
                        preset=DashboardThemePreset.CLARITY,
                        mode=DashboardThemeMode.LIGHT,
                    )
                ),
            ),
            metric_context=MetricContext(
                grain=", ".join(plan.dimensions),
                source_notes=["Generated from the selected DB-GPT data source."],
                metrics=metrics,
                dimensions=dimensions,
            ),
            filters=plan.filters,
            widgets=widgets,
            layouts=(
                template_layout(widgets, plan.layout_template.value)
                if layout_templates_enabled() and plan.layout_template
                else _layout_for(widgets, ordered_plan_widgets)
            ),
            metadata=DashboardMetadata(
                conversation_id=conversation_id,
                agent=AgentGenerationInfo(
                    generated=True,
                    model_name=model_name,
                    prompt=prompt,
                    generated_at=datetime.now(),
                ),
                compatibility=effective_compatibility,
            ),
        )
        self._normalize_filter_mappings(schema)
        return schema

    async def _execute_and_mark_widgets(
        self,
        schema: DashboardSchemaV1,
        event_callback: Optional[DashboardEventCallback],
    ) -> Dict[str, WidgetQueryResult]:
        results: Dict[str, WidgetQueryResult] = {}
        for widget in schema.widgets:
            await _emit(
                event_callback,
                "dashboard.widget.started",
                {
                    "widget_id": widget.id,
                    "title": widget.title,
                    "total_widgets": len(schema.widgets),
                },
            )
            if widget.error is not None:
                await _emit(
                    event_callback,
                    "dashboard.widget.failed",
                    {
                        "widget_id": widget.id,
                        "title": widget.title,
                        "error": widget.error.message,
                    },
                )
                continue
            result = _reject_empty_agent_result(
                await generation_read(
                    self.dashboard_service.validate_widget_query, schema, widget.id
                ),
                expected_empty=_expects_empty_table(schema, widget),
            )
            results[widget.id] = result
            widget.query.last_execution = LastExecution(
                status="failed" if result.error else "succeeded",
                executed_at=result.refreshed_at,
                duration_ms=result.duration_ms,
                row_count=result.row_count,
                error=result.error.message if result.error else None,
            )
            widget.query.refresh_time = result.refreshed_at
            if result.error:
                widget.error = WidgetError(
                    code="planner_widget_failed",
                    message=result.error.message,
                    retryable=True,
                )
                await _emit(
                    event_callback,
                    "dashboard.widget.failed",
                    {
                        "widget_id": widget.id,
                        "title": widget.title,
                        "error": result.error.message,
                    },
                )
            else:
                normalize_executed_chart(schema, widget, result)
                await _emit(
                    event_callback,
                    "dashboard.widget.validated",
                    {
                        "widget_id": widget.id,
                        "title": widget.title,
                        "row_count": result.row_count,
                        "duration_ms": result.duration_ms,
                    },
                )
        return results

    @staticmethod
    def _validate_publication_drafts(
        plan: DashboardPlan,
        query_request: DashboardQueryDraftRequest,
        *,
        only_widget_ids: Optional[List[str]] = None,
    ) -> None:
        """Require an executable frozen-data contract for every filtered widget."""

        if not plan.filters:
            return
        query_map = {item.widget_id: item for item in query_request.widgets}
        selected_ids = set(only_widget_ids) if only_widget_ids is not None else None
        plan_widgets = [
            item
            for item in plan.widgets
            if selected_ids is None or item.id in selected_ids
        ]
        missing = [
            item
            for item in plan_widgets
            if query_map.get(item.id) is None or query_map[item.id].publication is None
        ]
        if missing:
            raise DashboardSchemaValidationError(
                [
                    ValidationIssue(
                        path=f"widgets.{item.id}.publication",
                        code="publication_binding_required",
                        message=(
                            f"Component '{item.title}' is missing its share-page "
                            "frozen-data binding. Add publication.query, "
                            "filter_fields, row_mode or group_by/measures, sort, "
                            "and max_output_rows before generation can complete."
                        ),
                    )
                    for item in missing
                ]
            )
        issues: List[ValidationIssue] = []
        for plan_widget in plan_widgets:
            draft = query_map[plan_widget.id]
            publication = draft.publication
            if publication is None:  # pragma: no cover - guarded above
                continue
            missing_filters = set(draft.filter_parameters).difference(
                publication.filter_fields
            )
            if missing_filters:
                issues.append(
                    ValidationIssue(
                        path=f"widgets.{plan_widget.id}.publication.filter_fields",
                        code="publication_filter_binding_required",
                        message=(
                            f"Component '{plan_widget.title}' filters its editor "
                            "query but does not map the same filters in the "
                            "share-page dataset: "
                            + ", ".join(sorted(missing_filters))
                            + "."
                        ),
                    )
                )
        if issues:
            raise DashboardSchemaValidationError(issues)

    def _validate_publish_ready_generation(
        self, schema: DashboardSchemaV1, *, required: bool
    ) -> None:
        if not required:
            return
        validation = self.dashboard_service.validate_schema(
            schema,
            execute_queries=False,
            require_publication_bindings=True,
        )
        if not validation.valid:
            raise DashboardSchemaValidationError(validation.issues)

    @staticmethod
    def _pending_plan(record: DashboardRecord) -> Tuple[DashboardPlan, Dict[str, Any]]:
        workflow = record.schema_payload.metadata.compatibility.get(
            "agent_dashboard_workflow"
        )
        if not isinstance(workflow, dict) or workflow.get("status") != (
            "awaiting_confirmation"
        ):
            raise ValueError("Dashboard plan is not awaiting confirmation.")
        plan_payload = workflow.get("plan")
        if not isinstance(plan_payload, dict):
            raise ValueError("Dashboard plan metadata is missing.")
        return model_validate_compat(DashboardPlan, plan_payload), workflow

    async def create_plan_draft(
        self,
        *,
        plan: DashboardPlan,
        data_source_id: str,
        owner_id: Optional[str],
        conversation_id: Optional[str],
        prompt: Optional[str],
        model_name: Optional[str],
        request_token: str,
        event_callback: Optional[DashboardEventCallback] = None,
    ) -> DashboardRecord:
        """Persist a SQL-free plan and pause until a later user turn confirms it."""

        plan = normalize_plan_chart_selection(plan)
        self._validate_plan_ids(plan)
        workflow = {
            "status": "awaiting_confirmation",
            "plan": model_dump_compat(plan),
            "planned_request_token": request_token,
        }
        schema = self._build_schema(
            plan=plan,
            query_map={},
            data_source_id=data_source_id,
            conversation_id=conversation_id,
            prompt=prompt,
            model_name=model_name,
            compatibility={"agent_dashboard_workflow": workflow},
        )
        record = self.dashboard_service.create_agent_dashboard(
            DashboardCreateRequest(
                schema=schema,
                conversation_id=conversation_id,
                source_turn_id=request_token,
            ),
            owner_id,
        )
        await _emit(
            event_callback,
            "dashboard.plan.awaiting_confirmation",
            {
                "dashboard_id": record.id,
                "source_turn_id": record.source_turn_id,
                "title": plan.title,
                "data_source_id": data_source_id,
                "current_revision": record.current_revision,
                "asset_state": record.asset_state.value,
                "total_widgets": len(plan.widgets),
                "total_filters": len(plan.filters),
                "plan": model_dump_compat(plan),
                "confirmation_prompt": (
                    f"[[confirm-dashboard:{record.id}]] I confirm this dashboard "
                    f"plan at expected revision {record.current_revision}. Generate "
                    "and validate its SQL queries now."
                ),
                "revision_prompt": (
                    f"[[revise-dashboard-plan:{record.id}]] Revise this dashboard "
                    f"plan at expected revision {record.current_revision} as "
                    "follows: "
                ),
            },
        )
        return record

    async def complete_plan_draft(
        self,
        *,
        dashboard_id: str,
        query_request: DashboardQueryDraftRequest,
        owner_id: Optional[str],
        request_token: str,
        event_callback: Optional[DashboardEventCallback] = None,
    ) -> Tuple[DashboardRecord, Dict[str, WidgetQueryResult]]:
        record = self.dashboard_service.get_dashboard(dashboard_id, owner_id)
        plan, workflow = self._pending_plan(record)
        if workflow.get("planned_request_token") == request_token:
            raise ValueError(
                "The plan must be confirmed in a later user turn before SQL is "
                "generated."
            )
        if query_request.expected_revision is None:
            raise ValueError("expected_revision is required for plan confirmation.")
        if query_request.expected_revision != record.current_revision:
            raise ValueError(
                "The dashboard plan changed. Reload it before confirming generation."
            )
        plan, query_request, contract_repairs = self._repair_generation_contract(
            plan,
            query_request,
            record.schema_payload.dashboard.data_source_id,
        )
        query_map = self._validate_ids(plan, query_request)
        self._validate_filter_bindings(plan, query_request)
        await _emit(
            event_callback,
            "dashboard.generation.progress",
            {"stage": "publication_validation"},
        )
        self._validate_publication_drafts(plan, query_request)
        compatibility = dict(record.schema_payload.metadata.compatibility)
        compatibility["agent_dashboard_workflow"] = {
            "status": "generated",
            "plan": model_dump_compat(plan),
            "confirmed_revision": record.current_revision,
            "contract_repairs": contract_repairs,
        }
        schema = self._build_schema(
            plan=plan,
            query_map=query_map,
            data_source_id=record.schema_payload.dashboard.data_source_id,
            conversation_id=record.conversation_id,
            prompt=record.schema_payload.metadata.agent.prompt,
            model_name=record.schema_payload.metadata.agent.model_name,
            user_confirmed=True,
            compatibility=compatibility,
        )
        schema.dashboard.id = record.id
        schema.dashboard.created_at = record.schema_payload.dashboard.created_at
        self.dashboard_service.require_permission(
            dashboard_id, owner_id, DashboardAction.QUERY, schema
        )
        await generation_read(
            self._validate_publish_ready_generation, schema, required=bool(plan.filters)
        )

        if contract_repairs:
            await _emit(
                event_callback,
                "dashboard.generation.contract_repaired",
                {
                    "dashboard_id": record.id,
                    "source_turn_id": record.source_turn_id,
                    "widget_ids": contract_repairs,
                },
            )

        async def emit_generation_event(
            event_type: str, payload: Dict[str, Any]
        ) -> None:
            await _emit(
                event_callback,
                event_type,
                {
                    **payload,
                    "dashboard_id": record.id,
                    "source_turn_id": record.source_turn_id,
                },
            )

        results = await self._execute_and_mark_widgets(schema, emit_generation_event)
        await _emit(
            event_callback, "dashboard.generation.progress", {"stage": "saving"}
        )
        check_generation_deadline()
        updated = self.dashboard_service.update_agent_dashboard(
            dashboard_id,
            schema,
            record.current_revision,
            owner_id,
        )
        failed_count = sum(1 for item in updated.schema_payload.widgets if item.error)
        await _emit(
            event_callback,
            "dashboard.created",
            {
                "dashboard_id": updated.id,
                "source_turn_id": updated.source_turn_id,
                "title": updated.schema_payload.dashboard.title,
                "editor_path": f"/dashboards/{updated.id}",
                "total_widgets": len(updated.schema_payload.widgets),
                "validated_widgets": len(updated.schema_payload.widgets) - failed_count,
                "failed_widgets": failed_count,
                "asset_state": updated.asset_state.value,
            },
        )
        return updated, results

    async def revise_plan_draft(
        self,
        *,
        dashboard_id: str,
        plan: DashboardPlan,
        expected_revision: int,
        owner_id: Optional[str],
        request_token: str,
        prompt: Optional[str],
        model_name: Optional[str],
        event_callback: Optional[DashboardEventCallback] = None,
    ) -> DashboardRecord:
        current = self.dashboard_service.get_dashboard(dashboard_id, owner_id)
        original_plan, _ = self._pending_plan(current)
        plan = _merge_plan_revision_context(original_plan, plan)
        plan = normalize_plan_chart_selection(plan)
        self._validate_plan_ids(plan)
        workflow = {
            "status": "awaiting_confirmation",
            "plan": model_dump_compat(plan),
            "planned_request_token": request_token,
        }
        schema = self._build_schema(
            plan=plan,
            query_map={},
            data_source_id=current.schema_payload.dashboard.data_source_id,
            conversation_id=current.conversation_id,
            prompt=prompt,
            model_name=model_name,
            compatibility={"agent_dashboard_workflow": workflow},
        )
        schema.dashboard.id = dashboard_id
        schema.dashboard.created_at = current.schema_payload.dashboard.created_at
        updated = self.dashboard_service.update_agent_dashboard(
            dashboard_id,
            schema,
            expected_revision,
            owner_id,
        )
        await _emit(
            event_callback,
            "dashboard.plan.awaiting_confirmation",
            {
                "dashboard_id": updated.id,
                "source_turn_id": updated.source_turn_id,
                "title": plan.title,
                "data_source_id": updated.schema_payload.dashboard.data_source_id,
                "total_widgets": len(plan.widgets),
                "total_filters": len(plan.filters),
                "plan": model_dump_compat(plan),
                "confirmation_prompt": (
                    f"[[confirm-dashboard:{updated.id}]] I confirm this revised "
                    f"dashboard plan at expected revision {updated.current_revision}. "
                    "Generate and validate its SQL queries now."
                ),
                "revision_prompt": (
                    f"[[revise-dashboard-plan:{updated.id}]] Revise this dashboard "
                    f"plan at expected revision {updated.current_revision} as "
                    "follows: "
                ),
                "current_revision": updated.current_revision,
                "asset_state": updated.asset_state.value,
            },
        )
        return updated

    async def create_draft(
        self,
        *,
        plan: DashboardPlan,
        query_request: DashboardQueryDraftRequest,
        data_source_id: str,
        owner_id: Optional[str],
        conversation_id: Optional[str],
        prompt: Optional[str],
        model_name: Optional[str],
        source_turn_id: Optional[str] = None,
        event_callback: Optional[DashboardEventCallback] = None,
    ) -> Tuple[DashboardRecord, Dict[str, WidgetQueryResult]]:
        plan, query_request, contract_repairs = self._repair_generation_contract(
            plan, query_request, data_source_id
        )
        query_map = self._validate_ids(plan, query_request)
        self._validate_filter_bindings(plan, query_request)
        self._validate_publication_drafts(plan, query_request)
        schema = self._build_schema(
            plan=plan,
            query_map=query_map,
            data_source_id=data_source_id,
            conversation_id=conversation_id,
            prompt=prompt,
            model_name=model_name,
        )
        self.dashboard_service.authorize_schema_sources(owner_id, schema)
        self._validate_publish_ready_generation(schema, required=bool(plan.filters))
        if contract_repairs:
            await _emit(
                event_callback,
                "dashboard.generation.contract_repaired",
                {"widget_ids": contract_repairs},
            )
        results = await self._execute_and_mark_widgets(schema, event_callback)

        record = self.dashboard_service.create_agent_dashboard(
            DashboardCreateRequest(
                schema=schema,
                conversation_id=conversation_id,
                source_turn_id=source_turn_id,
            ),
            owner_id,
        )
        failed_count = sum(1 for item in record.schema_payload.widgets if item.error)
        await _emit(
            event_callback,
            "dashboard.created",
            {
                "dashboard_id": record.id,
                "source_turn_id": record.source_turn_id,
                "title": record.schema_payload.dashboard.title,
                "editor_path": f"/dashboards/{record.id}",
                "total_widgets": len(record.schema_payload.widgets),
                "validated_widgets": len(record.schema_payload.widgets) - failed_count,
                "failed_widgets": failed_count,
                "asset_state": record.asset_state.value,
            },
        )
        return record, results

    async def repair_draft(
        self,
        *,
        dashboard_id: str,
        plan: DashboardPlan,
        query_request: DashboardQueryDraftRequest,
        owner_id: Optional[str],
        event_callback: Optional[DashboardEventCallback] = None,
    ) -> Tuple[DashboardRecord, Dict[str, WidgetQueryResult]]:
        """Replace only submitted widgets in an existing Agent draft.

        Successful widgets that are not part of the repair request are left
        untouched.  This makes a model retry safe and avoids duplicate drafts.
        """

        record = self.dashboard_service.get_dashboard(dashboard_id, owner_id)
        plan, query_request, contract_repairs = self._repair_generation_contract(
            plan,
            query_request,
            record.schema_payload.dashboard.data_source_id,
        )
        query_map = self._validate_ids(plan, query_request)
        await _emit(
            event_callback,
            "dashboard.generation.progress",
            {"stage": "publication_validation"},
        )
        self._validate_publication_drafts(
            plan, query_request, only_widget_ids=list(query_map)
        )
        schema = (
            record.schema_payload.model_copy(deep=True)
            if hasattr(record.schema_payload, "model_copy")
            else record.schema_payload.copy(deep=True)
        )
        self.dashboard_service.require_permission(
            dashboard_id, owner_id, DashboardAction.QUERY, schema
        )
        # A confirmed generation or repair always produces the current visual
        # contract. Older saved and published documents remain untouched until a
        # user explicitly runs this workflow and saves a new revision.
        schema.schema_version = "1.4"
        if schema.dashboard.theme.preset is None:
            schema.dashboard.theme = DashboardVisualTheme(
                preset=DashboardThemePreset.CLARITY,
                mode=DashboardThemeMode.LIGHT,
            )
        elif schema.dashboard.theme.mode is None:
            schema.dashboard.theme.mode = (
                DashboardThemeMode.DARK
                if schema.dashboard.theme.preset == DashboardThemePreset.GRAPHITE
                else DashboardThemeMode.LIGHT
            )
        plan_map = {item.id: item for item in plan.widgets}
        current_map = {item.id: item for item in schema.widgets}
        results: Dict[str, WidgetQueryResult] = {}

        for widget_id, draft in query_map.items():
            plan_widget = plan_map[widget_id]
            widget = self._normalized_widget(
                plan_widget, draft, schema.dashboard.data_source_id
            )
            current_map[widget_id] = widget
            schema.widgets = [
                current_map[item.id] for item in plan.widgets if item.id in current_map
            ]
            self._normalize_filter_mappings(schema)
            await _emit(
                event_callback,
                "dashboard.widget.started",
                {
                    "widget_id": widget.id,
                    "title": widget.title,
                    "total_widgets": len(schema.widgets),
                    "repair": True,
                },
            )
            result = _reject_empty_agent_result(
                await generation_read(
                    self.dashboard_service.validate_widget_query, schema, widget.id
                ),
                expected_empty=_expects_empty_table(schema, widget),
            )
            results[widget.id] = result
            widget.query.last_execution = LastExecution(
                status="failed" if result.error else "succeeded",
                executed_at=result.refreshed_at,
                duration_ms=result.duration_ms,
                row_count=result.row_count,
                error=result.error.message if result.error else None,
            )
            widget.query.refresh_time = result.refreshed_at
            if result.error:
                widget.error = WidgetError(
                    code="planner_widget_failed",
                    message=result.error.message,
                    retryable=True,
                )
                await _emit(
                    event_callback,
                    "dashboard.widget.failed",
                    {
                        "widget_id": widget.id,
                        "title": widget.title,
                        "error": result.error.message,
                        "repair": True,
                    },
                )
            else:
                widget.error = None
                normalize_executed_chart(schema, widget, result)
                await _emit(
                    event_callback,
                    "dashboard.widget.validated",
                    {
                        "widget_id": widget.id,
                        "title": widget.title,
                        "row_count": result.row_count,
                        "duration_ms": result.duration_ms,
                        "repair": True,
                    },
                )

        await _emit(
            event_callback,
            "dashboard.generation.progress",
            {"stage": "publication_validation"},
        )
        await generation_read(
            self._validate_publish_ready_generation, schema, required=bool(plan.filters)
        )
        if contract_repairs:
            await _emit(
                event_callback,
                "dashboard.generation.contract_repaired",
                {
                    "dashboard_id": record.id,
                    "source_turn_id": record.source_turn_id,
                    "widget_ids": contract_repairs,
                    "repair": True,
                },
            )
        await _emit(
            event_callback, "dashboard.generation.progress", {"stage": "saving"}
        )
        workflow = schema.metadata.compatibility.get("agent_dashboard_workflow", {})
        if (
            workflow.get("status") == "awaiting_confirmation"
            and {widget.id for widget in schema.widgets} == set(plan_map)
            and all(widget.error is None for widget in schema.widgets)
        ):
            # A confirmed generation can reach repair after its initial batch
            # failed. Completing the last widget must complete the workflow too,
            # or confirmation keeps retrying a healthy draft until its deadline.
            schema.metadata.compatibility["agent_dashboard_workflow"] = {
                **workflow,
                "status": "generated",
                "plan": model_dump_compat(plan),
            }
        check_generation_deadline()
        updated = self.dashboard_service.update_agent_dashboard(
            dashboard_id,
            schema,
            record.current_revision,
            owner_id,
        )
        failed_count = sum(1 for item in updated.schema_payload.widgets if item.error)
        await _emit(
            event_callback,
            "dashboard.created",
            {
                "dashboard_id": updated.id,
                "source_turn_id": updated.source_turn_id,
                "title": updated.schema_payload.dashboard.title,
                "editor_path": f"/dashboards/{updated.id}",
                "total_widgets": len(updated.schema_payload.widgets),
                "validated_widgets": len(updated.schema_payload.widgets) - failed_count,
                "failed_widgets": failed_count,
                "repair": True,
                "asset_state": updated.asset_state.value,
            },
        )
        return updated, results
