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


@pytest.mark.parametrize(
    "prefix",
    [
        "",
        "scripts/",
        "scripts\\",
        "/scripts/",
        "\\scripts\\",
        "./",
        "scripts/./",
        "./scripts/./",
    ],
)
@pytest.mark.parametrize(
    "upstream_prefix",
    [
        "",
        "scripts/",
        "scripts\\",
        "/scripts/",
        "\\scripts\\",
        "./",
        "scripts/./",
        "./scripts/./",
    ],
)
def test_skill_contract_uses_captured_result_instead_of_model_values(
    monkeypatch, prefix, upstream_prefix
):
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
            "script_file_name": upstream_prefix + "extract_financials.py",
        },
        result=SimpleNamespace(inline={"revenue": 100}, uri=None),
    )
    sink = SimpleNamespace(snapshot=lambda: [artifact])
    value, ids = _apply_skill_input_contract(
        "financial-report-analyzer",
        prefix + "calculate_ratios.py",
        {"revenue": 999},
        [],
        sink,
    )
    assert value == {"revenue": 100}
    assert ids == ["python-1"]
    explicit_value, explicit_ids = _apply_skill_input_contract(
        "financial-report-analyzer",
        prefix + "calculate_ratios.py",
        {"revenue": 999},
        ["python-1"],
        sink,
    )
    assert explicit_value == {"revenue": 100}
    assert explicit_ids == ["python-1"]

    with pytest.raises(ValueError, match="SKILL_INPUT_REQUIRED"):
        _apply_skill_input_contract(
            "financial-report-analyzer",
            "calculate_ratios.py",
            {},
            [],
            SimpleNamespace(snapshot=lambda: []),
        )


@pytest.mark.parametrize(
    "prefix",
    [
        "",
        "scripts/",
        "scripts\\",
        "/scripts/",
        "\\scripts\\",
        "./",
        "scripts/./",
        "./scripts/./",
    ],
)
def test_verified_template_field_ignores_model_override(prefix):
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
        metadata={"skill_name": "finance", "script_file_name": prefix + "extract.py"},
        **common,
    )
    producer = capture_python_execution(
        code="calculate",
        result_inline={"GROSS_MARGIN_CHANGE": "+5.9pp", "MISSING_METRIC": "N/A"},
        input_artifact_ids=[original],
        metadata={
            "skill_name": "finance",
            "script_file_name": prefix + "calculate.py",
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


@pytest.mark.parametrize(
    "parent_metadata",
    [
        None,
        {},
        {"skill_name": "finance", "script_file_name": ""},
        {"skill_name": "finance", "script_file_name": "invalid:extract.py"},
        {"skill_name": "finance", "script_file_name": "../extract.py"},
        {"skill_name": "finance", "script_file_name": 42},
    ],
)
@pytest.mark.parametrize("include_valid_parent", [False, True])
def test_verified_template_skips_unusable_parent_script_names(
    parent_metadata, include_valid_parent
):
    from dbgpt.core.interface.report_capture import (
        ArtifactCaptureContext,
        InMemoryArtifactSink,
        capture_python_execution,
    )
    from dbgpt_app.openapi.api_v1.tools.html_interpreter import (
        _render_template_with_bindings,
    )

    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="mixed-parents"))
    common = {
        "duration_ms": 1,
        "status": "succeeded",
        "exit_code": 0,
        "stdout": "",
        "stderr": "",
        "artifact_sink": sink,
    }
    unrelated = capture_python_execution(
        code="code_interpreter input", result_inline={"revenue": 100}, **common
    )
    parents = [unrelated]
    if include_valid_parent:
        parents.append(
            capture_python_execution(
                code="extract",
                result_inline={"revenue": 100},
                metadata={"skill_name": "finance", "script_file_name": "./extract.py"},
                **common,
            )
        )
    producer = capture_python_execution(
        code="calculate",
        result_inline={"VERIFIED_METRIC": "+5.9pp"},
        input_artifact_ids=parents,
        metadata={
            "skill_name": "finance",
            "script_file_name": "calculate.py",
            "captured_input_contract": True,
        },
        **common,
    )
    artifacts = [
        artifact.model_copy(update={"metadata": parent_metadata})
        if artifact.artifact_id == unrelated
        else artifact
        for artifact in sink.snapshot()
    ]
    html = _render_template_with_bindings(
        "<!-- dbgpt-verified-fields: extract.py | calculate.py | VERIFIED_METRIC -->"
        "<p>{{VERIFIED_METRIC}}</p>",
        {"VERIFIED_METRIC": "999"},
        artifacts,
    )
    assert "999" not in html
    if include_valid_parent:
        assert "+5.9pp" in html
        assert producer in html
    else:
        assert "未取得数据" in html
        assert "+5.9pp" not in html


