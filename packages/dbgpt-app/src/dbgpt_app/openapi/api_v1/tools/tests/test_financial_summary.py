"""Completion prose and HTML must use the same saved financial snapshot."""

import json
from types import SimpleNamespace

import pytest

from dbgpt_app.openapi.api_v1.tools.financial_tools import (
    _result,
    finalize_financial_answer,
)
from dbgpt_serve.financial_analysis import workflow
from dbgpt_serve.financial_analysis.analysis import apply_findings, validate_findings
from dbgpt_serve.financial_analysis.exports import render_export
from dbgpt_serve.financial_analysis.report import build_report
from dbgpt_serve.financial_analysis.summary import (
    render_summary,
    report_summary,
    summary_context,
)


@pytest.fixture
def report():
    metrics = {
        "revenue": ("营业收入", "1200", "1000"),
        "net_profit": ("归母净利润", "120", "100"),
        "non_recurring_net_profit": ("扣非归母净利润", "90", "85"),
        "operating_cash_flow": ("经营现金流", "80", "130"),
        "cost_of_sales": ("营业成本", "720", "650"),
        "selling_expenses": ("销售费用", "90", "70"),
        "administrative_expenses": ("管理费用", "50", "60"),
        "research_expenses": ("研发费用", "80", "60"),
        "financial_expenses": ("财务费用", "-3", "-2"),
        "total_assets": ("资产总额", "2000", "1800"),
        "total_liabilities": ("负债总额", "800", "700"),
        "current_assets": ("流动资产", "1000", "900"),
        "current_liabilities": ("流动负债", "500", "450"),
        "inventory": ("存货", "200", "190"),
    }
    facts = []
    for code, (name, current, previous) in metrics.items():
        for year, value in (("2024", current), ("2023", previous)):
            facts.append(
                {
                    "id": f"fact-{code}-{year}",
                    "metricCode": code,
                    "metricName": name,
                    "rawValue": value,
                    "normalizedValue": value,
                    "fiscalPeriod": year,
                    "currency": "CNY",
                    "unit": "元",
                    "statementScope": "合并",
                    "attribution": "owners_of_parent"
                    if code in {"net_profit", "non_recurring_net_profit"}
                    else "consolidated",
                    "periodType": "instant"
                    if code
                    in {
                        "total_assets",
                        "total_liabilities",
                        "current_assets",
                        "current_liabilities",
                        "inventory",
                    }
                    else "flow",
                    "extractionStatus": "parsed",
                    "qualityStatus": "warning",
                    "evidenceExcerptIds": ["source"],
                }
            )
    result = build_report(
        {
            "report_year": "2024",
            "company_name": "测试公司",
            "document": {"id": "doc", "pageCount": 3},
            "facts": facts,
            "evidence": [
                {
                    "id": "source",
                    "sourceDocumentId": "doc",
                    "page": 2,
                    "snippet": "测试财务表格",
                }
            ],
        },
        {"id": "run", "completed_at": "2026-10-19T00:00:00+00:00"},
        SimpleNamespace(display_name="测试年报.pdf", file_id="file", size_bytes=1),
    )
    result["analysis"] = {"status": "partial", "completedAt": None}
    workflow.initialize(result)
    drafts = []
    for section, title, text, fact_ids, calc_ids in (
        (
            "overview",
            "收入与利润同步增长",
            "收入与利润均有增长：{{calculation:calc-revenue_yoy-2024}}，"
            "{{calculation:calc-net_profit_yoy-2024}}。",
            [],
            ["calc-revenue_yoy-2024", "calc-net_profit_yoy-2024"],
        ),
        (
            "profitability",
            "研发费用率上升",
            "研发投入占比提高：{{calculation:calc-research_expense_ratio_change-2024}}。",
            [],
            ["calc-research_expense_ratio_change-2024"],
        ),
        (
            "cashflow",
            "现金与利润存在差异",
            "经营现金流低于归母净利润：{{fact:fact-operating_cash_flow-2024}}，"
            "{{fact:fact-net_profit-2024}}。",
            ["fact-operating_cash_flow-2024", "fact-net_profit-2024"],
            [],
        ),
        (
            "balance",
            "资产负债结构",
            "资产负债结构可结合{{calculation:calc-debt_ratio-2024}}核对。",
            [],
            ["calc-debt_ratio-2024"],
        ),
    ):
        drafts.append(
            {
                "section": section,
                "title": title,
                "summary": text,
                "supportStatus": "partial",
                "factIds": fact_ids,
                "calculationIds": calc_ids,
                "evidenceExcerptIds": [],
            }
        )
    findings, _ = validate_findings(
        json.dumps({"findings": drafts}), result, strict=True
    )
    result = apply_findings(result, findings)
    ids = {"operating": 0, "expenses": 1, "cashflow": 2, "balance": 3}
    for topic in result["workflow"]["topics"]:
        topic["status"] = "ready"
        if topic["id"] in ids:
            topic["findingIds"] = [findings[ids[topic["id"]]]["id"]]
    workflow.review_report(
        result,
        [
            {
                "topic_id": topic_id,
                "verdict": "pass",
                "directionChecked": True,
                "scopeChecked": True,
                "causalityChecked": True,
                "note": "引用与方向已核对，具体原因仍需附注。",
            }
            for topic_id in workflow.TOPICS
        ],
    )
    return workflow.publish(result)


