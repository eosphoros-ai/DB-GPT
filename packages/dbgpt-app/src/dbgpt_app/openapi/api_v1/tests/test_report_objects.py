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
from dbgpt_app.openapi.api_v1.tools.html_interpreter import (
    _validate_evidence_bindings,
    make_html_interpreter,
)
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
@pytest.mark.parametrize("section_kpis", [False, True])
async def test_table_kpis_report_every_location_and_scalar_choices(
    monkeypatch, tmp_path, section_kpis
):
    from pathlib import Path

    from dbgpt.agent.resource.tool.pack import ToolPack
    from dbgpt_app.openapi.api_v1.tools import report_repair

    monkeypatch.setattr("dbgpt.configs.model_config.PILOT_PATH", str(tmp_path))
    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    root = next(p for p in Path(__file__).resolve().parents if (p / "skills").is_dir())
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="repair-kpi-kinds"))
    capture(
        sink, {"columns": ["orders", "gmv"], "rows": [{"orders": 632, "gmv": 80380}]}
    )
    registry = ReportObjects(sink.snapshot())
    table = object_id(registry, "table", "table")
    state = {"conv_id": sink.context.conv_uid, "_report_artifact_sink": sink}
    tools = make_report_object_tools(
        state,
        make_html_interpreter(state, str(root / "skills")),
        "business-report/templates/business_report.html",
        {"mode": "spec", "fields": []},
    )
    pack = ToolPack([t._tool for t in tools])
    invalid = [
        {"label": "订单", "object_id": table},
        {"label": "GMV", "object_id": table},
    ]
    section = {
        "heading": "经营概览",
        "intro": [["定性解读。"]],
        "table": {"object_id": table},
    }
    args = {"render": False, "append_sections": [section]}
    if section_kpis:
        section["kpis"] = invalid
    else:
        args["report"] = {"kpis": invalid}
    rejected = json.loads(
        await pack.async_execute(resource_name="patch_report", **args)
    )
    assert rejected["status"] == "invalid_selection"
    assert not state.get("_report_object_spec")
    error = rejected["error"]
    prefix = "sections[0].kpis" if section_kpis else "report.kpis"
    assert prefix + "[0].object_id" in error and prefix + "[1].object_id" in error
    assert "available_values" in error
    assert "rows.0.orders" in error and "rows.0.gmv" in error
    corrected = [
        {"label": label, "object_id": object_id(registry, "value", path)}
        for label, path in [("订单", "rows.0.orders"), ("GMV", "rows.0.gmv")]
    ]
    if section_kpis:
        section["kpis"] = corrected
    else:
        args["report"] = {"kpis": corrected}
    assert (
        json.loads(await pack.async_execute(resource_name="patch_report", **args))[
            "status"
        ]
        == "staged"
    )
    completed = json.loads(await pack.async_execute(resource_name="compose_report"))
    assert completed["status"] == "completed", completed
    assert "632" in state["_report_presentation"]["content"]
    assert "80,380" in state["_report_presentation"]["content"]


@pytest.mark.asyncio
async def test_unknown_prose_value_offers_candidates_and_recovers_append(
    monkeypatch, tmp_path
):
    from copy import deepcopy
    from pathlib import Path

    from dbgpt.agent.resource.tool.pack import ToolPack
    from dbgpt_app.openapi.api_v1.tools import report_repair

    monkeypatch.setattr("dbgpt.configs.model_config.PILOT_PATH", str(tmp_path))
    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    root = next(p for p in Path(__file__).resolve().parents if (p / "skills").is_dir())
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="repair-prose-value"))
    capture(sink, {"columns": ["orders"], "rows": [{"orders": 632}]})
    registry = ReportObjects(sink.snapshot())
    value = object_id(registry, "value", "rows.0.orders")
    artifact_ids = {item.artifact_id for item in sink.snapshot()}
    state = {"conv_id": sink.context.conv_uid, "_report_artifact_sink": sink}
    tools = make_report_object_tools(
        state,
        make_html_interpreter(state, str(root / "skills")),
        "business-report/templates/business_report.html",
        {"mode": "spec", "fields": []},
    )
    pack = ToolPack([t._tool for t in tools])
    staged = json.loads(
        await pack.async_execute(
            resource_name="patch_report",
            render=False,
            report={"title": "经营报告"},
            append_sections=[{"heading": "摘要", "intro": [["定性概览。"]]}],
        )
    )
    assert staged["status"] == "staged"
    before = deepcopy(state["_report_object_spec"])
    section = {
        "heading": "订单分析",
        "intro": [
            ["订单量为", {"object_id": "value-999c2******************"}, "。"],
            ["复核值为", {"object_id": "value-" + "1" * 23}, "。"],
        ],
    }
    rejected = json.loads(
        await pack.async_execute(
            resource_name="patch_report", render=False, append_sections=[section]
        )
    )
    assert rejected["status"] == "invalid_selection"
    assert rejected["rejected_sections"] == [section]
    assert state["_report_object_spec"] == before
    assert "sections[0].intro[0][1]" in rejected["error"]
    assert "sections[0].intro[1][1]" in rejected["error"]
    assert rejected["error"].count('"available_values"') == 1
    assert value in rejected["error"] and "rows.0.orders" in rejected["error"]
    checkpoint = json.loads(
        (tmp_path / "tmp/repair-prose-value/report-repair/checkpoint.json").read_text()
    )
    assert checkpoint["rejected_sections"] == [section]
    assert checkpoint["object_spec"] == before

    empty_append = json.loads(
        await pack.async_execute(
            resource_name="patch_report", render=False, append_sections=[]
        )
    )
    assert empty_append["status"] == "invalid_selection"
    assert empty_append["rejected_sections"] == [section]
    assert state["_report_rejected_sections"] == [section]

    premature = json.loads(
        await pack.async_execute(
            resource_name="compose_report", data={"title": "不应覆盖草稿"}
        )
    )
    assert premature["status"] == "invalid_selection"
    assert premature["rejected_sections"] == [section]
    assert state["_report_rejected_sections"] == [section]
    checkpoint = json.loads(
        (tmp_path / "tmp/repair-prose-value/report-repair/checkpoint.json").read_text()
    )
    assert checkpoint["rejected_sections"] == [section]

    corrected = deepcopy(rejected["rejected_sections"])
    for paragraph in corrected[0]["intro"]:
        paragraph[1]["object_id"] = value
    staged = json.loads(
        await pack.async_execute(
            resource_name="patch_report", render=False, append_sections=corrected
        )
    )
    assert staged["status"] == "staged"
    assert not state.get("_report_rejected_sections")
    assert {item.artifact_id for item in sink.snapshot()} == artifact_ids
    completed = json.loads(await pack.async_execute(resource_name="compose_report"))
    assert completed["status"] == "completed", completed
    assert "定性概览" in state["_report_presentation"]["content"]
    assert "632" in state["_report_presentation"]["content"]
    assert {item.artifact_id for item in sink.snapshot()} == artifact_ids


