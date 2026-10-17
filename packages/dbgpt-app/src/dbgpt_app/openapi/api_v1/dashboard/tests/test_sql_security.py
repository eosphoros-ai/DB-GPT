import pytest

from dbgpt_app.openapi.api_v1.dashboard.sql_security import (
    DashboardSQLSecurityError,
    apply_row_limit,
    bind_named_parameters,
    escape_literal_colons,
    prepare_multi_select_sql,
    validate_read_only_sql,
)


@pytest.mark.parametrize(
    "dialect,sql",
    [
        ("sqlite", "SELECT ':literal', :value -- :comment\n"),
        ("postgres", "SELECT $$:literal$$, :value::text /* :comment */"),
        ("mysql", "SELECT ':literal', :value AS `:column`"),
        ("tsql", "SELECT ':literal', :value AS [:column]"),
        ("duckdb", "SELECT ':literal', :value AS \":column\""),
    ],
)
def test_bindings_ignore_literals_identifiers_comments_and_casts(dialect, sql):
    validated = validate_read_only_sql(sql, dialect=dialect)
    assert validated.parameters == {"value"}
    executable, bound = bind_named_parameters(sql, {"value": 7}, dialect=dialect)
    assert executable == sql
    assert bound == {"value": 7}


def test_literal_colons_survive_real_connector_execution(tmp_path):
    from dbgpt_ext.datasource.rdbms.conn_sqlite import SQLiteConnector

    sql = (
        "SELECT ':literal' AS literal, '\\:escaped' AS escaped, ':123' AS digits, "
        "':中文' AS unicode_text, :value AS \":column\" "
        "WHERE :value IN (:values) /* :comment */"
    )
    validated = validate_read_only_sql(sql, dialect="sqlite")
    executable, bound = bind_named_parameters(
        validated.sql, {"value": 7, "values": [6, 7]}, dialect="sqlite"
    )
    limited = apply_row_limit(executable, 10, dialect="sqlite")
    connector = SQLiteConnector.from_file_path(str(tmp_path / "literal-colons.db"))
    try:
        fields, rows = connector.query_ex(
            escape_literal_colons(limited, dialect="sqlite"), params=bound
        )
        assert fields[-1] == ":column"
        assert tuple(rows[0]) == (":literal", "\\:escaped", ":123", ":中文", 7)
    finally:
        connector.close()


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT store, SUM(sales) AS total FROM sales GROUP BY store",
        (
            "WITH monthly AS (SELECT month, SUM(sales) AS total FROM sales "
            "GROUP BY month) SELECT month, total FROM monthly"
        ),
        "SELECT * FROM (SELECT store, sales FROM sales) AS ranked",
    ],
)
def test_select_and_cte_queries_are_allowed(sql):
    result = validate_read_only_sql(sql, allowed_tables={"sales"})
    assert result.tables == {"sales"}


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO sales VALUES (1)",
        "UPDATE sales SET amount = 0",
        "DELETE FROM sales",
        "DROP TABLE sales",
        "CREATE TABLE stolen AS SELECT * FROM sales",
        "PRAGMA table_info(sales)",
        "ATTACH DATABASE 'other.db' AS other",
        "SELECT * FROM sales; DELETE FROM sales",
        "COPY sales TO '/tmp/sales.csv'",
        "SELECT readfile('/etc/passwd')",
        "SELECT writefile('/tmp/leak', 'secret')",
        "SELECT pg_read_file('/etc/passwd')",
        "SELECT load_file('/etc/passwd')",
        "SELECT load_extension('/tmp/untrusted')",
        "SELECT pg_sleep(30)",
        "SELECT benchmark(1000000, SHA1('x'))",
        "SELECT system('whoami')",
        "SELECT shell('whoami')",
        "SELECT exec('whoami')",
        "SELECT /* comment */ SyStEm('whoami')",
        "CALL dangerous_procedure()",
    ],
)
def test_write_and_command_queries_are_rejected(sql):
    with pytest.raises(DashboardSQLSecurityError):
        validate_read_only_sql(sql, allowed_tables={"sales"})


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 'system' AS category",
        "SELECT 'CALL dangerous_procedure()' AS documentation",
        "SELECT 'it''s an export note' AS note",
        "SELECT 1 /* system note */ AS value",
        "SELECT 1 -- call is mentioned in documentation\nAS value",
        'SELECT 1 AS "system"',
    ],
)
def test_command_words_in_literals_comments_and_identifiers_are_allowed(sql):
    result = validate_read_only_sql(sql)
    assert result.sql == sql.strip()


