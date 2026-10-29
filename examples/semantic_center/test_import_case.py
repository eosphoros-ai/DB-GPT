"""Verify case import against real management routes in an isolated database."""

import io
import json
from urllib.parse import urlsplit

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from dbgpt.storage.metadata import db
from dbgpt_ext.datasource.rdbms.conn_sqlite import SQLiteConnector
from dbgpt_serve.semantic import api
from dbgpt_serve.semantic.publisher import LoggingSink, SemanticPublisher
from dbgpt_serve.semantic.reader import SemanticReader
from dbgpt_serve.semantic.service import SemanticService
from dbgpt_serve.semantic.sync import SemanticSyncService

from . import import_case
from .build_case import CONNECTION, build_database


def test_import_case_uses_real_routes_and_refuses_duplicate_or_other_space(
    tmp_path, monkeypatch
):
    source = build_database(tmp_path)
    db.init_db(f"sqlite:///{tmp_path / 'meta.db'}")
    db.create_all()
    connector = SQLiteConnector.from_file_path(str(source))
    sync = SemanticSyncService()
    report = sync.sync(CONNECTION, connector)
    service = SemanticService(publisher=SemanticPublisher(LoggingSink()))
    monkeypatch.setattr(api, "_service", service)
    monkeypatch.setattr(api, "_connector", lambda name: connector)
    app = FastAPI()
    app.include_router(api.router, prefix="/api")
    with TestClient(app) as client:

        def local_http(request, timeout):
            path = urlsplit(request.full_url)
            response = client.request(
                request.method,
                path.path + ("?" + path.query if path.query else ""),
                content=request.data,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            return io.BytesIO(response.content)

        monkeypatch.setattr(import_case, "urlopen", local_http)
        output = tmp_path / "import.json"
        import_case.import_case("http://testserver", report.ds_id, output)
        assert json.loads(output.read_text())["status"] == "completed"
        reader = SemanticReader(CONNECTION, service)
        metric = reader.get_metric(metric_name="净实收")["metric"]
        assert metric["version"] == 1  # First live publish, business case v2.
        assert metric["metric_definition"]["freight_included"] is False
        assert len(reader.business_semantics()["items"]) == 11
        assert all(
            e["status"] == "published" for e in reader.business_semantics()["items"]
        )
        assert (
            reader.get_metric(metric_name="净实收_含运费对照")["metric"][
                "metric_definition"
            ]["freight_included"]
            is True
        )
        with pytest.raises(ValueError, match="existing entries"):
            import_case.import_case("http://testserver", report.ds_id, output)
        other = sync.ensure_space("other_db", "other_db", "sqlite")
        with pytest.raises(ValueError, match="dedicated connection"):
            import_case.import_case(
                "http://testserver", other.id, tmp_path / "other.json"
            )
    connector._engine.dispose()