@pytest.mark.parametrize(
    "script_name", [None, "", "invalid:calculate.py", "../calculate.py", 42]
)
def test_verified_template_skips_unusable_result_script_names(script_name):
    from dbgpt_app.openapi.api_v1.tools.html_interpreter import (
        _render_template_with_bindings,
    )

    producer = SimpleNamespace(
        artifact_id="invalid-producer",
        type="python",
        status="succeeded",
        metadata={
            "skill_name": "finance",
            "script_file_name": script_name,
            "captured_input_contract": True,
        },
        input_artifact_ids=[],
    )
    html = _render_template_with_bindings(
        "<!-- dbgpt-verified-fields: extract.py | calculate.py | VERIFIED_METRIC -->"
        "<p>{{VERIFIED_METRIC}}</p>",
        {"VERIFIED_METRIC": "999"},
        [producer],
    )
    assert "未取得数据" in html
    assert "999" not in html


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


@pytest.mark.parametrize(
    "name",
    [
        "../calculate_ratios.py",
        "scripts/../calculate_ratios.py",
        "C:/calculate_ratios.py",
        "",
        ".",
        "scripts/",
    ],
)
def test_unsupported_script_paths_fail_before_contract_or_execution(name):
    from dbgpt.agent.skill.manage import normalize_script_file_name

    with pytest.raises(ValueError, match="SKILL_SCRIPT_PATH_INVALID"):
        normalize_script_file_name(name)


def test_negative_table_offset_is_rejected_before_partial_render():
    from dbgpt_app.openapi.api_v1.tools.report_spec import validate_report_spec

    with pytest.raises(ValueError, match="REPORT_TEMPLATE_SPEC_INVALID"):
        validate_report_spec(
            {
                "sections": [
                    {
                        "heading": "Invalid window",
                        "table": {
                            "artifact_id": "source",
                            "columns": ["sales"],
                            "offset": -1,
                        },
                    }
                ]
            }
        )


@pytest.mark.parametrize(
    "legacy_name",
    ["../scripts/extract_financials.py", "", None, "C:/old/extract_financials.py"],
)
def test_invalid_history_does_not_block_selected_contract_source(
    monkeypatch, legacy_name
):
    from dbgpt.agent import claude_skill
    from dbgpt_app.openapi.api_v1.tools.skill_tools import _apply_skill_input_contract

    skill = SimpleNamespace(
        file_path=str(ROOT / "skills/financial-report-analyzer/SKILL.md")
    )
    monkeypatch.setattr(
        claude_skill, "get_registry", lambda: SimpleNamespace(get_skill=lambda _: skill)
    )

    def artifact(identity, name, revenue):
        return SimpleNamespace(
            artifact_id=identity,
            type="python",
            status="succeeded",
            metadata={
                "skill_name": "financial-report-analyzer",
                "script_file_name": name,
            },
            result=SimpleNamespace(inline={"revenue": revenue}, uri=None),
        )

    sink = SimpleNamespace(
        snapshot=lambda: [
            artifact("legacy", legacy_name, 999),
            artifact("valid", "extract_financials.py", 100),
        ]
    )
    args, ids = _apply_skill_input_contract(
        "financial-report-analyzer",
        "calculate_ratios.py",
        {"revenue": 999},
        ["valid"],
        sink,
    )
    assert args == {"revenue": 100} and ids == ["valid"]
    for explicit_ids in (["legacy"], ["missing"]):
        with pytest.raises(ValueError, match="SKILL_INPUT_REQUIRED"):
            _apply_skill_input_contract(
                "financial-report-analyzer",
                "calculate_ratios.py",
                {"revenue": 999},
                explicit_ids,
                sink,
            )
    for implicit_ids in (None, []):
        value, selected_ids = _apply_skill_input_contract(
            "financial-report-analyzer",
            "calculate_ratios.py",
            {"revenue": 999},
            implicit_ids,
            sink,
        )
        assert value == {"revenue": 100}
        assert selected_ids == ["valid"]
    with pytest.raises(ValueError, match="SKILL_SCRIPT_PATH_INVALID"):
        _apply_skill_input_contract(
            "financial-report-analyzer",
            "../scripts/calculate_ratios.py",
            {},
            ["valid"],
            sink,
        )


