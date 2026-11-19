import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import pytest
from sqlalchemy import create_engine, inspect, text

from dbgpt_serve.financial_analysis.migrate import migrate
from dbgpt_serve.financial_analysis.models import FinancialRunEntity as Run
from dbgpt_serve.financial_analysis.revisions import save_revision
from dbgpt_serve.session_file.api.endpoints import SessionFileApiError

from .conftest import wait_ready
from .test_comparison_service import create


def test_mysql_and_postgres_schema_compile_without_live_database():
    from sqlalchemy.dialects import mysql, postgresql
    from sqlalchemy.schema import CreateTable

    from dbgpt_serve.financial_analysis.models import (
        FinancialReportRevisionEntity,
        FinancialRunDocumentEntity,
    )

    for dialect in [mysql.dialect(), postgresql.dialect()]:
        for model in [Run, FinancialReportRevisionEntity, FinancialRunDocumentEntity]:
            sql = str(CreateTable(model.__table__).compile(dialect=dialect))
            assert "CREATE TABLE" in sql
            if dialect.name == "mysql":
                assert "LONGTEXT" in sql


def test_json_and_html_export_pin_identical_revision_without_moving_current(
    isolated_service, tmp_path
):
    from dbgpt_serve.financial_analysis import workflow

    service, _, _, _ = isolated_service
    run_id = create(service)
    wait_ready(service, run_id)
    report = service.get("alice", "scope", run_id, report=True)
    report = service.update_agent_workflow(
        "alice", "scope", run_id, report["revision"], "start", topic_id="operating"
    )
    shell = tmp_path / "runtime.html"
    shell.write_text(
        '<script type="application/json"><!--FINANCIAL_REPORT_JSON--></script>',
        encoding="utf-8",
    )
    service.export_runtime = shell
    files = [
        service.create_export("alice", "scope", run_id, report["revision"], kind)
        for kind in ["json", "html"]
    ]
    bodies = [
        service.download_export("alice", "scope", run_id, file["id"])[0].decode()
        for file in files
    ]
    embedded = bodies[1].split('application/json">', 1)[1].split("</script>")[0]
    assert (
        json.loads(bodies[0])
        == json.loads(embedded)
        == workflow.public_snapshot(report)
    )
    assert (
        service.get("alice", "scope", run_id, report=True)["revision"]
        == report["revision"]
    )
    assert len(service.list_revisions("alice", "scope", run_id)) == 2


def test_export_languages_have_distinct_immutable_html_and_identical_data(
    isolated_service, tmp_path
):
    from dbgpt_serve.financial_analysis.workflow import public_snapshot

    service, _, _, _ = isolated_service
    run_id = create(service)
    wait_ready(service, run_id)
    report = service.get("alice", "scope", run_id, report=True)
    runtime = tmp_path / "runtime.html"
    runtime.write_text(
        '<html lang="<!--FINANCIAL_REPORT_LANGUAGE-->"><script type="application/json">'
        "<!--FINANCIAL_REPORT_JSON--></script></html>",
        encoding="utf-8",
    )
    service.export_runtime = runtime
    files = [
        service.create_export(
            "alice", "scope", run_id, report["revision"], "html", language=language
        )
        for language in ("zh", "en")
    ]
    assert files[0]["id"] != files[1]["id"]
    for file, language in zip(files, ("zh-CN", "en")):
        body = service.download_export("alice", "scope", run_id, file["id"])[0].decode()
        assert f'<html lang="{language}">' in body
        embedded = body.split('application/json">', 1)[1].split("</script>")[0]
        assert json.loads(embedded) == public_snapshot(report)
    assert (
        service.create_export("alice", "scope", run_id, report["revision"], "html")
        == files[0]
    )
    assert (
        service.create_export(
            "alice", "scope", run_id, report["revision"], "html", language="en"
        )
        == files[1]
    )
    with pytest.raises(SessionFileApiError) as error:
        service.create_export(
            "alice",
            "scope",
            run_id,
            report["revision"],
            "html",
            language='en"><script>',
        )
    assert error.value.err_code == "EXPORT_LANGUAGE_INVALID"


