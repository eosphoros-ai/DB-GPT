"""The author chooses captured objects; only the compiler constructs selectors."""

import json
import re

import pytest

from dbgpt.core.interface.report_capture import (
    ArtifactCaptureContext,
    InMemoryArtifactSink,
    capture_python_execution,
    select_artifact_result,
)
from dbgpt_app.openapi.api_v1.tools.html_interpreter import make_html_interpreter
from dbgpt_app.openapi.api_v1.tools.report_objects import (
    ReportObjects,
    compile_report_objects,
    make_report_object_tools,
    report_author_contract,
)


def capture(sink, result):
    return capture_python_execution(
        code="result",
        duration_ms=1,
        status="succeeded",
        exit_code=0,
        stdout="",
        stderr="",
        result_inline=result,
        artifact_sink=sink,
    )


def object_id(registry, kind, label):
    return next(
        key
        for key, item in registry.objects.items()
        if item["kind"] == kind and item["label"] == label
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("language", ["zh", "en"])
async def test_named_template_completes_with_numbered_advice_in_one_submission(
    monkeypatch, tmp_path, language
):
    from dbgpt_app.openapi.api_v1.tools import report_repair
    from dbgpt_app.openapi.api_v1.tools.html_interpreter import report_template_contract

    monkeypatch.setattr("dbgpt.configs.model_config.PILOT_PATH", str(tmp_path))
    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    template = (
        "<html><body><!-- dbgpt-required: SUMMARY, ADVICE -->"
        '<div class="prose">{{SUMMARY}}</div><h2>Recommendations</h2>'
        '<div class="prose">{{ADVICE}}</div></body></html>'
    )
    (tmp_path / "report.html").write_text(template, encoding="utf-8")
    sink = InMemoryArtifactSink(
        ArtifactCaptureContext(conv_uid="one-submission-advice")
    )
    capture(sink, {"total": 100})
    token = object_id(ReportObjects(sink.snapshot()), "value", "total")
    state = {
        "conv_id": sink.context.conv_uid,
        "_report_artifact_sink": sink,
        "_report_required_recommendation_count": 3,
    }
    _, compose, _ = make_report_object_tools(
        state,
        make_html_interpreter(state, str(tmp_path)),
        "report.html",
        report_template_contract(template),
    )
    advice = (
        [
            "建议一：建立成本复核机制。",
            "建议二：跟踪逾期回款。",
            "建议三：复核融资期限。",
        ]
        if language == "zh"
        else [
            "Recommendation A: Review operating costs.",
            "Recommendation B: Track overdue receivables.",
            "Recommendation C: Review debt maturities.",
        ]
    )
    result = json.loads(
        await compose(
            data={
                "SUMMARY": ["Total: ", {"object_id": token}],
                "ADVICE": [[a] for a in advice],
            }
        )
    )
    assert not state.get("_report_html_error"), result
    assert len([c for c in result["chunks"] if c["output_type"] == "html"]) == 1
    html = state["_report_presentation"]["content"]
    assert all(a in html for a in advice)
    assert ">100</span>" in html


@pytest.mark.parametrize("depth", [40, 700, 1800])
def test_catalogue_isolates_deep_json_strings(depth):
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="deep-json"))
    capture(sink, {"total": 100, "data": {"payload": "[" * depth + "0" + "]" * depth}})
    registry = ReportObjects(sink.snapshot())
    assert object_id(registry, "value", "total")
    manifest = registry.manifest()
    assert manifest["truncated"]
    assert "nesting limits" in manifest["instruction"]
    assert not any(
        item["label"].startswith("data.payload") for item in manifest["objects"]
    )


@pytest.mark.parametrize("serialized", [False, True])
@pytest.mark.parametrize("depth", [40, 700, 1800])
def test_prose_depth_has_a_controlled_error(depth, serialized):
    value = "A qualitative observation."
    if serialized:
        value = "[" * depth + json.dumps(value) + "]" * depth
    else:
        for _ in range(depth):
            value = [value]
    with pytest.raises(ValueError, match="REPORT_OBJECT_DEPTH_EXCEEDED"):
        compile_report_objects(
            {"SUMMARY": value},
            ReportObjects([]),
            spec_mode=False,
            fields=["SUMMARY"],
        )


def test_deep_report_json_has_a_controlled_error():
    data = '{"SUMMARY":' + "[" * 1800 + '"Observation"' + "]" * 1800 + "}"
    with pytest.raises(ValueError, match="REPORT_OBJECT_DEPTH_EXCEEDED"):
        compile_report_objects(
            data, ReportObjects([]), spec_mode=False, fields=["SUMMARY"]
        )