@pytest.mark.asyncio
async def test_rejected_append_restores_after_retry_exhaustion(monkeypatch, tmp_path):
    from copy import deepcopy
    from pathlib import Path

    from dbgpt.agent.resource.tool.pack import ToolPack
    from dbgpt_app.openapi.api_v1.tools import report_repair

    monkeypatch.setattr("dbgpt.configs.model_config.PILOT_PATH", str(tmp_path))
    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    root = next(p for p in Path(__file__).resolve().parents if (p / "skills").is_dir())
    conv_id = "restore-rejected-prose"
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid=conv_id))
    capture(sink, {"columns": ["orders"], "rows": [{"orders": 632}]})
    registry = ReportObjects(sink.snapshot())
    value = object_id(registry, "value", "rows.0.orders")
    artifact_ids = {item.artifact_id for item in sink.snapshot()}
    state = {"conv_id": conv_id, "_report_artifact_sink": sink}
    tools = make_report_object_tools(
        state,
        make_html_interpreter(state, str(root / "skills")),
        "business-report/templates/business_report.html",
        {"mode": "spec", "fields": []},
    )
    pack = ToolPack([t._tool for t in tools])
    assert (
        json.loads(
            await pack.async_execute(
                resource_name="patch_report",
                render=False,
                report={"title": "经营报告"},
                append_sections=[{"heading": "摘要", "intro": [["定性概览。"]]}],
            )
        )["status"]
        == "staged"
    )
    section = {
        "heading": "订单分析",
        "intro": [["订单量为", {"object_id": "value-999c2******************"}, "。"]],
    }
    for attempt in range(2):
        rejected = json.loads(
            await pack.async_execute(
                resource_name="patch_report", render=False, append_sections=[section]
            )
        )
        assert rejected["status"] == "invalid_selection"
        assert rejected["retryable"] is (attempt == 0)
    assert state["_report_retry_exhausted"]

    section["heading"] = "最新订单分析"
    rejected = json.loads(
        await pack.async_execute(
            resource_name="patch_report", render=False, append_sections=[section]
        )
    )
    assert rejected["status"] == "invalid_selection"
    assert rejected["rejected_sections"] == [section]
    assert state["_report_rejected_sections"] == [section]
    checkpoint = json.loads(
        (tmp_path / f"tmp/{conv_id}/report-repair/checkpoint.json").read_text()
    )
    assert checkpoint["rejected_sections"] == [section]

    restored = {"conv_id": conv_id}
    restored_sink = report_repair.restore_report_checkpoint(conv_id, restored)
    assert restored_sink is not None
    assert {item.artifact_id for item in restored_sink.snapshot()} == artifact_ids
    assert restored["_report_rejected_sections"] == [section]
    restored["_report_artifact_sink"] = restored_sink
    tools = make_report_object_tools(
        restored,
        make_html_interpreter(restored, str(root / "skills")),
        "business-report/templates/business_report.html",
        {"mode": "spec", "fields": []},
    )
    pack = ToolPack([t._tool for t in tools])
    corrected = deepcopy(restored["_report_rejected_sections"])
    corrected[0]["intro"][0][1]["object_id"] = value
    assert (
        json.loads(
            await pack.async_execute(
                resource_name="patch_report",
                render=False,
                append_sections=corrected,
            )
        )["status"]
        == "staged"
    )
    assert not restored.get("_report_rejected_sections")

    # A checkpoint written before rejected_sections existed remains recoverable.
    checkpoint_path = tmp_path / f"tmp/{conv_id}/report-repair/checkpoint.json"
    checkpoint = json.loads(checkpoint_path.read_text())
    checkpoint.pop("rejected_sections")
    checkpoint_path.write_text(json.dumps(checkpoint))
    legacy = {"conv_id": conv_id}
    legacy_sink = report_repair.restore_report_checkpoint(conv_id, legacy)
    assert legacy_sink is not None
    assert legacy["_report_rejected_sections"] == []
    assert len(legacy["_report_object_spec"]["sections"]) == 2
    legacy["_report_artifact_sink"] = legacy_sink
    tools = make_report_object_tools(
        legacy,
        make_html_interpreter(legacy, str(root / "skills")),
        "business-report/templates/business_report.html",
        {"mode": "spec", "fields": []},
    )
    pack = ToolPack([t._tool for t in tools])
    completed = json.loads(await pack.async_execute(resource_name="compose_report"))
    assert completed["status"] == "completed", completed
    assert "632" in legacy["_report_presentation"]["content"]
    assert {item.artifact_id for item in legacy_sink.snapshot()} == artifact_ids


def test_rejected_section_retention_is_bounded():
    from dbgpt_app.openapi.api_v1.tools import report_repair

    section = {"heading": "订单分析", "intro": [["定性说明。"]]}
    retained = report_repair._bounded_rejected_sections([section])
    assert retained == [section]
    assert retained is not section and retained[0] is not section
    oversized = {"heading": "订" * report_repair.MAX_REJECTED_SECTION_BYTES}
    assert report_repair._bounded_rejected_sections([oversized]) is None
    too_deep = {"intro": ["定性说明。"]}
    for _ in range(report_repair.MAX_REJECTED_SECTION_DEPTH + 1):
        too_deep = {"intro": [too_deep]}
    assert report_repair._bounded_rejected_sections([too_deep]) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("unknown", ["intro", "note", "table", "chart", "title"])
async def test_public_repair_rejects_unknown_arguments_and_renders_corrections(
    monkeypatch, tmp_path, unknown
):
    from copy import deepcopy
    from pathlib import Path

    from dbgpt.agent.resource.tool.exceptions import ToolExecutionException
    from dbgpt.agent.resource.tool.pack import ToolPack
    from dbgpt_app.openapi.api_v1.tools import report_repair

    monkeypatch.setattr("dbgpt.configs.model_config.PILOT_PATH", str(tmp_path))
    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    root = next(p for p in Path(__file__).resolve().parents if (p / "skills").is_dir())
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="public-repair"))
    capture(sink, {"columns": ["region", "sales"], "rows": [["East", 100]]})
    objects = ReportObjects(sink.snapshot())
    table = object_id(objects, "table", "table")
    value = object_id(objects, "value", "rows.0.1")
    state = {"conv_id": sink.context.conv_uid, "_report_artifact_sink": sink}
    wrappers = make_report_object_tools(
        state,
        make_html_interpreter(state, str(root / "skills")),
        "business-report/templates/business_report.html",
        {"mode": "spec", "fields": []},
    )
    pack = ToolPack([entry._tool for entry in wrappers])
    await pack.async_execute(
        resource_name="patch_report",
        render=False,
        report={"title": "旧标题"},
        append_sections=[
            {
                "heading": "地区分析",
                "intro": [["原有错误说明"]],
                "table": {"object_id": table},
            }
        ],
    )
    for field, content in [
        ("title", "已修正标题"),
        ("subtitle", "已修正副标题"),
        ("scope", "已修正范围"),
        ("kpis", [{"label": "销售额", "object_id": value}]),
    ]:
        sections = deepcopy(state["_report_object_spec"]["sections"])
        result = json.loads(
            await pack.async_execute(
                resource_name="patch_report",
                report={field: content},
            )
        )
        assert result["status"] == "staged"
        assert state["_report_object_spec"]["sections"] == sections
    # Rebuilding a ToolPack must retain argument validation on the resource.
    pack = ToolPack([entry._tool for entry in wrappers])
    before = deepcopy(state["_report_object_spec"])
    checkpoint = (
        tmp_path / "tmp/public-repair/report-repair/checkpoint.json"
    ).read_bytes()
    with pytest.raises(
        ToolExecutionException, match="REPORT_OBJECT_INVALID: unknown arguments"
    ):
        await pack.async_execute(
            resource_name="patch_report",
            section_index=0,
            section={"heading": "不应生效的标题"},
            **{unknown: "放错层级的内容"},
        )
    assert state["_report_object_spec"] == before
    assert (
        tmp_path / "tmp/public-repair/report-repair/checkpoint.json"
    ).read_bytes() == checkpoint
    result = json.loads(
        await pack.async_execute(
            resource_name="patch_report",
            section_index=0,
            section={"intro": [["新的正确说明"]]},
        )
    )
    assert result["status"] == "staged"
    completed = json.loads(await pack.async_execute(resource_name="compose_report"))
    assert completed["status"] == "completed", completed
    html = state["_report_presentation"]["content"]
    for expected in (
        "已修正标题",
        "已修正副标题",
        "已修正范围",
        "新的正确说明",
        "East",
        "100",
    ):
        assert expected in html
    assert "原有错误说明" not in html and "不应生效的标题" not in html


