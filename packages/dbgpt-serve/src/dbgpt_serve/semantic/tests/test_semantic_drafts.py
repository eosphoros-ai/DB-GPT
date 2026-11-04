"""L2 annotator + L3 metric miner tests (heuristic and fake-LLM modes)."""

import json

import pytest

from dbgpt.storage.metadata import db
from dbgpt_serve.semantic.annotator import SemanticAnnotator
from dbgpt_serve.semantic.metric_miner import MetricMiner
from dbgpt_serve.semantic.models import SemEntryDao, SemMetricDao
from dbgpt_serve.semantic.sync import SemanticSyncService
from dbgpt_serve.semantic.tests.test_semantic_phase12 import (
    TABLES_V1,
    FakeConnector,
)


@pytest.fixture(scope="module")
def sem_db(tmp_path_factory):
    path = tmp_path_factory.mktemp("sem_drafts") / "sem.db"
    db.init_db(f"sqlite:///{path}")
    import dbgpt_serve.semantic.models  # noqa: F401  (register tables)

    db.create_all()
    yield db


def _space(conn: str):
    sync = SemanticSyncService()
    space = sync.ensure_space(conn, conn, "sqlite")
    sync.sync(conn, FakeConnector(TABLES_V1))
    return space.id


def test_annotator_heuristic_drafts(sem_db):
    ds_id = _space("draft_conn_a")
    annotator = SemanticAnnotator()
    counts = annotator.generate_drafts(ds_id)
    assert counts["table_entries"] == 2  # orders + users
    assert counts["column_entries"] == 5
    entries = SemEntryDao().list_by_ds(ds_id, status="draft")
    by_name = {e.entry_name: e for e in entries}
    # comment-derived: high confidence, provenance auto
    assert by_name["orders"].confidence == 0.95
    assert by_name["orders.id"].provenance == "auto"
    # enum-like column: low confidence, pending business confirm
    status_entry = by_name["orders.status"]
    assert status_entry.confidence == 0.6
    assert "待业务确认" in (status_entry.entry_comment or "")
    # idempotent: second run adds nothing
    again = annotator.generate_drafts(ds_id)
    assert again["table_entries"] == 0 and again["column_entries"] == 0
    assert again["skipped"] == counts["table_entries"] + counts["column_entries"]


def test_annotator_llm_mode(sem_db):
    ds_id = _space("draft_conn_b")

    def fake_llm(prompt: str) -> str:
        return json.dumps(
            {
                "columns": [
                    {
                        "column": "status",
                        "comment": "订单状态：0待支付 1已支付 2已发货",
                        "synonyms": ["订单状态", "支付状态"],
                    }
                ]
            }
        )

    counts = SemanticAnnotator().generate_drafts(ds_id, llm_client=fake_llm)
    assert counts["column_entries"] == 5
    entries = SemEntryDao().list_by_ds(ds_id, status="draft")
    status_entry = next(e for e in entries if e.entry_name == "orders.status")
    assert status_entry.provenance == "llm_draft"
    assert json.loads(status_entry.synonyms) == ["订单状态", "支付状态"]


def test_miner_heuristic_candidates(sem_db):
    ds_id = _space("draft_conn_c")
    counts = MetricMiner().mine(ds_id)
    # cnt_orders + cnt_users + sum_orders_amount (decimal amount column)
    assert counts["metrics"] == 3
    metrics = SemMetricDao().list_by_ds(ds_id, status="draft")
    names = {m.metric_name for m in metrics}
    assert "sum_orders_amount" in names
    assert "cnt_orders" in names
    summed = next(m for m in metrics if m.metric_name == "sum_orders_amount")
    assert summed.formula == "SUM(amount)"
    assert summed.version == 0
    # idempotent
    assert MetricMiner().mine(ds_id)["metrics"] == 0


def test_miner_llm_mode(sem_db):
    ds_id = _space("draft_conn_d")

    def fake_llm(prompt: str) -> str:
        return json.dumps(
            {
                "metrics": [
                    {
                        "name": "valid_gmv",
                        "comment": "有效订单GMV",
                        "formula": "SUM(order_amount)",
                        "dimensions": ["region"],
                    }
                ]
            }
        )

    counts = MetricMiner().mine(ds_id, llm_client=fake_llm)
    assert counts["metrics"] == 1
    metric = SemMetricDao().get_by_name(ds_id, "valid_gmv")
    assert metric.provenance == "llm_draft"
    assert metric.formula == "SUM(order_amount)"


def test_api_drafts_endpoint(sem_db):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from dbgpt_serve.semantic.api import router

    app = FastAPI()
    app.include_router(router, prefix="/api")
    client = TestClient(app)
    ds_id = _space("draft_conn_e")
    resp = client.post(f"/api/v1/semantic/spaces/{ds_id}/drafts")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["entries"]["column_entries"] == 5
    assert data["metrics"]["metrics"] == 3
    entries = client.get(
        f"/api/v1/semantic/spaces/{ds_id}/entries", params={"status": "draft"}
    ).json()["data"]
    assert any(e.get("confidence") == 0.6 for e in entries)