def test_same_file_contract_alias_cannot_bypass_captured_input(monkeypatch, tmp_path):
    from dbgpt.agent import claude_skill
    from dbgpt_app.openapi.api_v1.tools.skill_tools import _apply_skill_input_contract

    scripts = tmp_path / "scripts"
    scripts.mkdir()
    canonical = scripts / "calculate_ratios.py"
    canonical.write_text("print('test')", encoding="utf-8")
    alias = scripts / "CALCULATE_RATIOS.PY"
    if not alias.exists():
        # On a case-sensitive filesystem a hard link provides the same-file
        # alias; Windows naturally resolves this case variant to the same file.
        alias.hardlink_to(canonical)
    (tmp_path / "script_input_contract.json").write_text(
        '{"calculate_ratios.py":"extract_financials.py"}', encoding="utf-8"
    )
    skill = SimpleNamespace(file_path=str(tmp_path / "SKILL.md"))
    monkeypatch.setattr(
        claude_skill, "get_registry", lambda: SimpleNamespace(get_skill=lambda _: skill)
    )
    assert alias.samefile(canonical)
    with pytest.raises(ValueError, match="SKILL_SCRIPT_ALIAS_UNSUPPORTED"):
        _apply_skill_input_contract("finance", alias.name, {"revenue": 999}, [], None)


@pytest.mark.parametrize(
    "heading",
    [
        "母公司利润表",
        "2 母公司利润表",
        "2、母公司利润表",
        "（二）母公司利润表",
        "母公司利润表（续）",
    ],
)
def test_parent_statement_boundary_never_inherits_consolidated_scope(tmp_path, heading):
    path = tmp_path / "report.txt"
    path.write_text(
        "2019年年度报告\n1、合并利润表\n单位：元\n"
        "项目 2019年度 2018年度\n营业成本 100 90\n"
        + heading
        + "\n单位：元\n项目 2019年度 2018年度\n营业收入 999 888\n",
        encoding="utf-8",
    )
    result = load_script("extract_financials").extract_financials(str(path))
    assert result["revenue"] is None
    assert "revenue" not in result["_meta"]["sources"]
    assert result["cost_of_sales"] == 100


@pytest.mark.parametrize(
    "heading", ["合并利润表", "1 合并利润表", "1、合并利润表", "（一）合并利润表"]
)
def test_supported_consolidated_heading_variants_keep_provenance(tmp_path, heading):
    path = tmp_path / "report.txt"
    path.write_text(
        "2019年年度报告\n"
        + heading
        + "\n单位：元\n项目 2019年度 2018年度\n营业收入 100 90\n",
        encoding="utf-8",
    )
    result = load_script("extract_financials").extract_financials(str(path))
    assert result["revenue"] == 100 and result["prev_revenue"] == 90
    assert result["_meta"]["sources"]["revenue"]["statement"] == "合并利润表"


