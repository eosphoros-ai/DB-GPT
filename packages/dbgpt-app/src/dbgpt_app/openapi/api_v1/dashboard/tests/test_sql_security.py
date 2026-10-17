import pytest

from dbgpt_app.openapi.api_v1.dashboard.sql_security import (
    DashboardSQLSecurityError,
    apply_row_limit,
    bind_named_parameters,
    prepare_multi_select_sql,
    validate_read_only_sql,
)


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
