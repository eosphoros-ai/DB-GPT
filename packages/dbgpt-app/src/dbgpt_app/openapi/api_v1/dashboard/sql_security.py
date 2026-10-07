"""Fail-closed SQL validation and safe named-parameter expansion."""

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Set


class DashboardSQLSecurityError(ValueError):
    """Raised when a dashboard query violates the read-only policy."""


class DashboardUnsupportedDialectError(DashboardSQLSecurityError):
    """The connector dialect cannot be safely parsed and rendered by SQLGlot."""


_NAMED_PARAMETER = re.compile(r"(?<!:):([A-Za-z_][A-Za-z0-9_]*)")
_UNSAFE_TEXT = re.compile(
    r"\b(PRAGMA|ATTACH|DETACH|VACUUM|COPY|LOAD\s+DATA|INTO\s+(?:OUT|DUMP)FILE|"
    r"INSTALL|EXPORT|IMPORT|SYSTEM|SHELL|EXEC(?:UTE)?|CALL)\b",
    re.IGNORECASE,
)
_NON_EXECUTABLE_TOKEN_NAMES = {
    "BIT_STRING",
    "BYTE_STRING",
    "HEREDOC_STRING",
    "HEX_STRING",
    "IDENTIFIER",
    "NATIONAL_STRING",
    "RAW_STRING",
    "STRING",
    "UNICODE_STRING",
}
_BLOCKED_FUNCTIONS = {
    "benchmark",
    "call",
    "dblink",
    "dblink_exec",
    "exec",
    "execute",
    "export",
    "import",
    "load_file",
    "load_extension",
    "lo_export",
    "lo_import",
    "pg_ls_dir",
    "pg_logdir_ls",
    "pg_read_binary_file",
    "pg_read_file",
    "pg_sleep",
    "pg_stat_file",
    "readfile",
    "sleep",
    "shell",
    "system",
    "sys_eval",
    "sys_exec",
    "writefile",
    "xp_cmdshell",
}


@dataclass(frozen=True)
class ValidatedSQL:
    sql: str
    parameters: Set[str]
    tables: Set[str]
    columns: Set[str]


def _load_sqlglot():
    try:
        import sqlglot
        from sqlglot import expressions as exp
    except ImportError as exc:  # pragma: no cover - production dependency guard
        raise DashboardSQLSecurityError(
            "sqlglot is required for dashboard SQL validation; validation "
            "failed closed."
        ) from exc
    return sqlglot, exp


def resolve_sql_dialect(value: Optional[str]) -> Optional[str]:
    """Resolve known aliases without treating unknown databases as generic SQL."""

    if value is None:
        return None
    value = str(value).strip().lower()
    if not value:
        return None
    aliases = {
        "postgresql": "postgres",
        "mariadb": "mysql",
        "mssql": "tsql",
        "sqlserver": "tsql",
    }
    dialect = aliases.get(value, value)
    sqlglot, _ = _load_sqlglot()
    try:
        sqlglot.Dialect.get_or_raise(dialect)
    except ValueError as exc:
        raise DashboardUnsupportedDialectError(
            f"Dashboard queries do not support data source dialect '{value}'. "
            "Choose a supported data source; editing this SQL will not enable "
            "support for this database."
        ) from exc
    return dialect


def _keyword_scan_text(sqlglot: Any, sql: str, dialect: Optional[str]) -> str:
    """Return executable token text for the conservative keyword scan.

    sqlglot's tokenizer attaches comments to neighboring tokens instead of exposing
    them as executable SQL tokens. Literal values and quoted identifiers are also
    deliberately removed here. The broad keyword expression therefore remains a
    fail-closed second signal for commands without treating documentation text or
    data values as executable operations.
    """

    tokens = sqlglot.tokenize(sql, read=dialect or None)
    return " ".join(
        token.text
        for token in tokens
        if token.token_type.name not in _NON_EXECUTABLE_TOKEN_NAMES
    )


