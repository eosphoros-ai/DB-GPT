"""Read real captured SQL blobs in a child with a conflicting editable checkout."""

import inspect
import json

import pytest

from dbgpt.core.interface.report_capture import (
    ArtifactCaptureContext,
    InMemoryArtifactSink,
    capture_sql_execution,
    read_artifact_result,
)
from dbgpt_app.openapi.api_v1.tools.code_interpreter import make_code_interpreter


@pytest.mark.asyncio
async def test_sql_to_python_uses_current_checkout_and_preserves_lineage(
    tmp_path, monkeypatch
):
    from dbgpt_sandbox.sandbox.execution_layer import runtime_factory

    monkeypatch.setattr(runtime_factory, "SANDBOX_RUNTIME", "local")
    conflicting = tmp_path / "other checkout"
    conflicting.mkdir()
    (conflicting / "dbgpt.py").write_text(
        "raise RuntimeError('Imported a different checkout')", encoding="utf-8"
    )
    monkeypatch.setenv("PYTHONPATH", str(conflicting))
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="sql-child-checkout"))
    sql_id = capture_sql_execution(
        sql="SELECT 3 AS sales UNION ALL SELECT 7 AS sales",
        database="test",
        columns=["sales"],
        rows=[{"sales": 3}, {"sales": 7}],
        duration_ms=1,
        artifact_sink=sink,
    )
    state = {"conv_id": "sql-child-checkout", "_report_artifact_sink": sink}
    execute = inspect.unwrap(make_code_interpreter(state))
    response = json.loads(
        await execute(
            code="frame = sql_result_frame(-1)\n"
            "REPORT_RESULT = {'total': int(frame.sales.sum()), 'rows': len(frame)}\n"
            "print(REPORT_RESULT)"
        )
    )
    artifact = next(
        a for a in sink.snapshot() if a.artifact_id == response["artifact_id"]
    )
    assert artifact.status == "succeeded", artifact.error
    assert read_artifact_result(artifact) == {"total": 10, "rows": 2}
    assert sql_id in artifact.input_artifact_ids
