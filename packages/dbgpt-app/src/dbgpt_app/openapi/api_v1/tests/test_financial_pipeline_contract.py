"""Financial statement provenance and captured-input contract."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[7]


def load_script(name):
    path = ROOT / "skills" / "financial-report-analyzer" / "scripts" / (name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_statement_rows_are_scoped_and_keep_years_and_provenance(tmp_path):
    script = load_script("extract_financials")
    path = tmp_path / "report.txt"
    path.write_text(
        "2019年年度报告\n医药 1,608,858,743.47 54.70%\n"
        "1、合并资产负债表\n单位：元\n项目 2019年12月31日 2018年12月31日\n"
        "流动负债合计 940,281,788.69 1,579,026,351.68\n"
        "负债合计 1,022,736,568.92 1,644,823,412.34\n"
        "2、母公司资产负债表\n单位：元\n项目 2019年12月31日 2018年12月31日\n"
        "负债合计 525,802,580.88 692,654,284.96\n"
        "3、合并利润表\n单位：元\n项目 2019年度 2018年度\n"
        "其中：营业收入 2,941,412,770.30 2,718,608,796.51\n"
        "其中：营业成本 1,463,159,361.04 1,511,944,676.18\n",
        encoding="utf-8",
    )
    result = script.extract_financials(str(path))
    assert result["total_liabilities"] == 1022736568.92
    assert result["cost_of_sales"] == 1463159361.04
    assert result["prev_cost_of_sales"] == 1511944676.18
    assert result["_meta"]["sources"]["cost_of_sales"]["page"] == 1
    assert (
        load_script("calculate_ratios").calculate_template_data(result)["GROSS_MARGIN"]
        == "50.26%"
    )


def test_unknown_or_ambiguous_statement_is_not_guessed(tmp_path):
    script = load_script("extract_financials")
    path = tmp_path / "report.txt"
    path.write_text("2019年年度报告\n营业成本 123\n", encoding="utf-8")
    assert script.extract_financials(str(path))["cost_of_sales"] is None
    path.write_text(
        "2019年年度报告\n1、合并利润表\n单位：元\n项目 2019年度 2018年度\n"
        "营业成本 100 90\n营业成本 200 90\n",
        encoding="utf-8",
    )
    assert script.extract_financials(str(path))["cost_of_sales"] is None


def test_percentage_point_precision_preserves_reportable_value():
    script = load_script("calculate_ratios")
    assert script.format_pp_change(0.1346, 0.1122)[0] == "+2.24pp"


def test_inline_financial_units_use_captured_values():
    from dbgpt.core.interface.report_capture import (
        ArtifactCaptureContext,
        InMemoryArtifactSink,
        capture_python_execution,
    )
    from dbgpt_app.openapi.api_v1.tools.html_interpreter import (
        _resolve_inline_report_references,
    )

    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="financial-units"))
    source = capture_python_execution(
        code="metrics",
        duration_ms=1,
        status="succeeded",
        exit_code=0,
        stdout="",
        stderr="",
        artifact_sink=sink,
        result_inline={"revenue": 2941412770.3, "ratio": 0.262},
    )
    content = (
        f"<strong>{{artifact_id:{source},field:revenue,format:亿元}}</strong> 亿元 "
        f"{{artifact_id:{source},field:ratio,format:百分比}}"
    )
    rendered = _resolve_inline_report_references(content, sink.snapshot())
    assert "29.41亿元</span></strong> " in rendered
    assert "</strong> 亿元" not in rendered
    assert "26.20%</span>" in rendered


def test_scaled_amount_requires_matching_raw_sibling():
    from dbgpt.core.interface.report_capture import (
        ArtifactCaptureContext,
        InMemoryArtifactSink,
        capture_python_execution,
    )
    from dbgpt_app.openapi.api_v1.tools.html_interpreter import (
        _numeric_evidence_validator,
    )

    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="scaled-evidence"))
    source = capture_python_execution(
        code="metrics",
        duration_ms=1,
        status="succeeded",
        exit_code=0,
        stdout="",
        stderr="",
        artifact_sink=sink,
        result_inline={
            "metrics": {"debt": 482938909.59, "debt_yi": 4.83, "other_yi": 4.83}
        },
    )
    validate = _numeric_evidence_validator(sink.snapshot())

    def binding(field):
        return {
            "artifact_ids": [source],
            "artifact_selectors": {source: {"field": "metrics", "path": [field]}},
        }

    assert validate("4.83亿元", binding("debt_yi"), "4.83亿元")
    assert not validate("4.83亿元", binding("other_yi"), "4.83亿元")
    assert not validate("4.84亿元", binding("debt_yi"), "4.84亿元")


def test_chart_markup_resolves_only_captured_image():
    from dbgpt.core.interface.report_capture import (
        ArtifactCaptureContext,
        InMemoryArtifactSink,
        capture_chart_execution,
    )
    from dbgpt_app.openapi.api_v1.tools.html_interpreter import (
        _render_template_with_bindings,
        _result_number,
    )

    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="finance-chart"))
    chart = capture_chart_execution(
        input_artifact_ids=[],
        chart_type="image",
        spec={},
        action="chart",
        output_uri="/images/chart.png",
        output_inline={},
        artifact_sink=sink,
    )
    template = '<img src="{{CHART_OVERVIEW}}">'
    markup = f'<div data-dbgpt-artifacts="{chart}"><img src="/images/chart.png"></div>'
    result = _render_template_with_bindings(
        template, {"CHART_OVERVIEW": markup}, sink.snapshot()
    )
    assert result == '<img src="/images/chart.png">'
    with pytest.raises(ValueError, match="exactly one captured"):
        _render_template_with_bindings(
            template,
            {"CHART_OVERVIEW": '<img src="/images/other.png">'},
            sink.snapshot(),
        )
    assert _result_number("+5.9pp")[0] == _result_number("5.9个百分点")[0]


def test_skill_contract_uses_captured_result_instead_of_model_values(monkeypatch):
    from dbgpt.agent import claude_skill
    from dbgpt_app.openapi.api_v1.tools.skill_tools import _apply_skill_input_contract

    skill = SimpleNamespace(
        file_path=str(ROOT / "skills" / "financial-report-analyzer" / "SKILL.md")
    )
    monkeypatch.setattr(
        claude_skill, "get_registry", lambda: SimpleNamespace(get_skill=lambda _: skill)
    )
    artifact = SimpleNamespace(
        artifact_id="python-1",
        type="python",
        status="succeeded",
        metadata={
            "skill_name": "financial-report-analyzer",
            "script_file_name": "extract_financials.py",
        },
        result=SimpleNamespace(inline={"revenue": 100}, uri=None),
    )
    sink = SimpleNamespace(snapshot=lambda: [artifact])
    value, ids = _apply_skill_input_contract(
        "financial-report-analyzer", "calculate_ratios.py", {"revenue": 999}, [], sink
    )
    assert value == {"revenue": 100}
    assert ids == ["python-1"]
    with pytest.raises(ValueError, match="SKILL_INPUT_REQUIRED"):
        _apply_skill_input_contract(
            "financial-report-analyzer",
            "calculate_ratios.py",
            {},
            [],
            SimpleNamespace(snapshot=lambda: []),
        )


def test_verified_template_field_ignores_model_override():
    from dbgpt.core.interface.report_capture import (
        ArtifactCaptureContext,
        InMemoryArtifactSink,
        capture_python_execution,
    )
    from dbgpt_app.openapi.api_v1.tools.html_interpreter import (
        _render_template_with_bindings,
    )

    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="financial-source"))
    common = {
        "duration_ms": 1,
        "status": "succeeded",
        "exit_code": 0,
        "stdout": "",
        "stderr": "",
        "artifact_sink": sink,
    }
    original = capture_python_execution(
        code="extract",
        result_inline={"revenue": 100},
        metadata={"skill_name": "finance", "script_file_name": "extract.py"},
        **common,
    )
    producer = capture_python_execution(
        code="calculate",
        result_inline={"GROSS_MARGIN_CHANGE": "+5.9pp", "MISSING_METRIC": "N/A"},
        input_artifact_ids=[original],
        metadata={
            "skill_name": "finance",
            "script_file_name": "calculate.py",
            "captured_input_contract": True,
        },
        **common,
    )
    template = (
        "<!-- dbgpt-verified-fields: extract.py | calculate.py | "
        "GROSS_MARGIN_CHANGE, MISSING_METRIC -->"
        "<p>{{GROSS_MARGIN_CHANGE}}</p><p>{{MISSING_METRIC}}</p>"
    )
    html = _render_template_with_bindings(
        template, {"GROSS_MARGIN_CHANGE": "45.3%"}, sink.snapshot()
    )
    assert "+5.9pp" in html
    assert "45.3%" not in html
    assert "未取得数据" in html
    assert producer in html


def test_report_with_unverified_values_is_partial():
    import json

    from dbgpt_app.openapi.api_v1.subagent.report_agent import (
        _completed_report_response,
    )

    response = json.loads(
        _completed_report_response(
            {
                "_report_presentation": {"content": "<p>--</p>", "title": "Report"},
                "_report_warnings": [
                    "REPORT_NUMERIC_VALUE_UNAVAILABLE: missing selector"
                ],
            }
        )
    )
    assert response["status"] == "partial"
    assert "未完整完成" in response["chunks"][0]["content"]
