"""Tests for the benchmark SQL read-only guard.

The benchmark pipeline extracts a SQL statement from an LLM/agent HTTP
response and executes it against the benchmark SQLite database
(``_post_sql_query`` → ``BenchmarkDataManager.query``). That text is
attacker-influenceable (in AGENT mode it is fully attacker-controlled),
so only single read-only statements may reach the sink.
"""

import pytest

from ..service.benchmark.sql_guard import validate_read_only_sql


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM t",
        "  select 1",
        "-- leading note\nSELECT 1",
        "/* block */ SELECT 1",
        "WITH cte AS (SELECT 1 AS x) SELECT x FROM cte",
        # semicolon inside a string literal is not a statement separator
        "SELECT ';' AS sep, `a;b` FROM \"t\"",
        "SELECT 1;",
        # trailing comment after the single trailing semicolon
        "SELECT 1;\n-- done",
    ],
)
def test_read_only_statements_are_accepted(sql):
    assert validate_read_only_sql(sql) == sql


@pytest.mark.parametrize(
    "sql, reason",
    [
        ("", "empty"),
        ("   ", "whitespace only"),
        ("-- comment only", "comment only"),
        (";", "bare semicolon"),
        ("INSERT INTO t VALUES (1)", "insert"),
        ("UPDATE t SET a = 1", "update"),
        ("DELETE FROM t", "delete"),
        ("DROP TABLE t", "drop"),
        ("CREATE TABLE t (a int)", "create"),
        ("ATTACH DATABASE '/tmp/evil.db' AS evil", "attach"),
        ("PRAGMA database_list", "pragma"),
        ("VACUUM", "vacuum"),
        ("EXPLAIN SELECT 1", "explain"),
        ("SELECT 1; DROP TABLE t", "stacked statements"),
        ("SELECT 1; ATTACH DATABASE 'x' AS e", "stacked attach"),
        # comment cannot smuggle a write before the SELECT keyword
        ("/* harmless */ ATTACH DATABASE 'x' AS e", "comment prefixed attach"),
        # quote-terminated string followed by a second statement
        ("SELECT 'a'; DELETE FROM t", "string then delete"),
        # SQLite allows a WITH prefix on DML statements — the guard must
        # not assume "starts with WITH" == read-only
        ("WITH cte AS (SELECT 1) INSERT INTO t VALUES (1)", "with-prefixed insert"),
        ("WITH cte AS (SELECT 1) DELETE FROM t", "with-prefixed delete"),
        ("WITH cte AS (SELECT 1) UPDATE t SET a = 1", "with-prefixed update"),
        ("WITH cte AS (SELECT 1) REPLACE INTO t VALUES (1)", "with-prefixed replace"),
        # SQLite treats comments as token separators: REPLACE/**/INTO and
        # REPLACE--x\nINTO still parse as DML, but a scanner that drops
        # comments without emitting a boundary would merge them into the
        # single token REPLACEINTO and miss the pair check
        ("WITH c AS (SELECT 1) REPLACE/**/INTO t VALUES (1)", "block comment split"),
        (
            "WITH c AS (SELECT 1) REPLACE-- note\nINTO t VALUES (1)",
            "line comment split",
        ),
        (
            "WITH c AS (SELECT/**/1) INSERT/**/INTO t VALUES (1)",
            "block comment keyword",
        ),
    ],
)
def test_non_read_only_statements_are_rejected(sql, reason):
    with pytest.raises(ValueError):
        validate_read_only_sql(sql)


@pytest.mark.parametrize(
    "sql",
    [
        # REPLACE() is a legit string function; only REPLACE INTO is DML
        "SELECT REPLACE(name, 'a', 'b') FROM t",
        "WITH cte AS (SELECT REPLACE(a, 'x', 'y') AS r FROM t) SELECT r FROM cte",
        # underscore-suffixed identifiers must not substring-match keywords
        "SELECT updated, inserted_rows FROM report",
    ],
)
def test_write_like_names_in_read_positions_are_allowed(sql):
    assert validate_read_only_sql(sql) == sql
