"""Read-only audit of current templates, live semantics and AWEL scheduling."""

import asyncio
import json
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).with_name("semantic-flow-evidence.json")


async def main():
    from dbgpt.storage.metadata import db
    from dbgpt_app.openapi.api_v1.tools.semantic_tools import make_semantic_tools
    from dbgpt_app.operators.agent_runner import SELECTABLE_TOOLS
    from dbgpt_serve.flow.taskflow import compile_taskflow
    from dbgpt.core.awel import DAG, MapOperator, JoinOperator
    from dbgpt.core.awel.flow.flow_factory import FlowFactory, FlowPanel

    db.init_db(f"sqlite:///file:{ROOT / 'pilot/meta_data/dbgpt.db'}?mode=ro&uri=true")
    evidence = {"templates": [], "semantics": {}, "metric_sql": [], "checks": []}
    def check(name, passed):
        evidence["checks"].append({"name": name, "passed": bool(passed)})
        assert passed, name

    template_dir = ROOT / "packages/dbgpt-serve/src/dbgpt_serve/flow/templates"
    for path in sorted(template_dir.glob("*/*.json")):
        flow = json.loads(path.read_text())["flow"]
        source = flow.get("taskflow_source")
        result = {"language": path.parent.name, "file": path.name, "label": flow["label"]}
        if source:
            compiled = compile_taskflow(source)
            dag = FlowFactory().build(FlowPanel(
                label=flow["label"], name=flow["name"], flow_data=compiled,
                description=flow["description"],
            ))
            check(f"dag:{path.parent.name}/{path.name}", len(dag.trigger_nodes) == len(dag.leaf_nodes) == 1)
            agents = [n for n in source["nodes"] if n["kind"] == "agent"]
            result.update(
                compiled=True,
                dag_built=True,
                awel_nodes=len(compiled.nodes),
                agents=len(agents),
                edges=source["edges"],
                unknown_tools=sorted({
                    tool for n in agents for tool in n["config"].get("tools", [])
                    if tool not in SELECTABLE_TOOLS
                }),
                skills=sorted({s for n in agents for s in n["config"].get("skills", [])}),
                datasources=sorted({s for n in agents for s in n["config"].get("datasources", [])}),
            )
        else:
            FlowPanel(**flow)
            result["validation"] = "legacy FlowPanel schema validated; not executed"
        evidence["templates"].append(result)

    with sqlite3.connect(f"file:{ROOT / 'pilot/meta_data/dbgpt.db'}?mode=ro", uri=True) as conn:
        paths = dict(conn.execute("select db_name,db_path from connect_config"))
    for name in paths:
        tools = {t._tool.name: t for t in make_semantic_tools(name)}
        async def call(tool, **kwargs):
            return json.loads(await tools[tool](**kwargs))
        metadata = await call("semantic_get_metadata", limit=50)
        business = await call("semantic_search_business", limit=50)
        metrics = await call("semantic_search_metrics", limit=50)
        check(f"scope:{name}", all(r["conn_id"] == name for r in (metadata, business, metrics)))
        check(f"published_business:{name}", all(r["status"] == "published" for r in business["items"]))
        item = {"metadata": metadata, "business": business, "metrics": metrics}
        item["unknown_metric"] = await call("semantic_get_metric", metric_name="__audit_absent__")
        check(f"missing_metric:{name}", item["unknown_metric"]["status"] == "not_found")
        item["exact_versions"] = []
        for metric in metrics["items"]:
            resolved = await call("semantic_get_metric", metric_id=metric["id"], version=metric["version"])
            missing = await call("semantic_get_metric", metric_id=metric["id"], version=999999)
            check(f"snapshot:{name}/{metric['id']}", resolved["metric"]["citation"] == metric["citation"])
            check(f"no_version_fallback:{name}/{metric['id']}", missing["status"] == "version_not_found" and missing["metric"] is None)
            item["exact_versions"].append({"resolved": resolved, "missing": missing})
            definition = resolved["metric"].get("metric_definition") or {}
            sql = definition.get("sql") if isinstance(definition, dict) else None
            if sql and name == "Semantic_Commerce_Case":
                # Existing synthetic commerce fixture, never production data.
                with sqlite3.connect(f"file:{paths[name]}?mode=ro", uri=True) as data:
                    data.row_factory = sqlite3.Row
                    rows = [dict(r) for r in data.execute(sql)]
                evidence["metric_sql"].append({"dataset": "existing synthetic fixture", "name": metric["metric_name"], "citation": metric["citation"], "sql": sql, "rows": rows})
                golden = json.loads((ROOT / "output/semantic-center-case-20261028/expected.json").read_text())
                expected_key = {"成功支付额": "successful_payments", "成功退款额": "successful_refunds", "净实收_含运费对照": "net_v1", "净实收": "net_v2", "有效GMV": "gmv"}[metric["metric_name"]]
                check(f"gold_sql:{metric['metric_name']}", rows == golden[expected_key])
        evidence["semantics"][name] = item
    walmart = {t._tool.name: t for t in make_semantic_tools("Walmart_Sales")}
    foreign = json.loads(await walmart["semantic_get_metric"](metric_id=17))
    check("metric_cross_database_denied", foreign["status"] == "not_found" and foreign["metric"] is None)
    empty = {t._tool.name: t for t in make_semantic_tools("__audit_absent_database__")}
    check("missing_space", json.loads(await empty["semantic_get_metadata"]())["status"] == "space_not_found")
    check("no_tools_without_database", make_semantic_tools(None) == [])

    # Scheduling probes replace model calls with timed operations. They prove
    # scheduling only, not agent/model accuracy.
    events = []
    async def root(value):
        return value
    def branch(name):
        async def run(value):
            events.append({"branch": name, "event": "start", "time": time.perf_counter()})
            await asyncio.sleep(0.2)
            events.append({"branch": name, "event": "end", "time": time.perf_counter()})
            return name
        return run
    with DAG("audit_two_branches"):
        start = MapOperator(map_function=root)
        a = MapOperator(map_function=branch("A"))
        b = MapOperator(map_function=branch("B"))
        join = JoinOperator(combine_function=lambda *values: list(values))
        start >> a >> join
        start >> b >> join
    began = time.perf_counter()
    output = await join.call(call_data="probe")
    elapsed = time.perf_counter() - began
    intervals = {name: {r["event"]: r["time"] for r in events if r["branch"] == name} for name in ("A", "B")}
    overlap = max(intervals["A"]["start"], intervals["B"]["start"]) < min(intervals["A"]["end"], intervals["B"]["end"])
    evidence["scheduling"] = {"probe": "real default AWEL runner, two independent 200ms MapOperators", "elapsed_s": elapsed, "overlap": overlap, "output": output, "events": [{**r, "time": r["time"] - began} for r in events]}

    source = {"format": "taskflow/1", "nodes": [
        {"id": "s", "kind": "start"},
        {"id": "a", "kind": "agent", "config": {"goal": "A"}},
        {"id": "b", "kind": "agent", "config": {"goal": "B", "parallel_with_prev": True}},
        {"id": "o", "kind": "output"},
    ], "edges": [["s", "a"], ["s", "b"], ["a", "o"], ["b", "o"]]}
    compiled = compile_taskflow(source)
    agent_ids = [n.id for n in compiled.nodes if "taskflow_agent_operator" in n.id]
    evidence["branch_compile"] = {
        "source": source,
        "agent_ids": agent_ids,
        "added_agent_dependencies": [e.model_dump() for e in compiled.edges if e.source in agent_ids and e.target in agent_ids],
    }
    OUT.write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
    print(json.dumps({
        "templates": evidence["templates"],
        "semantics": {name: {"tables": len(v["metadata"]["items"]), "published_business": len(v["business"]["items"]), "metrics": [(m["metric_name"], m["citation"]) for m in v["metrics"]["items"]]} for name, v in evidence["semantics"].items()},
        "metric_sql": evidence["metric_sql"],
        "scheduling": evidence["scheduling"],
        "branch_compile": evidence["branch_compile"],
        "checks": evidence["checks"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
