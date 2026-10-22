"""Phase 1/2 unit tests: L1 sync + drift, whitelist, review & metric publish."""

from typing import Dict, List

import pytest

from dbgpt.storage.metadata import db
from dbgpt_serve.semantic.models import (
    SemColumnDao,
    SemEntryDao,
    SemEntryEntity,
    SemMetricVersionDao,
    SemPublishLogEntity,
    SemTableDao,
)
from dbgpt_serve.semantic.publisher import LoggingSink, SemanticPublisher
from dbgpt_serve.semantic.service import SemanticService
from dbgpt_serve.semantic.sync import SemanticSyncService

TABLES_V1: Dict[str, Dict] = {
    "orders": {
        "comment": "order master",
        "columns": [
            {"name": "id", "type": "int", "comment": "pk", "is_in_primary_key": True},
            {
                "name": "status",
                "type": "int",
                "comment": "",
                "is_in_primary_key": False,
            },
            {
                "name": "amount",
                "type": "decimal",
                "comment": "",
                "is_in_primary_key": False,
            },
        ],
    },
    "users": {
        "comment": "",
        "columns": [
            {"name": "id", "type": "int", "comment": "pk", "is_in_primary_key": True},
            {
                "name": "name",
                "type": "varchar",
                "comment": "",
                "is_in_primary_key": False,
            },
        ],
    },
}

TABLES_V2: Dict[str, Dict] = {
    "orders": {
        "comment": "order master",
        "columns": [
            {"name": "id", "type": "int", "comment": "pk", "is_in_primary_key": True},
            {
                "name": "amount",
                "type": "decimal",
                "comment": "",
                "is_in_primary_key": False,
            },
        ],
    },
    "users": {
        "comment": "",
        "columns": [
            {"name": "id", "type": "int", "comment": "pk", "is_in_primary_key": True},
            {
                "name": "name",
                "type": "varchar",
                "comment": "",
                "is_in_primary_key": False,
            },
        ],
    },
}


class FakeConnector:
    db_type = "sqlite"

    def __init__(self, tables: Dict[str, Dict]) -> None:
        self._tables = tables

    def get_current_db_name(self) -> str:
        return "fake"

    def get_table_names(self) -> List[str]:
        return list(self._tables.keys())

    def get_table_comments(self, db_name: str) -> List[tuple]:
        return [(n, t.get("comment")) for n, t in self._tables.items()]

    def get_columns(self, table: str) -> List[Dict]:
        return self._tables[table]["columns"]

    def get_indexes(self, table: str) -> List[Dict]:
        return []


@pytest.fixture(scope="module")
def sem_db(tmp_path_factory):
    path = tmp_path_factory.mktemp("sem") / "sem.db"
    db.init_db(f"sqlite:///{path}")
    import dbgpt_serve.semantic.models  # noqa: F401  (register tables)

    db.create_all()
    yield db


def _add_entry(ds_id: int, entry_type: str, target_id: int, name: str) -> int:
    dao = SemEntryDao()
    session = dao.get_raw_session()
    session.expire_on_commit = False
    try:
        entry = SemEntryEntity(
            ds_id=ds_id,
            entry_type=entry_type,
            target_id=target_id,
            entry_name=name,
            entry_comment="order status enum",
            status="draft",
        )
        session.add(entry)
        session.commit()
        return entry.id
    finally:
        session.close()


def test_sync_creates_snapshot(sem_db):
    svc = SemanticSyncService()
    space = svc.ensure_space("conn_a", "conn_a", "sqlite")
    report = svc.sync("conn_a", FakeConnector(TABLES_V1))
    assert report.tables_added == 2
    assert report.columns_added == 5
    tables = SemTableDao().list_by_ds(space.id, status="active")
    assert {t.table_name for t in tables} == {"orders", "users"}
    orders = next(t for t in tables if t.table_name == "orders")
    cols = SemColumnDao().list_by_table(space.id, orders.id, status="active")
    assert {c.column_name for c in cols} == {"id", "status", "amount"}
    assert next(c for c in cols if c.column_name == "id").is_pk