def test_numeric_values_precede_column_names_in_value_catalogue():
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="numeric-catalogue"))
    capture(sink, {"columns": ["region", "revenue"], "rows": [["East", 100]]})
    page = ReportObjects(sink.snapshot()).manifest(kind="value", limit=1)
    assert page["objects"][0]["preview"] == "100"
    assert page["objects"][0]["label"] == "rows.0.1"


def test_all_invalid_prose_references_are_reported_before_repair():
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="reference-errors"))
    capture(sink, {"columns": ["region", "revenue"], "rows": [["East", 100]]})
    objects = ReportObjects(sink.snapshot())
    table = object_id(objects, "table", "table")
    with pytest.raises(ValueError) as failure:
        compile_report_objects(
            {
                "sections": [
                    {
                        "heading": "地区分析",
                        "intro": [["地区表现。", {"object_id": table}]],
                        "bullets": [["复核差异。", {"object_id": table}]],
                    }
                ]
            },
            objects,
            spec_mode=True,
            fields=[],
        )
    assert "sections[0].intro[0][1]" in str(failure.value)
    assert "sections[0].bullets[0][1]" in str(failure.value)
    assert "repair every invalid prose reference" in str(failure.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("language", ["zh", "en"])
@pytest.mark.parametrize("flat", [False, True])
async def test_named_template_completes_with_numbered_advice_in_one_submission(
    monkeypatch, tmp_path, language, flat
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
                "ADVICE": advice if flat else [[a] for a in advice],
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


@pytest.mark.asyncio
async def test_correcting_unknown_template_field_is_not_repeated_failure(
    monkeypatch, tmp_path
):
    from dbgpt_app.openapi.api_v1.tools import report_repair

    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    state = {"conv_id": "correct-template-field"}
    rendered = []

    async def renderer(**arguments):
        rendered.append(arguments)
        return json.dumps({"status": "completed"})

    _, compose, _ = make_report_object_tools(
        state, renderer, "report.html", {"mode": "placeholders", "fields": ["SUMMARY"]}
    )
    for extra in ["SUMMARY_EXTRA", "title"]:
        response = json.loads(await compose({"SUMMARY": "定性分析。", extra: "内容"}))
        assert response["status"] == "invalid_selection"
        assert response["retryable"]
        assert extra in response["error"] and "allowed fields" in response["error"]
        assert not rendered
    assert json.loads(await compose({"SUMMARY": "定性分析。"}))["status"] == "completed"
    assert len(rendered) == 1


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
async def test_interpretation_handoff_does_not_offer_forbidden_value_handles(
    monkeypatch, tmp_path
):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from dbgpt_app.openapi.api_v1.subagent import report_agent

    (tmp_path / "report.html").write_text(
        '<!-- dbgpt-required: SUMMARY --><html><div class="prose">{{SUMMARY}}</div>'
        "<script>{{CHART_DATA_JSON}}</script></html>",
        encoding="utf-8",
    )
    sink = InMemoryArtifactSink(
        ArtifactCaptureContext(conv_uid="interpretation-handoff")
    )
    capture(
        sink,
        {
            "CHART_DATA_JSON": json.dumps(
                {"overview": {"rows": 6435}, "scatter": [100] * 4000}
            )
        },
    )
    generate = AsyncMock(
        return_value=SimpleNamespace(success=True, content="Draft", context={})
    )
    monkeypatch.setattr(
        report_agent,
        "build_report_agent",
        AsyncMock(return_value=SimpleNamespace(generate_reply=generate)),
    )
    monkeypatch.setattr(
        report_agent, "select_report_template", lambda *_: "report.html"
    )
    await report_agent.make_generate_report_tool(
        react_state={"conv_id": sink.context.conv_uid, "_report_artifact_sink": sink},
        skills_dir=str(tmp_path),
        llm_client=object(),
    )("Build the report")
    message = generate.call_args.kwargs["received_message"].content
    handoff, _ = json.JSONDecoder().raw_decode(message[message.index('{"total"') :])
    assert handoff["objects"] == []
    assert handoff["template_fields"] == ["SUMMARY"]
    statistics = handoff["statistics_for_interpretation"]
    assert "6435" in statistics["overview"]["preview"]
    assert statistics["scatter"]["truncated"]
    assert len(statistics["scatter"]["preview"]) == 1000
    assert "value-" not in message


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


@pytest.mark.parametrize(
    "text",
    [
        "；2018 年 1—8 月订单量 ",
        "2018年1至8月商品 GMV",
        "分析2017 年 01～12 月的销售趋势。",
    ],
)
def test_report_calendar_month_ranges_with_year_are_not_measured_values(text):
    report = compile_report_objects(
        {"sections": [{"heading": "销售趋势", "intro": [[text]]}]},
        ReportObjects([]),
        spec_mode=True,
        fields=[],
    )
    assert report["REPORT_SPEC"]["sections"][0]["intro"] == [[text]]
    assert _validate_evidence_bindings(f"<p>{text}</p>", []) is None


@pytest.mark.parametrize(
    "text",
    [
        "2018 年 1—8 月订单量为 632 单。",
        "实际配送耗时为 1—8 月。",
        "2018 年配送耗时为 1 至 8 月。",
        "平均配送时长为 8 个月。",
        "2018 年 0—8 月订单量。",
        "2018 年 13—14 月订单量。",
        "2018 年 1—13 月订单量。",
    ],
)
def test_report_month_ranges_do_not_exempt_measured_values(text):
    with pytest.raises(ValueError, match="REPORT_OBJECT_LITERAL"):
        compile_report_objects(
            {"sections": [{"heading": "分析", "intro": [[text]]}]},
            ReportObjects([]),
            spec_mode=True,
            fields=[],
        )
    error = _validate_evidence_bindings(f"<p>{text}</p>", [])
    assert error and "REPORT_TARGET_BINDING_REQUIRED" in error


@pytest.mark.parametrize("root_note", [False, True])
def test_knowledge_note_paragraphs_compile_to_flat_bound_parts(root_note):
    from dbgpt.core.interface.report_capture import (
        bind_artifact_sink,
        capture_reference_artifact,
    )

    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="note-paragraphs"))
    with bind_artifact_sink(sink):
        source = capture_reference_artifact(
            reference_type="knowledge",
            source_id="governance",
            action="kb_cat",
            duration_ms=1,
            source_name="业务口径",
            excerpt="无评价不可当作0分。",
        )
    registry = ReportObjects(sink.snapshot())
    token = next(
        key for key, item in registry.objects.items() if item["kind"] == "reference"
    )
    paragraphs = [
        ["口径说明：", {"object_id": token}],
        ["无评价记录为空值，不按 0 分处理。"],
        ["平均评分排除空值且不可当 0 分。"],
    ]
    data = (
        {"note": paragraphs}
        if root_note
        else {"sections": [{"heading": "业务口径", "note": paragraphs}]}
    )
    spec = compile_report_objects(data, registry, spec_mode=True, fields=[])[
        "REPORT_SPEC"
    ]
    parts = spec["sections"][0]["note"]["parts"]
    assert all(isinstance(part, (str, dict)) for part in parts)
    assert any(
        isinstance(part, dict) and part.get("artifact_id") == source for part in parts
    )
    with pytest.raises(ValueError, match="REPORT_OBJECT_LITERAL"):
        compile_report_objects(
            {"note": [["收入999元"]]}, registry, spec_mode=True, fields=[]
        )
    with pytest.raises(ValueError, match="REPORT_OBJECT_LITERAL"):
        compile_report_objects(
            {"note": [["缺失评分按 0 分统计。"]]}, registry, spec_mode=True, fields=[]
        )