@pytest.mark.parametrize(
    "suffix",
    [
        "（单位：元）",
        " ( 单位: 元 )。",
        "：单位：元",
        "（续）",
        "（续表）（单位：元）",
        "（单位：万元）",
        "（未知后缀）",
    ],
)
@pytest.mark.parametrize(
    "heading", ["母公司利润表", "【母公司利 润 表{}】", "其他：母公司利 润 表{}"]
)
def test_parent_heading_suffix_cannot_inherit_consolidated_income(
    tmp_path, suffix, heading
):
    path = tmp_path / "report.txt"
    path.write_text(
        "2019年年度报告\n主要会计数据和财务指标（合并）\n营业收入（元） 500 400 300\n"
        "合并利润表\n单位：元\n项目 2019年度 2018年度\n"
        "营业收入 附注七、61 500 400\n营业成本 100 90\n"
        + (heading.format(suffix) if "{}" in heading else heading + suffix)
        + "\n项目 2019年度 2018年度\n营业收入 999 888\n",
        encoding="utf-8",
    )
    result = load_script("extract_financials").extract_financials(str(path))
    assert result["revenue"] == 500
    assert result["_meta"]["sources"]["revenue"]["statement"] == "合并利润表"
    assert result["cost_of_sales"] == 100
    calculated = load_script("calculate_ratios").calculate_template_data(result)
    assert calculated["REVENUE"] != "999.00元"
    assert calculated["GROSS_MARGIN"] != "89.99%"
    assert_financial_template_binding(result, calculated)


@pytest.mark.parametrize("suffix", ["（续）", "（续表）", "（续表）（单位：元）"])
def test_consolidated_continuation_keeps_its_own_context(tmp_path, suffix):
    path = tmp_path / "report.txt"
    path.write_text(
        "2019年年度报告\n合并利润表\n单位：元\n"
        "项目 2019年度 2018年度\n营业成本 100 90\n"
        + "合并利润表"
        + suffix
        + "\n营业收入 500 400\n",
        encoding="utf-8",
    )
    result = load_script("extract_financials").extract_financials(str(path))
    assert result["revenue"] == 500
    assert result["_meta"]["sources"]["revenue"]["statement"] == "合并利润表"
    calculated = load_script("calculate_ratios").calculate_template_data(result)
    assert calculated["GROSS_MARGIN"] == "80.00%"
    assert_financial_template_binding(result, calculated)


@pytest.mark.parametrize(
    "alias",
    [
        "./financial-report-analyzer",
        "financial-report-analyzer/.",
        "financial-report-analyzer\\.",
    ],
)
@pytest.mark.asyncio
async def test_skill_directory_alias_rejected_by_public_tool(alias):
    from dbgpt_app.openapi.api_v1.tools.skill_tools import (
        make_execute_skill_script_file,
    )

    execute = make_execute_skill_script_file({})
    result = await execute(
        skill_name=alias, script_file_name="calculate_ratios.py", args={"revenue": 999}
    )
    assert "SKILL_NAME_INVALID" in result
    assert "999.00" not in result


def assert_financial_template_binding(extracted, calculated):
    from unittest.mock import patch

    from dbgpt.agent import claude_skill
    from dbgpt.core.interface.report_capture import (
        ArtifactCaptureContext,
        InMemoryArtifactSink,
        capture_python_execution,
    )
    from dbgpt_app.openapi.api_v1.tools.html_interpreter import (
        _render_template_with_bindings,
    )
    from dbgpt_app.openapi.api_v1.tools.skill_tools import _apply_skill_input_contract

    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="boundary-binding"))
    common = dict(
        duration_ms=1,
        status="succeeded",
        exit_code=0,
        stdout="",
        stderr="",
        artifact_sink=sink,
    )
    upstream = capture_python_execution(
        code="extract_financials",
        result_inline=extracted,
        metadata={
            "skill_name": "financial-report-analyzer",
            "script_file_name": "extract_financials.py",
        },
        **common,
    )
    skill = SimpleNamespace(
        file_path=str(ROOT / "skills/financial-report-analyzer/SKILL.md")
    )
    model_args = {"revenue": 999, "cost_of_sales": 100}
    with patch.object(
        claude_skill, "get_registry", lambda: SimpleNamespace(get_skill=lambda _: skill)
    ):
        resolved, dependencies = _apply_skill_input_contract(
            "financial-report-analyzer",
            "calculate_ratios.py",
            model_args,
            [upstream],
            sink,
        )
    assert resolved == extracted
    assert dependencies == [upstream]
    assert (
        load_script("calculate_ratios").calculate_template_data(resolved) == calculated
    )
    producer = capture_python_execution(
        code="calculate_ratios",
        result_inline=calculated,
        input_artifact_ids=dependencies,
        metadata={
            "skill_name": "financial-report-analyzer",
            "script_file_name": "calculate_ratios.py",
            "captured_input_contract": resolved is not model_args,
        },
        **common,
    )
    template = (
        ROOT / "skills/financial-report-analyzer/templates/report_template.html"
    ).read_text(encoding="utf-8")
    fields = {
        key: "Qualitative explanation."
        for key in (
            "PROFITABILITY_ANALYSIS",
            "SOLVENCY_ANALYSIS",
            "EFFICIENCY_ANALYSIS",
            "CASHFLOW_ANALYSIS",
            "ADVANTAGES_LIST",
            "RISKS_LIST",
            "OVERALL_ASSESSMENT",
        )
    }
    html = _render_template_with_bindings(template, fields, sink.snapshot())
    assert "999.00" not in html
    assert "89.99%" not in html
    if extracted["revenue"] is not None:
        assert calculated["REVENUE"] in html
        assert calculated["GROSS_MARGIN"] in html
        assert producer in html