def validate_read_only_sql(
    sql: str,
    *,
    dialect: Optional[str] = None,
    allowed_tables: Optional[Iterable[str]] = None,
    allowed_columns: Optional[Iterable[str]] = None,
) -> ValidatedSQL:
    """Parse one query and reject all non-read-only constructs.

    Named parameters are replaced only in a validation copy.  The original SQL is
    returned unchanged and is later executed with connector parameter binding.
    """

    if not sql or not sql.strip():
        raise DashboardSQLSecurityError("SQL must not be empty.")
    if "${" in sql or "{{" in sql:
        raise DashboardSQLSecurityError(
            "Template interpolation is not allowed; use named parameters "
            "such as :store_id."
        )

    sqlglot, exp = _load_sqlglot()
    dialect = resolve_sql_dialect(dialect)
    parameters = set(_NAMED_PARAMETER.findall(sql))
    validation_sql = _NAMED_PARAMETER.sub("NULL", sql.strip())
    try:
        keyword_scan_text = _keyword_scan_text(sqlglot, validation_sql, dialect)
        statements = sqlglot.parse(validation_sql, read=dialect or None)
    except Exception as exc:
        raise DashboardSQLSecurityError(f"SQL cannot be parsed: {exc}") from exc
    if _UNSAFE_TEXT.search(keyword_scan_text):
        raise DashboardSQLSecurityError(
            "SQL contains an operation not allowed in dashboards."
        )
    if len(statements) != 1:
        raise DashboardSQLSecurityError("Exactly one SQL statement is allowed.")

    statement = statements[0]
    if statement is None or not isinstance(statement, exp.Query):
        raise DashboardSQLSecurityError("Dashboard SQL must be a SELECT query or CTE.")

    forbidden_names = (
        "Insert",
        "Update",
        "Delete",
        "Create",
        "Drop",
        "Alter",
        "Merge",
        "Command",
        "Copy",
        "Transaction",
        "Grant",
        "Revoke",
        "Use",
        "Attach",
        "Detach",
        "Pragma",
        "Into",
        "Lock",
        "Call",
        "Execute",
        "System",
        "Shell",
        "Export",
        "Import",
        "Install",
        "LoadData",
    )
    forbidden_types = tuple(
        item for item in (getattr(exp, name, None) for name in forbidden_names) if item
    )
    if forbidden_types and any(statement.find_all(*forbidden_types)):
        raise DashboardSQLSecurityError(
            "Dashboard SQL contains a write or command node."
        )

    functions = set()
    for function in statement.find_all(exp.Func):
        if isinstance(function, exp.Anonymous):
            name = function.name
        else:
            name = function.sql_name()
        if name:
            functions.add(str(name).lower())
    blocked_functions = functions.intersection(_BLOCKED_FUNCTIONS)
    if blocked_functions:
        raise DashboardSQLSecurityError(
            "Dashboard SQL calls blocked file, command, or delay functions: "
            + ", ".join(sorted(blocked_functions))
            + "."
        )

    cte_names = {
        str(cte.alias_or_name).lower()
        for cte in statement.find_all(exp.CTE)
        if cte.alias_or_name
    }
    tables = {
        str(table.name).lower()
        for table in statement.find_all(exp.Table)
        if table.name and str(table.name).lower() not in cte_names
    }
    columns = {
        str(column.name).lower()
        for column in statement.find_all(exp.Column)
        if column.name and str(column.name) != "*"
    }

    if allowed_tables is not None:
        allowed = {str(name).lower() for name in allowed_tables}
        unknown = tables.difference(allowed)
        if unknown:
            raise DashboardSQLSecurityError(
                "SQL references tables outside the data source allowlist: "
                f"{', '.join(sorted(unknown))}."
            )

    if allowed_columns is not None:
        aliases = {
            str(alias.alias).lower()
            for alias in statement.find_all(exp.Alias)
            if alias.alias
        }
        allowed = {str(name).lower() for name in allowed_columns}.union(aliases)
        unknown = columns.difference(allowed)
        if unknown:
            raise DashboardSQLSecurityError(
                "SQL references columns outside the data source allowlist: "
                f"{', '.join(sorted(unknown))}."
            )

    return ValidatedSQL(
        sql=sql.strip().rstrip(";"),
        parameters=parameters,
        tables=tables,
        columns=columns,
    )