def test_table_and_column_allowlists_are_enforced():
    with pytest.raises(DashboardSQLSecurityError, match="tables outside"):
        validate_read_only_sql("SELECT * FROM secrets", allowed_tables={"sales"})
    with pytest.raises(DashboardSQLSecurityError, match="columns outside"):
        validate_read_only_sql(
            "SELECT password FROM sales",
            allowed_tables={"sales"},
            allowed_columns={"store", "sales"},
        )


@pytest.mark.parametrize(
    "sql",
    [
        "WITH secret AS (SELECT 1) SELECT * FROM main.secret",
        "SELECT * FROM secret WHERE EXISTS "
        "(WITH secret AS (SELECT 1) SELECT * FROM secret)",
        "SELECT * FROM private.sales",
    ],
)
def test_table_allowlist_cannot_be_bypassed_by_cte_names_or_qualifiers(sql):
    with pytest.raises(DashboardSQLSecurityError, match="tables outside"):
        validate_read_only_sql(sql, dialect="sqlite", allowed_tables={"sales"})


def test_explicit_qualified_allowlist_and_recursive_cte_are_supported():
    result = validate_read_only_sql(
        "SELECT * FROM main.sales", dialect="sqlite", allowed_tables={"main.sales"}
    )
    assert result.tables == {"main.sales"}
    result = validate_read_only_sql(
        "WITH RECURSIVE counter(value) AS (SELECT 1 UNION ALL "
        "SELECT value + 1 FROM counter WHERE value < 3) SELECT * FROM counter",
        dialect="sqlite",
        allowed_tables=set(),
    )
    assert result.tables == set()


def test_named_values_are_bound_and_multi_select_is_expanded():
    sql = "SELECT * FROM sales WHERE store IN (:stores) AND date >= :start_date"
    validated = validate_read_only_sql(sql, allowed_tables={"sales"})
    executable, params = bind_named_parameters(
        validated.sql,
        {"stores": [1, 2], "start_date": "2010-01-01", "unused": "ignored"},
        validated.parameters,
    )
    assert "IN (:__dbgpt_stores_0, :__dbgpt_stores_1)" in executable
    assert params == {
        "__dbgpt_stores_0": 1,
        "__dbgpt_stores_1": 2,
        "start_date": "2010-01-01",
    }


def test_list_expansion_cannot_shadow_an_existing_parameter():
    executable, params = bind_named_parameters(
        "SELECT * FROM sales WHERE store IN (:stores) OR store = :stores_0",
        {"stores": [1, 2], "stores_0": 9},
    )

    assert "IN (:__dbgpt_stores_0, :__dbgpt_stores_1)" in executable
    assert "store = :stores_0" in executable
    assert params == {
        "__dbgpt_stores_0": 1,
        "__dbgpt_stores_1": 2,
        "stores_0": 9,
    }


@pytest.mark.parametrize("value", [{1, 2}, [(1, 2)], [[1, 2]], [{"id": 1}]])
def test_multi_select_parameters_must_be_ordered_and_scalar(value):
    with pytest.raises(DashboardSQLSecurityError):
        bind_named_parameters(
            "SELECT * FROM sales WHERE store IN (:stores)", {"stores": value}
        )