@pytest.mark.asyncio
async def test_deep_prose_is_rejected_at_report_tool_boundary():
    async def renderer(**kwargs):
        raise AssertionError("Invalid prose must not reach the renderer")

    _, compose, stage = make_report_object_tools(
        {},
        renderer,
        "report.html",
        {"mode": "placeholders", "fields": ["SUMMARY"]},
    )
    value = "[" * 1800 + '"Observation"' + "]" * 1800
    for response in [stage("SUMMARY", value), await compose({"SUMMARY": value})]:
        result = json.loads(response)
        assert result["status"] == "invalid_selection"
        assert "REPORT_OBJECT_DEPTH_EXCEEDED" in result["error"]


def test_json_depth_ignores_brackets_and_escaped_quotes_in_normal_text():
    text = 'The label "' + "[" * 80 + ']" contains a backslash \\ and ordinary text.'
    result = compile_report_objects(
        json.dumps({"SUMMARY": json.dumps([[text]])}),
        ReportObjects([]),
        spec_mode=False,
        fields=["SUMMARY"],
    )
    assert result == {"SUMMARY": [[text]]}


@pytest.mark.asyncio
async def test_generate_report_deep_field_does_not_block_agent_handoff(
    tmp_path, monkeypatch
):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from dbgpt_app.openapi.api_v1.subagent import report_agent

    (tmp_path / "report.html").write_text("<html>{{SUMMARY}}</html>", encoding="utf8")
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="deep-handoff"))
    capture(sink, {"total": 100, "data": {"payload": "[" * 1800 + "0" + "]" * 1800}})
    generate = AsyncMock(
        return_value=SimpleNamespace(success=True, content="Draft", context={})
    )
    build = AsyncMock(return_value=SimpleNamespace(generate_reply=generate))
    monkeypatch.setattr(report_agent, "build_report_agent", build)
    monkeypatch.setattr(
        report_agent, "select_report_template", lambda *_: "report.html"
    )
    response = json.loads(
        await report_agent.make_generate_report_tool(
            react_state={"conv_id": "deep-handoff", "_report_artifact_sink": sink},
            skills_dir=str(tmp_path),
            llm_client=object(),
        )("Build the report")
    )
    assert build.await_count == 1
    assert response["status"] == "partial"
    assert "total" in generate.call_args.kwargs["received_message"].content


def test_author_contract_excludes_engine_owned_and_optional_data_fields():
    contract = {
        "mode": "placeholders",
        "fields": [
            "SUMMARY",
            "REPORT_TITLE",
            "REVENUE",
            "INDUSTRY_AVG",
            "CHART_REVENUE",
            "ARTIFACT_ID_REVENUE",
        ],
        "prose_fields": ["SUMMARY"],
        "verified_fields": ["REVENUE"],
    }
    assert report_author_contract(contract, {})["fields"] == ["SUMMARY"]


@pytest.mark.asyncio
async def test_self_contained_statistics_cannot_be_relabelled_in_prose(
    tmp_path, monkeypatch
):
    from dbgpt_app.openapi.api_v1.tools import report_repair

    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="typed-statistics"))
    capture(sink, {"min_sales": 209986, "missing_cells": 0, "CHART_DATA_JSON": "{}"})
    state = {"conv_id": "typed-statistics", "_report_artifact_sink": sink}
    contract = report_author_contract(
        {
            "mode": "placeholders",
            "fields": ["SUMMARY", "CHART_DATA_JSON"],
            "prose_fields": ["SUMMARY"],
        },
        {"CHART_DATA_JSON": {}},
    )
    rendered = []

    async def renderer(**arguments):
        rendered.append(arguments)
        return json.dumps({"status": "completed"})

    _, compose, stage = make_report_object_tools(
        state, renderer, "report.html", contract
    )
    token = object_id(ReportObjects(sink.snapshot()), "value", "min_sales")
    invalid = json.loads(
        stage("SUMMARY", json.dumps(["缺失单元格为", {"object_id": token}]))
    )
    assert invalid["status"] == "invalid_selection"
    assert "INTERPRETATION_ONLY" in invalid["error"]
    assert not rendered
    assert (
        json.loads(stage("SUMMARY", "数据完整，门店间销售表现存在差异。"))["status"]
        == "staged"
    )
    assert json.loads(await compose())["status"] == "completed"
    assert "object_id" not in json.dumps(rendered)


def test_objects_resolve_nested_json_and_survive_sink_restore():
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="objects"))
    capture(
        sink,
        {
            "payload": json.dumps(
                {
                    "total": 100,
                    "rows": [
                        {"region": "华东", "sales": 100},
                        {"region": "华南", "sales": 200},
                    ],
                }
            )
        },
    )
    registry = ReportObjects(sink.snapshot())
    token = object_id(registry, "value", "payload.total")
    node = registry.reference(token)
    assert select_artifact_result(sink.snapshot()[0], node) == 100
    restored = InMemoryArtifactSink(sink.context)
    for artifact in sink.snapshot():
        restored.restore_artifact(artifact)
    assert ReportObjects(restored.snapshot()).reference(token) == node
    table = registry.table(object_id(registry, "table", "payload.rows"))
    assert table["columns"] == ["region", "sales"]


