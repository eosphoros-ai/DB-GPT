"""ER exports retain identity and evidence without fabricating constraints."""

import copy
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from dbgpt_app.openapi.api_v1.harness_pi_stream import _embedded_artifact_outputs
from dbgpt_app.openapi.api_v1.tools.er_diagram import (
    er_dbml,
    er_drawio,
    er_html,
    er_svg,
    make_generate_er_diagram,
    validate_er_model,
)


@pytest.fixture
def model():
    return {
        "title": "销售 <ER>",
        "evidence_artifact_ids": ["metadata-1"],
        "tables": [
            {
                "id": "parent",
                "schema": "sales",
                "name": "客户",
                "columns": [
                    {"name": "tenant", "type": "varchar(32)", "primary_key": True},
                    {"name": "id", "type": "int", "primary_key": True},
                ],
            },
            {
                "id": "child",
                "schema": "sales",
                "name": "订单",
                "columns": [
                    {"name": "tenant", "type": "varchar(32)", "nullable": False},
                    {"name": "customer", "type": "int"},
                ],
            },
        ],
        "relationships": [
            {
                "name": "fk_customer",
                "from_table": "child",
                "to_table": "parent",
                "from_columns": ["tenant", "customer"],
                "to_columns": ["tenant", "id"],
                "kind": "declared",
                "basis": "information_schema FK catalog",
            },
        ],
    }


@pytest.fixture
def state():
    return {"_query_artifacts": {"metadata-1": {"truncated": False}}}


def test_composite_keys_and_column_connector_mapping(model, state):
    graph = validate_er_model(model, state)
    dbml = er_dbml(graph)
    assert '("tenant", "id") [pk]' in dbml
    assert (
        '"sales"."订单".("tenant", "customer") > "sales"."客户".("tenant", "id")'
        in dbml
    )
    root = ET.fromstring(er_drawio(graph))
    cells = {cell.get("id"): cell for cell in root.iter("mxCell")}
    edges = [cell for cell in cells.values() if cell.get("edge") == "1"]
    assert len(edges) == 2
    assert [
        (cells[e.get("source")].get("value"), cells[e.get("target")].get("value"))
        for e in edges
    ] == [
        ("tenant : varchar(32)", "PK tenant : varchar(32)"),
        ("customer : int", "PK id : int"),
    ]


def test_inferred_links_do_not_create_dbml_constraints(model, state):
    model["relationships"][0]["kind"] = "inferred"
    graph = validate_er_model(model, state)
    assert not any(line.startswith("Ref ") for line in er_dbml(graph).splitlines())
    assert 'stroke-dasharray="6 4"' in er_svg(graph)
    assert "dashed=1;" in er_drawio(graph)


@pytest.mark.parametrize(
    "mutation",
    ["missing_evidence", "truncated", "endpoint", "mapping", "duplicate", "kind"],
)
def test_rejects_unexportable_models(model, state, mutation):
    if mutation == "missing_evidence":
        model["evidence_artifact_ids"] = ["unknown"]
    elif mutation == "truncated":
        state["_query_artifacts"]["metadata-1"]["truncated"] = True
    elif mutation == "endpoint":
        model["relationships"][0]["to_table"] = "missing"
    elif mutation == "mapping":
        model["relationships"][0]["to_columns"] = ["id"]
    elif mutation == "duplicate":
        duplicate = copy.deepcopy(model["tables"][0])
        duplicate["id"] = "alias"
        model["tables"].append(duplicate)
    else:
        model["relationships"][0]["kind"] = "guess"
    with pytest.raises(ValueError):
        validate_er_model(model, state)


def test_zero_foreign_keys_still_renders_tables_and_escapes_text(model, state):
    model["relationships"] = []
    model["tables"][0]["name"] = '</text><script>alert("x")</script>'
    graph = validate_er_model(model, state)
    svg = er_svg(graph)
    ET.fromstring(svg)
    assert "<script>" not in svg
    html = er_html(graph, svg, {})
    assert "声明关系 0" in html
    assert "&lt;script&gt;" in html
    assert 'data-dbgpt-er="1"' in html


def test_real_exports_promote_through_pi_without_losing_content(model, state):
    result = json.loads(make_generate_er_diagram(state)(model))
    assert result["success"] is True
    chunks = result["chunks"]
    promoted = _embedded_artifact_outputs(json.dumps(result))
    assert promoted[0]["content"]["content"] == chunks[0]["content"]
    assert promoted[1:] == chunks[1:]
    assert chunks[0]["output_type"] == "html"
    paths = [Path(chunk["content"]["file_path"]) for chunk in chunks[1:]]
    try:
        assert {path.suffix for path in paths} == {
            ".drawio",
            ".dbml",
            ".mmd",
            ".svg",
            ".json",
        }
        for chunk, path in zip(chunks[1:], paths):
            assert path.read_text() == chunk["content"]["content"]
        assert json.loads(paths[-1].read_text())["relationships"][0]["to_columns"] == [
            "tenant",
            "id",
        ]
    finally:
        shutil.rmtree(paths[0].parent)