@pytest.mark.asyncio
async def test_corrected_named_draft_clears_stale_error_and_renders(
    monkeypatch, tmp_path
):
    from dbgpt.agent.resource.tool.pack import ToolPack
    from dbgpt_app.openapi.api_v1.tools import report_repair

    monkeypatch.setattr("dbgpt.configs.model_config.PILOT_PATH", str(tmp_path))
    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    (tmp_path / "report.html").write_text(
        "<html><body>{{SUMMARY}}{{INSIGHTS}}</body></html>", encoding="utf-8"
    )
    state = {"conv_id": "clear-stale-error"}
    contract = {"mode": "placeholders", "fields": ["SUMMARY", "INSIGHTS"]}
    wrappers = make_report_object_tools(
        state, make_html_interpreter(state, str(tmp_path)), "report.html", contract
    )
    pack = ToolPack([entry._tool for entry in wrappers])
    await pack.async_execute(
        resource_name="set_report_field", field="INSIGHTS", content="旧的有效分析。"
    )
    rejected = json.loads(
        await pack.async_execute(
            resource_name="compose_report",
            data={"SUMMARY": "真实业务概况。", "INSIGHTS": "收入 999"},
        )
    )
    assert rejected["status"] == "invalid_selection"
    assert state["_report_html_error"].startswith("REPORT_OBJECT_LITERAL")
    attempts = state["_report_tool_call_count"]
    unrelated = json.loads(
        await pack.async_execute(
            resource_name="set_report_field", field="SUMMARY", content="更新后的概况。"
        )
    )
    assert unrelated["remaining_fields"] == []
    assert not unrelated["ready_to_compose"]
    assert state["_report_html_error"].startswith("REPORT_OBJECT_LITERAL")
    staged = json.loads(
        await pack.async_execute(
            resource_name="set_report_field",
            field="INSIGHTS",
            content="修正后的定性分析。",
        )
    )
    assert staged["remaining_fields"] == [] and staged["ready_to_compose"]
    assert "compose_report()" in staged["instruction"]
    assert not state.get("_report_html_error")
    assert not state.get("_report_last_render_error")
    assert state["_report_preflight_attempts"] == 0
    assert state["_report_tool_call_count"] == attempts
    checkpoint = json.loads(
        (tmp_path / "tmp/clear-stale-error/report-repair/checkpoint.json").read_text(
            encoding="utf-8"
        )
    )
    assert checkpoint["render_error"] is None
    completed = json.loads(await pack.async_execute(resource_name="compose_report"))
    assert completed["status"] == "completed", completed
    assert "修正后的定性分析" in state["_report_presentation"]["content"]


@pytest.mark.parametrize(
    "error",
    ["KB_REPORT_BINDING_REQUIRED: missing source", "REPORT_OBJECT_LITERAL: old error"],
)
def test_named_field_does_not_clear_other_failures_or_exhaustion(error):
    state = {
        "_report_object_template": "report.html",
        "_report_object_fields": {},
        "_report_html_error": error,
        "_report_last_render_error": error,
        "_report_retry_exhausted": error.startswith("REPORT_OBJECT_"),
    }
    _, _, stage = make_report_object_tools(
        state,
        None,
        "report.html",
        {"mode": "placeholders", "fields": ["SUMMARY", "INSIGHTS"]},
    )
    stage("SUMMARY", "定性说明。")
    assert state["_report_html_error"] == error
    assert state["_report_last_render_error"] == error


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
async def test_full_named_submission_retains_valid_fields_for_targeted_repair(
    monkeypatch, tmp_path
):
    from dbgpt_app.openapi.api_v1.tools import report_repair

    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    state = {"conv_id": "partial-named-submission"}
    rendered = []

    async def renderer(**arguments):
        rendered.append(arguments)
        return json.dumps({"status": "completed"})

    contract = {"mode": "placeholders", "fields": ["SUMMARY", "CASHFLOW"]}
    _, compose, stage = make_report_object_tools(
        state, renderer, "report.html", contract
    )
    rejected = json.loads(
        await compose({"SUMMARY": "经营规模稳定。", "CASHFLOW": "现金收入 999"})
    )
    assert rejected["status"] == "invalid_selection" and not rendered
    assert state["_report_object_fields"] == {"SUMMARY": "经营规模稳定。"}
    restored = {"conv_id": state["conv_id"]}
    assert report_repair.restore_report_checkpoint(state["conv_id"], restored)
    assert restored["_report_object_fields"] == state["_report_object_fields"]
    stage("CASHFLOW", "现金流情况需结合回款周期评估。")
    assert json.loads(await compose())["status"] == "completed"
    assert rendered[0]["data"] == {
        "SUMMARY": "经营规模稳定。",
        "CASHFLOW": "现金流情况需结合回款周期评估。",
    }


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