@pytest.mark.asyncio
@pytest.mark.parametrize("subdir", ["", "user", "claude", "project"])
async def test_contract_directory_case_alias_rejected_before_execution(
    monkeypatch, tmp_path, subdir
):
    from dbgpt.agent import claude_skill
    from dbgpt.configs import model_config
    from dbgpt_app.openapi.api_v1.tools.skill_tools import (
        make_execute_skill_script_file,
    )

    canonical = tmp_path / subdir / "financial-report-analyzer"
    canonical.mkdir(parents=True)
    (canonical / "script_input_contract.json").write_text(
        '{"calculate_ratios.py":"extract_financials.py"}', encoding="utf-8"
    )
    alias = canonical.with_name("FINANCIAL-REPORT-ANALYZER")
    if not alias.exists():
        alias.symlink_to(canonical, target_is_directory=True)
    assert alias.samefile(canonical)
    registry = claude_skill.SkillRegistry()
    registry.register_skill(
        SimpleNamespace(
            metadata=SimpleNamespace(name="financial-report-analyzer"),
            file_path=str(canonical / "SKILL.md"),
        )
    )
    monkeypatch.setattr(claude_skill, "get_registry", lambda: registry)
    monkeypatch.setattr(model_config, "SKILLS_DIR", str(tmp_path))
    execute = make_execute_skill_script_file({})
    result = await execute(
        skill_name=alias.name,
        script_file_name="calculate_ratios.py",
        args={"revenue": 999},
    )
    assert "SKILL_IDENTITY_MISMATCH" in result
    assert "999.00" not in result


@pytest.mark.parametrize(
    "units,expected",
    [(["万元"], 5000000), (["未知"], None), (["万元", "元"], 500), (["元"], 500)],
)
@pytest.mark.parametrize(
    "declaration",
    [
        "单位：{}",
        "（单位：{}）",
        "(单位：{})",
        "单 位：{}",
        "【（ 单 位 : {} ）】。",
        "币种：人民币；单位：{}",
    ],
)
def test_continuation_unit_declaration_supersedes_previous_unit(
    tmp_path, units, expected, declaration
):
    path = tmp_path / "report.txt"
    path.write_text(
        "2019年年度报告\n合并利润表\n单位：元\n"
        "项目 2019年度 2018年度\n营业成本 100 90\n合并利润表（续）\n"
        + "\n".join(declaration.format(unit) for unit in units)
        + "\n项目 2019年度 2018年度\n营业收入 500 400\n",
        encoding="utf-8",
    )
    result = load_script("extract_financials").extract_financials(str(path))
    assert result["revenue"] == expected
    if expected is None:
        assert "revenue" not in result["_meta"]["sources"]
    calculated = load_script("calculate_ratios").calculate_template_data(result)
    assert calculated["GROSS_MARGIN"] == (
        "N/A" if expected is None else "100.00%" if expected == 5000000 else "80.00%"
    )
    assert_financial_template_binding(result, calculated)