def final(content, report, **state):
    return finalize_financial_answer(
        content, dict(financial_report_context=report, **state)
    )


def test_published_tool_returns_summary_context_from_exact_revision(report):
    result = json.loads(_result(report, "session"))
    context = result["model_context"]["completion_context"]
    assert context["revision"] == report["revision"]
    assert context["statementScope"] == report["report"]["statementScope"]
    assert all(item["reference"].startswith("{{fact:") for item in context["facts"])
    assert "整体总结" in result["model_context"]["completion_instructions"]
    assert result["model_context"]["next_action"] is None
    assert result["chunks"][1]["content"] == report["agent"]["summary"]
    assert "个专题" not in result["chunks"][1]["content"]
    assert "已保存" not in result["chunks"][1]["content"]


def test_agent_business_summary_survives_and_matches_html_data(report, tmp_path):
    template = tmp_path / "runtime.html"
    template.write_text(
        "<script><!--FINANCIAL_REPORT_JSON--></script>", encoding="utf-8"
    )
    html = render_export(report, "html", template)
    exported = json.loads(html.removeprefix("<script>").removesuffix("</script>"))
    facts = {item["id"]: item for item in exported["facts"]}
    calcs = {item["id"]: item for item in exported["calculations"]}
    answer = final(
        "整体看，收入和利润同步增长，但现金流支撑仍需关注："
        "{{calculation:calc-revenue_yoy-2024}}，{{fact:fact-net_profit-2024}}，"
        "{{fact:fact-operating_cash_flow-2024}}。",
        report,
    )
    assert answer.startswith("整体看，收入和利润同步增长，但现金流支撑仍需关注")
    assert calcs["calc-revenue_yoy-2024"]["displayResult"] in answer
    assert facts["fact-net_profit-2024"]["displayValue"] in answer
    assert facts["fact-operating_cash_flow-2024"]["displayValue"] in answer
    assert "2024 年归母净利润" in answer
    assert "右侧报告" in answer
    assert "{{" not in answer
    assert "部分分析" not in answer


@pytest.mark.parametrize(
    "content",
    [
        "收入同比增长99%，{{fact:fact-revenue-2024}}。",
        "收入{{fact:fact-revenue-2024}}万元。",
        "未知指标{{fact:invented}}。",
        "旧数据{{fact:fact-revenue-2019}}。",
        "收入增加了{{fact:fact-revenue-2024}}。",
        "增长率为{{fact:fact-revenue-2024}}。",
        "偿债安全，{{calculation:calc-debt_ratio-2024}}。",
        "领先行业水平，{{calculation:calc-revenue_yoy-2024}}。",
        "归因于客户需求，{{calculation:calc-revenue_yoy-2024}}。",
        "分析已完成。",
    ],
)
def test_invalid_completion_falls_back_to_saved_findings(report, content):
    assert final(content, report).startswith(report_summary(report))