@pytest.mark.asyncio
@pytest.mark.parametrize("finish_on_resume", [True, False])
async def test_progressing_spec_resumes_saved_sections_after_step_limit(
    monkeypatch, tmp_path, finish_on_resume
):
    from copy import deepcopy
    from pathlib import Path
    from types import SimpleNamespace

    from dbgpt.core.interface.report_capture import bind_artifact_sink
    from dbgpt_app.openapi.api_v1.subagent import report_agent
    from dbgpt_app.openapi.api_v1.tools import report_repair

    monkeypatch.setattr("dbgpt.configs.model_config.PILOT_PATH", str(tmp_path))
    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    root = next(p for p in Path(__file__).resolve().parents if (p / "skills").is_dir())
    template = "business-report/templates/business_report.html"
    monkeypatch.setattr(report_agent, "select_report_template", lambda *_: template)
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="progressing-spec"))
    capture(sink, {"columns": ["region", "revenue"], "rows": [["East", 100]]})
    table = object_id(ReportObjects(sink.snapshot()), "table", "table")
    state = {
        "conv_id": sink.context.conv_uid,
        "_report_artifact_sink": sink,
        "_report_required_recommendation_count": 3,
    }
    contract = {"mode": "spec", "fields": []}
    calls = []
    staged_sections = []
    reason = "AGENT_STEP_LIMIT: reached 20 steps without completing the task"

    async def build(**kwargs):
        state["_report_template_contract"] = contract
        _, compose, patch = make_report_object_tools(
            state,
            make_html_interpreter(state, str(root / "skills")),
            template,
            contract,
        )

        async def generate_reply(**kwargs):
            calls.append(True)
            if len(calls) == 1:
                result = json.loads(
                    await patch(
                        render=False,
                        report={"title": "经营分析报告"},
                        append_sections=[
                            {"heading": heading, "table": {"object_id": table}}
                            for heading in ("地区表现", "经营概览")
                        ],
                    )
                )
                assert result["status"] == "staged", result
                staged_sections.extend(
                    deepcopy(state["_report_object_spec"]["sections"])
                )
            else:
                assert state["_report_object_spec"]["sections"] == staged_sections
                if finish_on_resume:
                    advice = [
                        {"title": title, "lines": [["建立复核流程并持续跟踪。"]]}
                        for title in ("复核经营口径", "核验地区差异", "检查执行效果")
                    ]
                    result = json.loads(
                        await patch(
                            append_sections=[
                                {"heading": "结论与建议", "recommendations": advice}
                            ]
                        )
                    )
                    assert result["status"] == "staged", result
                    rendered = json.loads(await compose())
                    assert rendered.get("status") == "completed", rendered
                    return SimpleNamespace(success=True, content="完成", context={})
            return SimpleNamespace(
                success=False, content=reason, context={"execution_error": reason}
            )

        return SimpleNamespace(generate_reply=generate_reply)

    monkeypatch.setattr(report_agent, "build_report_agent", build)
    generate = report_agent.make_generate_report_tool(
        react_state=state, skills_dir=str(root / "skills"), llm_client=object()
    )
    with bind_artifact_sink(sink):
        first = json.loads(await generate(instructions="生成报告"))
        assert first["status"] == "draft_pending" and first["retryable"], first
        assert not state.get("_report_presentation")
        assert not state.get("_report_agent_failure")
        second = json.loads(await generate(instructions="继续完成报告"))
    assert len(calls) == 2
    assert len([item for item in sink.snapshot() if item.type == "python"]) == 1
    if finish_on_resume:
        assert second["status"] == "completed", second
        html = state["_report_presentation"]["content"]
        assert all(text in html for text in ("地区表现", "经营概览", "结论与建议"))
    else:
        assert second["status"] == "failed" and not second["retryable"], second
        assert state["_report_object_spec"]["sections"] == staged_sections
        assert not state.get("_report_presentation")


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


@pytest.mark.parametrize(
    "change,rounds,exhausted,expected",
    [
        ("unchanged", 0, False, "failed"),
        ("reordered", 0, False, "failed"),
        ("deleted", 0, False, "failed"),
        ("scope_only", 0, False, "failed"),
        ("invalid_entry", 0, False, "failed"),
        ("repaired", 0, False, "draft_pending"),
        ("repaired", 2, False, "failed"),
        ("repaired", 0, True, "failed"),
    ],
)
def test_spec_step_limit_requires_content_progress_and_remaining_budget(
    monkeypatch, tmp_path, change, rounds, exhausted, expected
):
    from copy import deepcopy

    from dbgpt_app.openapi.api_v1.subagent import report_agent
    from dbgpt_app.openapi.api_v1.tools import report_repair

    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    before = [
        {"heading": "地区表现", "intro": [["原有解读。"]]},
        {"heading": "经营概览", "intro": [["保留有效分析。"]]},
    ]
    sections = deepcopy(before)
    if change == "reordered":
        sections.reverse()
    elif change == "deleted":
        sections.pop()
    elif change == "scope_only":
        sections.append(
            {"heading": "范围", "source_field": "scope", "intro": [["范围说明。"]]}
        )
    elif change == "invalid_entry":
        sections.append(None)
    elif change == "repaired":
        sections[0]["intro"] = [["补充地区差异的解释。"]]
    state = {
        "conv_id": "spec-progress-boundary",
        "_report_template_contract": {"mode": "spec", "fields": []},
        "_report_object_sections_before": before,
        "_report_object_spec": {"title": "修改后的标题", "sections": sections},
        "_report_draft_continuations": rounds,
        "_report_retry_exhausted": exhausted,
    }
    result = json.loads(report_agent._report_agent_failure(state, "AGENT_STEP_LIMIT"))
    assert result["status"] == expected
    assert result["retryable"] is (expected == "draft_pending")


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_draft", [None, {"heading": "旧章节"}, "旧文本", 42])
async def test_saved_spec_progress_requires_section_changes(
    monkeypatch, tmp_path, invalid_draft
):
    from copy import deepcopy
    from pathlib import Path
    from types import SimpleNamespace

    from dbgpt.core.interface.report_capture import bind_artifact_sink
    from dbgpt_app.openapi.api_v1.subagent import report_agent
    from dbgpt_app.openapi.api_v1.tools import report_repair

    monkeypatch.setattr("dbgpt.configs.model_config.PILOT_PATH", str(tmp_path))
    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    root = next(p for p in Path(__file__).resolve().parents if (p / "skills").is_dir())
    template = "business-report/templates/business_report.html"
    monkeypatch.setattr(report_agent, "select_report_template", lambda *_: template)
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="saved-title-change"))
    capture(sink, {"columns": ["region", "revenue"], "rows": [["East", 100]]})
    registry = ReportObjects(sink.snapshot())
    compiled = compile_report_objects(
        {
            "title": "已有报告",
            "sections": [
                {
                    "heading": "地区表现",
                    "table": {"object_id": object_id(registry, "table", "table")},
                }
            ],
        },
        registry,
        spec_mode=True,
        fields=[],
    )
    state = {
        "conv_id": sink.context.conv_uid,
        "_report_artifact_sink": sink,
        "_report_required_recommendation_count": 3,
        "_report_saved_arguments": {"template_path": template, "data": compiled},
    }
    if invalid_draft is not None:
        state["_report_object_spec"] = {"title": "旧草稿", "sections": invalid_draft}
        state["_report_object_template"] = template
    before = deepcopy(compiled["REPORT_SPEC"]["sections"])
    calls = []

    async def build(**kwargs):
        contract = {"mode": "spec", "fields": []}
        state["_report_template_contract"] = contract
        _, _, patch = make_report_object_tools(
            state,
            make_html_interpreter(state, str(root / "skills")),
            template,
            contract,
        )

        async def generate_reply(**kwargs):
            calls.append(True)
            edits = (
                {
                    "replace_invalid_sections": [
                        {
                            "heading": "地区表现",
                            "table": {
                                "object_id": object_id(registry, "table", "table")
                            },
                        }
                    ]
                }
                if invalid_draft is not None
                else {"report": {"title": "新标题"}}
            )
            result = json.loads(await patch(render=False, **edits))
            assert result["status"] == "staged", result
            return SimpleNamespace(
                success=False,
                content="AGENT_STEP_LIMIT",
                context={"execution_error": "AGENT_STEP_LIMIT"},
            )

        return SimpleNamespace(generate_reply=generate_reply)

    monkeypatch.setattr(report_agent, "build_report_agent", build)
    generate = report_agent.make_generate_report_tool(
        react_state=state, skills_dir=str(root / "skills"), llm_client=object()
    )
    with bind_artifact_sink(sink):
        result = json.loads(await generate(instructions="完成三条建议并生成报告"))
    assert len(calls) == 1
    expected = "draft_pending" if invalid_draft is not None else "failed"
    assert result["status"] == expected, result
    assert result["retryable"] is (invalid_draft is not None)
    assert state["_report_object_spec"]["sections"] == before


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
async def test_financial_named_fields_recover_after_progress_without_weakening_binding(
    monkeypatch, tmp_path
):
    from dbgpt_app.openapi.api_v1.tools import report_repair

    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    fields = [
        "PROFITABILITY_ANALYSIS",
        "SOLVENCY_ANALYSIS",
        "EFFICIENCY_ANALYSIS",
        "RISKS_LIST",
    ]
    state = {"conv_id": "financial-preflight-progress"}
    _, _, stage = make_report_object_tools(
        state, None, "financial.html", {"mode": "placeholders", "fields": fields}
    )
    for index, field in enumerate(fields[:3]):
        for suffix in range(2):
            rejected = json.loads(
                stage(field, f"净利润同比增长 {20 + index * 2 + suffix}%")
            )
            assert rejected["status"] == "invalid_selection" and rejected["retryable"]
        assert (
            json.loads(stage(field, f"需要结合实际业务核验{'。' * (index + 1)}"))[
                "status"
            ]
            == "staged"
        )
        assert state["_report_preflight_attempts"] == 0
    assert state["_report_tool_call_count"] == 6
    rejected = json.loads(
        stage("RISKS_LIST", ["净利润同比增长27.40%，现金流下降22.62%。"])
    )
    assert rejected["status"] == "invalid_selection" and rejected["retryable"]
    assert "RISKS_LIST" not in state["_report_object_fields"]
    staged = json.loads(stage("RISKS_LIST", ["盈利与现金流变化存在差异，应持续核验。"]))
    assert staged["status"] == "staged" and staged["ready_to_compose"]
    assert state["_report_tool_call_count"] == 7


