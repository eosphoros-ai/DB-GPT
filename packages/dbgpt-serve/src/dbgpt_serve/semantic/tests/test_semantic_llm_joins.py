"""LLM bridge adapter + L4 join discovery tests."""

import json
from types import SimpleNamespace

import pytest

from dbgpt.storage.metadata import db
from dbgpt_serve.semantic.join_discovery import JoinDiscoverer
from dbgpt_serve.semantic.llm_bridge import build_sync_llm, build_sync_llm_from_client
from dbgpt_serve.semantic.models import SemRelationEntity, SemTableDao
from dbgpt_serve.semantic.sync import SemanticSyncService
from dbgpt_serve.semantic.tests.test_semantic_phase12 import FakeConnector

TABLES_JOIN = {
    "users": {
        "comment": "",
        "columns": [
            {"name": "id", "type": "int", "comment": "", "is_in_primary_key": True},
        ],
    },
    "orders": {
        "comment": "order master",
        "columns": [
            {"name": "id", "type": "int", "comment": "", "is_in_primary_key": True},
            {
                "name": "user_id",
                "type": "int",
                "comment": "",
                "is_in_primary_key": False,
            },
        ],
    },
    "order_items": {
        "comment": "",
        "columns": [
            {"name": "id", "type": "int", "comment": "", "is_in_primary_key": True},
            {
                "name": "order_id",
                "type": "int",
                "comment": "",
                "is_in_primary_key": False,
            },
        ],
    },
}


class FakeInspector:
    def get_foreign_keys(self, table: str):
        if table == "orders":
            return [
                {
                    "referred_table": "users",
                    "constrained_columns": ["user_id"],
                    "referred_columns": ["id"],
                }
            ]
        return []


class FakeConnWithFK(FakeConnector):
    def __init__(self, tables):
        super().__init__(tables)
        self._inspector = FakeInspector()


class FakeLLMClient:
    def __init__(self, text: str):
        self._text = text

    async def generate(self, request):
        return SimpleNamespace(text=self._text)


@pytest.fixture(scope="module")
def sem_db(tmp_path_factory):
    path = tmp_path_factory.mktemp("sem_joins") / "sem.db"
    db.init_db(f"sqlite:///{path}")
    import dbgpt_serve.semantic.models  # noqa: F401  (register tables)

    db.create_all()
    yield db


def test_sync_llm_adapter_runs_own_loop():
    llm = build_sync_llm_from_client(FakeLLMClient('{"columns": []}'), "fake-model")
    assert llm("hi") == '{"columns": []}'


def test_build_sync_llm_none_without_server():
    # No SYSTEM_APP / LLM_MODEL in the test process -> graceful None.
    assert build_sync_llm() is None


def test_join_discovery_fk_and_naming(sem_db):
    sync = SemanticSyncService()
    space = sync.ensure_space("join_conn", "join_conn", "sqlite")
    sync.sync("join_conn", FakeConnWithFK(TABLES_JOIN))
    counts = JoinDiscoverer().discover(space.id, connector=FakeConnWithFK(TABLES_JOIN))
    assert counts["fk"] == 1  # orders.user_id -> users.id (declared)
    assert counts["inferred"] == 1  # order_items.order_id -> orders.id (naming)
    session = SemTableDao().get_raw_session()
    try:
        rows = (
            session.query(SemRelationEntity)
            .filter(SemRelationEntity.ds_id == space.id)
            .all()
        )
    finally:
        session.close()
    by_kind = {r.relation_type: r for r in rows}
    assert by_kind["fk"].status == "active"
    assert by_kind["fk"].confidence == 1.0
    assert by_kind["inferred"].status == "draft"
    assert "orders.user_id" in by_kind["fk"].join_condition
    # idempotent (fk edge also deduped in the naming pass -> 3 skips)
    again = JoinDiscoverer().discover(space.id, connector=FakeConnWithFK(TABLES_JOIN))
    assert again["fk"] == 0 and again["inferred"] == 0 and again["skipped"] == 3


def test_drafts_endpoint_includes_joins(sem_db):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from dbgpt_serve.semantic.api import router

    app = FastAPI()
    app.include_router(router, prefix="/api")
    client = TestClient(app)
    sync = SemanticSyncService()
    space = sync.ensure_space("join_conn_api", "join_conn_api", "sqlite")
    sync.sync("join_conn_api", FakeConnector(TABLES_JOIN))
    resp = client.post(
        f"/api/v1/semantic/spaces/{space.id}/drafts", json={"use_llm": False}
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert set(data) == {"entries", "metrics", "joins"}
    # naming heuristic still fires without an inspector-backed connector
    assert data["joins"]["inferred"] >= 1
    assert json.dumps(data)  # serializable
