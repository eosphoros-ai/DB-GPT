"""Report completion must preserve saved analysis and still require real advice."""

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from dbgpt.core.interface.report_capture import (
    ArtifactCaptureContext,
    InMemoryArtifactSink,
    bind_artifact_sink,
    capture_python_execution,
    capture_sql_execution,
)
from dbgpt_app.openapi.api_v1.subagent.report_agent import make_append_report_sections
from dbgpt_app.openapi.api_v1.tools.html_interpreter import make_html_interpreter
from dbgpt_app.openapi.api_v1.tools.report_charts import (
    analysis_groups,
    missing_analysis_groups,
)


def test_nested_python_table_counts_as_completed_analysis_but_images_do_not():
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="nested-analysis"))
    common = dict(
        code="REPORT_RESULT = ...",
        duration_ms=1,
        status="succeeded",
        exit_code=0,
        stdout="",
        stderr="",
        artifact_sink=sink,
    )
    identifier = capture_python_execution(
        **common,
        metadata={"agent_name": "地区表现"},
        result_inline={
            "tables": {
                "regions": {
                    "columns": ["region", "sales"],
                    "rows": [
                        {"region": "A", "sales": 10},
                        {"region": "B", "sales": 20},
                    ],
                }
            }
        },
    )
    capture_python_execution(
        **common,
        metadata={"agent_name": "只有图片"},
        result_inline={"images": ["a.png", "b.png"]},
    )
    groups = analysis_groups(sink.snapshot())
    assert groups == {"地区表现": [identifier]}
    selected = {
        "sections": [
            {
                "heading": "地区表现",
                "table": {
                    "artifact_id": identifier,
                    "path": ["tables", "regions"],
                    "columns": ["region", "sales"],
                },
            }
        ]
    }
    assert missing_analysis_groups(selected, groups) == []
    assert missing_analysis_groups(
        {
            "sections": [
                {
                    "heading": "建议",
                    "recommendations": [selected["sections"][0]],
                }
            ]
        },
        groups,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("extra_sections", [0, 6])
async def test_append_advice_completes_saved_report_without_replacing_analysis(
    tmp_path, monkeypatch, extra_sections
):
    from dbgpt_app.openapi.api_v1.tools import report_repair

    monkeypatch.setattr(report_repair, "PILOT_PATH", str(tmp_path))
    repository = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "skills/business-report").is_dir()
    )
    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="append-advice-test"))
    state = {
        "conv_id": "append-advice-test",
        "_report_artifact_sink": sink,
        "_report_required_recommendation_count": 3,
    }
    renderer = make_html_interpreter(state, str(repository / "skills"))
    with bind_artifact_sink(sink):
        artifact_id = capture_sql_execution(
            sql="SELECT 10 AS delayed_orders",
            database="test",
            duration_ms=1,
            columns=["delayed_orders"],
            rows=[{"delayed_orders": 10}],
        )
        section = {
            "heading": "配送分析",
            "intro": [
                [
                    "逾期订单数：",
                    {
                        "artifact_id": artifact_id,
                        "path": ["rows", 0, "delayed_orders"],
                    },
                ]
            ],
        }
        result = json.loads(
            await renderer(
                template_path="business-report/templates/business_report.html",
                title="配送报告",
                data={"REPORT_SPEC": {"title": "配送报告", "sections": [section]}},
            )
        )
        assert "REPORT_REQUIREMENT_MISSING" in str(result)
        saved = copy.deepcopy(state["_report_saved_arguments"]["data"]["REPORT_SPEC"])
        append = make_append_report_sections(state, renderer)
        for index in range(extra_sections):
            progress = json.loads(
                await append(
                    sections=[
                        {
                            "heading": "补充分析 " + chr(ord("A") + index),
                            "intro": [["复用既有配送分析结果，保留可追溯来源。"]],
                        }
                    ]
                )
            )
            assert progress["retryable"] is True
        advice = {
            "heading": "改进建议",
            "recommendations": [
                {
                    "title": title,
                    "lines": [{"parts": [description]}],
                }
                for title, description in [
                    (
                        "识别高风险订单",
                        "交接时检查预计送达日，优先处理存在延期风险的订单。",
                    ),
                    ("主动通知客户", "发现运输延迟时告知客户预计送达时间与处理入口。"),
                    ("复盘承运表现", "定期检查承运线路的延迟原因并跟进整改。"),
                ]
            ],
        }
        partial = copy.deepcopy(advice)
        last = partial["recommendations"].pop()
        incomplete = json.loads(await append(sections=[partial]))
        assert "REPORT_REQUIREMENT_MISSING" in str(incomplete)
        assert "found=2" in state["_report_html_error"]
        from dbgpt_app.openapi.api_v1.subagent import report_agent

        async def generate_reply(received_message, sender):
            prompt = received_message.content
            assert "引擎已重新校验" in prompt
            assert "已保存章节摘要" in prompt
            assert "第一个渲染调用必须使用" not in prompt
            await append(
                sections=[
                    {
                        "heading": "补充建议",
                        "recommendations": [last],
                    }
                ]
            )
            return SimpleNamespace(success=True, content="完成", context={})

        async def build_agent(**kwargs):
            return SimpleNamespace(generate_reply=generate_reply)

        monkeypatch.setattr(report_agent, "build_report_agent", build_agent)
        completed = json.loads(
            await report_agent.make_generate_report_tool(
                react_state=state,
                skills_dir=str(repository / "skills"),
                llm_client=object(),
            )("继续生成报告，保留全部分析并补齐第三条建议")
        )
        assert completed["status"] == "completed"
        assert not state.get("_report_html_error"), completed
        html = state["_report_presentation"]["content"]
        assert "识别高风险订单" in html
        assert "主动通知客户" in html
        assert "复盘承运表现" in html
        assert artifact_id in html
        spec = state["_report_saved_arguments"]["data"]["REPORT_SPEC"]
        assert spec["sections"][0] == saved["sections"][0]
        assert len(spec["sections"]) == 3 + extra_sections


@pytest.mark.asyncio
async def test_append_rejects_invalid_sections_before_changing_saved_content():
    state = {
        "_report_saved_arguments": {
            "template_path": "business-report/templates/business_report.html",
            "data": {"REPORT_SPEC": {"sections": [{"heading": "已保存"}]}},
        }
    }
    saved = copy.deepcopy(state)

    async def renderer(**kwargs):
        raise AssertionError("Invalid sections must not reach the renderer")

    append = make_append_report_sections(state, renderer)
    with pytest.raises(ValueError):
        await append(sections=[{"heading": "建议", "recommendations": ["空泛建议"]}])
    with pytest.raises(ValueError, match="one or two"):
        await append(sections=[])
    assert state == saved