@pytest.mark.asyncio
async def test_business_progress_renews_preflight_but_not_total_budget(
    monkeypatch, tmp_path
):
    from dbgpt.agent.resource.tool.pack import ToolPack
    from dbgpt_app.openapi.api_v1.tools import report_repair

    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    state = {"conv_id": "preflight-progress"}
    tools = make_report_object_tools(
        state, None, "report.html", {"mode": "spec", "fields": []}
    )
    pack = ToolPack([entry._tool for entry in tools])

    async def append(text):
        return json.loads(
            await pack.async_execute(
                resource_name="patch_report",
                render=False,
                append_sections=[{"heading": "配送分析", "intro": [[text]]}],
            )
        )

    for i in range(3):
        for j in range(2):
            result = await append(f"平均时长为 {100 + i * 2 + j} 天。")
            assert result["status"] == "invalid_selection"
            assert result["retryable"]
            assert "request_report_calculation" in result["error"]
            assert "source_artifact_ids" in result["error"]
        assert (await append(f"配送表现需要持续复核{'。' * (i + 1)}"))[
            "status"
        ] == "staged"
        assert state["_report_preflight_attempts"] == 0
        assert state["_report_tool_call_count"] == (i + 1) * 2
    assert len(state["_report_object_spec"]["sections"]) == 3
    await append("平均时长为 999 天。")
    # A no-op metadata patch must not renew the budget.
    await pack.async_execute(resource_name="patch_report", report={"title": "报告"})
    await append("平均时长为 998 天。")
    count = state["_report_preflight_attempts"]
    assert count == 1
    await pack.async_execute(resource_name="patch_report", report={"title": "报告"})
    assert state["_report_preflight_attempts"] == count
    state["_report_tool_call_count"] = report_repair.MAX_REPORT_CALLS - 1
    await append("新的定性说明。")
    result = await append("平均时长为 1234 天。")
    assert not result["retryable"]
    assert state["_report_tool_call_count"] == report_repair.MAX_REPORT_CALLS


@pytest.mark.asyncio
async def test_business_sections_stage_restore_and_render_only_on_commit(
    monkeypatch, tmp_path
):
    from copy import deepcopy
    from pathlib import Path

    from dbgpt_app.openapi.api_v1.tools import report_repair

    monkeypatch.setattr("dbgpt.configs.model_config.PILOT_PATH", str(tmp_path))
    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    root = next(p for p in Path(__file__).resolve().parents if (p / "skills").is_dir())
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="staged-business"))
    source = capture(sink, {"columns": ["region", "revenue"], "rows": [["East", 100]]})
    table = object_id(ReportObjects(sink.snapshot()), "table", "table")
    state = {
        "conv_id": sink.context.conv_uid,
        "_report_artifact_sink": sink,
        "_report_required_recommendation_count": 3,
    }
    template = "business-report/templates/business_report.html"
    contract = {"mode": "spec", "fields": []}
    _, compose, patch = make_report_object_tools(
        state, make_html_interpreter(state, str(root / "skills")), template, contract
    )
    header_only = json.loads(await patch(render=False, report={"title": "业务报告"}))
    assert header_only["status"] == "invalid_selection"
    assert "append_sections" in header_only["error"]
    assert not state.get("_report_object_spec")
    staged = json.loads(
        await patch(
            render=False,
            report={"title": "业务报告", "scope": "演示数据"},
            append_sections=[{"heading": "地区表现", "table": {"object_id": table}}],
        )
    )
    assert staged["status"] == "staged"
    assert not state.get("_report_presentation")
    before = deepcopy(state["_report_object_spec"])
    malformed = json.loads(await patch(section_index=0, section="地区表现"))
    assert malformed["status"] == "invalid_selection"
    assert "section must be an object" in malformed["error"]
    assert state["_report_object_spec"] == before
    repeat_header = json.loads(await patch(render=False, report={"title": "新标题"}))
    assert repeat_header["status"] == "staged"
    before["title"] = "新标题"
    assert state["_report_object_spec"] == before
    invalid = json.loads(
        await patch(
            render=False,
            append_sections=[{"heading": "错误章节", "intro": [["收入 999"]]}],
        )
    )
    assert invalid["status"] == "invalid_selection"
    assert state["_report_object_spec"] == before
    assert not await report_repair.render_saved_report(state, str(root / "skills"))
    restored = {"conv_id": sink.context.conv_uid}
    restored_sink = report_repair.restore_report_checkpoint(
        sink.context.conv_uid, restored
    )
    assert restored_sink
    restored["_report_artifact_sink"] = restored_sink
    assert restored["_report_object_spec"] == before
    _, compose, patch = make_report_object_tools(
        restored,
        make_html_interpreter(restored, str(root / "skills")),
        template,
        contract,
    )
    # Once a draft exists, a patch's default cannot publish a partial document.
    advice = [
        {"title": text, "lines": [["建立复核流程并持续跟踪。"]]}
        for text in (
            "复核经营口径",
            "核验地区差异",
            "检查执行效果",
        )
    ]
    assert (
        json.loads(
            await patch(
                append_sections=[{"heading": "结论与建议", "recommendations": advice}]
            )
        )["status"]
        == "staged"
    )
    assert not restored.get("_report_presentation")
    result = json.loads(await compose())
    assert not restored.get("_report_html_error"), result
    html = restored["_report_presentation"]["content"]
    assert "地区表现" in html and "结论与建议" in html and source in html
    assert "East" in html and "100" in html
    assert not restored.get("_report_object_spec")