@pytest.mark.parametrize(
    "data",
    [
        {"kpis": [{"label": "营收", "object_id": "invented"}]},
        {"sections": [{"heading": "销售", "intro": [["收入 999"]]}]},
        {
            "sections": [
                {
                    "heading": "销售",
                    "intro": [[{"artifact_id": "invented", "field": "sales"}]],
                }
            ]
        },
        {
            "sections": [
                {"heading": "销售", "chart": {"object_id": "invented", "option": {}}}
            ]
        },
        {"sections": [{"heading": "销售", "intro": ["<strong>999</strong>"]}]},
    ],
)
def test_authored_numbers_selectors_and_options_are_rejected(data):
    with pytest.raises(ValueError, match="REPORT_OBJECT"):
        compile_report_objects(data, ReportObjects([]), spec_mode=True, fields=[])


def test_summary_handles_remain_available_after_large_table_and_new_artifact():
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="bounded-objects"))
    capture(sink, {"rows": [{"sales": i} for i in range(2000)], "total": 1999000})
    registry = ReportObjects(sink.snapshot())
    token = object_id(registry, "value", "total")
    assert len(registry.objects) <= 512
    capture(sink, {"other": 123})
    restored = ReportObjects(sink.snapshot())
    assert restored.reference(token) == registry.reference(token)
    with pytest.raises(ValueError, match="value"):
        restored.reference(object_id(restored, "table", "rows"))


@pytest.mark.asyncio
@pytest.mark.parametrize("same_source", [False, True])
async def test_table_and_chart_preserve_independent_sources_and_windows(
    tmp_path, monkeypatch, same_source
):
    import re
    from pathlib import Path

    from dbgpt_app.openapi.api_v1.tools import report_repair

    monkeypatch.setattr("dbgpt.configs.model_config.PILOT_PATH", str(tmp_path))
    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    repository = next(
        p for p in Path(__file__).resolve().parents if (p / "skills").is_dir()
    )
    sink = InMemoryArtifactSink(
        ArtifactCaptureContext(conv_uid="independent-projections")
    )
    table_id = capture(
        sink,
        {
            "rows": [
                {"region": "EAST_ONLY", "sales": 100},
                {"region": "WEST_ONLY", "sales": 200},
                {"region": "NORTH_ONLY", "sales": 300},
            ]
        },
    )
    chart_id = (
        table_id
        if same_source
        else capture(
            sink,
            {
                "rows": [
                    {"month": "JAN_ONLY", "profit": 20},
                    {"month": "FEB_ONLY", "profit": 30},
                ]
            },
        )
    )
    registry = ReportObjects(sink.snapshot())
    tokens = {
        item["artifact_id"]: token
        for token, item in registry.objects.items()
        if item["kind"] == "table"
    }
    data = {
        "sections": [
            {
                "heading": "Captured analysis",
                "table": {"object_id": tokens[table_id], "limit": 3},
                "chart": {"object_id": tokens[chart_id], "limit": 2},
            }
        ]
    }
    compiled = compile_report_objects(data, registry, spec_mode=True, fields=[])[
        "REPORT_SPEC"
    ]["sections"][0]
    assert compiled["table"]["artifact_id"] == table_id
    assert compiled["table"]["limit"] == 3
    assert compiled["chart"]["source_table"]["artifact_id"] == chart_id
    assert compiled["chart"]["source_table"]["limit"] == 2
    state = {"conv_id": sink.context.conv_uid, "_report_artifact_sink": sink}
    _, compose, *_ = make_report_object_tools(
        state,
        make_html_interpreter(state, str(repository / "skills")),
        "business-report/templates/business_report.html",
        {"mode": "spec", "fields": []},
    )
    result = json.loads(await compose(data=data))
    assert result["status"] == "completed"
    assert not state.get("_report_warnings")
    tables = re.findall(
        r"<table\b.*?</table>", state["_report_presentation"]["content"], re.S
    )
    selected = next(table for table in tables if "NORTH_ONLY" in table)
    assert len(re.findall(r"<tr\b", selected)) == 4  # header plus all three rows
    charts = [a for a in sink.snapshot() if a.type == "chart"]
    assert charts[0].spec["source_artifact_id"] == chart_id
    assert charts[0].spec["projection"]["limit"] == 2
    assert len(charts[0].spec["option"]["series"][0]["data"]) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("targeted", [True, False])
