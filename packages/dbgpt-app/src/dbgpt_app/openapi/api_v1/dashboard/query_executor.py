"""Validated single-source and constrained federated dashboard execution."""

import re
import time
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple

from .anomaly_detection import attach_widget_anomalies
from .federation import DashboardFederationService
from .models import DashboardNotFoundError
from .schemas import (
    DashboardSchemaV1,
    DashboardValidationResult,
    FederatedSourceQuery,
    FilterParameterBinding,
    FilterType,
    ValidationIssue,
    WidgetError,
    WidgetQueryResult,
    collect_schema_issues,
    model_validate_compat,
)
from .sql_security import (
    DashboardSQLSecurityError,
    DashboardUnsupportedDialectError,
    apply_row_limit,
    bind_named_parameters,
    prepare_multi_select_sql,
    resolve_sql_dialect,
    validate_read_only_sql,
)


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return str(value)


class DashboardQueryExecutor:
    """Own query metadata, validation, binding, execution, and federation.

    Persistence, authorization, publishing, and audit remain outside this class.
    The executor has no direct access to dashboard rows or user identities.
    """

    def __init__(
        self,
        connector_resolver: Optional[Callable[[str], Any]] = None,
        federation_service: Optional[DashboardFederationService] = None,
        max_federation_seconds: int = 90,
        max_dashboard_workers: int = 4,
        max_dashboard_seconds: int = 120,
    ) -> None:
        self._connector_resolver = connector_resolver
        self.federation_service = federation_service or DashboardFederationService()
        self.max_federation_seconds = max_federation_seconds
        self.max_dashboard_workers = max(1, min(max_dashboard_workers, 8))
        self.max_dashboard_seconds = max(1, min(max_dashboard_seconds, 300))

    def _get_connector(self, data_source_id: str):
        if self._connector_resolver:
            return self._connector_resolver(data_source_id)
        # Keep heavyweight application imports lazy for deterministic unit tests.
        from dbgpt._private.config import Config
        from dbgpt_serve.datasource.manages import ConnectorManager

        cfg = Config()
        manager = ConnectorManager.get_instance(cfg.SYSTEM_APP)
        return manager.get_connector(data_source_id)

    @staticmethod
    def _dialect(connector: Any) -> Optional[str]:
        value = getattr(connector, "db_type", None) or getattr(
            connector, "dialect", None
        )
        return resolve_sql_dialect(value)

    @staticmethod
    def _column_name(raw: Any) -> str:
        if isinstance(raw, (list, tuple)) and raw:
            return str(raw[0])
        if hasattr(raw, "name"):
            return str(raw.name)
        return str(raw)

    @staticmethod
    def _casefold_names(names) -> Dict[str, str]:
        """Index database column names without hiding case-only ambiguity."""

        indexed: Dict[str, str] = {}
        for raw_name in names:
            name = str(raw_name)
            normalized = name.casefold()
            previous = indexed.get(normalized)
            if previous is not None and previous != name:
                raise ValueError(
                    "Query result contains ambiguous columns that differ only by "
                    f"case: '{previous}' and '{name}'."
                )
            indexed[normalized] = name
        return indexed

    def _allowlists(
        self, connector: Any, data_source_id: str
    ) -> Tuple[List[str], List[str]]:
        tables = [str(name) for name in connector.get_table_names()]
        columns: List[str] = []
        for table in tables:
            try:
                fields = connector.get_fields(table, data_source_id)
            except TypeError:
                try:
                    fields = connector.get_fields(table)
                except Exception:
                    fields = []
            except Exception:
                fields = []
            for field in fields or []:
                columns.append(self._column_name(field))
        return tables, columns

    def validate_schema(
        self,
        schema: DashboardSchemaV1,
        *,
        execute_queries: bool = False,
        filters: Optional[Dict[str, Any]] = None,
        skip_errored_widgets: bool = False,
    ) -> DashboardValidationResult:
        from .chart_semantics import validate_stacked_measures

        issues = collect_schema_issues(schema)
        widget_status: Dict[str, str] = {}
        connector_cache: Dict[str, Tuple[Any, List[str], List[str]]] = {}

        def connector_metadata(source_id: str) -> Tuple[Any, List[str], List[str]]:
            if source_id not in connector_cache:
                source_connector = self._get_connector(source_id)
                tables, columns = self._allowlists(source_connector, source_id)
                connector_cache[source_id] = (source_connector, tables, columns)
            return connector_cache[source_id]

        for index, widget in enumerate(schema.widgets):
            widget_path = f"widgets.{index}.query"
            federation = widget.query.federation
            if (
                federation is None
                and widget.query.data_source_id != schema.dashboard.data_source_id
            ):
                issues.append(
                    ValidationIssue(
                        path=f"{widget_path}.data_source_id",
                        code="cross_source_query_not_supported",
                        message=(
                            "A single-source widget must use the dashboard's primary "
                            "data source. Use the schema 1.1 federation contract for "
                            "cross-source work."
                        ),
                    )
                )
                widget_status[widget.id] = "invalid"
                continue
            if skip_errored_widgets and widget.error is not None:
                widget_status[widget.id] = "failed"
                continue
            try:
                if federation is None:
                    if not widget.query.sql:
                        raise DashboardSQLSecurityError("Widget SQL is required.")
                    connector, tables, columns = connector_metadata(
                        widget.query.data_source_id
                    )
                    validate_read_only_sql(
                        widget.query.sql,
                        dialect=self._dialect(connector),
                        allowed_tables=tables,
                        allowed_columns=columns or None,
                    )
                else:
                    for source in federation.sources:
                        connector, tables, columns = connector_metadata(
                            source.data_source_id
                        )
                        validate_read_only_sql(
                            source.sql,
                            dialect=self._dialect(connector),
                            allowed_tables=tables,
                            allowed_columns=columns or None,
                        )
                validate_stacked_measures(widget, self._dialect(connector))
                widget_status[widget.id] = "valid"
                if any(
                    issue.severity == "error"
                    and issue.path.startswith(f"widgets.{index}")
                    for issue in issues
                ):
                    widget_status[widget.id] = "invalid"
                    continue
                if execute_queries:
                    result = self.execute_widget(schema, widget.id, filters or {})
                    if result.error:
                        raise DashboardSQLSecurityError(result.error.message)
                    widget_status[widget.id] = "executed"
            except Exception as exc:
                issues.append(
                    ValidationIssue(
                        path=widget_path,
                        code=(
                            "unsupported_data_source"
                            if isinstance(exc, DashboardUnsupportedDialectError)
                            else "query_validation_failed"
                        ),
                        message=str(exc),
                    )
                )
                widget_status[widget.id] = "invalid"

        return DashboardValidationResult(
            valid=not any(issue.severity == "error" for issue in issues),
            issues=issues,
            widget_status=widget_status,
        )

    @staticmethod
    def filter_values(
        schema: DashboardSchemaV1,
        supplied: Dict[str, Any],
        *,
        today: Optional[date] = None,
    ) -> Dict[str, Any]:
        evaluation_date = today or date.today()
        values: Dict[str, Any] = {}
        for item in schema.filters:
            if item.id in supplied and supplied[item.id] is not None:
                values[item.id] = supplied[item.id]
            elif item.relative_date is not None:
                values[item.id] = [
                    (
                        evaluation_date
                        + timedelta(days=item.relative_date.start_offset_days)
                    ).isoformat(),
                    (
                        evaluation_date
                        + timedelta(days=item.relative_date.end_offset_days)
                    ).isoformat(),
                ]
            else:
                values[item.id] = item.default
        return values

    @staticmethod
    def _canonical_parameter_stems(value: str) -> set[str]:
        """Return stable names used to recover one legacy mapping mismatch.

        Persisted dashboards created by older prompts sometimes mapped a filter to
        ``fiscal_year_filter`` while their SQL used ``:fiscal_year``.  Execution
        may recover only when the SQL placeholder unambiguously matches the filter
        id or physical field; new schemas are still rejected by the schema
        validator until the explicit mapping is corrected and saved.
        """

        normalized = re.sub(r"[^A-Za-z0-9]+", "_", str(value)).strip("_").casefold()
        values = {normalized} if normalized else set()
        if "." in str(value):
            tail = re.sub(r"[^A-Za-z0-9]+", "_", str(value).rsplit(".", 1)[-1])
            tail = tail.strip("_").casefold()
            if tail:
                values.add(tail)
        for candidate in list(values):
            for suffix in ("_filter", "_select", "_multi_select", "_date_range"):
                if candidate.endswith(suffix):
                    base = candidate[: -len(suffix)]
                    if base:
                        values.add(base)
            for prefix in ("start_", "end_", "from_", "to_"):
                if candidate.startswith(prefix) and candidate[len(prefix) :]:
                    values.add(candidate[len(prefix) :])
            for suffix in ("_start", "_end", "_from", "_to", "_ids", "_values"):
                if candidate.endswith(suffix) and candidate[: -len(suffix)]:
                    values.add(candidate[: -len(suffix)])
        return values

    @classmethod
    def _filter_value(
        cls,
        schema: DashboardSchemaV1,
        supplied: Dict[str, Any],
        filter_id: str,
    ) -> Tuple[bool, Any, Optional[FilterType]]:
        definition = next(
            (item for item in schema.filters if item.id == filter_id), None
        )
        if definition is None:
            return False, None, None
        if filter_id in supplied:
            return True, supplied[filter_id], definition.type
        if definition.default is not None:
            return True, definition.default, definition.type
        return False, None, definition.type

    @staticmethod
    def _set_parameter_with_priority(
        params: Dict[str, Any],
        parameter: Optional[str],
        *,
        has_filter_value: bool,
        filter_value: Any,
        optional_value: Any,
    ) -> None:
        if not parameter:
            return
        if has_filter_value:
            params[parameter] = filter_value
        elif parameter not in params:
            # No user value, filter default, or component default exists.  Bind
            # an explicit empty/all value so the connector never receives an
            # incomplete parameter dictionary.
            params[parameter] = optional_value

    @classmethod
    def _parameters_from_bindings(
        cls,
        schema: DashboardSchemaV1,
        supplied: Dict[str, Any],
        defaults,
        filter_parameters,
    ) -> Dict[str, Any]:
        params = dict(defaults)
        for filter_id, binding in filter_parameters.items():
            has_value, value, filter_type = cls._filter_value(
                schema, supplied, filter_id
            )
            optional_value = [] if filter_type == FilterType.MULTI_SELECT else None
            if filter_type in {FilterType.DATE_RANGE, FilterType.NUMBER_RANGE}:
                parsed_binding = (
                    None
                    if isinstance(binding, str)
                    else model_validate_compat(FilterParameterBinding, binding)
                )
                if (
                    parsed_binding is None
                    or parsed_binding.parameter
                    or not parsed_binding.start_parameter
                    or not parsed_binding.end_parameter
                    or parsed_binding.start_parameter == parsed_binding.end_parameter
                ):
                    raise DashboardSQLSecurityError(
                        f"Range filter '{filter_id}' requires distinct start_parameter "
                        "and end_parameter bindings, not a scalar/list parameter."
                    )
            if isinstance(binding, str):
                cls._set_parameter_with_priority(
                    params,
                    binding,
                    has_filter_value=has_value,
                    filter_value=value,
                    optional_value=optional_value,
                )
                continue
            if not isinstance(binding, FilterParameterBinding):
                binding = model_validate_compat(FilterParameterBinding, binding)
            if binding.parameter:
                cls._set_parameter_with_priority(
                    params,
                    binding.parameter,
                    has_filter_value=has_value,
                    filter_value=value,
                    optional_value=optional_value,
                )
            if binding.start_parameter or binding.end_parameter:
                if (
                    has_value
                    and value is not None
                    and (not isinstance(value, (list, tuple)) or len(value) != 2)
                ):
                    raise DashboardSQLSecurityError(
                        f"Filter '{filter_id}' requires a two-value range."
                    )
                start_value = value[0] if has_value and value is not None else None
                end_value = value[1] if has_value and value is not None else None
                cls._set_parameter_with_priority(
                    params,
                    binding.start_parameter,
                    has_filter_value=has_value,
                    filter_value=start_value,
                    optional_value=None,
                )
                cls._set_parameter_with_priority(
                    params,
                    binding.end_parameter,
                    has_filter_value=has_value,
                    filter_value=end_value,
                    optional_value=None,
                )
        return params

    @classmethod
    def _complete_legacy_filter_parameters(
        cls,
        schema: DashboardSchemaV1,
        supplied: Dict[str, Any],
        values: Dict[str, Any],
        required: set[str],
    ) -> Dict[str, Any]:
        """Fill only unambiguous filter-shaped placeholders left by old drafts."""

        completed = dict(values)
        for parameter in required:
            canonical = cls._canonical_parameter_stems(parameter)
            matches = []
            for dashboard_filter in schema.filters:
                stems = cls._canonical_parameter_stems(dashboard_filter.id).union(
                    cls._canonical_parameter_stems(dashboard_filter.field)
                )
                if canonical.intersection(stems):
                    matches.append(dashboard_filter)
            if len(matches) != 1:
                continue
            dashboard_filter = matches[0]
            has_value, value, filter_type = cls._filter_value(
                schema, supplied, dashboard_filter.id
            )
            if has_value:
                if (
                    filter_type in {FilterType.DATE_RANGE, FilterType.NUMBER_RANGE}
                    and value is not None
                ):
                    if not isinstance(value, (list, tuple)) or len(value) != 2:
                        raise DashboardSQLSecurityError(
                            f"Filter '{dashboard_filter.id}' requires a two-value "
                            "date range."
                        )
                    normalized = parameter.casefold()
                    if normalized.startswith(
                        ("start_", "from_", "min_")
                    ) or normalized.endswith(("_start", "_from", "_min")):
                        completed[parameter] = value[0]
                    elif normalized.startswith(
                        ("end_", "to_", "max_")
                    ) or normalized.endswith(("_end", "_to", "_max")):
                        completed[parameter] = value[1]
                else:
                    completed[parameter] = value
            elif parameter not in completed:
                completed[parameter] = (
                    [] if filter_type == FilterType.MULTI_SELECT else None
                )
        return completed

    @classmethod
    def _parameters_for_widget(
        cls, schema, widget, supplied: Dict[str, Any]
    ) -> Dict[str, Any]:
        return cls._parameters_from_bindings(
            schema,
            supplied,
            widget.query.default_parameters,
            widget.query.filter_parameters,
        )

    @classmethod
    def _parameters_for_source(
        cls,
        schema: DashboardSchemaV1,
        source: FederatedSourceQuery,
        supplied: Dict[str, Any],
    ) -> Dict[str, Any]:
        return cls._parameters_from_bindings(
            schema,
            supplied,
            source.default_parameters,
            source.filter_parameters,
        )

    @staticmethod
    def _multi_select_parameter_names(
        schema: DashboardSchemaV1, filter_parameters
    ) -> set[str]:
        """Return SQL parameters fed by multi-select dashboard filters."""

        multi_select_filter_ids = {
            item.id for item in schema.filters if item.type == FilterType.MULTI_SELECT
        }
        names: set[str] = set()
        for filter_id, binding in filter_parameters.items():
            if filter_id not in multi_select_filter_ids:
                continue
            if isinstance(binding, str):
                names.add(binding)
                continue
            if not isinstance(binding, FilterParameterBinding):
                binding = model_validate_compat(FilterParameterBinding, binding)
            if binding.parameter:
                names.add(binding.parameter)
        return names

    def _prepare_executable_query(
        self,
        schema: DashboardSchemaV1,
        sql: str,
        values: Dict[str, Any],
        filter_parameters,
        supplied_filters: Dict[str, Any],
        connector: Any,
        tables: List[str],
        columns: List[str],
    ) -> Tuple[str, Dict[str, Any]]:
        """Validate, normalize multi-select predicates, then validate again."""

        dialect = self._dialect(connector)
        validated = validate_read_only_sql(
            sql,
            dialect=dialect,
            allowed_tables=tables,
            allowed_columns=columns or None,
        )
        values = self._complete_legacy_filter_parameters(
            schema, supplied_filters, values, validated.parameters
        )
        prepared_sql, prepared_values = prepare_multi_select_sql(
            validated.sql,
            values,
            self._multi_select_parameter_names(schema, filter_parameters),
            dialect=dialect,
        )
        # AST rewriting is never trusted implicitly.  The resulting statement
        # crosses the execution boundary only after the full read-only and
        # allowlist policy has run a second time.
        prepared = validate_read_only_sql(
            prepared_sql,
            dialect=dialect,
            allowed_tables=tables,
            allowed_columns=columns or None,
        )
        return bind_named_parameters(prepared.sql, prepared_values, prepared.parameters)

    def _execute_federated_source(
        self,
        schema: DashboardSchemaV1,
        source: FederatedSourceQuery,
        supplied_filters: Dict[str, Any],
    ) -> Tuple[List[Dict[str, Any]], bool]:
        connector = self._get_connector(source.data_source_id)
        tables, columns = self._allowlists(connector, source.data_source_id)
        values = self._parameters_for_source(schema, source, supplied_filters)
        executable_sql, bound = self._prepare_executable_query(
            schema,
            source.sql,
            values,
            source.filter_parameters,
            supplied_filters,
            connector,
            tables,
            columns,
        )
        limited_sql = apply_row_limit(
            executable_sql, source.max_rows, dialect=self._dialect(connector)
        )
        raw_columns, raw_rows = connector.query_ex(
            limited_sql,
            params=bound,
            timeout=source.timeout_seconds,
        )
        result_columns = [self._column_name(item) for item in raw_columns]
        result_column_index = self._casefold_names(result_columns)
        missing = {
            name
            for name in source.column_mapping
            if name.casefold() not in result_column_index
        }
        if missing:
            raise ValueError(
                f"Federation source '{source.alias}' is missing mapped fields: "
                f"{', '.join(sorted(missing))}."
            )
        rows = list(raw_rows or [])
        truncated = len(rows) > source.max_rows
        mapped_rows: List[Dict[str, Any]] = []
        for raw_row in rows[: source.max_rows]:
            if isinstance(raw_row, dict):
                physical_row: Dict[str, Any] = {}
                for raw_name, value in raw_row.items():
                    normalized = str(raw_name).casefold()
                    if normalized in physical_row:
                        raise ValueError(
                            "Query row contains ambiguous dictionary keys that "
                            f"differ only by case: '{raw_name}'."
                        )
                    physical_row[normalized] = value
            else:
                physical_row = {
                    name.casefold(): value
                    for name, value in zip(result_columns, raw_row)
                }
            mapped_rows.append(
                {
                    output_name: _json_safe(physical_row[physical_name.casefold()])
                    for physical_name, output_name in source.column_mapping.items()
                }
            )
        return mapped_rows, truncated

    def _execute_federated_widget(
        self,
        schema: DashboardSchemaV1,
        widget,
        supplied_filters: Dict[str, Any],
    ) -> Tuple[List[str], List[List[Any]], bool]:
        federation = widget.query.federation
        if federation is None:  # pragma: no cover - guarded by caller
            raise ValueError("Federation is not configured.")
        started = time.perf_counter()
        source_rows: Dict[str, List[Dict[str, Any]]] = {}
        truncated = False
        for source in federation.sources:
            if source.alias in source_rows:
                raise ValueError("Federation source aliases must be unique.")
            rows, source_truncated = self._execute_federated_source(
                schema, source, supplied_filters
            )
            source_rows[source.alias] = rows
            truncated = truncated or source_truncated
            if time.perf_counter() - started > self.max_federation_seconds:
                raise TimeoutError(
                    "Federation exceeded the total execution limit of "
                    f"{self.max_federation_seconds} seconds."
                )

        output_columns = [item.name for item in widget.query.output_fields]
        return self.federation_service.combine(
            federation,
            source_rows,
            output_columns,
            source_truncated=truncated,
        )

    def execute_widget(
        self,
        schema: DashboardSchemaV1,
        widget_id: str,
        supplied_filters: Dict[str, Any],
    ) -> WidgetQueryResult:
        widget = next((item for item in schema.widgets if item.id == widget_id), None)
        if widget is None:
            raise DashboardNotFoundError(f"Widget {widget_id}")
        effective_filters = dict(supplied_filters)
        relative_values = self.filter_values(schema, {})
        for definition in schema.filters:
            if definition.relative_date is None:
                continue
            if (
                definition.id not in effective_filters
                or effective_filters[definition.id] is None
            ):
                effective_filters[definition.id] = relative_values[definition.id]
        started = time.perf_counter()
        refreshed_at = datetime.now()
        try:
            if widget.query.federation is not None:
                result_columns, rows, truncated = self._execute_federated_widget(
                    schema, widget, effective_filters
                )
            else:
                if not widget.query.sql:
                    raise DashboardSQLSecurityError("Widget SQL is required.")
                connector = self._get_connector(widget.query.data_source_id)
                tables, columns = self._allowlists(
                    connector, widget.query.data_source_id
                )
                values = self._parameters_for_widget(schema, widget, effective_filters)
                executable_sql, bound = self._prepare_executable_query(
                    schema,
                    widget.query.sql,
                    values,
                    widget.query.filter_parameters,
                    effective_filters,
                    connector,
                    tables,
                    columns,
                )
                limited_sql = apply_row_limit(
                    executable_sql,
                    widget.query.max_rows,
                    dialect=self._dialect(connector),
                )
                raw_columns, raw_rows = connector.query_ex(
                    limited_sql,
                    params=bound,
                    timeout=widget.query.timeout_seconds,
                )
                result_columns = [self._column_name(item) for item in raw_columns]
                result_column_index = self._casefold_names(result_columns)
                declared = {item.name for item in widget.query.output_fields}
                missing = {
                    name
                    for name in declared
                    if name.casefold() not in result_column_index
                }
                if missing:
                    raise ValueError(
                        "Query result is missing declared fields: "
                        f"{', '.join(sorted(missing))}."
                    )
                raw_rows = list(raw_rows or [])
                truncated = len(raw_rows) > widget.query.max_rows
                rows = [
                    [_json_safe(value) for value in row]
                    for row in raw_rows[: widget.query.max_rows]
                ]
            duration_ms = int((time.perf_counter() - started) * 1000)
            return attach_widget_anomalies(
                widget,
                WidgetQueryResult(
                    widget_id=widget.id,
                    columns=result_columns,
                    rows=rows,
                    row_count=len(rows),
                    truncated=truncated,
                    duration_ms=duration_ms,
                    refreshed_at=refreshed_at,
                ),
            )
        except Exception as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            return attach_widget_anomalies(
                widget,
                WidgetQueryResult(
                    widget_id=widget.id,
                    duration_ms=duration_ms,
                    refreshed_at=refreshed_at,
                    error=WidgetError(
                        code=(
                            "unsupported_data_source"
                            if isinstance(exc, DashboardUnsupportedDialectError)
                            else "widget_query_failed"
                        ),
                        message=str(exc),
                        retryable=not isinstance(exc, DashboardUnsupportedDialectError),
                    ),
                ),
            )

    def execute_dashboard(
        self,
        schema: DashboardSchemaV1,
        supplied_filters: Dict[str, Any],
    ) -> Dict[str, WidgetQueryResult]:
        """Refresh widgets with bounded concurrency and a dashboard-wide deadline.

        Connector-level timeouts remain the first line of defence.  The global
        deadline prevents a collection of individually valid slow widgets from
        holding the request open indefinitely.  Timed-out widgets are isolated;
        completed widget results remain available.
        """

        if not schema.widgets:
            return {}
        started = time.perf_counter()
        executor = ThreadPoolExecutor(
            max_workers=min(self.max_dashboard_workers, len(schema.widgets)),
            thread_name_prefix="dashboard-query",
        )
        futures = {
            widget.id: executor.submit(
                self.execute_widget, schema, widget.id, supplied_filters
            )
            for widget in schema.widgets
        }
        done, _ = wait(futures.values(), timeout=self.max_dashboard_seconds)
        results: Dict[str, WidgetQueryResult] = {}
        for widget in schema.widgets:
            future = futures[widget.id]
            if future in done:
                try:
                    results[widget.id] = future.result()
                except Exception as exc:  # defensive boundary for custom executors
                    results[widget.id] = attach_widget_anomalies(
                        widget,
                        WidgetQueryResult(
                            widget_id=widget.id,
                            duration_ms=int((time.perf_counter() - started) * 1000),
                            refreshed_at=datetime.now(),
                            error=WidgetError(
                                code="widget_query_failed",
                                message=str(exc),
                                retryable=True,
                            ),
                        ),
                    )
                continue
            future.cancel()
            results[widget.id] = attach_widget_anomalies(
                widget,
                WidgetQueryResult(
                    widget_id=widget.id,
                    duration_ms=int((time.perf_counter() - started) * 1000),
                    refreshed_at=datetime.now(),
                    error=WidgetError(
                        code="dashboard_refresh_timeout",
                        message=(
                            "Dashboard refresh exceeded the total execution limit of "
                            f"{self.max_dashboard_seconds} seconds."
                        ),
                        retryable=True,
                    ),
                ),
            )
        executor.shutdown(wait=False, cancel_futures=True)
        return results
