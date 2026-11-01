import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from dbgpt_app.openapi.api_v1.tools import _execution
from dbgpt_app.openapi.api_v1.tools.execute_analysis import make_execute_analysis
from dbgpt_app.openapi.api_v1.tools.load_file import make_load_file
from dbgpt_sandbox.sandbox.execution_layer.base import ExecutionResult, ExecutionStatus


def test_load_file_returns_complete_upload_group():
    tool = make_load_file(
        {
            "file_path": "orders.csv",
            "file_paths": ["orders.csv", "customers.csv"],
            "dataset_id": "dataset-1",
            "uploaded_files": [
                {"file_id": "orders", "name": "orders.csv"},
                {"file_id": "customers", "name": "customers.csv"},
            ],
        }
    )

    payload = json.loads(tool())

    assert payload["chunks"][0]["content"] == {
        "dataset_id": "dataset-1",
        "files": [
            {"file_id": "orders", "name": "orders.csv"},
            {"file_id": "customers", "name": "customers.csv"},
        ],
    }
    assert "validate keys/cardinality" in payload["chunks"][1]["content"]


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["docker", "podman", "nerdctl"])
async def test_execute_analysis_inspects_every_uploaded_file(
    monkeypatch, tmp_path, kind
):
    executions = []

    class FakeSession:
        async def execute(self, code):
            executions.append(code)
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                output=json.dumps(
                    {
                        "files": [
                            {
                                "file_name": "orders.csv",
                                "sheet_name": None,
                                "shape": [1, 2],
                                "columns": ["order_id", "customer_id"],
                                "dtypes": {
                                    "order_id": "int64",
                                    "customer_id": "int64",
                                },
                                "head": [{"order_id": 1, "customer_id": 10}],
                            },
                            {
                                "file_name": "customers.csv",
                                "sheet_name": None,
                                "shape": [1, 2],
                                "columns": ["customer_id", "city"],
                                "dtypes": {
                                    "customer_id": "int64",
                                    "city": "object",
                                },
                                "head": [{"customer_id": 10, "city": "Hangzhou"}],
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
            )

    runtime = SimpleNamespace(
        runtime_id=kind,
        create_session=AsyncMock(return_value=FakeSession()),
        destroy_session=AsyncMock(),
        docker_client=Mock(),
    )
    monkeypatch.setattr(_execution.RuntimeFactory, "create", lambda: runtime)
    monkeypatch.setattr("dbgpt.configs.model_config.PILOT_PATH", str(tmp_path))
    tool = make_execute_analysis(
        {
            "file_paths": ["orders.csv", "customers.csv"],
            "matched": SimpleNamespace(
                metadata=SimpleNamespace(
                    name="dashboard-builder",
                    description="Dashboard workflow",
                    tags=["dashboard"],
                )
            ),
        }
    )

    payload = json.loads(await tool())

    assert len(executions) == 1
    code = executions[0]
    config = runtime.create_session.call_args.args[1]
    assert config.language == "python"
    assert config.timeout == 60
    assert config.max_memory == 512 * 1024 * 1024
    assert {Path(p).name for p in config.input_files} == {
        "orders.csv",
        "customers.csv",
        "files.json",
    }
    assert "orders.csv" not in code
    assert "customers.csv" not in code
    runtime.destroy_session.assert_awaited_once()
    assert not Path(config.working_dir).exists()
    json_chunks = [item for item in payload["chunks"] if item["output_type"] == "json"]
    assert len(json_chunks[0]["content"]["files"]) == 2
    table_chunks = [
        item for item in payload["chunks"] if item["output_type"] == "table"
    ]
    assert table_chunks[0]["content"]["rows"] == [{"order_id": 1, "customer_id": 10}]
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "orders.csv" in serialized  # result metadata remains useful
    assert "file_paths =" not in serialized  # executable server paths are private