async def test_full_catalogue_filters_and_renders_new_result_after_restore(
    tmp_path, monkeypatch, targeted
):
    from pathlib import Path

    from dbgpt_app.openapi.api_v1.tools import report_repair
    from dbgpt_app.openapi.api_v1.tools.report_objects import MAX_OBJECTS

    monkeypatch.setattr("dbgpt.configs.model_config.PILOT_PATH", str(tmp_path))
    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    repository = next(
        p for p in Path(__file__).resolve().parents if (p / "skills").is_dir()
    )
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="full-catalogue"))
    for i in range(16):
        capture(sink, {f"historical_{i}_{j}": j for j in range(512)})
    latest = capture(sink, {"net_profit": 777})
    state = {"conv_id": sink.context.conv_uid, "_report_artifact_sink": sink}
    listing, compose, *_ = make_report_object_tools(
        state,
        make_html_interpreter(state, str(repository / "skills")),
        "business-report/templates/business_report.html",
        {"mode": "spec", "fields": []},
    )
    assert json.loads(listing(limit=100))["truncated"]
    result = json.loads(
        listing(
            artifact_ids=[latest] if targeted else None,
            query="net_profit",
            kind="value",
        )
    )
    assert result["total"] == 1 and not result["truncated"]
    token = result["objects"][0]["object_id"]
    rendered = json.loads(
        await compose(
            data={"kpis": [{"label": "Net profit", "object_id": token}], "sections": []}
        )
    )
    assert rendered["status"] == "completed"
    assert ">777</span>" in state["_report_presentation"]["content"]
    restored = report_repair.restore_report_checkpoint(
        sink.context.conv_uid, {}, include_completed=True
    )
    registry = ReportObjects(restored.snapshot())
    evicted_token = next(iter(registry.objects))
    ref = registry.reference(token)
    assert ref["artifact_id"] == latest
    assert select_artifact_result(registry.artifacts[latest], ref) == 777
    registry.reference(evicted_token)
    assert len(registry.objects) <= MAX_OBJECTS


@pytest.mark.parametrize("field_count", [512, 700])
def test_query_and_handle_resolution_do_not_share_unfiltered_source_limit(
    tmp_path, monkeypatch, field_count
):
    monkeypatch.setattr("dbgpt.configs.model_config.PILOT_PATH", str(tmp_path))
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="wide-result"))
    source = capture(
        sink, {**{f"padding_{i}": i for i in range(field_count)}, "net_profit": 777}
    )
    listing, *_ = make_report_object_tools(
        {"_report_artifact_sink": sink}, None, "unused", {"mode": "spec", "fields": []}
    )
    unfiltered = json.loads(listing(artifact_ids=[source]))
    assert unfiltered["truncated"] and unfiltered["total_is_lower_bound"]
    result = json.loads(
        listing(artifact_ids=[source], kind="value", query="net_profit")
    )
    assert result["total"] == 1 and not result["truncated"]
    registry = ReportObjects(sink.snapshot())
    ref = registry.reference(result["objects"][0]["object_id"])
    assert select_artifact_result(registry.artifacts[source], ref) == 777


@pytest.mark.asyncio
@pytest.mark.parametrize("rows", [[], [["EAST", 100]]])
async def test_zero_row_table_with_headers_can_be_selected_and_rendered(
    tmp_path, monkeypatch, rows
):
    from pathlib import Path

    from dbgpt_app.openapi.api_v1.tools import report_repair

    monkeypatch.setattr("dbgpt.configs.model_config.PILOT_PATH", str(tmp_path))
    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    repository = next(
        p for p in Path(__file__).resolve().parents if (p / "skills").is_dir()
    )
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="zero-row-table"))
    source = capture(
        sink, {"columns": ["region", "sales"], "rows": rows, "total": len(rows)}
    )
    registry = ReportObjects(sink.snapshot())
    state = {"conv_id": sink.context.conv_uid, "_report_artifact_sink": sink}
    listing, compose, *_ = make_report_object_tools(
        state,
        make_html_interpreter(state, str(repository / "skills")),
        "business-report/templates/business_report.html",
        {"mode": "spec", "fields": []},
    )
    tables = json.loads(listing(artifact_ids=[source], kind="table"))["objects"]
    assert len(tables) == 1 and tables[0]["columns"] == ["region", "sales"]
    result = json.loads(
        await compose(
            data={
                "kpis": [
                    {
                        "label": "Matching records",
                        "object_id": object_id(registry, "value", "total"),
                    }
                ],
                "sections": [
                    {
                        "heading": "Matching records",
                        "table": {"object_id": tables[0]["object_id"]},
                    }
                ],
            }
        )
    )
    assert result["status"] == "completed"
    assert not state.get("_report_warnings")


def test_preflight_reports_all_literal_locations_in_one_response():
    with pytest.raises(ValueError) as error:
        compile_report_objects(
            {"sections": [{"heading": "销售", "intro": [["收入 999"], ["销量 888"]]}]},
            ReportObjects([]),
            spec_mode=True,
            fields=[],
        )
    assert "sections[0].intro[0][0]" in str(error.value)
    assert "sections[0].intro[1][0]" in str(error.value)
    assert "999" in str(error.value) and "888" in str(error.value)


