"""S7 REST API smoke tests (TestClient over the semantic router)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from dbgpt.storage.metadata import db
from dbgpt_serve.semantic.api import router
from dbgpt_serve.semantic.sync import SemanticSyncService
from dbgpt_serve.semantic.tests.test_semantic_phase12 import (
    TABLES_V1,
    FakeConnector,
)

P = "/api/v1/semantic"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    path = tmp_path_factory.mktemp("sem_api") / "sem.db"
    db.init_db(f"sqlite:///{path}")
    import dbgpt_serve.semantic.models  # noqa: F401  (register tables)
    import dbgpt_serve.datasource.manages.connect_config_db  # noqa: F401

    db.create_all()
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


def _seed() -> int:
    sync = SemanticSyncService()
    space = sync.ensure_space("api_conn", "api_conn", "sqlite")
    sync.sync("api_conn", FakeConnector(TABLES_V1))
    return space.id


def test_list_spaces_empty_then_seeded(client):
    resp = client.get(f"{P}/spaces")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    before = len(body["data"])
    ds_id = _seed()
    resp = client.get(f"{P}/spaces")
    data = resp.json()["data"]
    assert len(data) == before + 1
    assert any(s["id"] == ds_id and s["status"] == "not_activated" for s in data)


def test_activate_and_coverage(client):
    ds_id = _seed()
    resp = client.post(
        f"{P}/spaces/{ds_id}/activate",
        json={"sampling_limit": 1, "embedding_model": "bge-large-zh"},
    )
    assert resp.status_code == 200
    payload = resp.json()["data"]
    assert payload["status"] == "activated"
    assert payload["whitelist"] == 1
    cov = client.get(f"{P}/spaces/{ds_id}/coverage").json()["data"]
    assert cov["tables"] == 2
    assert cov["whitelisted"] == 1


def test_tables_and_entries_review_flow(client):
    ds_id = _seed()
    tables = client.get(f"{P}/spaces/{ds_id}/tables").json()["data"]
    assert {t["table_name"] for t in tables} == {"orders", "users"}
    orders = next(t for t in tables if t["table_name"] == "orders")
    cols = client.get(
        f"{P}/tables/{orders['id']}/columns", params={"ds_id": ds_id}
    ).json()["data"]
    assert {c["column_name"] for c in cols} == {"id", "status", "amount"}

    from dbgpt_serve.semantic.service import SemanticService

    service = SemanticService()
    created = service.create_entry(
        ds_id,
        {
            "entry_type": "table",
            "target_id": orders["id"],
            "entry_name": "orders",
            "entry_comment": "order master table",
        },
        user="ckt",
    )
    entry_id = created["id"]
    drafts = client.get(
        f"{P}/spaces/{ds_id}/entries", params={"status": "draft"}
    ).json()["data"]
    assert any(e["id"] == entry_id for e in drafts)

    resp = client.post(
        f"{P}/entries/{entry_id}/review", json={"action": "confirm", "user": "ckt"}
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "published"
    bad = client.post(f"{P}/entries/{entry_id}/review", json={"action": "nope"})
    assert bad.status_code == 400


def test_metric_create_publish_and_rules(client):
    ds_id = _seed()
    resp = client.post(
        f"{P}/spaces/{ds_id}/metrics",
        json={"metric_name": "valid_gmv", "formula": "SUM(order_amount)"},
    )
    metric_id = resp.json()["data"]["id"]
    pub = client.post(f"{P}/metrics/{metric_id}/publish", json={"user": "ckt"})
    assert pub.json()["data"]["version"] == 1
    metrics = client.get(f"{P}/spaces/{ds_id}/metrics").json()["data"]
    row = next(m for m in metrics if m["id"] == metric_id)
    assert row["status"] == "published" and row["version"] == 1

    from dbgpt_serve.semantic.models import SemRuleEntity
    from dbgpt_serve.semantic.service import SemanticService

    session = SemanticService()._rule_dao.get_raw_session()
    rule = SemRuleEntity(ds_id=ds_id, rule_name="readonly", rule_type="readonly")
    session.add(rule)
    session.commit()
    rule_id = rule.id
    session.close()
    toggled = client.post(
        f"{P}/rules/{rule_id}/status", json={"status": "inactive"}
    ).json()["data"]
    assert toggled["status"] == "inactive"
    rules = client.get(f"{P}/spaces/{ds_id}/rules").json()["data"]
    assert any(r["id"] == rule_id and r["status"] == "inactive" for r in rules)


def test_backfill_without_datasources(client):
    resp = client.post(f"{P}/spaces/backfill")
    assert resp.status_code == 200
    assert resp.json()["data"]["synced"] == []


def test_activate_seeds_default_rules(client):
    sync = SemanticSyncService()
    space = sync.ensure_space("api_conn_rules", "api_conn_rules", "sqlite")
    sync.sync("api_conn_rules", FakeConnector(TABLES_V1))
    resp = client.post(f"{P}/spaces/{space.id}/activate", json={})
    assert resp.json()["data"]["rules_seeded"] == 6
    rules = client.get(f"{P}/spaces/{space.id}/rules").json()["data"]
    assert len(rules) == 6
    by_type = {r["rule_type"]: r for r in rules}
    assert by_type["readonly"]["status"] == "active"
    assert by_type["tenant_filter"]["status"] == "inactive"


def test_create_example_endpoint(client):
    ds_id = _seed()
    resp = client.post(
        f"{P}/spaces/{ds_id}/examples",
        json={"question": "q1", "sql_text": "SELECT 1", "source": "import"},
    )
    assert resp.status_code == 200
    examples = client.get(f"{P}/spaces/{ds_id}/examples").json()["data"]
    assert any(e["question"] == "q1" and e["source"] == "import" for e in examples)


def test_unknown_space_404(client):
    assert client.get(f"{P}/spaces/999999").status_code == 404