@pytest.mark.asyncio
async def test_unfinished_draft_cannot_fall_back_to_old_saved_report(
    monkeypatch, tmp_path
):
    from dbgpt_app.openapi.api_v1.tools import report_repair

    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    saved = {"sections": [{"heading": "已有章节"}]}
    state = {
        "conv_id": "preserve-incomplete-draft",
        "_report_saved_arguments": {
            "template_path": "report.html",
            "data": {"REPORT_SPEC": saved},
        },
    }

    async def renderer(**kwargs):
        raise AssertionError("A draft must not call the renderer")

    _, _, patch = make_report_object_tools(
        state, renderer, "report.html", {"mode": "spec", "fields": []}
    )
    response = json.loads(
        await patch(
            render=False,
            append_sections=[{"heading": "待完成章节", "intro": [["定性分析。"]]}],
        )
    )
    assert response["status"] == "staged"
    assert not await report_repair.render_saved_report(state, str(tmp_path))
    assert state["_report_saved_arguments"]["data"]["REPORT_SPEC"] == saved


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


# ── Staged repairs must supersede the cached deliverable of the same request ──

BUSINESS_TEMPLATE = "business-report/templates/business_report.html"
SPEC_CONTRACT = {"mode": "spec", "fields": []}


def _business_skills_dir():
    from pathlib import Path

    root = next(p for p in Path(__file__).resolve().parents if (p / "skills").is_dir())
    return str(root / "skills")


async def _cached_partial_repair_context(tmp_path, monkeypatch, conv_uid):
    """Reproduce the reported same-turn state: a partial cached as deliverable.

    The first render fails on a wrong table column (``salse``), the
    deterministic fallback keeps a table-less partial, and the completion lock
    engages exactly like ``build_report_agent`` does before the repair turn.
    """
    from dbgpt_app.openapi.api_v1.tools import report_repair

    monkeypatch.setattr("dbgpt.configs.model_config.PILOT_PATH", str(tmp_path))
    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    skills = _business_skills_dir()
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid=conv_uid))
    source = capture(sink, {"total": 100, "rows": [{"region": "华东", "sales": 100}]})
    state = {"conv_id": conv_uid, "_report_artifact_sink": sink}
    renderer = make_html_interpreter(state, skills)
    first = json.loads(
        await renderer(
            template_path=BUSINESS_TEMPLATE,
            data={
                "REPORT_SPEC": {
                    "title": "销售报告",
                    "sections": [
                        {
                            "heading": "地区",
                            "intro": [
                                ["合计", {"artifact_id": source, "field": "total"}]
                            ],
                            "table": {
                                "artifact_id": source,
                                "field": "rows",
                                "columns": ["region", "salse"],
                            },
                        }
                    ],
                }
            },
        )
    )
    assert first["retryable"] is True
    assert await report_repair.render_saved_report(
        state, skills, allow_unavailable_references=True
    )
    old_html = state["_report_presentation"]["content"]
    assert "<table" not in old_html and state["_report_success_response"]
    state["_report_lock_after_completion"] = True
    table = object_id(ReportObjects(sink.snapshot()), "table", "rows")
    repair = {"section_index": 0, "section": {"table": {"object_id": table}}}
    return state, renderer, repair, old_html


def _assert_repaired_delivery(state, response, old_html):
    """The deliverable is the freshly rendered report, not the cached partial."""
    assert response["status"] == "completed", response
    assert any(chunk["output_type"] == "html" for chunk in response["chunks"])
    html = state["_report_presentation"]["content"]
    assert "<table" in html and "华东" in html
    assert html != old_html and "部分表格" not in html
    assert not state.get("_report_html_error")


@pytest.mark.asyncio
async def test_staged_repair_supersedes_cached_partial_in_same_turn(
    tmp_path, monkeypatch
):
    from dbgpt.agent.resource.tool.pack import ToolPack

    state, renderer, repair, old_html = await _cached_partial_repair_context(
        tmp_path, monkeypatch, "stale-cache-compose"
    )
    wrappers = make_report_object_tools(
        state, renderer, BUSINESS_TEMPLATE, SPEC_CONTRACT
    )
    pack = ToolPack([entry._tool for entry in wrappers])
    staged = json.loads(
        await pack.async_execute(resource_name="patch_report", render=False, **repair)
    )
    assert staged["status"] == "staged"
    # Even with the completion lock engaged, committing the staged draft must
    # render it instead of returning the cached table-less partial.
    completed = json.loads(await pack.async_execute(resource_name="compose_report"))
    _assert_repaired_delivery(state, completed, old_html)


@pytest.mark.asyncio
async def test_agent_may_continue_to_compose_after_staging_a_repair(
    tmp_path, monkeypatch
):
    from dbgpt.agent import AgentContext, AgentMessage
    from dbgpt.agent.expand.tool_calling_agent import ToolCallingReActAgent
    from dbgpt.agent.resource.tool.pack import ToolPack

    state, renderer, repair, old_html = await _cached_partial_repair_context(
        tmp_path, monkeypatch, "stale-cache-agent"
    )
    wrappers = make_report_object_tools(
        state, renderer, BUSINESS_TEMPLATE, SPEC_CONTRACT
    )
    pack = ToolPack([entry._tool for entry in wrappers])
    agent = ToolCallingReActAgent()
    agent.agent_context = AgentContext(
        conv_id="stale-cache-agent", enable_native_function_calling=True
    )
    agent.resource = pack
    for action in agent.actions:
        action.init_resource(pack)
    object.__setattr__(agent, "_report_repair_state", state)

    async def drive(name, arguments):
        calls = [
            {
                "function": {
                    "name": name,
                    "arguments": json.dumps(arguments, ensure_ascii=False),
                }
            }
        ]
        object.__setattr__(agent, "_pending_native_tool_calls", calls)
        return await agent.act(
            AgentMessage(content=""),
            sender=agent,
            parser=agent.parser,
            enable_parallel=False,
            tool_calls=calls,
        )

    staged = await drive("patch_report", {**repair, "render": False})
    assert staged.is_exe_success
    # Staging accepted pending content; the cached partial no longer represents
    # a completed delivery, so the repair turn must not terminate here.
    assert staged.terminate is not True
    completed = await drive("compose_report", {})
    assert completed.is_exe_success
    assert completed.terminate is True
    html = state["_report_presentation"]["content"]
    assert "<table" in html and "华东" in html and html != old_html