@pytest.mark.parametrize(
    ("values", "expected_fragment", "expected_params"),
    [
        ([], "WHERE TRUE", {}),
        ([1], "store IN (:__dbgpt_stores_0)", {"__dbgpt_stores_0": 1}),
        (
            [1, 2],
            "store IN (:__dbgpt_stores_0, :__dbgpt_stores_1)",
            {"__dbgpt_stores_0": 1, "__dbgpt_stores_1": 2},
        ),
    ],
)
def test_optional_multi_select_supports_empty_one_and_many(
    values, expected_fragment, expected_params
):
    prepared_sql, prepared_values = prepare_multi_select_sql(
        "SELECT * FROM sales WHERE store IN (:stores)",
        {"stores": values},
        {"stores"},
        dialect="sqlite",
    )
    validated = validate_read_only_sql(prepared_sql, allowed_tables={"sales"})
    executable, params = bind_named_parameters(
        validated.sql, prepared_values, validated.parameters
    )

    assert expected_fragment.lower() in executable.lower()
    assert params == expected_params


def test_legacy_null_guard_is_normalized_before_multi_select_expansion():
    prepared_sql, prepared_values = prepare_multi_select_sql(
        ("SELECT * FROM sales WHERE (:stores IS NULL OR store IN (:stores))"),
        {"stores": [1, 2]},
        {"stores"},
        dialect="sqlite",
    )
    validated = validate_read_only_sql(prepared_sql, allowed_tables={"sales"})
    executable, params = bind_named_parameters(
        validated.sql, prepared_values, validated.parameters
    )

    assert "IS NULL" not in executable.upper()
    assert "IN (:__dbgpt_stores_0, :__dbgpt_stores_1)" in executable
    assert params == {"__dbgpt_stores_0": 1, "__dbgpt_stores_1": 2}


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM sales WHERE store = :stores",
        "SELECT * FROM sales WHERE :stores IS NULL",
        "SELECT :stores AS documentation FROM sales",
    ],
)
def test_multi_select_parameter_outside_in_predicate_is_rejected(sql):
    with pytest.raises(DashboardSQLSecurityError, match="IN or NOT IN"):
        prepare_multi_select_sql(
            sql,
            {"stores": [1, 2]},
            {"stores"},
            dialect="sqlite",
        )


def test_missing_named_value_fails_closed():
    with pytest.raises(DashboardSQLSecurityError, match="Missing SQL parameters"):
        bind_named_parameters("SELECT * FROM sales WHERE store = :store", {})


def test_template_interpolation_is_never_accepted():
    with pytest.raises(DashboardSQLSecurityError, match="named parameters"):
        validate_read_only_sql("SELECT * FROM ${table}")


def test_server_row_limit_cannot_be_overridden_by_user_sql():
    limited = apply_row_limit("SELECT * FROM sales LIMIT 999999", 100)
    assert limited.endswith("LIMIT 101")
    assert "AS dbgpt_dashboard_query" in limited


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM read_text('/tmp/private.txt')",
        "SELECT * FROM read_blob('/tmp/private.bin')",
        "SELECT * FROM read_csv_auto('/tmp/private.csv')",
        "SELECT * FROM '/tmp/private.csv'",
        "SELECT * FROM glob('/tmp/*')",
        "SELECT * FROM query('SELECT * FROM read_text(''/tmp/private.txt'')')",
    ],
)
def test_duckdb_external_sources_cannot_bypass_table_allowlist(sql):
    with pytest.raises(DashboardSQLSecurityError):
        validate_read_only_sql(sql, dialect="duckdb", allowed_tables={"sales"})


def test_duckdb_registered_table_cte_and_scalar_functions_remain_available():
    result = validate_read_only_sql(
        "WITH monthly AS (SELECT date_trunc('month', day) AS month, value FROM sales) "
        "SELECT month, sum(value) FROM monthly GROUP BY month",
        dialect="duckdb",
        allowed_tables={"sales"},
    )
    assert result.tables == {"sales"}
