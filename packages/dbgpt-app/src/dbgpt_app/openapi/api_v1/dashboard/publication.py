"""Immutable publication datasets and database-free public filtering."""

from __future__ import annotations

from collections import OrderedDict
from datetime import date, datetime, time, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Tuple

from .anomaly_detection import attach_widget_anomalies
from .generation_budget import check_generation_deadline
from .query_executor import DashboardQueryExecutor
from .schemas import (
    DashboardFilter,
    DashboardPublicationAggregation,
    DashboardPublicationFilterBinding,
    DashboardPublicationFilterOperator,
    DashboardSchemaV1,
    DashboardSnapshot,
    DashboardSortDirection,
    DashboardWidget,
    FilterType,
    PublicDashboardFilterResponse,
    WidgetQueryResult,
)


class DashboardPublicationError(ValueError):
    """Raised when a frozen publication dataset cannot be safely computed."""


def _model_copy(model, *, deep: bool = False):
    if hasattr(model, "model_copy"):
        return model.model_copy(deep=deep)
    return model.copy(deep=deep)


def _rows_as_objects(result: WidgetQueryResult) -> List[Dict[str, Any]]:
    return [dict(zip(result.columns, row)) for row in result.rows]


def _json_equal(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, (int, float, Decimal)) and isinstance(
        right, (int, float, Decimal)
    ):
        try:
            return Decimal(str(left)) == Decimal(str(right))
        except InvalidOperation:
            return False
    return type(left) is type(right) and left == right


def _number(value: Any) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise DashboardPublicationError("A publication measure must be numeric.")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise DashboardPublicationError(
            f"Publication measure value {value!r} is not numeric."
        ) from exc


def _json_number(value: Decimal) -> Any:
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def _ordered(value: Any) -> Tuple[int, Any]:
    if value is None:
        return (1, "")
    if isinstance(value, bool):
        return (0, int(value))
    if isinstance(value, (int, float, Decimal)):
        return (0, Decimal(str(value)))
    if isinstance(value, (datetime, date)):
        return (0, value.isoformat())
    text = str(value)
    try:
        return (0, datetime.fromisoformat(text.replace("Z", "+00:00")))
    except ValueError:
        return (0, text.casefold())


def _date_value(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, time.min)
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise DashboardPublicationError(
                f"Invalid publication date value: {value!r}."
            ) from exc
    else:
        raise DashboardPublicationError(f"Invalid publication date value: {value!r}.")
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


