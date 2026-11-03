"""Generate verification files from actual Olist catalog and composite fixtures."""

import json
import runpy
import shutil
from pathlib import Path

from dbgpt_app.openapi.api_v1.tools.er_diagram import make_generate_er_diagram
from dbgpt_app.openapi.api_v1.tools.sql_query import make_sql_query
from dbgpt.core.interface.report_capture import ArtifactCaptureContext, InMemoryArtifactSink
from dbgpt_ext.datasource.rdbms.conn_sqlite import SQLiteConnector

root = Path(__file__).parent
state = {"database_name": "Olist_Ecommerce"}
state["_report_artifact_sink"] = InMemoryArtifactSink(
    ArtifactCaptureContext(conv_uid="er-verification", run_id="er-olist-verification")
)
connector = SQLiteConnector.from_file_path("pilot/examples/Olist_Ecommerce.db")
query = make_sql_query(state, connector, max_output_chars=None)
catalog_sql = """
SELECT m.name AS table_name, p.name AS column_name, p.type AS data_type,
       p.pk AS primary_key_position, p."notnull" AS not_null
FROM sqlite_master m JOIN pragma_table_info(m.name) p
WHERE m.type = 'table' AND m.name NOT LIKE 'sqlite_%'
ORDER BY m.name, p.cid
"""
fk_sql = """
SELECT m.name AS from_table, f.id, f.seq, f."table" AS to_table,
       f."from" AS from_column, f."to" AS to_column
FROM sqlite_master m JOIN pragma_foreign_key_list(m.name) f
WHERE m.type = 'table' AND m.name NOT LIKE 'sqlite_%'
ORDER BY m.name, f.id, f.seq
"""
columns = json.loads(query(catalog_sql))
fks = json.loads(query(fk_sql))
assert "artifact_id" in columns and "artifact_id" in fks, (columns, fks)
evidence_ids = [columns["artifact_id"], fks["artifact_id"]]
tables = {}
for name, column, dtype, primary, not_null in state["_query_artifacts"][evidence_ids[0]]["rows"]:
    table = tables.setdefault(name, {"id": name, "name": name, "columns": []})
    table["columns"].append({
        "name": column, "type": dtype or "unknown",
        "primary_key": bool(primary), "nullable": not bool(not_null),
    })
relationships = {}
for source, identity, sequence, target, source_column, target_column in state["_query_artifacts"][evidence_ids[1]]["rows"]:
    relation = relationships.setdefault((source, identity), {
        "name": f"fk_{source}_{identity}", "from_table": source, "to_table": target,
        "from_columns": [], "to_columns": [], "kind": "declared", "basis": fk_sql.strip(),
    })
    relation["from_columns"].append(source_column)
    relation["to_columns"].append(target_column)
model = {
    "title": "Olist Ecommerce · 物理 ER",
    "evidence_artifact_ids": evidence_ids,
    "tables": list(tables.values()), "relationships": list(relationships.values()),
}


def save_example(name, graph, tool_state):
    result = json.loads(make_generate_er_diagram(tool_state)(graph))
    assert result["success"], result
    target = root / name
    target.mkdir(exist_ok=True)
    (target / "er-diagram.html").write_text(result["chunks"][0]["content"])
    for chunk in result["chunks"][1:]:
        file = chunk["content"]
        shutil.copy2(file["file_path"], target / file["name"])
    shutil.rmtree(Path(result["chunks"][1]["content"]["file_path"]).parent)


save_example("olist", model, state)
(root / "catalog-evidence.json").write_text(json.dumps({
    "queries": [catalog_sql, fk_sql], "artifacts": state["_query_artifacts"],
}, ensure_ascii=False, indent=2))
fixtures = runpy.run_path("packages/dbgpt-app/src/dbgpt_app/tests/test_er_diagram.py")
fixture_model = fixtures["model"].__wrapped__()
fixture_state = fixtures["state"].__wrapped__()
save_example("composite-declared", fixture_model, fixture_state)
fixture_model["relationships"][0]["kind"] = "inferred"
save_example("composite-inferred", fixture_model, fixture_state)
print(json.dumps({"tables": len(tables), "columns": sum(len(t["columns"]) for t in tables.values()),
                  "declared_relationships": len(relationships)}, ensure_ascii=False))
