"""Tests for bounded ReAct database context construction."""

from dbgpt_app.openapi.api_v1.database_context import (
    DATABASE_CONTEXT_MAX_CHARS,
    DATABASE_MENTIONED_TABLES_MAX_CHARS,
    DATABASE_SCHEMA_CONTEXT_MAX_CHARS,
    DATABASE_TABLE_PREVIEW_LIMIT,
    DATABASE_TABLE_PREVIEW_MAX_CHARS,
    build_database_context,
    build_database_tools_prompt,
    format_table_names_bounded,
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


def test_large_database_context_is_bounded_without_eager_schema_loading():
    connector = _Connector([f"table_{index:04d}" for index in range(1000)])

    context, table_names, mentioned_tables = build_database_context(
        "warehouse", "summarize recent activity", connector
    )

    assert len(context) <= DATABASE_CONTEXT_MAX_CHARS
    assert len(table_names) == 1000
    assert mentioned_tables == []
    assert connector.schema_calls == []
    assert context.count("`table_") == DATABASE_TABLE_PREVIEW_LIMIT
    assert "CREATE TABLE" not in context


def test_context_only_embeds_schema_for_explicitly_mentioned_table():
    connector = _Connector(
        ["ads_risk_user_risk_1h", "ads_risk_user_risk_1h_archive", "other_table"]
    )

    context, _, mentioned_tables = build_database_context(
        "uat",
        "Build a dashboard from ads_risk_user_risk_1h.",
        connector,
    )

    assert mentioned_tables == ["ads_risk_user_risk_1h"]
    assert connector.schema_calls == [["ads_risk_user_risk_1h"]]
    assert "CREATE TABLE `ads_risk_user_risk_1h`" in context
    assert "CREATE TABLE `ads_risk_user_risk_1h_archive`" not in context
    assert "already\n  registered" in context


def test_embedded_schema_has_a_strict_budget():
    connector = _Connector(["wide_table"], schema_size=50_000)

    context, _, _ = build_database_context("warehouse", "Inspect wide_table", connector)

    assert len(context) <= DATABASE_CONTEXT_MAX_CHARS
    assert f"truncated at {DATABASE_SCHEMA_CONTEXT_MAX_CHARS} characters" in context


def test_knowledge_mode_does_not_claim_database_tools_are_registered():
    connector = _Connector(["events"])

    context, _, _ = build_database_context(
        "warehouse",
        "Summarize the knowledge base",
        connector,
        database_tools_enabled=False,
    )

    assert "database tools are disabled" in context.lower()
    assert "tools are already" not in context


def test_database_tool_prompt_matches_tool_mode():
    assert build_database_tools_prompt("knowledge", 6) == ""

    prompt = build_database_tools_prompt("full", 14)
    assert "14. **sql_query**" in prompt
    assert "14.1. **list_database_tables**" in prompt
    assert "14.2. **get_table_schema**" in prompt


def test_mandatory_guidance_survives_long_table_names_and_schema():
    table_names = [f"table_{index}_{'x' * 220}" for index in range(40)]
    connector = _Connector(table_names, schema_size=50_000)

    context, _, _ = build_database_context(
        "warehouse", f"Inspect {table_names[0]}", connector
    )

    assert len(context) <= DATABASE_CONTEXT_MAX_CHARS
    assert "Only run read-only SELECT statements" in context
    assert "tools are already\n  registered" in context


def test_bounded_table_names_never_split_an_identifier():
    table_names = [f"table_{index}_{'x' * 300}" for index in range(5)]

    formatted = format_table_names_bounded(table_names, 1_000)

    assert len(formatted) <= 1_000
    assert formatted.endswith("[2 table names omitted]")
    assert all(f"`{name}`" in formatted for name in table_names[:3])
    assert all(name not in formatted for name in table_names[3:])
    assert formatted.count("`") == 6


def test_bounded_table_names_omit_an_individually_oversized_name():
    table_name = "table_" + "x" * 1_100

    formatted = format_table_names_bounded([table_name], 100)

    assert formatted == "... [1 table name omitted]"
    assert table_name[:50] not in formatted


def test_context_keeps_multiple_long_mentioned_names_intact():
    table_names = [f"table_{index}_{'x' * 300}" for index in range(8)]
    connector = _Connector(table_names)

    context, _, mentioned_tables = build_database_context(
        "warehouse", "Inspect " + " and ".join(table_names[:5]), connector
    )

    detected_line = next(
        line
        for line in context.splitlines()
        if line.startswith("- Tables detected in the user request:")
    )
    detected_names = detected_line.split(": ", 1)[1]
    preview_line = next(
        line for line in context.splitlines() if line.startswith("- Table preview")
    )
    preview_names = preview_line.split(": ", 1)[1]

    assert mentioned_tables == table_names[:5]
    assert connector.schema_calls == [table_names[:5]]
    assert len(detected_names) <= DATABASE_MENTIONED_TABLES_MAX_CHARS
    assert len(preview_names) <= DATABASE_TABLE_PREVIEW_MAX_CHARS
    assert detected_names.endswith("[2 table names omitted]")
    assert preview_names.endswith("[2 table names omitted]")
    assert all(
        fragment.strip("`") in table_names
        for fragment in detected_names.split(", ")
        if fragment.startswith("`")
    )
    assert all(
        fragment.strip("`") in table_names
        for fragment in preview_names.split(", ")
        if fragment.startswith("`")
    )