def test_percentage_point_and_negative_expense_use_canonical_display(report):
    context = summary_context(report)
    calculation = next(
        item
        for item in context["calculations"]
        if "research_expense_ratio_change" in item["id"]
    )
    answer = render_summary(
        "研发费用率上升：" + calculation["reference"] + "。", report
    )
    assert calculation["displayResult"] in answer
    assert "百分点" in answer
    # Negative expenses are a valid amount, not missing data.
    findings, _ = validate_findings(
        json.dumps(
            {
                "findings": [
                    {
                        "section": "profitability",
                        "title": "财务费用为负",
                        "summary": "财务费用为负："
                        "{{fact:fact-financial_expenses-2024}}。",
                        "supportStatus": "partial",
                        "factIds": ["fact-financial_expenses-2024"],
                        "calculationIds": [],
                        "evidenceExcerptIds": [],
                    }
                ]
            }
        ),
        report,
        strict=True,
    )
    findings[0]["id"] = "negative-fee"
    report["findings"].append(findings[0])
    workflow.topic(report, "expenses")["findingIds"].append("negative-fee")
    answer = render_summary(
        "财务费用为负：{{fact:fact-financial_expenses-2024}}。", report
    )
    assert "-3.00 元" in answer


def test_partial_report_retains_business_summary_and_precise_limitations(report):
    item = workflow.topic(report, "operating")
    item.update(status="failed", errorCode="FINDING_VALIDATION_FAILED")
    workflow.topic(report, "balance")["status"] = "insufficient"
    report["analysis"]["status"] = "partial"
    context = summary_context(report)
    assert "calc-revenue_yoy-2024" not in {
        item["id"] for item in context["calculations"]
    }
    assert "fact-total_assets-2024" not in {item["id"] for item in context["facts"]}
    answer = final(
        "现金流支撑仍需关注：{{fact:fact-operating_cash_flow-2024}}。", report
    )
    assert answer.startswith("现金流支撑仍需关注")
    assert "经营表现的分析结论尚待核对" in answer
    assert "资产负债与流动性的分析依据不足" in answer
    assert "缺数据" not in answer
    assert "个专题" not in answer
    assert "收入与利润均有增长" not in report_summary(report)
    assert render_summary(
        "{{calculation:calc-revenue_yoy-2024}}", report
    ) == report_summary(report)


def test_data_only_report_does_not_invent_a_business_summary(report):
    report["findings"] = []
    answer = final("公司经营稳健，收入翻倍。", report)
    assert "尚无可用于整体总结的分析结论" in answer
    assert "经营稳健" not in answer
    assert "翻倍" not in answer


def test_draft_does_not_claim_a_report_is_finished(report):
    report["workflow"]["status"] = "draft"
    workflow.sync(report)
    answer = final("报告已生成。", report)
    assert "正在" in answer
    assert "报告已生成" not in answer
    assert "完整报告" not in answer
    assert (
        "completion_context"
        not in json.loads(_result(report, "session"))["model_context"]
    )


def test_final_uses_current_snapshot_instead_of_numbers_from_chat_history(report):
    fact = next(item for item in report["facts"] if item["id"] == "fact-revenue-2024")
    fact.update(normalizedValue="1300", displayValue="1,300.00 元")
    report["revision"] = "new-revision"
    answer = final("本期情况：{{fact:fact-revenue-2024}}。", report)
    assert "1,300.00 元" in answer
    assert "1,200.00 元" not in answer
    assert summary_context(report)["revision"] == "new-revision"


def test_legacy_report_and_follow_up_remain_supported(report):
    report.pop("workflow")
    report["analysis"]["status"] = "partial"
    assert final("本期情况：{{fact:fact-net_profit-2024}}。", report).startswith(
        "本期情况：2024 年"
    )
    reading = json.loads(_result(report, "session", include_context=True, reading=True))
    assert "completion_context" not in reading["model_context"]
    answer = final(
        "本期情况：{{fact:fact-net_profit-2024}}。", report, financial_read=True
    )
    assert "120.00 元" in answer
    assert "原 PDF 物理第 2 页" in answer
    assert finalize_financial_answer("普通回答", {}) == "普通回答"


def test_failed_legacy_analysis_does_not_claim_it_is_still_running(report):
    report.pop("workflow")
    report["analysis"]["status"] = "failed"
    answer = final("公司经营稳健。", report)
    assert "尚未形成可用的分析结论" in answer
    assert "正在" not in answer


def test_fallback_preserves_limits_in_saved_summary(report):
    report["findings"][0]["summary"] += "变化原因缺少业务附注依据。"
    assert "变化原因缺少业务附注依据" in report_summary(report)
