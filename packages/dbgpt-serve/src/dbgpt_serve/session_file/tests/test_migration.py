"""Contract tests for the session file Alembic migration."""

import importlib.util
from pathlib import Path
from unittest.mock import call

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Integer, String, Text
from sqlalchemy.dialects import mysql, sqlite

MIGRATION_PATH = Path("pilot/meta_data/alembic/versions/20260804_session_files.py")


def _load_migration():
    spec = importlib.util.spec_from_file_location(
        "session_file_migration", MIGRATION_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_session_file_migration_file_exists():
    assert MIGRATION_PATH.is_file()


def test_session_file_migration_has_expected_lineage():
    migration = _load_migration()

    assert migration.revision == "20260804sf01"
    assert migration.down_revision == "015827d5a9d0"


def test_session_file_migration_upgrade_creates_complete_contract(monkeypatch):
    migration = _load_migration()
    create_table_calls = []
    create_index_calls = []
    monkeypatch.setattr(
        migration.op,
        "create_table",
        lambda *args, **kwargs: create_table_calls.append((args, kwargs)),
    )
    monkeypatch.setattr(
        migration.op,
        "create_index",
        lambda *args, **kwargs: create_index_calls.append((args, kwargs)),
    )

    migration.upgrade()

    assert len(create_table_calls) == 1
    args, kwargs = create_table_calls[0]
    assert args[0] == "dbgpt_session_file"
    columns = {item.name: item for item in args[1:] if hasattr(item, "type")}
    assert set(columns) == {
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
    assert isinstance(columns["id"].type, BigInteger)
    assert columns["id"].type.compile(dialect=sqlite.dialect()) == "INTEGER"
    assert isinstance(columns["size_bytes"].type, BigInteger)
    assert isinstance(columns["ordinal"].type, Integer)
    assert isinstance(columns["inspection_json"].type, Text)
    assert (
        columns["inspection_json"].type.compile(dialect=mysql.dialect()) == "LONGTEXT"
    )
    assert isinstance(columns["error_message"].type, Text)
    assert isinstance(columns["created_at"].type, DateTime)
    assert isinstance(columns["file_id"].type, String)
    assert columns["file_id"].type.length == 64
    assert kwargs == {}

    checks = [item for item in args[1:] if isinstance(item, CheckConstraint)]
    assert len(checks) == 1
    assert checks[0].name == "ck_session_file_scope"
    assert str(checks[0].sqltext) == "(session_id IS NULL) <> (task_id IS NULL)"
    assert create_index_calls == [
        (
            ("uk_session_file_file_id", "dbgpt_session_file", ["file_id"]),
            {"unique": True},
        ),
        (
            (
                "idx_session_file_owner_session",
                "dbgpt_session_file",
                ["owner_id", "session_id", "ordinal"],
            ),
            {},
        ),
        (
            (
                "idx_session_file_owner_task",
                "dbgpt_session_file",
                ["owner_id", "task_id", "ordinal"],
            ),
            {},
        ),
        (
            (
                "idx_session_file_sha256",
                "dbgpt_session_file",
                ["owner_id", "sha256"],
            ),
            {},
        ),
    ]


def test_session_file_migration_downgrade_only_drops_table(monkeypatch):
    migration = _load_migration()
    calls = []
    monkeypatch.setattr(
        migration.op,
        "drop_table",
        lambda *args, **kwargs: calls.append(call(*args, **kwargs)),
    )

    migration.downgrade()

    assert calls == [call("dbgpt_session_file")]
