"""Validate model-supplied SQL as a single read-only statement."""

import re

import sqlparse
from sqlparse import tokens as T

_MARKDOWN_ESCAPES = re.compile(r"\\([_`*])")
_EXPLAIN_PREFIX = re.compile(
    r"^EXPLAIN\s+(?:QUERY\s+PLAN\s+|ANALYZE\s+)?", re.IGNORECASE
)


class ReadOnlySqlError(ValueError):
    """Raised when SQL is not one read-only SELECT/WITH statement."""


def read_only_sql(sql: str) -> str:
    """Normalize ``sql`` and reject anything that could modify the database.

    Statement type comes from a full parse (not the leading keyword), so a
    ``WITH`` prefix cannot smuggle a DELETE/UPDATE/INSERT past validation, and
    multiple statements are rejected outright.
    """
    value = _MARKDOWN_ESCAPES.sub(r"\1", sql).strip().rstrip(";")
    statements = sqlparse.parse(value)
    if len(statements) == 1:
        # get_type() identifies the outer statement only. Inspect every token
        # as writable CTEs can have an outer SELECT, and SELECT INTO writes too.
        for token in statements[0].flatten():
            if (
                token.ttype in T.Keyword.DDL
                or (token.ttype in T.Keyword.DML and token.normalized != "SELECT")
                or (token.ttype in T.Keyword and token.normalized == "INTO")
            ):
                raise ReadOnlySqlError("查询中不允许包含写入语句或 SELECT INTO。")
        statement_type = statements[0].get_type()
        if statement_type == "SELECT":
            return value
        if _EXPLAIN_PREFIX.match(value):
            explained = sqlparse.parse(_EXPLAIN_PREFIX.sub("", value, count=1))
            if len(explained) == 1 and explained[0].get_type() == "SELECT":
                return value
    raise ReadOnlySqlError("仅支持单条只读 SELECT / WITH 查询及其 EXPLAIN。")
