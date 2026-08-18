"""Tests for bounded database schema-discovery tools."""

import json

from dbgpt_app.openapi.api_v1.tools.database import (
    DATABASE_SCHEMA_CACHE_MAX_ENTRIES,
    DATABASE_TOOL_OUTPUT_MAX_CHARS,
    make_database_tools,
    make_get_table_schema,
    make_list_database_tables,
)


class _Connector:
    def __init__(self, table_names, schema_size=0):
        self.table_names = table_names
        self.schema_calls = []
        self.schema_size = schema_size

    def get_table_names(self):
        return self.table_names

    def get_table_info_no_throw(self, table_names=None):
        self.schema_calls.append(table_names)
        tables = table_names or self.table_names
        schema = "\n".join(f"CREATE TABLE `{name}` (`id` BIGINT);" for name in tables)
        if self.schema_size:
            schema += "x" * self.schema_size
        return schema

    def run(self, sql):
        return [[("value",)], (1,)]


def _content(tool_result: str) -> str:
    return json.loads(tool_result)["chunks"][0]["content"]


def test_get_table_schema_validates_name_and_caches_result():
    connector = _Connector(["Events"])
    schema_tool = make_get_table_schema(connector)

    unknown = _content(schema_tool("missing"))
    first = _content(schema_tool("events"))
    second = _content(schema_tool("`Events`"))

    assert "Unknown or ambiguous table" in unknown
    assert "CREATE TABLE `Events`" in first
    assert second == first
    assert connector.schema_calls == [["Events"]]


def test_get_table_schema_output_is_bounded():
    connector = _Connector(["wide_table"], schema_size=50_000)
    schema_tool = make_get_table_schema(connector)

    content = _content(schema_tool("wide_table"))

    assert len(content) <= DATABASE_TOOL_OUTPUT_MAX_CHARS
    assert f"truncated at {DATABASE_TOOL_OUTPUT_MAX_CHARS} characters" in content


def test_get_table_schema_cache_evicts_least_recently_used_entry():
    table_names = [
        f"table_{index}" for index in range(DATABASE_SCHEMA_CACHE_MAX_ENTRIES + 1)
    ]
    connector = _Connector(table_names, schema_size=50_000)
    schema_tool = make_get_table_schema(connector)

    for table_name in table_names:
        content = _content(schema_tool(table_name))
        assert len(content) <= DATABASE_TOOL_OUTPUT_MAX_CHARS

    _content(schema_tool(table_names[0]))

    assert connector.schema_calls.count([table_names[0]]) == 2


def test_list_database_tables_filters_and_limits_results():
    connector = _Connector(["sales_daily", "sales_monthly", "users"])
    list_tool = make_list_database_tables(connector)

    content = _content(list_tool(query="SALES", limit=1))

    assert "Matched 2 of 3 tables; showing 1" in content
    assert "`sales_daily`" in content
    assert "`sales_monthly`" not in content


def test_list_database_tables_never_splits_long_names():
    table_names = [f"table_{index}_{'x' * 300}" for index in range(100)]
    list_tool = make_list_database_tables(_Connector(table_names))

    content = _content(list_tool(limit=100))
    formatted_names = content.splitlines()[1]
    rendered_names = [
        fragment for fragment in formatted_names.split(", ") if fragment.startswith("`")
    ]

    assert len(content) <= DATABASE_TOOL_OUTPUT_MAX_CHARS
    assert "table names omitted" in formatted_names
    assert rendered_names
    assert all(
        fragment.endswith("`") and fragment.strip("`") in table_names
        for fragment in rendered_names
    )


def test_database_tool_factory_is_shared_by_agent_modes():
    tools = make_database_tools({}, _Connector(["events"]))

    assert [tool.__name__ for tool in tools] == [
        "sql_query",
        "list_database_tables",
        "get_table_schema",
    ]