def test_offline_json_cannot_close_data_script(tmp_path):
    from dbgpt_serve.financial_analysis.exports import render_export

    from .test_comparison_analysis import comparison_report

    report = comparison_report()
    report["report"]["title"] = '</script><script>alert("untrusted")</script>'
    shell = tmp_path / "runtime.html"
    shell.write_text(
        '<script type="application/json"><!--FINANCIAL_REPORT_JSON--></script>',
        encoding="utf-8",
    )
    content = render_export(report, "html", shell)
    assert content.count("</script>") == 1
    embedded = content.split('application/json">', 1)[1].split("</script>")[0]
    assert json.loads(embedded)["report"]["title"] == report["report"]["title"]


def test_explicit_sqlite_migration_preserves_legacy_report_and_repeats(tmp_path):
    engine = create_engine("sqlite:///" + (tmp_path / "legacy.db").as_posix())
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE dbgpt_financial_analysis_run "
                "(id VARCHAR(36) PRIMARY KEY, "
                "owner_id VARCHAR(255), session_id VARCHAR(255), "
                "file_id VARCHAR(64) NOT NULL, "
                "status VARCHAR(16), stage VARCHAR(32), created_at VARCHAR(40), "
                "updated_at VARCHAR(40), completed_at VARCHAR(40), "
                "error TEXT, report_json TEXT)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO dbgpt_financial_analysis_run "
                "(id, file_id, report_json) VALUES ('legacy', 'pdf', :saved)"
            ),
            {"saved": '{"schemaVersion":1,"mode":"report","revision":"only-existing"}'},
        )
    assert len(migrate(engine)) == 3
    assert "mode" not in {
        c["name"] for c in inspect(engine).get_columns(Run.__tablename__)
    }
    assert len(migrate(engine, apply=True)) == 3
    assert migrate(engine, apply=True) == []
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT mode, report_json FROM dbgpt_financial_analysis_run")
        ).one()
        assert row[0] == "report" and json.loads(row[1])["revision"] == "only-existing"
    engine.dispose()


def test_revision_content_is_immutable_and_failed_transaction_keeps_pointer(
    isolated_service,
):
    service, _, _, _ = isolated_service
    run_id = create(service)
    wait_ready(service, run_id)
    before = service.get("alice", "scope", run_id, report=True)
    with pytest.raises(SessionFileApiError):
        with service.session() as session:
            row = session.query(Run).filter_by(id=run_id).one()
            changed = deepcopy(before)
            changed["facts"][0]["normalizedValue"] = "999999"
            save_revision(session, row, changed, timestamp="later")
    assert service.get("alice", "scope", run_id, report=True) == before
    with pytest.raises(SessionFileApiError):
        service.get("alice", "scope", run_id, report=True, revision="lost-history")
    from dbgpt_serve.financial_analysis import workflow

    from .fixtures import report_config

    draft = service.update_agent_workflow(
        "alice", "scope", run_id, before["revision"], "start", topic_id="operating"
    )
    service.comparisons.reconfigure(
        "alice", "scope", run_id, draft["revision"], report_config(baseline="b")
    )
    assert service.get(
        "alice", "scope", run_id, report=True, revision=draft["revision"]
    ) == workflow.public_snapshot(draft)


def test_concurrent_configuration_requires_fresh_revision(isolated_service):
    from .fixtures import report_config

    service, _, _, _ = isolated_service
    run_id = create(service)
    wait_ready(service, run_id)
    revision = service.get("alice", "scope", run_id, report=True)["revision"]

    def change():
        try:
            service.comparisons.reconfigure(
                "alice", "scope", run_id, revision, report_config(baseline="b")
            )
            return "saved"
        except SessionFileApiError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(lambda _: change(), range(2))) == [
            "conflict",
            "saved",
        ]
