import json
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text

from dbgpt_serve.financial_analysis.api import make_router
from dbgpt_serve.financial_analysis.migrate import ensure_schema, migrate
from dbgpt_serve.financial_analysis.service import FinancialAnalysisService
from dbgpt_serve.session_file.api.endpoints import (
    SessionFileApiError,
    get_authenticated_owner,
)

from .conftest import wait_ready
from .fixtures import report_config

pytestmark = pytest.mark.parametrize("isolated_service", ["legacy"], indirect=True)


def schema(engine):
    inspector = inspect(engine)
    return {
        table: [column["name"] for column in inspector.get_columns(table)]
        for table in inspector.get_table_names()
    }


@pytest.mark.parametrize("migrate_during_startup", [False, True])
def test_session_file_component_registers_with_legacy_database(
    isolated_service, monkeypatch, migrate_during_startup
):
    from dbgpt.component import SystemApp
    from dbgpt_serve.session_file.api import endpoints
    from dbgpt_serve.session_file.config import ServeConfig
    from dbgpt_serve.session_file.serve import SessionFileServe

    service, _, _, engine = isolated_service
    before = schema(engine)
    for name in ["global_system_app", "_service_instance", "_config_instance"]:
        monkeypatch.setattr(endpoints, name, getattr(endpoints, name))
    system_app = SystemApp(FastAPI())
    component = system_app.register(
        SessionFileServe, registry=service.registry, config=ServeConfig()
    )
    try:
        assert not component.financial_analysis.comparison_schema_ready
        system_app.app.dependency_overrides[get_authenticated_owner] = lambda: "alice"
        with TestClient(system_app.app) as client:
            response = client.get("/api/v1/financial-analysis/runs")
        assert response.status_code == 200
        assert response.json()["data"]["total"] == 0
        assert schema(engine) == before
        if migrate_during_startup:
            migrate(engine, apply=True)
        system_app.after_init()
        assert (
            component.financial_analysis.comparison_schema_ready
            == migrate_during_startup
        )
        if migrate_during_startup:
            component.financial_analysis.extractor = service.extractor
            run_id = str(uuid4())
            component.financial_analysis.comparisons.create(
                "alice",
                "scope",
                ["a", "b"],
                run_id,
                report_config(),
                agent_model="synthetic",
            )
            assert (
                wait_ready(component.financial_analysis, run_id)["status"]
                == "completed"
            )
        else:
            assert schema(engine) == before
    finally:
        component.financial_analysis.close()


def test_legacy_api_single_report_and_comparison_gate_without_ddl(isolated_service):
    service, _, calls, engine = isolated_service
    before = schema(engine)
    assert set(before) == {
        "dbgpt_financial_analysis_run",
        "dbgpt_financial_analysis_export",
    }
    assert not {"mode", "config_json", "request_fingerprint"} & set(
        before["dbgpt_financial_analysis_run"]
    )
    app = FastAPI()
    app.dependency_overrides[get_authenticated_owner] = lambda: "alice"
    app.include_router(make_router(service), prefix="/financial")
    run_id = str(uuid4())
    with TestClient(app) as client:
        response = client.post(
            "/financial/runs",
            json={"session_id": "scope", "file_ids": ["a"], "request_id": run_id},
        )
        assert response.status_code == 202
        assert wait_ready(service, run_id)["status"] == "completed"
        assert client.get("/financial/runs").json()["data"]["total"] == 1
        response = client.post(
            "/financial/runs",
            json={
                "session_id": "scope",
                "mode": "comparison",
                "file_ids": ["a", "b"],
                "comparison": report_config(),
            },
        )
        assert response.status_code == 503
        assert response.json()["err_code"] == "COMPARISON_MIGRATION_REQUIRED"
    for operation in [
        lambda: service.comparisons.resume("alice", "scope", run_id),
        lambda: service.comparisons.reconfigure(
            "alice", "scope", run_id, "revision", report_config()
        ),
        lambda: service.comparisons.retry_topic(
            "alice", "scope", run_id, "revision", "operating"
        ),
        lambda: service.comparisons.members(run_id),
    ]:
        with pytest.raises(SessionFileApiError) as error:
            operation()
        assert error.value.err_code == "COMPARISON_MIGRATION_REQUIRED"
    for owner, scope in [("bob", "scope"), ("alice", "other")]:
        with pytest.raises(SessionFileApiError) as error:
            service.get(owner, scope, run_id, report=True)
        assert error.value.err_code == "RUN_NOT_FOUND"
    assert calls == ["a"] and schema(engine) == before


def test_legacy_restart_preserves_saved_report_and_recovers_interrupted_analysis(
    isolated_service,
):
    service, _, calls, engine = isolated_service
    before = schema(engine)
    completed_id, interrupted_id = str(uuid4()), str(uuid4())
    for run_id in [completed_id, interrupted_id]:
        service.create("alice", "scope", "a", run_id, agent_model="synthetic")
        assert wait_ready(service, run_id)["status"] == "completed"
    saved = service.get("alice", "scope", completed_id, report=True)
    service._update(interrupted_id, stage="analyze")
    service.close()
    restarted = FinancialAnalysisService(service.registry)
    try:
        assert restarted.get("alice", "scope", completed_id, report=True) == saved
        with engine.connect() as connection:
            assert (
                json.loads(
                    connection.execute(
                        text(
                            "SELECT report_json FROM dbgpt_financial_analysis_run "
                            "WHERE id = :id"
                        ),
                        {"id": completed_id},
                    ).scalar_one()
                )
                == saved
            )
        recovered = restarted.get("alice", "scope", interrupted_id, report=True)
        assert recovered["analysis"]["status"] == "failed"
        assert recovered["facts"] and calls == ["a", "a"]
        assert restarted.latest_agent_report("alice", "scope")
        assert schema(engine) == before
    finally:
        restarted.close()


def test_explicit_migration_and_restart_enable_comparison_without_losing_single(
    isolated_service,
):
    service, _, calls, engine = isolated_service
    run_id = str(uuid4())
    service.create("alice", "scope", "a", run_id)
    assert wait_ready(service, run_id)["status"] == "completed"
    saved = service.get("alice", "scope", run_id, report=True)
    service.close()
    assert len(migrate(engine, apply=True)) == 3
    restarted = FinancialAnalysisService(service.registry, extractor=service.extractor)
    try:
        assert restarted.comparison_schema_ready
        assert (
            restarted.get(
                "alice", "scope", run_id, report=True, revision=saved["revision"]
            )
            == saved
        )
        comparison_id = str(uuid4())
        restarted.comparisons.create(
            "alice", "scope", ["a", "b"], comparison_id, report_config()
        )
        assert wait_ready(restarted, comparison_id)["status"] == "completed"
        assert restarted.get("alice", "scope", comparison_id)["mode"] == "comparison"
        assert calls == ["a", "a", "b"]
    finally:
        restarted.close()


def test_partial_migration_stays_explicit(isolated_service):
    service, _, _, engine = isolated_service
    service.close()
    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE dbgpt_financial_analysis_run "
                "ADD COLUMN mode VARCHAR(16) NOT NULL DEFAULT 'report'"
            )
        )
    before = schema(engine)
    with pytest.raises(RuntimeError, match="schema migration required"):
        ensure_schema(engine, allow_legacy=True)
    assert schema(engine) == before
