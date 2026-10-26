"""Recover existing financial results only within their authenticated scope."""

import json
from contextlib import contextmanager
from types import SimpleNamespace

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from dbgpt_serve.financial_analysis.api import make_router
from dbgpt_serve.financial_analysis.models import FinancialRunEntity
from dbgpt_serve.financial_analysis.service import FinancialAnalysisService
from dbgpt_serve.session_file.api.endpoints import get_authenticated_owner


def test_latest_report_is_session_owner_scoped_and_does_not_expose_repair_drafts():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    factory = sessionmaker(bind=engine)

    @contextmanager
    def session(commit=True):
        with factory() as value:
            yield value
            if commit:
                value.commit()

    service = FinancialAnalysisService(
        SimpleNamespace(dao=SimpleNamespace(session=session))
    )
    report = {
        "revision": "saved-revision",
        "analysis": {"driver": "agent"},
        "workflow": {
            "topics": [{"id": "cashflow", "draftFindings": ["private draft"]}]
        },
    }
    try:
        with session() as value:
            for run_id, owner, scope in [
                ("a" * 36, "alice", "current"),
                ("b" * 36, "bob", "current"),
                ("c" * 36, "alice", "other"),
            ]:
                value.add(
                    FinancialRunEntity(
                        id=run_id,
                        owner_id=owner,
                        session_id=scope,
                        file_id="pdf",
                        status="completed",
                        stage="agent_topics",
                        created_at="2026-10-20",
                        updated_at="2026-10-20",
                        report_json=json.dumps({**report, "id": run_id}),
                    )
                )
        app = FastAPI()

        def owner(request: Request):
            return request.headers["user-id"]

        app.dependency_overrides[get_authenticated_owner] = owner
        app.include_router(make_router(service), prefix="/financial")
        with TestClient(app) as client:
            response = client.get(
                "/financial/runs/latest?session_id=current",
                headers={"user-id": "alice"},
            )
            assert response.status_code == 200
            saved = response.json()["data"]
            assert saved["id"] == "a" * 36
            assert "draftFindings" not in saved["workflow"]["topics"][0]
            response = client.get(
                "/financial/runs/latest?session_id=current", headers={"user-id": "bob"}
            )
            assert response.json()["data"]["id"] == "b" * 36
            response = client.get(
                "/financial/runs/latest?session_id=missing",
                headers={"user-id": "alice"},
            )
            assert response.json()["data"] is None
            response = client.get(
                "/financial/runs/latest?session_id=current",
                headers={"user-id": "stranger"},
            )
            assert response.json()["data"] is None
            assert (
                client.get(
                    "/financial/runs/latest", headers={"user-id": "alice"}
                ).status_code
                == 422
            )
        assert service.latest_agent_report("alice", "current")["workflow"]["topics"][0][
            "draftFindings"
        ]
    finally:
        service._executor.shutdown()
        engine.dispose()