@pytest.mark.asyncio
async def test_staged_fields_survive_restore_and_invalid_update(monkeypatch, tmp_path):
    from dbgpt_app.openapi.api_v1.tools import report_repair

    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="staged-fields"))
    capture(sink, {"total": 100})
    state = {"conv_id": "staged-fields", "_report_artifact_sink": sink}
    rendered = []

    async def renderer(**arguments):
        rendered.append(arguments)
        return json.dumps({"status": "completed"})

    contract = {
        "mode": "placeholders",
        "fields": ["SUMMARY", "INSIGHTS", "OPTIONAL"],
        "prose_fields": ["SUMMARY", "INSIGHTS"],
    }
    _, compose, stage = make_report_object_tools(
        state, renderer, "report.html", contract
    )
    token = object_id(ReportObjects(sink.snapshot()), "value", "total")
    assert (
        json.loads(stage("SUMMARY", ["收入", {"object_id": token}]))["status"]
        == "staged"
    )
    assert json.loads(stage("SUMMARY", "收入 999"))["status"] == "invalid_selection"
    assert json.loads(await compose())["status"] == "invalid_selection"
    assert not rendered
    restored = {"conv_id": "staged-fields", "_report_artifact_sink": sink}
    assert report_repair.restore_report_checkpoint("staged-fields", restored)
    _, compose, stage = make_report_object_tools(
        restored, renderer, "report.html", contract
    )
    stage("INSIGHTS", "结合实际业务进一步验证影响因素。")
    assert json.loads(await compose())["status"] == "completed"
    assert (
        rendered[0]["data"]["SUMMARY"][1]["artifact_id"]
        == sink.snapshot()[0].artifact_id
    )
    assert rendered[0]["data"]["INSIGHTS"]


@pytest.mark.asyncio
async def test_parallel_field_updates_checkpoint_all_fields(monkeypatch, tmp_path):
    import asyncio

    from dbgpt_app.openapi.api_v1.tools import report_repair

    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    state = {"conv_id": "parallel-fields"}
    fields = [f"FIELD_{i}" for i in range(12)]
    _, _, stage = make_report_object_tools(
        state,
        None,
        "report.html",
        {"mode": "placeholders", "fields": fields},
    )
    results = await asyncio.gather(
        *[asyncio.to_thread(stage, field, "分析结论") for field in fields]
    )
    assert all(json.loads(result)["status"] == "staged" for result in results)
    restored = {}
    report_repair.restore_report_checkpoint("parallel-fields", restored)
    assert set(restored["_report_object_fields"]) == set(fields)


@pytest.mark.asyncio
async def test_progressing_draft_continues_without_repeating_analysis(
    monkeypatch, tmp_path
):
    from types import SimpleNamespace

    from dbgpt.core.interface.report_capture import bind_artifact_sink
    from dbgpt_app.openapi.api_v1.subagent import report_agent
    from dbgpt_app.openapi.api_v1.tools import report_repair
    from dbgpt_app.openapi.api_v1.tools.html_interpreter import report_template_contract

    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    template = (
        '<html><body><div class="prose">{{SUMMARY}}</div>'
        '<div class="prose">{{INSIGHTS}}</div></body></html>'
    )
    (tmp_path / "report.html").write_text(template, encoding="utf-8")
    monkeypatch.setattr(
        report_agent, "select_report_template", lambda *_: "report.html"
    )
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="progressing-draft"))
    capture(sink, {"total": 100})
    state = {"conv_id": "progressing-draft", "_report_artifact_sink": sink}
    contract = report_template_contract(template)
    calls = []

    async def build(**kwargs):
        state["_report_template_contract"] = contract
        _, compose, stage = make_report_object_tools(
            state, make_html_interpreter(state, str(tmp_path)), "report.html", contract
        )

        async def generate_reply(**kwargs):
            calls.append(True)
            if len(calls) == 1:
                stage(
                    "SUMMARY",
                    [
                        "经营分析合计",
                        {
                            "object_id": object_id(
                                ReportObjects(sink.snapshot()), "value", "total"
                            )
                        },
                    ],
                )
                raise RuntimeError("AGENT_STEP_LIMIT: reached 20 steps")
            stage("INSIGHTS", "结合业务背景评估影响因素。")
            rendered = json.loads(await compose())
            assert rendered.get("status") == "completed", rendered
            return SimpleNamespace(success=True, content="完成", context={})

        return SimpleNamespace(generate_reply=generate_reply)

    monkeypatch.setattr(report_agent, "build_report_agent", build)
    generate = report_agent.make_generate_report_tool(
        react_state=state, skills_dir=str(tmp_path), llm_client=object()
    )
    with bind_artifact_sink(sink):
        first = json.loads(await generate(instructions="生成报告"))
        assert first["status"] == "draft_pending" and first["retryable"]
        assert first["remaining_fields"] == ["INSIGHTS"]
        second = json.loads(await generate(instructions="继续完成报告"))
    assert second["status"] == "completed", {
        key: value for key, value in second.items() if key != "chunks"
    }
    assert len(calls) == 2
    assert len([a for a in sink.snapshot() if a.type == "python"]) == 1