def bind_named_parameters(
    sql: str, parameters: Dict[str, Any], required: Optional[Set[str]] = None
) -> tuple[str, Dict[str, Any]]:
    """Expand list parameters without interpolating values into SQL text."""

    required_names = (
        required if required is not None else set(_NAMED_PARAMETER.findall(sql))
    )
    missing = required_names.difference(parameters)
    if missing:
        raise DashboardSQLSecurityError(
            f"Missing SQL parameters: {', '.join(sorted(missing))}."
        )
    extra = set(parameters).difference(required_names)
    if extra:
        parameters = {
            key: value for key, value in parameters.items() if key in required_names
        }

    bound: Dict[str, Any] = {}
    reserved_names = set(required_names).union(parameters)

    def expanded_parameter_name(name: str, index: int) -> str:
        """Return a generated name that cannot shadow a caller parameter."""

        candidate = f"__dbgpt_{name}_{index}"
        suffix = 0
        while candidate in reserved_names or candidate in bound:
            suffix += 1
            candidate = f"__dbgpt_{name}_{index}_{suffix}"
        reserved_names.add(candidate)
        return candidate

    def replace(match: re.Match) -> str:
        name = match.group(1)
        value = parameters[name]
        if isinstance(value, set):
            raise DashboardSQLSecurityError(
                f"SQL parameter '{name}' must use an ordered list or tuple, not a set."
            )
        if isinstance(value, (list, tuple)):
            values = list(value)
            if not values:
                return "NULL"
            placeholders = []
            for index, item in enumerate(values):
                if isinstance(item, (dict, list, tuple, set)):
                    raise DashboardSQLSecurityError(
                        f"SQL parameter '{name}' contains a nested collection; "
                        "multi-select values must be scalar."
                    )
                expanded_name = expanded_parameter_name(name, index)
                placeholders.append(f":{expanded_name}")
                bound[expanded_name] = item
            return ", ".join(placeholders)
        bound[name] = value
        return f":{name}"

    return _NAMED_PARAMETER.sub(replace, sql), bound


def prepare_multi_select_sql(
    sql: str,
    parameters: Dict[str, Any],
    multi_select_parameters: Set[str],
    *,
    dialect: Optional[str] = None,
) -> tuple[str, Dict[str, Any]]:
    """Normalize optional multi-select predicates before parameter expansion.

    A multi-select value is safe only when its placeholder is an item in an
    ``IN``/``NOT IN`` predicate.  Empty selections mean "do not filter", so the
    complete predicate is replaced with ``TRUE`` instead of expanding the list
    to ``IN (NULL)``.  The legacy planner shape
    ``(:items IS NULL OR field IN (:items))`` is reduced to the same canonical
    predicate first; this keeps already-saved dashboards working.

    The returned SQL is deliberately parsed again by ``validate_read_only_sql``
    at the execution boundary.  This helper only performs a structural rewrite;
    it never interpolates caller values into SQL text.
    """

    dialect = resolve_sql_dialect(dialect)
    names = {str(name) for name in multi_select_parameters if name}
    if not names:
        return sql, dict(parameters)

    sqlglot, exp = _load_sqlglot()
    try:
        statements = sqlglot.parse(sql.strip().rstrip(";"), read=dialect or None)
    except Exception as exc:
        raise DashboardSQLSecurityError(f"SQL cannot be parsed: {exc}") from exc
    if len(statements) != 1 or statements[0] is None:
        raise DashboardSQLSecurityError("Exactly one SQL statement is allowed.")
    statement = statements[0]
    if not isinstance(statement, exp.Query):
        raise DashboardSQLSecurityError("Dashboard SQL must be a SELECT query or CTE.")

    prepared_values = dict(parameters)
    normalized_legacy = False

    def placeholder_name(node: Any) -> Optional[str]:
        return str(node.this) if isinstance(node, exp.Placeholder) else None

    def null_guard_name(node: Any) -> Optional[str]:
        if not isinstance(node, exp.Is):
            return None
        left, right = node.this, node.expression
        if isinstance(right, exp.Null):
            return placeholder_name(left)
        if isinstance(left, exp.Null):
            return placeholder_name(right)
        return None

    def in_parameter_names(node: Any) -> Set[str]:
        if not isinstance(node, exp.In):
            return set()
        return {
            str(item.this)
            for item in node.expressions
            if isinstance(item, exp.Placeholder)
        }

    # Backward compatibility for dashboards generated before the planner used
    # the canonical ``field IN (:items)`` form.
    for or_node in list(statement.find_all(exp.Or)):
        pairs = (
            (or_node.this, or_node.expression),
            (or_node.expression, or_node.this),
        )
        for guard, predicate in pairs:
            name = null_guard_name(guard)
            if name not in names or name not in in_parameter_names(predicate):
                continue
            replacement_target = (
                or_node.parent if isinstance(or_node.parent, exp.Paren) else or_node
            )
            replacement_target.replace(predicate.copy())
            normalized_legacy = True
            break

    placeholders = [
        item for item in statement.find_all(exp.Placeholder) if str(item.this) in names
    ]
    for placeholder in placeholders:
        parent = placeholder.parent
        if not isinstance(parent, exp.In) or placeholder not in parent.expressions:
            raise DashboardSQLSecurityError(
                f"Multi-select SQL parameter '{placeholder.this}' may only appear "
                "inside an IN or NOT IN value list."
            )

    for name in names:
        if name not in prepared_values:
            continue
        value = prepared_values[name]
        if value is None:
            values: list[Any] = []
        elif isinstance(value, set):
            raise DashboardSQLSecurityError(
                f"SQL parameter '{name}' must use an ordered list or tuple, not a set."
            )
        elif isinstance(value, (list, tuple)):
            values = list(value)
        else:
            raise DashboardSQLSecurityError(
                f"Multi-select SQL parameter '{name}' must be a list or tuple."
            )

        if values:
            prepared_values[name] = values
            continue

        matching_predicates = [
            item
            for item in statement.find_all(exp.In)
            if name in in_parameter_names(item)
        ]
        for predicate in matching_predicates:
            target = (
                predicate.parent if isinstance(predicate.parent, exp.Not) else predicate
            )
            target.replace(exp.true())
        prepared_values.pop(name, None)

    rendered = _render_bound_sql(statement, dialect)
    if not normalized_legacy and rendered == sql.strip().rstrip(";"):
        rendered = sql.strip().rstrip(";")
    return rendered, prepared_values


