from unittest.mock import MagicMock

import pytest
from sqlalchemy import exc
from sqlalchemy.sql import sqltypes

from dbgpt_ext.datasource.rdbms.conn_starrocks import StarRocksConnector
from dbgpt_ext.datasource.rdbms.dialect.starrocks.sqlalchemy.datatype import (
    parse_sqltype,
)
from dbgpt_ext.datasource.rdbms.dialect.starrocks.sqlalchemy.dialect import (
    StarRocksDialect,
)


class _IdentifierPreparer:
    @staticmethod
    def quote_identifier(identifier):
        return f"`{identifier.replace('`', '``')}`"


class _Dialect:
    identifier_preparer = _IdentifierPreparer()


class _Engine:
    dialect = _Dialect()


def _connector() -> StarRocksConnector:
    connector = object.__new__(StarRocksConnector)
    connector._is_closed = True
    connector._engine = _Engine()
    connector._custom_table_info = {}
    connector._sample_rows_in_table_info = 0
    connector._indexes_in_table_info = False
    return connector


def test_starrocks_skips_eager_metadata_reflection():
    connector = _connector()
    connector._metadata = MagicMock()

    connector._reflect_metadata()

    connector._metadata.reflect.assert_not_called()


def test_starrocks_columns_preserve_special_type_names(monkeypatch):
    connector = _connector()
    monkeypatch.setattr(
        connector,
        "get_fields",
        lambda table_name: [
            ("bitmap_value", "BITMAP", None, "NO", "bitmap column"),
            ("hll_value", "HLL", None, "YES", None),
            ("array_value", "ARRAY<INT>", None, "YES", None),
        ],
    )

    columns = connector.get_columns("events")

    assert [column["type"] for column in columns] == ["BITMAP", "HLL", "ARRAY<INT>"]
    assert columns[0]["nullable"] is False
    assert columns[0]["comment"] == "bitmap column"


def test_starrocks_table_info_does_not_require_reflected_metadata(monkeypatch):
    connector = _connector()
    monkeypatch.setattr(connector, "get_usable_table_names", lambda: {"events"})
    monkeypatch.setattr(
        connector,
        "get_fields",
        lambda table_name: [
            ("bitmap_value", "BITMAP", None, "NO", "bitmap's value"),
            ("array_value", "ARRAY<INT>", None, "YES", None),
        ],
    )

    table_info = connector.get_table_info()

    assert "CREATE TABLE `events`" in table_info
    assert "`bitmap_value` BITMAP NOT NULL COMMENT 'bitmap''s value'" in table_info
    assert "`array_value` ARRAY<INT>" in table_info


def test_starrocks_table_info_does_not_sample_aggregate_columns(monkeypatch):
    connector = _connector()
    connector._sample_rows_in_table_info = 3
    monkeypatch.setattr(connector, "get_usable_table_names", lambda: {"events"})
    monkeypatch.setattr(
        connector,
        "get_fields",
        lambda table_name: [
            ("bitmap_value", "BITMAP", None, "YES", None),
            ("hll_value", "HLL", None, "YES", None),
            ("event_id", "BIGINT", None, "NO", None),
        ],
    )
    sample_rows = MagicMock(return_value="")
    monkeypatch.setattr(connector, "_get_sample_rows_by_name", sample_rows)

    connector.get_table_info()

    sample_rows.assert_called_once_with("events", ["event_id"])


def test_starrocks_table_info_skips_concurrently_removed_table(monkeypatch):
    connector = _connector()
    monkeypatch.setattr(
        connector, "get_usable_table_names", lambda: {"events", "temporary_table"}
    )

    class _OriginalError(Exception):
        pass

    class _DatabaseError(Exception):
        def __init__(self):
            self.orig = _OriginalError(5502, "Unknown table")

    def _build_table_info(table_name):
        if table_name == "temporary_table":
            raise _DatabaseError()
        return "CREATE TABLE `events` (`id` INT)"

    monkeypatch.setattr(connector, "_build_table_info", _build_table_info)

    assert connector.get_table_info() == "CREATE TABLE `events` (`id` INT)"


def test_starrocks_table_info_does_not_hide_connection_errors(monkeypatch):
    connector = _connector()
    monkeypatch.setattr(connector, "get_usable_table_names", lambda: {"events"})
    monkeypatch.setattr(
        connector,
        "_build_table_info",
        lambda table_name: (_ for _ in ()).throw(RuntimeError("connection lost")),
    )

    with pytest.raises(RuntimeError, match="connection lost"):
        connector.get_table_info()


def test_starrocks_dialect_has_table_uses_information_schema(monkeypatch):
    dialect = StarRocksDialect()
    monkeypatch.setattr(
        dialect, "_ensure_has_table_connection", lambda connection: None
    )
    result = MagicMock()
    result.first.return_value = (1,)
    connection = MagicMock()
    connection.execute.return_value = result

    assert dialect.has_table(connection, "events", schema="analytics") is True
    statement, parameters = connection.execute.call_args.args
    assert "information_schema.tables" in str(statement)
    assert parameters == {"schema": "analytics", "table_name": "events"}


def test_starrocks_dialect_parses_columns_without_describe():
    dialect = StarRocksDialect()
    connection = MagicMock()
    connection.execute.return_value = [
        ("bitmap_value", "BITMAP", "NO", None, "bitmap column"),
        ("unknown_value", "FUTURE_TYPE(20)", "YES", None, None),
    ]

    columns = dialect.get_columns(connection, "events", schema="analytics")

    assert columns[0]["type"].__visit_name__ == "BITMAP"
    assert isinstance(columns[1]["type"], sqltypes.NullType)
    assert columns[0]["comment"] == "bitmap column"


def test_starrocks_dialect_reports_missing_table():
    dialect = StarRocksDialect()
    connection = MagicMock()
    connection.execute.return_value = []

    with pytest.raises(exc.NoSuchTableError):
        dialect.get_columns(connection, "missing", schema="analytics")


def test_starrocks_type_parser_preserves_length_and_precision():
    varchar = parse_sqltype("VARCHAR(255)")
    decimal = parse_sqltype("DECIMAL(18, 2)")

    assert varchar.length == 255
    assert decimal.precision == 18
    assert decimal.scale == 2