def test_sync_drift_marks_deleted_and_stale(sem_db):
    svc = SemanticSyncService()
    space = svc.ensure_space("conn_b", "conn_b", "sqlite")
    svc.sync("conn_b", FakeConnector(TABLES_V1))
    orders = SemTableDao().get_by_name(space.id, "orders")
    status_col = SemColumnDao().get_by_name(space.id, orders.id, "status")
    entry_id = _add_entry(space.id, "column", status_col.id, "orders.status")

    report = svc.sync("conn_b", FakeConnector(TABLES_V2))
    assert report.columns_deleted == 1
    assert report.entries_staled == 1
    col = SemColumnDao().get_by_name(space.id, orders.id, "status")
    assert col.status == "deleted"
    entry = SemEntryDao().get(entry_id)
    assert entry.status == "stale"


def test_whitelist_limit(sem_db):
    svc = SemanticSyncService()
    space = svc.ensure_space("conn_c", "conn_c", "sqlite")
    svc.sync("conn_c", FakeConnector(TABLES_V1))
    chosen = svc.apply_whitelist(space.id, limit=1)
    assert chosen == 1
    tables = SemTableDao().list_by_ds(space.id, status="active")
    whitelisted = [t for t in tables if t.is_whitelisted]
    assert len(whitelisted) == 1
    # comment coverage is the P0 ordering proxy: "orders" has a comment.
    assert whitelisted[0].table_name == "orders"


def test_review_entry_confirm_publishes_chunk(sem_db):
    sink = LoggingSink()
    service = SemanticService(publisher=SemanticPublisher(sink=sink))
    sync = SemanticSyncService()
    space = sync.ensure_space("conn_d", "conn_d", "sqlite")
    sync.sync("conn_d", FakeConnector(TABLES_V1))
    table = SemTableDao().get_by_name(space.id, "orders")
    entry_id = _add_entry(space.id, "table", table.id, "orders")

    result = service.review_entry(entry_id, "confirm", user="ckt")
    assert result["status"] == "published"
    chunks = sink.spaces.get(space.space_name, [])
    assert any(c.chunk_id == result["chunk_id"] for c in chunks)
    entry = SemEntryDao().get(entry_id)
    assert entry.publish_version == entry.version


def test_publish_metric_versions_and_log(sem_db):
    sink = LoggingSink()
    service = SemanticService(publisher=SemanticPublisher(sink=sink))
    sync = SemanticSyncService()
    space = sync.ensure_space("conn_e", "conn_e", "sqlite")
    metric = service.create_metric(
        space.id,
        {
            "metric_name": "valid_gmv",
            "formula": "SUM(order_amount)",
            "dimensions": ["region", "dt"],
        },
        user="ckt",
    )
    first = service.publish_metric(metric.id, user="ckt", change_note="init")
    second = service.publish_metric(metric.id, user="ckt", change_note="filter fix")
    assert first["version"] == 1
    assert second["version"] == 2
    latest = SemMetricVersionDao().latest(metric.id)
    assert latest.version == 2
    session = SemMetricVersionDao().get_raw_session()
    try:
        logs = (
            session.query(SemPublishLogEntity)
            .filter(SemPublishLogEntity.ds_id == space.id)
            .all()
        )
    finally:
        session.close()
    assert len(logs) == 2
    chunks = sink.spaces.get(space.space_name, [])
    assert any(c.metadata["type"] == "metric" for c in chunks)


def test_coverage_counts(sem_db):
    service = SemanticService()
    sync = SemanticSyncService()
    space = sync.ensure_space("conn_f", "conn_f", "sqlite")
    sync.sync("conn_f", FakeConnector(TABLES_V1))
    table = SemTableDao().get_by_name(space.id, "orders")
    _add_entry(space.id, "table", table.id, "orders")
    cov = service.coverage(space.id)
    assert cov["tables"] == 2
    assert cov["tables_annotated"] == 1
    assert cov["coverage_pct"] == 50.0
