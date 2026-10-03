import json
import sys
import types
from types import SimpleNamespace

import pytest

from dbgpt_app.openapi.api_v1.tools.execute_analysis import make_execute_analysis
from dbgpt_app.openapi.api_v1.tools.load_file import make_load_file


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
async def test_execute_analysis_inspects_every_uploaded_file(monkeypatch):
    executions = []

    class FakeCodeServer:
        async def exec(self, code, language):
            executions.append((code, language))
            return SimpleNamespace(
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
                ).encode("utf-8")
            )

    async def fake_get_code_server(system_app):
        return FakeCodeServer()

    fake_code_server_module = types.ModuleType("dbgpt.util.code.server")
    fake_code_server_module.get_code_server = fake_get_code_server
    monkeypatch.setitem(sys.modules, "dbgpt.util.code.server", fake_code_server_module)
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
    code, language = executions[0]
    assert language == "python"
    assert "orders.csv" in code
    assert "customers.csv" in code
    json_chunks = [item for item in payload["chunks"] if item["output_type"] == "json"]
    assert len(json_chunks[0]["content"]["files"]) == 2
    table_chunks = [
        item for item in payload["chunks"] if item["output_type"] == "table"
    ]
    assert table_chunks[0]["content"]["rows"] == [{"order_id": 1, "customer_id": 10}]
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "orders.csv" in serialized  # result metadata remains useful
    assert "file_paths =" not in serialized  # executable server paths are private