@pytest.mark.parametrize(
    "rounds,staged", [(2, {"SUMMARY": "摘要"}), (0, {"OPTIONAL": "标题"})]
)
def test_draft_without_required_progress_or_budget_is_terminal(
    monkeypatch, tmp_path, rounds, staged
):
    from dbgpt_app.openapi.api_v1.subagent import report_agent
    from dbgpt_app.openapi.api_v1.tools import report_repair

    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    result = json.loads(
        report_agent._report_agent_failure(
            {
                "conv_id": "stopped-draft",
                "_report_object_fields": staged,
                "_report_template_contract": {"prose_fields": ["SUMMARY", "INSIGHTS"]},
                "_report_draft_continuations": rounds,
            },
            "AGENT_STEP_LIMIT",
        )
    )
    assert result["status"] == "failed" and not result["retryable"]


@pytest.mark.asyncio
@pytest.mark.parametrize("transport", [dict, json.dumps])
async def test_compose_named_template_reads_value_and_rejects_before_renderer(
    tmp_path, transport
):
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="compose-named"))
    capture(sink, {"revenue": 100})
    state = {"conv_id": "compose-named", "_report_artifact_sink": sink}
    path = tmp_path / "report.html"
    path.write_text(
        "<html><body><h1>{{REPORT_TITLE}}</h1><p>{{SUMMARY}}</p></body></html>",
        encoding="utf-8",
    )
    renderer = make_html_interpreter(state, str(tmp_path))
    listing, compose, stage = make_report_object_tools(
        state,
        renderer,
        "report.html",
        report_author_contract(
            {
                "mode": "placeholders",
                "fields": ["SUMMARY", "REPORT_TITLE"],
                "prose_fields": ["SUMMARY"],
            },
            {},
        ),
    )
    manifest = json.loads(listing())
    token = manifest["objects"][0]["object_id"]
    assert "selector" not in manifest["objects"][0]
    invalid = json.loads(await compose(data={"SUMMARY": "收入 999"}))
    assert invalid["status"] == "invalid_selection"
    assert "_report_html_attempted" not in state
    result = json.loads(
        await compose(
            data=transport(
                {
                    "SUMMARY": json.dumps(["收入", {"object_id": token}])
                    if transport is json.dumps
                    else ["收入", {"object_id": token}]
                }
            ),
            title="经营分析",
        )
    )
    assert result["status"] == "completed"
    assert ">100</span>" in state["_report_presentation"]["content"]
    # Random artifact IDs may contain 999; inspect the displayed text only.
    assert "999" not in re.sub(r"<[^>]*>", "", state["_report_presentation"]["content"])
    assert "<h1>经营分析</h1>" in state["_report_presentation"]["content"]


@pytest.mark.asyncio
async def test_compiled_table_and_chart_use_captured_columns(tmp_path):
    from pathlib import Path
    from unittest.mock import patch

    from dbgpt_app.openapi.api_v1.tools import report_repair

    repository = next(
        p for p in Path(__file__).resolve().parents if (p / "skills").is_dir()
    )
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="compose-spec"))
    capture(
        sink,
        {
            "rows": [
                {"region": "华东", "sales": 100},
                {"region": "华南", "sales": 200},
            ]
        },
    )
    state = {"conv_id": "compose-spec", "_report_artifact_sink": sink}
    renderer = make_html_interpreter(state, str(repository / "skills"))
    _, compose, *_ = make_report_object_tools(
        state,
        renderer,
        "business-report/templates/business_report.html",
        {"mode": "spec", "fields": []},
    )
    token = object_id(ReportObjects(sink.snapshot()), "table", "rows")
    with patch.object(report_repair, "PILOT_PATH", str(tmp_path)):
        result = json.loads(
            await compose(
                data={
                    "title": "销售报告",
                    "scope": [
                        "销售来源",
                        {
                            "object_id": object_id(
                                ReportObjects(sink.snapshot()), "value", "rows.0.sales"
                            )
                        },
                    ],
                    "sections": [
                        {"heading": "地区表现", "chart": {"object_id": token}}
                    ],
                }
            )
        )
    assert result["status"] == "completed"
    assert "华东" in state["_report_presentation"]["content"]
    assert any(a.type == "chart" for a in sink.snapshot())


def test_compose_schema_exposes_objects_and_hides_selector_contract():
    from jsonschema import ValidationError, validate

    from dbgpt_app.openapi.api_v1.tools.report_objects import report_object_schema

    schema = report_object_schema({"mode": "spec", "fields": []})
    validate(
        {
            "sections": [
                {"heading": "销售", "intro": [[{"object_id": "value-" + "a" * 24}]]}
            ]
        },
        schema,
    )
    with pytest.raises(ValidationError):
        validate(
            {
                "sections": [
                    {
                        "heading": "销售",
                        "intro": [
                            [{"artifact_id": "source", "path": ["rows", 0, "sales"]}]
                        ],
                    }
                ]
            },
            schema,
        )
    assert "artifact_id" not in json.dumps(schema)
    assert '"option"' not in json.dumps(schema)


