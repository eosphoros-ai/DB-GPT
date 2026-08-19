"""Tests for session file persistence metadata and SQL schemas."""

from pathlib import Path

import pytest
from sqlalchemy import BigInteger, CheckConstraint, DateTime, String, Text
from sqlalchemy.dialects import mysql, sqlite

from dbgpt_serve.session_file.models.models import SessionFileEntity

EXPECTED_COLUMNS = {
    "id",
    "file_id",
    "owner_id",
    "session_id",
    "task_id",
    "display_name",
    "storage_uri",
    "media_type",
    "file_kind",
    "size_bytes",
    "sha256",
    "ordinal",
    "status",
    "inspection_json",
    "error_code",
    "error_message",
    "source_file_id",
    "created_at",
    "updated_at",
}
EXPECTED_INDEXES = {
    "uk_session_file_file_id": ("file_id",),
    "idx_session_file_owner_session": (
        "owner_id",
        "session_id",
        "ordinal",
    ),
    "idx_session_file_owner_task": (
        "owner_id",
        "task_id",
        "ordinal",
    ),
    "idx_session_file_sha256": ("owner_id", "sha256"),
}
SCHEMA_PATHS = (
    "assets/schema/dbgpt.sql",
    "assets/schema/upgrade/v0_8_2/upgrade_to_v0.8.2.sql",
    "assets/schema/upgrade/v0_8_2/v0.8.2.sql",
)


def test_session_file_model_matches_persistence_contract():
    table = SessionFileEntity.__table__

    assert table.name == "dbgpt_session_file"
    assert set(table.columns.keys()) == EXPECTED_COLUMNS
    assert isinstance(table.c.id.type, BigInteger)
    assert table.c.id.primary_key and table.c.id.autoincrement is True
    assert isinstance(table.c.size_bytes.type, BigInteger)
    assert isinstance(table.c.inspection_json.type, Text)
    assert isinstance(table.c.error_message.type, Text)
    assert table.c.inspection_json.type.compile(dialect=mysql.dialect()) == "LONGTEXT"
    assert table.c.inspection_json.type.compile(dialect=sqlite.dialect()) == "TEXT"
    assert table.c.error_message.type.compile(dialect=mysql.dialect()) == "TEXT"

    expected_string_lengths = {
        "file_id": 64,
        "owner_id": 255,
        "session_id": 255,
        "task_id": 64,
        "display_name": 256,
        "storage_uri": 512,
        "media_type": 255,
        "file_kind": 32,
        "sha256": 64,
        "status": 32,
        "error_code": 64,
        "source_file_id": 64,
    }
    for column_name, length in expected_string_lengths.items():
        column = table.c[column_name]
        assert isinstance(column.type, String)
        assert column.type.length == length

    assert table.c.inspection_json.nullable is True
    assert table.c.error_code.nullable is True
    assert table.c.error_message.nullable is True
    for timestamp_name in ("created_at", "updated_at"):
        timestamp = table.c[timestamp_name]
        assert isinstance(timestamp.type, DateTime)
        assert timestamp.nullable is False
        assert timestamp.server_default is not None
        assert timestamp.default is not None
    assert table.c.updated_at.onupdate is not None


def test_session_file_big_integer_primary_key_compiles_for_sqlite_autoincrement():
    id_type = SessionFileEntity.__table__.c.id.type

    assert isinstance(id_type, BigInteger)
    assert id_type.compile(dialect=sqlite.dialect()) == "INTEGER"
    assert id_type.compile(dialect=mysql.dialect()) == "BIGINT"


def test_session_file_model_is_registered_for_database_initialization():
    initialization = Path(
        "packages/dbgpt-app/src/dbgpt_app/initialization/db_model_initialization.py"
    ).read_text(encoding="utf-8")

    assert (
        "from dbgpt_serve.session_file.models.models import SessionFileEntity"
        in initialization
    )
    assert "    SessionFileEntity," in initialization


def test_session_file_model_has_only_named_contract_indexes():
    indexes = {
        index.name: tuple(column.name for column in index.columns)
        for index in SessionFileEntity.__table__.indexes
    }

    assert indexes == EXPECTED_INDEXES
    assert next(
        index
        for index in SessionFileEntity.__table__.indexes
        if index.name == "uk_session_file_file_id"
    ).unique
    assert all("storage_uri" not in columns for columns in indexes.values())
    assert all(columns != ("source_file_id",) for columns in indexes.values())


def test_session_file_model_requires_exactly_one_scope():
    constraints = {
        constraint.name: str(constraint.sqltext)
        for constraint in SessionFileEntity.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert constraints == {
        "ck_session_file_scope": "(session_id IS NULL) <> (task_id IS NULL)"
    }


@pytest.mark.parametrize("schema_path", SCHEMA_PATHS)
def test_mysql_schema_matches_session_file_contract(schema_path):
    sql = Path(schema_path).read_text(encoding="utf-8")
    table_sql = sql[sql.index("CREATE TABLE IF NOT EXISTS `dbgpt_session_file`") :]
    table_sql = table_sql[: table_sql.index(";") + 1]

    expected_definitions = (
        "`id` bigint NOT NULL AUTO_INCREMENT",
        "`file_id` varchar(64) NOT NULL",
        "`owner_id` varchar(255) NOT NULL",
        "`session_id` varchar(255) DEFAULT NULL",
        "`task_id` varchar(64) DEFAULT NULL",
        "`display_name` varchar(256) NOT NULL",
        "`storage_uri` varchar(512) NOT NULL",
        "`media_type` varchar(255) NOT NULL",
        "`file_kind` varchar(32) NOT NULL",
        "`size_bytes` bigint NOT NULL",
        "`sha256` varchar(64) NOT NULL",
        "`ordinal` int NOT NULL",
        "`status` varchar(32) NOT NULL",
        "`inspection_json` longtext DEFAULT NULL",
        "`error_code` varchar(64) DEFAULT NULL",
        "`error_message` text DEFAULT NULL",
        "`source_file_id` varchar(64) DEFAULT NULL",
        "`created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP",
        "`updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP "
        "ON UPDATE CURRENT_TIMESTAMP",
    )
    for definition in expected_definitions:
        assert definition in table_sql

    assert "UNIQUE KEY `uk_session_file_file_id` (`file_id`)" in table_sql
    assert (
        "CONSTRAINT `ck_session_file_scope` CHECK "
        "((`session_id` IS NULL) <> (`task_id` IS NULL))" in table_sql
    )
    assert (
        "KEY `idx_session_file_owner_session` "
        "(`owner_id`,`session_id`,`ordinal`)" in table_sql
    )
    assert (
        "KEY `idx_session_file_owner_task` "
        "(`owner_id`,`task_id`,`ordinal`)" in table_sql
    )
    assert "KEY `idx_session_file_sha256` (`owner_id`,`sha256`)" in table_sql
    assert "idx_session_file_source_file_id" not in table_sql
    assert "idx_session_file_storage_uri" not in table_sql
    assert "DEFAULT CHARSET=utf8mb4" in table_sql
