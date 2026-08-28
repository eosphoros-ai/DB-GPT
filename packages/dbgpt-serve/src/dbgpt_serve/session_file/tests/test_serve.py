"""Lifecycle and mounting tests for the session file Serve component."""

import os
import tempfile
from pathlib import Path
from typing import List

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool

from dbgpt.component import SystemApp
from dbgpt.core.interface.file import (
    FileStorageClient,
    FileStorageSystem,
    LocalFileStorage,
)
from dbgpt.storage.metadata import Model, db
from dbgpt_serve.core.tests.conftest import create_system_app
from dbgpt_serve.session_file.api import endpoints as endpoints_module
from dbgpt_serve.session_file.config import ServeConfig
from dbgpt_serve.session_file.models.models import SessionFileEntity  # noqa: F401
from dbgpt_serve.session_file.serve import SessionFileServe, default_work_root

PREFIX = "/api/v1/agent/files"
ALICE = {"user-id": "alice"}
CSV_CONTENT = b"colA,colB\n1,2\n"


def _test_config() -> ServeConfig:
    return ServeConfig(
        max_files_per_upload=5,
        max_file_bytes=1024,
        max_upload_bytes=4096,
        max_owner_bytes=8 * 1024,
        upload_concurrency_advice=2,
        upload_chunk_bytes=8,
        upload_spool_bytes=64,
        download_chunk_bytes=8,
        max_file_name_bytes=64,
    )


def _local_storage_client(tmp_path: Path) -> FileStorageClient:
    backend = LocalFileStorage(base_path=str(tmp_path / "blobstore"))
    return FileStorageClient(
        storage_system=FileStorageSystem({backend.storage_type: backend})
    )


@pytest.fixture(autouse=True)
def _isolate_state():
    endpoints_module._reset_endpoints()
    db.init_db(
        "sqlite:///:memory:",
        engine_args={
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        },
    )
    db.create_all()
    yield
    endpoints_module._reset_endpoints()


@pytest.fixture()
def system_app(request) -> SystemApp:
    param = getattr(request, "param", {})
    return create_system_app(param)


@pytest.fixture()
def serve(system_app: SystemApp, tmp_path) -> SessionFileServe:
    instance = SessionFileServe(
        system_app,
        config=_test_config(),
        storage_client=_local_storage_client(tmp_path),
        work_root=tmp_path / "work",
    )
    instance.init_app(system_app)
    return instance


class TestServeMounting:
    def test_router_mounted_under_agent_files_prefix(self, serve, system_app):
        routes = {
            (route.path, method)
            for route in system_app.app.routes
            for method in getattr(route, "methods", set())
        }
        expected = {
            (PREFIX, "POST"),
            (PREFIX, "GET"),
            (PREFIX + "/capabilities", "GET"),
            (PREFIX + "/{file_id}", "GET"),
            (PREFIX + "/{file_id}", "DELETE"),
            (PREFIX + "/{file_id}/preview", "GET"),
            (PREFIX + "/{file_id}/download", "GET"),
        }
        assert expected <= routes

    def test_serve_name_and_registry_binding(self, serve, tmp_path):
        assert serve.name == "dbgpt_serve_session_file"
        assert serve.registry is not None
        assert endpoints_module._service_instance is serve.registry
        # The injected work root is honored verbatim (tests never write to
        # the system temp or the home cache defaults).
        assert serve.registry.work_root == tmp_path / "work"

    def test_upload_smoke_through_mounted_app(self, serve, system_app, tmp_path):
        client = TestClient(system_app.app)
        response = client.post(
            PREFIX,
            data={"session_id": "sess-1"},
            files=[("files", ("report.csv", CSV_CONTENT, "text/csv"))],
            headers=ALICE,
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["success"] is True
        (item,) = payload["data"]
        assert item["name"] == "report.csv"
        assert item["status"] == "ready"
        # Blob really landed in the configured local backend bucket.
        blobs = list((tmp_path / "blobstore" / "session-files").iterdir())
        assert len(blobs) == 1
        assert blobs[0].read_bytes() == CSV_CONTENT

    def test_default_work_root_is_persistent_not_system_temp(self):
        root = default_work_root()
        resolved = os.path.realpath(root)
        system_tmp = os.path.realpath(tempfile.gettempdir())
        assert resolved != system_tmp
        assert not resolved.startswith(system_tmp + os.sep)
        assert "session_file" in str(root)


class TestServeLifecycle:
    def test_on_init_registers_entity_metadata(self, serve):
        serve.on_init()
        assert "dbgpt_session_file" in Model.metadata.tables

    def test_before_start_creates_db_manager(self, serve):
        serve.before_start()
        assert serve._db_manager is not None

    def test_async_before_stop_unbinds_service_and_closes_registry(
        self, serve, system_app, monkeypatch
    ):
        closed: List[bool] = []
        monkeypatch.setattr(serve.registry, "close", lambda: closed.append(True))

        import asyncio

        asyncio.run(serve.async_before_stop())

        assert closed == [True]
        assert endpoints_module._service_instance is None
        client = TestClient(system_app.app)
        response = client.get(PREFIX, params={"session_id": "sess-1"}, headers=ALICE)
        assert response.status_code == 503
        assert response.json()["err_code"] == "SESSION_FILE_SERVICE_UNAVAILABLE"


class TestServeRegistration:
    def test_registered_in_serve_initialization(self):
        import inspect

        from dbgpt_app.initialization import serve_initialization

        source = inspect.getsource(serve_initialization.register_serve_apps)
        assert "SessionFileServe" in source
        assert "/api/v1/agent/files" in source

    def test_dbgpt_server_has_no_manual_session_file_routes(self):
        import inspect

        import dbgpt_app.dbgpt_server as dbgpt_server

        for name, member in inspect.getmembers(dbgpt_server):
            if not callable(member):
                continue
            try:
                source = inspect.getsource(member)
            except (OSError, TypeError):
                continue
            assert "/api/v1/agent/files" not in source