@pytest.mark.parametrize(
    "wrapper", ["{}", "（{}）", "【{}】", "[ {} ]", "（【 {} 】）"]
)
@pytest.mark.parametrize(
    "transition", ["parent", "unit", "unknown_unit", "year", "valid"]
)
@pytest.mark.parametrize("spacing", [False, True])
def test_financial_context_transition_matrix(tmp_path, wrapper, transition, spacing):
    parser = load_script("extract_financials")
    label = {
        "parent": "母公司利润表（单位：元）",
        "unit": "单位：万元",
        "unknown_unit": "单位：未知",
        "year": "项目 2020年度 2018年度",
        "valid": "单位：元",
    }[transition]
    if spacing:
        label = " ".join(label)
    path = tmp_path / "matrix.txt"
    path.write_text(
        "2019年年度报告\n合并利润表\n单位：元\n"
        "项目 2019年度 2018年度\n营业成本 100 90\n合并利润表（续）\n"
        + wrapper.format(label)
        + "\n营业收入 500 400\n",
        encoding="utf-8",
    )
    result = parser.extract_financials(str(path))
    assert result["revenue"] == (
        500 if transition == "valid" else 5000000 if transition == "unit" else None
    )
    assert ("revenue" in result["_meta"]["sources"]) == (
        transition in {"valid", "unit"}
    )
    assert result["cost_of_sales"] == 100


@pytest.mark.parametrize("contract_location", ["registered", "actual", "both"])
def test_execution_directory_must_match_contract_identity(
    tmp_path, monkeypatch, contract_location
):
    from dbgpt.agent import claude_skill
    from dbgpt_app.openapi.api_v1.tools.skill_tools import _apply_skill_input_contract

    registered = tmp_path / "registered"
    actual = tmp_path / "actual"
    registered.mkdir()
    actual.mkdir()
    for directory, name in [(registered, "registered"), (actual, "actual")]:
        if contract_location in (name, "both"):
            (directory / "script_input_contract.json").write_text(
                "{}", encoding="utf-8"
            )
    skill = SimpleNamespace(file_path=str(registered / "SKILL.md"))
    monkeypatch.setattr(
        claude_skill, "get_registry", lambda: SimpleNamespace(get_skill=lambda _: skill)
    )
    with pytest.raises(ValueError, match="SKILL_IDENTITY_MISMATCH"):
        _apply_skill_input_contract(
            "finance", "calculate.py", {}, [], None, execution_path=str(actual)
        )
    # Exact filesystem identity remains usable, including registered contracts.
    args = {}
    assert _apply_skill_input_contract(
        "finance", "calculate.py", args, [], None, execution_path=str(registered)
    ) == (args, [])


@pytest.mark.parametrize(
    "unit,factor",
    [
        ("元", 1),
        ("千元", 1000),
        ("万元", 10000),
        ("百万元", 1000000),
        ("亿元", 100000000),
    ],
)
@pytest.mark.parametrize("note", ["", "附注七、61 ", "61 ", "七、61 ", "（七） "])
def test_scaled_units_and_note_columns_preserve_source(tmp_path, unit, factor, note):
    path = tmp_path / "financial.txt"
    path.write_text(
        "2019年年度报告\n合并利润表\n单位："
        + unit
        + "\n项目 附注 2019年度 2018年度\n营业收入 "
        + note
        + "500.25 400.10\n营业成本 "
        + note
        + "100.05 80.02\n母公司利润表\n单位：元\n"
        "项目 2019年度 2018年度\n营业收入 999 888\n",
        encoding="utf-8",
    )
    extracted = load_script("extract_financials").extract_financials(str(path))
    assert extracted["revenue"] == 500.25 * factor
    assert extracted["cost_of_sales"] == 100.05 * factor
    source = extracted["_meta"]["sources"]["revenue"]
    assert source["unit"] == unit and source["normalized_unit"] == "元"
    assert source["unit_multiplier"] == factor
    assert source["raw_values"] == ["500.25", "400.10"]
    calculated = load_script("calculate_ratios").calculate_template_data(extracted)
    assert calculated["GROSS_MARGIN"] == "80.00%"
    assert_financial_template_binding(extracted, calculated)