def _render_bound_sql(statement: Any, dialect: Optional[str]) -> str:
    """Keep SQLAlchemy named binds while rendering database-specific syntax."""

    sqlglot, exp = _load_sqlglot()

    def preserve_bind(node):
        if isinstance(node, exp.Placeholder):
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(node.this or "")):
                raise DashboardSQLSecurityError(
                    "Only named SQL parameters are allowed."
                )
            # T-SQL's renderer otherwise turns :name into @name, which is a
            # database variable rather than a bind understood by SQLAlchemy.
            return exp.Var(this=f":{node.this}")
        return node

    return statement.transform(preserve_bind).sql(
        dialect=dialect or None,
        unsupported_level=sqlglot.ErrorLevel.RAISE,
    )


def apply_row_limit(sql: str, max_rows: int, *, dialect: Optional[str] = None) -> str:
    """Apply a dialect-aware outer cap and fetch one extra truncation row.

    Preserve an existing inner limit/offset (including TOP PERCENT/WITH TIES).
    SQL Server requires TOP or OFFSET for ORDER BY inside a derived table.
    sqlglot also hoists its CTEs and omits AS for Oracle inline-view aliases.
    """

    safe_max = max(1, min(int(max_rows), 5000)) + 1
    sqlglot, exp = _load_sqlglot()
    dialect = resolve_sql_dialect(dialect)
    try:
        validate_read_only_sql(sql, dialect=dialect)
        inner = sqlglot.parse_one(sql.strip().rstrip(";"), read=dialect or None)
        if (
            dialect == "tsql"
            and inner.args.get("order")
            and not inner.args.get("limit")
            and not inner.args.get("offset")
        ):
            inner = inner.limit(safe_max)
        statement = (
            exp.select("*")
            .from_(inner.subquery("dbgpt_dashboard_query"))
            .limit(safe_max)
        )
        rendered = _render_bound_sql(statement, dialect)
        validate_read_only_sql(rendered, dialect=dialect)
        return rendered
    except DashboardSQLSecurityError:
        raise
    except Exception as exc:
        raise DashboardSQLSecurityError(
            f"SQL row limit cannot be rendered for dialect {dialect!r}."
        ) from exc