@pytest.mark.asyncio
async def test_csv_qualitative_prose_can_bind_selected_knowledge(
    tmp_path, monkeypatch, capsys
):
    import importlib.util
    from pathlib import Path
    from types import SimpleNamespace

    import jsonschema

    from dbgpt.core.interface.report_capture import (
        bind_artifact_sink,
        capture_reference_artifact,
    )
    from dbgpt_app.openapi.api_v1.tools import report_repair
    from dbgpt_app.openapi.api_v1.tools._helpers import _extract_auto_data_markers
    from dbgpt_app.openapi.api_v1.tools.html_interpreter import report_template_contract
    from dbgpt_app.openapi.api_v1.tools.report_objects import report_object_schema
    from dbgpt_serve.rag.tools import kb_file_tools

    chunk = SimpleNamespace(
        id=1, meta_info={"chunk_id": "slice"}, content="销售口径按区域复核。"
    )
    monkeypatch.setattr(
        kb_file_tools,
        "_get_all_file_paths",
        lambda _: [{"doc_id": 1, "file_path": "policy.txt", "vector_ids": ["slice"]}],
    )
    monkeypatch.setattr(
        kb_file_tools,
        "_get_chunk_dao",
        lambda: (
            SimpleNamespace(get_document_chunks=lambda *a, **k: [chunk]),
            SimpleNamespace,
        ),
    )
    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    root = next(p for p in Path(__file__).resolve().parents if (p / "skills").is_dir())
    script = root / "skills/csv-data-analysis/scripts/csv_analyzer.py"
    module_spec = importlib.util.spec_from_file_location(
        "csv_knowledge_regression", script
    )
    analyzer = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(analyzer)
    csv = tmp_path / "sales.csv"
    csv.write_text("region,sales\nEast,100\nWest,200\nEast,150\n", encoding="utf-8")
    analyzer.analyze_csv(str(csv))
    output = json.loads(capsys.readouterr().out)
    _, fields = _extract_auto_data_markers(output["chunks"][0]["content"])
    assert "CHART_DATA_JSON" in fields
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="csv-knowledge"))
    capture(sink, fields)
    with bind_artifact_sink(sink):
        reference = capture_reference_artifact(
            reference_type="knowledge",
            source_id="slice",
            action="knowledge_retrieve",
            duration_ms=1,
            source_name="Sales policy",
            locator={"knowledge_id": "selected", "document_id": 1, "chunk_id": "slice"},
            excerpt="销售口径按区域复核。",
        )
    state = {
        "conv_id": "csv-knowledge",
        "_report_artifact_sink": sink,
        "_report_knowledge_requested": True,
        "_report_knowledge_space": "selected",
        "_report_require_knowledge_bindings": True,
    }
    template_path = "csv-data-analysis/templates/report_template.html"
    template = (root / "skills" / template_path).read_text(encoding="utf-8")
    contract = report_author_contract(report_template_contract(template), fields)
    assert contract["interpretation_only"]
    listing, compose, stage = make_report_object_tools(
        state,
        make_html_interpreter(state, str(root / "skills")),
        template_path,
        contract,
    )
    listed = json.loads(listing())["objects"]
    assert len(listed) == 1 and listed[0]["kind"] == "reference"
    token = listed[0]["object_id"]
    plain = {field: "按区域核验业务表现。" for field in contract["fields"]}
    failed = await compose(plain)
    assert "KB_REPORT_BINDING_REQUIRED" in failed
    field = contract["fields"][0]
    plain[field] = ["销售口径按区域复核。", {"object_id": token}]
    jsonschema.validate(plain, report_object_schema(contract))
    result = json.loads(await compose(plain))
    assert result.get("status") == "completed", result
    assert reference in state["_report_presentation"]["content"]
    assert not state.get("_report_warnings")
    forged = {field: [{"object_id": "reference-" + "0" * 24}]}
    assert json.loads(await compose(forged))["status"] == "invalid_selection"
    value = "value-" + "0" * 24
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            {field: [{"object_id": value}]}, report_object_schema(contract)
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("append", [False, True])
async def test_generate_report_repairs_table_without_replacing_saved_prose(
    tmp_path, monkeypatch, append
):
    from copy import deepcopy
    from pathlib import Path
    from types import SimpleNamespace

    from dbgpt_app.openapi.api_v1.subagent import report_agent
    from dbgpt_app.openapi.api_v1.tools import report_repair

    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    root = next(p for p in Path(__file__).resolve().parents if (p / "skills").is_dir())
    template = "business-report/templates/business_report.html"
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="repair-preserve"))
    source = capture(sink, {"total": 100, "rows": [{"region": "East", "sales": 100}]})
    state = {"conv_id": "repair-preserve", "_report_artifact_sink": sink}
    original = {
        "title": "Business report",
        "kpis": [{"label": "Total", "ref": {"artifact_id": source, "field": "total"}}],
        "sections": [
            {
                "heading": "Regional results",
                "intro": [["保留重点客户名单并安排区域复核"]],
                "table": {
                    "artifact_id": source,
                    "field": "rows",
                    "columns": ["region", "salse"],
                },
                "recommendations": [
                    {
                        "title": "Follow up",
                        "lines": [{"parts": ["由区域负责人逐店跟进"]}],
                    }
                ],
            },
            {"heading": "Untouched", "intro": [["原有独立结论保持不变"]]},
        ],
    }
    renderer = make_html_interpreter(state, str(root / "skills"))
    await renderer(
        template_path=template,
        title="Original title",
        data={"REPORT_SPEC": deepcopy(original)},
    )
    assert state.get("_report_html_error")
    before = deepcopy(state["_report_saved_arguments"]["data"]["REPORT_SPEC"])
    monkeypatch.setattr(report_agent, "select_report_template", lambda *_: template)

    async def build(**kwargs):
        listing, compose, patch = make_report_object_tools(
            state, renderer, template, {"mode": "spec", "fields": []}
        )

        async def generate_reply(**kwargs):
            message = kwargs["received_message"].content
            assert "patch_report" in message and '"section_index": 0' in message
            rejected = json.loads(
                await compose({"sections": [{"heading": "Replacement"}]})
            )
            assert rejected["status"] == "invalid_selection"
            tables = json.loads(listing(kind="table"))["objects"]
            arguments = {
                "section_index": 0,
                "section": {"table": {"object_id": tables[0]["object_id"]}},
            }
            if append:
                arguments["append_recommendations"] = [
                    {"title": "Additional action", "lines": [["新增复核安排"]]}
                ]
                arguments["append_sections"] = [
                    {"heading": "Additional section", "intro": [["新增结论"]]}
                ]
            response = json.loads(await patch(**arguments))
            assert response["status"] == "completed", response
            return SimpleNamespace(success=True, content="Repaired", context={})

        return SimpleNamespace(generate_reply=generate_reply)

    monkeypatch.setattr(report_agent, "build_report_agent", build)
    response = json.loads(
        await report_agent.make_generate_report_tool(
            react_state=state, skills_dir=str(root / "skills"), llm_client=object()
        )("Repair the invalid table")
    )
    assert response["status"] == "completed", response
    after = state["_report_saved_arguments"]["data"]["REPORT_SPEC"]
    assert after["kpis"] == before["kpis"]
    assert after["sections"][1] == before["sections"][1]
    assert after["sections"][0]["intro"] == before["sections"][0]["intro"]
    assert (
        after["sections"][0]["recommendations"][:1]
        == before["sections"][0]["recommendations"]
    )
    html = state["_report_presentation"]["content"]
    assert "保留重点客户名单并安排区域复核" in html and "由区域负责人逐店跟进" in html
    assert source in html
    if append:
        assert "新增复核安排" in html and "新增结论" in html


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["", " ", "\n\t"])
@pytest.mark.parametrize("pending_report", [False, True])
async def test_empty_report_reply_uses_existing_invocation_budget(
    tmp_path, monkeypatch, text, pending_report
):
    from functools import partial

    from dbgpt.agent import AgentContext, AgentMessage
    from dbgpt.agent.expand.tool_calling_agent import ToolCallingReActAgent
    from dbgpt.agent.resource.tool.pack import ToolPack
    from dbgpt_app.openapi.api_v1.tools import report_repair

    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    state = {"conv_id": "empty-repair"}
    if pending_report:
        state.update(
            _report_html_error="REPORT_TEMPLATE_SPEC_INVALID: fix table",
            _report_saved_arguments={
                "template_path": "report.html",
                "data": {"REPORT_SPEC": {"sections": []}},
            },
        )
    state["_report_invalid_call_handler"] = partial(
        report_repair.record_report_invocation_failure, state
    )
    agent = ToolCallingReActAgent()
    agent.agent_context = AgentContext(
        conv_id="empty-repair", enable_native_function_calling=True
    )
    agent.resource = ToolPack([])
    for action in agent.actions:
        action.init_resource(agent.resource)
    object.__setattr__(agent, "_report_repair_state", state)
    for _ in range(2):
        out = await agent.act(
            AgentMessage(content=text),
            sender=agent,
            parser=agent.parser,
            tool_calls=None,
        )
        assert not out.is_exe_success
    assert state.get("_report_invocation_failures", 0) == (2 if pending_report else 0)
    assert bool(state.get("_report_retry_exhausted")) is pending_report
    if pending_report:
        assert out.have_retry is False