@pytest.mark.parametrize("ambiguous", [False, True])
def test_engine_resolves_captured_chart_for_hidden_template_field(ambiguous):
    from dbgpt.core.interface.report_capture import (
        ArtifactCaptureContext,
        InMemoryArtifactSink,
        capture_chart_execution,
    )
    from dbgpt_app.openapi.api_v1.tools.html_interpreter import (
        _render_template_with_bindings,
    )

    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="chart-field"))
    capture_chart_execution(
        input_artifact_ids=[],
        chart_type="image",
        spec={},
        action="test",
        output_inline="first image",
        output_uri="/images/financial_overview.png",
        name="financial_overview.png",
        media_type="image/png",
        artifact_sink=sink,
    )
    if ambiguous:
        capture_chart_execution(
            input_artifact_ids=[],
            chart_type="image",
            spec={},
            action="test",
            output_inline="different image",
            output_uri="/images/other.png",
            name="financial_overview.png",
            media_type="image/png",
            artifact_sink=sink,
        )
        with pytest.raises(ValueError, match="ambiguous captured chart"):
            _render_template_with_bindings(
                '<img src="{{CHART_FINANCIAL_OVERVIEW}}">', {}, sink.snapshot()
            )
    else:
        html = _render_template_with_bindings(
            '<img src="{{CHART_FINANCIAL_OVERVIEW}}">', {}, sink.snapshot()
        )
        assert "/images/financial_overview.png" in html


@pytest.mark.parametrize(
    "fmt,expected",
    [
        (None, "80.00%"),
        ("percent", "80.00%"),
        ("pct1", "80.0%"),
        ("pct0", "80%"),
        ("percentage", "80.00%"),
        ("raw", "0.8"),
    ],
)
def test_captured_ratio_unit_controls_percent_display(fmt, expected):
    from dbgpt.core.interface.report_capture import (
        ArtifactCaptureContext,
        InMemoryArtifactSink,
        capture_python_execution,
    )
    from dbgpt_app.openapi.api_v1.tools.html_interpreter import _resolve_reference_node

    sink = InMemoryArtifactSink(ArtifactCaptureContext(conv_uid="ratio-display"))
    source = capture_python_execution(
        code="metrics",
        duration_ms=1,
        status="succeeded",
        exit_code=0,
        stdout="",
        stderr="",
        artifact_sink=sink,
        result_inline={"metric": {"value": 0.8, "unit": "ratio"}, "untyped": 0.8},
    )
    by_id = {a.artifact_id: a for a in sink.snapshot()}
    result = _resolve_reference_node(
        {"artifact_id": source, "path": ["metric", "value"], "format": fmt}, by_id
    )
    assert result["value"] == expected
    assert result["raw"] == 0.8
    assert result["selector"]["path"] == ["metric", "value"]
    untyped = _resolve_reference_node(
        {"artifact_id": source, "path": ["untyped"], "format": "percent"}, by_id
    )
    assert untyped["value"] == "0.80%"


@pytest.mark.parametrize("currency", ["人民币", "美元", "USD", "港币", "未知", ""])
@pytest.mark.parametrize("inline", [False, True])
def test_currency_label_does_not_add_input_restrictions(tmp_path, currency, inline):
    # Match main's acceptance policy: a currency label does not reject amounts.
    path = tmp_path / "currency.txt"
    heading = (
        "合并利润表（单位：元；币种：" + currency + "）\n"
        if inline
        else "合并利润表\n单位：元\n币种：" + currency + "\n"
    )
    path.write_text(
        "2019年年度报告\n"
        + heading
        + "项目 2019年度 2018年度\n营业收入 500 400\n营业成本 100 90\n",
        encoding="utf-8",
    )
    result = load_script("extract_financials").extract_financials(str(path))
    assert result["revenue"] == 500
    assert result["cost_of_sales"] == 100
    assert "warnings" not in result["_meta"]
    calculated = load_script("calculate_ratios").calculate_template_data(result)
    assert calculated["GROSS_MARGIN"] == "80.00%"