@pytest.mark.asyncio
async def test_immediate_render_over_cached_partial_repairs_the_report(
    tmp_path, monkeypatch
):
    state, renderer, repair, old_html = await _cached_partial_repair_context(
        tmp_path, monkeypatch, "stale-cache-immediate"
    )
    _, _, patch = make_report_object_tools(
        state, renderer, BUSINESS_TEMPLATE, SPEC_CONTRACT
    )
    result = json.loads(await patch(**repair))
    _assert_repaired_delivery(state, result, old_html)


@pytest.mark.asyncio
async def test_compose_cancellation_restores_the_staged_draft(tmp_path, monkeypatch):
    import asyncio

    state, renderer, repair, _ = await _cached_partial_repair_context(
        tmp_path, monkeypatch, "stale-cache-cancel"
    )
    armed = {"cancel": True}

    async def cancelling_renderer(**kwargs):
        if armed["cancel"]:
            armed["cancel"] = False
            raise asyncio.CancelledError
        return await renderer(**kwargs)

    _, compose, patch = make_report_object_tools(
        state, cancelling_renderer, BUSINESS_TEMPLATE, SPEC_CONTRACT
    )
    staged = json.loads(await patch(render=False, **repair))
    assert staged["status"] == "staged"
    draft = state["_report_object_spec"]
    with pytest.raises(asyncio.CancelledError):
        await compose()
    # Cancellation keeps the existing recovery semantics: the draft returns to
    # the pending state and the next compose renders it.
    assert state["_report_object_spec"] == draft
    completed = json.loads(await compose())
    assert completed["status"] == "completed", completed
    html = state["_report_presentation"]["content"]
    assert "<table" in html and "华东" in html


@pytest.mark.asyncio
async def test_render_failure_after_commit_keeps_the_candidate_for_recovery(
    tmp_path, monkeypatch
):
    state, renderer, repair, _ = await _cached_partial_repair_context(
        tmp_path, monkeypatch, "stale-cache-failure"
    )
    state["_report_required_recommendation_count"] = 3
    _, compose, patch = make_report_object_tools(
        state, renderer, BUSINESS_TEMPLATE, SPEC_CONTRACT
    )
    staged = json.loads(await patch(render=False, **repair))
    assert staged["status"] == "staged"
    failed = json.loads(await compose())
    assert "REPORT_REQUIREMENT_MISSING" in json.dumps(failed, ensure_ascii=False)
    assert failed["retryable"] is True
    # A normal render error must not put the committed candidate back as a
    # pending draft: render_saved_report stops while _report_object_spec is
    # set, and the saved arguments already carry the corrected table.
    assert state.get("_report_object_spec") is None
    assert state["_report_html_error"]
    saved_table = state["_report_saved_arguments"]["data"]["REPORT_SPEC"]["sections"][
        0
    ]["table"]
    assert saved_table["columns"] == ["region", "sales"]
    checkpoint = json.loads(
        (tmp_path / "tmp/stale-cache-failure/report-repair/checkpoint.json").read_text(
            encoding="utf-8"
        )
    )
    assert checkpoint["error"]
    assert checkpoint["arguments"]["data"]["REPORT_SPEC"]["sections"][0]["table"][
        "columns"
    ] == ["region", "sales"]


@pytest.mark.asyncio
async def test_staged_draft_composes_after_checkpoint_restore(tmp_path, monkeypatch):
    from dbgpt_app.openapi.api_v1.tools import report_repair

    state, renderer, repair, old_html = await _cached_partial_repair_context(
        tmp_path, monkeypatch, "stale-cache-restore"
    )
    _, _, patch = make_report_object_tools(
        state, renderer, BUSINESS_TEMPLATE, SPEC_CONTRACT
    )
    staged = json.loads(await patch(render=False, **repair))
    assert staged["status"] == "staged"
    # A new request rebuilds its state from the checkpoint; the previous
    # request's cached deliverable never comes along.
    fresh = {"conv_id": "stale-cache-restore"}
    restored = report_repair.restore_report_checkpoint("stale-cache-restore", fresh)
    assert restored is not None
    fresh["_report_artifact_sink"] = restored
    _, fresh_compose, _ = make_report_object_tools(
        fresh,
        make_html_interpreter(fresh, _business_skills_dir()),
        BUSINESS_TEMPLATE,
        SPEC_CONTRACT,
    )
    completed = json.loads(await fresh_compose())
    _assert_repaired_delivery(fresh, completed, old_html)


@pytest.mark.asyncio
async def test_named_template_accepts_new_content_over_a_cached_render(
    tmp_path, monkeypatch
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
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="named-supersede"))
    capture(sink, {"total": 100})
    token = object_id(ReportObjects(sink.snapshot()), "value", "total")
    state = {
        "conv_id": "named-supersede",
        "_report_artifact_sink": sink,
        "_report_required_recommendation_count": 3,
    }
    renderer = make_html_interpreter(state, str(tmp_path))
    _, compose, stage_field = make_report_object_tools(
        state, renderer, "report.html", report_template_contract(template)
    )

    def summary(prefix):
        return [f"{prefix}总结，合计 ", {"object_id": token}, "。"]

    def advice(prefix):
        return [
            f"建议一：{prefix}复核成本结构。",
            f"建议二：{prefix}跟踪逾期回款。",
            f"建议三：{prefix}复核融资期限。",
        ]

    first = json.loads(
        await compose(data={"SUMMARY": summary("初始"), "ADVICE": advice("")})
    )
    assert first["status"] == "completed", first
    state["_report_lock_after_completion"] = True
    cached = state["_report_success_response"]

    # Fully rejected content accepts nothing and keeps the cached deliverable.
    rejected = json.loads(
        await compose(data={"SUMMARY": "<b>非法</b>", "ADVICE": "<i>非法</i>"})
    )
    assert rejected["status"] == "invalid_selection"
    assert state["_report_success_response"] == cached

    # One retained field is newly accepted content: after correcting the
    # rejected field, compose must render it instead of the cached report.
    mixed = json.loads(
        await compose(data={"SUMMARY": summary("修订后的"), "ADVICE": "<i>非法</i>"})
    )
    assert mixed["status"] == "invalid_selection"
    assert "SUMMARY" in mixed["error"]
    staged = json.loads(stage_field("ADVICE", advice("修订后")))
    assert staged["status"] == "staged" and staged["ready_to_compose"]
    final = json.loads(await compose())
    assert final["status"] == "completed", final
    html = state["_report_presentation"]["content"]
    assert "修订后的" in html and "修订后复核成本结构" in html
    assert "初始总结" not in html