class DashboardPublicationService:
    """Create and query bounded datasets attached to immutable revisions."""

    @staticmethod
    def missing_bindings(schema: DashboardSchemaV1) -> List[str]:
        """Return widgets that cannot be recalculated from a frozen snapshot.

        Schema 1.3 introduced the binding format, but dashboards created by
        older clients can still contain global filters.  A filtered dashboard
        must therefore make an explicit publication decision for every widget
        regardless of the document's original schema version.  Otherwise the
        public page would render active controls while silently keeping the
        published values unchanged.
        A binding without ``filter_fields`` is still valid: it deliberately
        materializes a widget whose value does not depend on global filters.
        """

        if not schema.filters:
            return []
        return [widget.id for widget in schema.widgets if widget.publication is None]

    def validate_coverage(
        self, schema: DashboardSchemaV1, *, allow_static_widgets: bool = False
    ) -> None:
        missing = self.missing_bindings(schema)
        if missing and not allow_static_widgets:
            raise DashboardPublicationError(
                "Interactive publication requires a frozen-data binding for "
                "every widget. Missing bindings: "
                + ", ".join(missing)
                + ". Configure the widgets and publish a new revision."
            )
        if schema.filters and not allow_static_widgets:
            used_filter_ids = {
                filter_id
                for widget in schema.widgets
                if widget.publication is not None
                for filter_id in widget.publication.filter_fields
            }
            unused = [
                item.id for item in schema.filters if item.id not in used_filter_ids
            ]
            if unused:
                raise DashboardPublicationError(
                    "Interactive publication contains filters that do not "
                    "recalculate any widget: "
                    + ", ".join(unused)
                    + ". Bind each visible filter to at least one widget or "
                    "remove it before publishing."
                )

    def materialize(
        self,
        schema: DashboardSchemaV1,
        query_executor: DashboardQueryExecutor,
        *,
        allow_static_widgets: bool = False,
    ) -> Dict[str, WidgetQueryResult]:
        self.validate_coverage(schema, allow_static_widgets=allow_static_widgets)
        datasets: Dict[str, WidgetQueryResult] = {}
        for widget in schema.widgets:
            binding = widget.publication
            if binding is None:
                continue
            datasets[widget.id] = self._materialize_widget(
                schema, widget, query_executor
            )
        return datasets

    def validate_materialization(
        self,
        schema: DashboardSchemaV1,
        query_executor: DashboardQueryExecutor,
    ) -> Dict[str, str]:
        """Run the publish-time dataset contract and retain every widget error."""

        failures: Dict[str, str] = {}
        for widget in schema.widgets:
            check_generation_deadline()
            if widget.publication is None:
                continue
            try:
                self._materialize_widget(schema, widget, query_executor)
            except DashboardPublicationError as exc:
                failures[widget.id] = str(exc)
        return failures

    def _materialize_widget(
        self,
        schema: DashboardSchemaV1,
        widget: DashboardWidget,
        query_executor: DashboardQueryExecutor,
    ) -> WidgetQueryResult:
        binding = widget.publication
        if binding is None:  # pragma: no cover - guarded by callers
            raise DashboardPublicationError("Publication binding is required.")
        materialized_widget = _model_copy(widget, deep=True)
        materialized_widget.query = _model_copy(binding.query, deep=True)
        materialized_widget.publication = None
        materialized_schema = _model_copy(schema, deep=True)
        materialized_schema.widgets = [materialized_widget]
        result = query_executor.execute_widget(
            materialized_schema, materialized_widget.id, {}
        )
        if result.error is not None:
            raise DashboardPublicationError(
                f"Publication dataset for widget '{widget.id}' failed: "
                f"{result.error.message}"
            )
        self._validate_dataset(widget, result)
        return result

    @staticmethod
    def _validate_dataset(widget: DashboardWidget, result: WidgetQueryResult) -> None:
        binding = widget.publication
        if binding is None:  # pragma: no cover - guarded by caller
            return
        available = set(result.columns)
        required = set(binding.group_by)
        required.update(measure.source_field for measure in binding.measures)
        required.update(
            measure.denominator_field
            for measure in binding.measures
            if measure.denominator_field
        )
        required.update(
            value if isinstance(value, str) else value.field
            for value in binding.filter_fields.values()
        )
        if binding.row_mode:
            required.update(binding.output_columns)
        missing = required.difference(available)
        if missing:
            raise DashboardPublicationError(
                f"Publication dataset for widget '{widget.id}' is missing: "
                + ", ".join(sorted(missing))
                + "."
            )
        if result.truncated:
            raise DashboardPublicationError(
                f"Publication dataset for widget '{widget.id}' exceeded its "
                "configured row limit. Increase the bounded query limit or "
                "reduce the materialized fields."
            )

    def filter_snapshot(
        self,
        schema: DashboardSchemaV1,
        published_snapshot: DashboardSnapshot,
        supplied_filters: Dict[str, Any],
    ) -> PublicDashboardFilterResponse:
        effective = self._validate_filters(schema, supplied_filters)
        widgets = dict(published_snapshot.widgets)
        unsupported: List[str] = []
        for widget in schema.widgets:
            binding = widget.publication
            dataset = published_snapshot.publication_datasets.get(widget.id)
            if binding is None or dataset is None:
                unsupported.append(widget.id)
                continue
            rows = self._filter_rows(
                _rows_as_objects(dataset), schema, binding.filter_fields, effective
            )
            widgets[widget.id] = self._result_from_rows(
                widget, rows, published_snapshot.refreshed_at
            )
        return PublicDashboardFilterResponse(
            snapshot=DashboardSnapshot(
                dashboard_id=published_snapshot.dashboard_id,
                refreshed_at=published_snapshot.refreshed_at,
                filters=effective,
                widgets=widgets,
            ),
            unsupported_widget_ids=unsupported,
        )

    @staticmethod
    def _validate_filters(
        schema: DashboardSchemaV1, supplied: Dict[str, Any]
    ) -> Dict[str, Any]:
        known = {item.id: item for item in schema.filters}
        unknown = set(supplied).difference(known)
        if unknown:
            raise DashboardPublicationError(
                "Unknown public dashboard filters: " + ", ".join(sorted(unknown)) + "."
            )
        effective: Dict[str, Any] = {}
        for filter_id, item in known.items():
            value = supplied[filter_id] if filter_id in supplied else item.default
            if item.type == FilterType.DATE_RANGE:
                if value not in (None, []) and (
                    not isinstance(value, (list, tuple)) or len(value) != 2
                ):
                    raise DashboardPublicationError(
                        f"Filter '{filter_id}' requires a two-value date range."
                    )
                if value not in (None, []):
                    start, end = value
                    if _date_value(start) > _date_value(end):
                        raise DashboardPublicationError(
                            f"Filter '{filter_id}' has an end date before its "
                            "start date."
                        )
                    value = [start, end]
            elif item.type == FilterType.NUMBER_RANGE:
                if value not in (None, []) and (
                    not isinstance(value, (list, tuple)) or len(value) != 2
                ):
                    raise DashboardPublicationError(
                        f"Filter '{filter_id}' requires a two-value number range."
                    )
                if value not in (None, []):
                    start, end = value
                    try:
                        start_number = _number(start)
                        end_number = _number(end)
                    except DashboardPublicationError as exc:
                        raise DashboardPublicationError(
                            f"Filter '{filter_id}' requires numeric range values."
                        ) from exc
                    if start_number > end_number:
                        raise DashboardPublicationError(
                            f"Filter '{filter_id}' has a maximum below its minimum."
                        )
                    value = [start, end]
            elif item.type == FilterType.MULTI_SELECT:
                if value is not None and not isinstance(value, (list, tuple)):
                    raise DashboardPublicationError(
                        f"Filter '{filter_id}' requires a list of values."
                    )
                DashboardPublicationService._validate_options(item, list(value or []))
                value = list(value or [])
            elif item.type == FilterType.TEXT:
                if value is not None and not isinstance(value, str):
                    raise DashboardPublicationError(
                        f"Filter '{filter_id}' requires text."
                    )
            elif value not in (None, "", "all"):
                DashboardPublicationService._validate_options(item, [value])
            effective[filter_id] = value
        return effective

    @staticmethod
    def _validate_options(item: DashboardFilter, values: Iterable[Any]) -> None:
        if not item.options:
            return
        allowed = [option.value for option in item.options]
        invalid = [
            value
            for value in values
            if not any(_json_equal(value, option) for option in allowed)
        ]
        if invalid:
            raise DashboardPublicationError(
                f"Filter '{item.id}' contains unsupported values: {invalid!r}."
            )

    @staticmethod
    def _filter_rows(
        rows: List[Dict[str, Any]],
        schema: DashboardSchemaV1,
        filter_fields,
        effective: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        definitions = {item.id: item for item in schema.filters}

        def includes(row: Dict[str, Any]) -> bool:
            for filter_id, raw_binding in filter_fields.items():
                definition = definitions[filter_id]
                binding = (
                    DashboardPublicationFilterBinding(field=raw_binding)
                    if isinstance(raw_binding, str)
                    else raw_binding
                )
                selected = effective.get(filter_id)
                if selected in (None, "", "all", []):
                    continue
                actual = row.get(binding.field)
                operator = binding.operator
                if definition.type == FilterType.DATE_RANGE:
                    start, end = selected
                    if (
                        actual is None
                        or _date_value(actual) < _date_value(start)
                        or _date_value(actual) > _date_value(end)
                    ):
                        return False
                elif definition.type == FilterType.NUMBER_RANGE:
                    start, end = selected
                    if actual is None:
                        return False
                    try:
                        actual_number = _number(actual)
                    except DashboardPublicationError:
                        return False
                    if actual_number < _number(start) or actual_number > _number(end):
                        return False
                elif definition.type == FilterType.TEXT:
                    if (
                        actual is None
                        or str(selected).casefold() not in str(actual).casefold()
                    ):
                        return False
                elif definition.type == FilterType.MULTI_SELECT:
                    if not any(_json_equal(actual, value) for value in selected):
                        return False
                elif operator == DashboardPublicationFilterOperator.LESS_THAN_OR_EQUAL:
                    if actual is None or _ordered(actual) > _ordered(selected):
                        return False
                elif (
                    operator == DashboardPublicationFilterOperator.GREATER_THAN_OR_EQUAL
                ):
                    if actual is None or _ordered(actual) < _ordered(selected):
                        return False
                elif not _json_equal(actual, selected):
                    return False
            return True

        return [row for row in rows if includes(row)]

    def _result_from_rows(
        self,
        widget: DashboardWidget,
        rows: List[Dict[str, Any]],
        refreshed_at: datetime,
    ) -> WidgetQueryResult:
        binding = widget.publication
        if binding is None:  # pragma: no cover - guarded by caller
            raise DashboardPublicationError("Publication binding is required.")
        if binding.row_mode:
            output = [
                {column: row.get(column) for column in binding.output_columns}
                for row in rows
            ]
        else:
            output = self._aggregate(rows, binding.group_by, binding.measures)
        output = self._sort(output, binding.sort)
        truncated = len(output) > binding.max_output_rows
        output = output[: binding.max_output_rows]
        return attach_widget_anomalies(
            widget,
            WidgetQueryResult(
                widget_id=widget.id,
                columns=binding.output_columns,
                rows=[
                    [row.get(column) for column in binding.output_columns]
                    for row in output
                ],
                row_count=len(output),
                truncated=truncated,
                duration_ms=0,
                refreshed_at=refreshed_at,
            ),
        )

    @staticmethod
    def _aggregate(rows, group_by, measures) -> List[Dict[str, Any]]:
        groups: "OrderedDict[Tuple[Any, ...], Dict[str, Any]]" = OrderedDict()
        for row in rows:
            key = tuple(row.get(field) for field in group_by)
            state = groups.setdefault(
                key,
                {
                    "__count": {},
                    "__distinct": {},
                    "__denominator": {},
                    **{field: value for field, value in zip(group_by, key)},
                },
            )
            for measure in measures:
                source = row.get(measure.source_field)
                output = measure.output_field
                aggregation = measure.aggregation
                if aggregation == DashboardPublicationAggregation.SUM:
                    state[output] = state.get(output, Decimal(0)) + _number(source)
                elif aggregation == DashboardPublicationAggregation.AVERAGE:
                    if source is not None:
                        state[output] = state.get(output, Decimal(0)) + _number(source)
                        state["__count"][output] = state["__count"].get(output, 0) + 1
                elif aggregation == DashboardPublicationAggregation.COUNT:
                    state[output] = state.get(output, 0) + (source is not None)
                elif aggregation == DashboardPublicationAggregation.COUNT_DISTINCT:
                    state["__distinct"].setdefault(output, set()).add(source)
                elif aggregation == DashboardPublicationAggregation.MINIMUM:
                    if source is not None and (
                        output not in state
                        or _ordered(source) < _ordered(state[output])
                    ):
                        state[output] = source
                elif aggregation == DashboardPublicationAggregation.MAXIMUM:
                    if source is not None and (
                        output not in state
                        or _ordered(source) > _ordered(state[output])
                    ):
                        state[output] = source
                elif aggregation == DashboardPublicationAggregation.FIRST:
                    if output not in state and source is not None:
                        state[output] = source
                elif aggregation == DashboardPublicationAggregation.RATIO:
                    denominator = row.get(measure.denominator_field or "")
                    if source is not None and denominator is not None:
                        state[output] = state.get(output, Decimal(0)) + _number(source)
                        state["__denominator"][output] = state["__denominator"].get(
                            output, Decimal(0)
                        ) + _number(denominator)

        result: List[Dict[str, Any]] = []
        for state in groups.values():
            for measure in measures:
                output = measure.output_field
                if measure.aggregation == DashboardPublicationAggregation.AVERAGE:
                    count = state["__count"].get(output, 0)
                    state[output] = (
                        _json_number(state.get(output, Decimal(0)) / count)
                        if count
                        else None
                    )
                elif (
                    measure.aggregation
                    == DashboardPublicationAggregation.COUNT_DISTINCT
                ):
                    state[output] = len(state["__distinct"].get(output, set()))
                elif measure.aggregation == DashboardPublicationAggregation.RATIO:
                    denominator = state["__denominator"].get(output, Decimal(0))
                    state[output] = (
                        _json_number(
                            state.get(output, Decimal(0))
                            / denominator
                            * Decimal(str(measure.scale))
                        )
                        if denominator
                        else None
                    )
                elif isinstance(state.get(output), Decimal):
                    state[output] = _json_number(state[output])
                elif output not in state:
                    state[output] = None
            state.pop("__count", None)
            state.pop("__distinct", None)
            state.pop("__denominator", None)
            result.append(state)
        return result

    @staticmethod
    def _sort(rows, sort_rules) -> List[Dict[str, Any]]:
        sorted_rows = list(rows)
        for rule in reversed(sort_rules):
            if rule.direction == DashboardSortDirection.DEFAULT:
                continue
            descending = rule.direction == DashboardSortDirection.DESCENDING
            non_null = [row for row in sorted_rows if row.get(rule.field) is not None]
            nulls = [row for row in sorted_rows if row.get(rule.field) is None]
            non_null.sort(
                key=lambda row: _ordered(row.get(rule.field))[1],
                reverse=descending,
            )
            sorted_rows = non_null + nulls
        return sorted_rows
