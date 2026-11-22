import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from dbgpt_app.openapi.api_v1 import python_upload_api
from dbgpt_app.openapi.api_v1.dashboard.uploaded_source import prepare_dashboard_files


@pytest.mark.asyncio
@pytest.mark.parametrize("extension", ["csv", "xlsx"])
async def test_session_file_becomes_a_durable_owned_dashboard_source(
    tmp_path, monkeypatch, extension
):
    temporary = tmp_path / ("temporary-copy." + extension)
    if extension == "csv":
        temporary.write_text("month,amount\n2026-01,10\n2026-02,20\n", encoding="utf-8")
    else:
        from openpyxl import Workbook

        workbook = Workbook()
        workbook.active.append(["month", "amount"])
        workbook.active.append(["2026-01", 10])
        workbook.active.append(["2026-02", 20])
        workbook.save(temporary)
        workbook.close()
    registrations = []

    def register_ready(**values):
        registrations.append(values)
        return SimpleNamespace(
            public_dict=lambda: {
                "dataset_id": values["dataset_id"],
                "database_name": values["database_name"],
                "files": [],
            }
        )

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )
    monkeypatch.setattr(
        python_upload_api, "_register_uploaded_dataset", lambda *args: None
    )
    monkeypatch.setattr(
        python_upload_api,
        "_get_uploaded_dataset_service",
        lambda: SimpleNamespace(register_ready=register_ready),
    )
    result = await prepare_dashboard_files(
        attachment_ctx=SimpleNamespace(
            manifests=[SimpleNamespace(file_id="f1", name="sales." + extension)],
            local_paths={"f1": str(temporary)},
        ),
        legacy_paths=[],
        owner_id="alice",
        conversation_id="dashboard-files",
    )
    temporary.unlink()
    stored = registrations[0]
    assert stored["owner_id"] == "alice"
    assert stored["conversation_id"] == "dashboard-files"
    assert result["database_name"] == stored["database_name"]
    assert Path(stored["files"][0]["stored_path"]).is_file()
    with sqlite3.connect(stored["database_path"]) as database:
        table = stored["files"][0]["tables"][0]["table_name"]
        assert (
            database.execute(f'SELECT SUM(amount) FROM "{table}"').fetchone()[0] == 30
        )


@pytest.mark.asyncio
async def test_unsupported_attachment_is_rejected_before_generation(
    tmp_path, monkeypatch
):
    temporary = tmp_path / "report.pdf"
    temporary.write_bytes(b"not a table")
    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )
    with pytest.raises(ValueError, match="Unsupported"):
        await prepare_dashboard_files(
            attachment_ctx=SimpleNamespace(
                manifests=[SimpleNamespace(file_id="f1", name="report.pdf")],
                local_paths={"f1": str(temporary)},
            ),
            legacy_paths=[],
            owner_id="alice",
            conversation_id="dashboard-files",
        )
