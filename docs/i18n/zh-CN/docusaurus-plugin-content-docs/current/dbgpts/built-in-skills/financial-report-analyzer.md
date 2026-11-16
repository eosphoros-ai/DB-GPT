# financial-report-analyzer

## 概览

`financial-report-analyzer` 是一个用于上市公司年报、季报等财务报告深度分析的内置 skill。

它可以提取结构化财务数据、计算财务比率、生成图表，并渲染出适合交付的财务分析页面。

## 仓库路径

```text
skills/financial-report-analyzer/
├── SKILL.md
├── scripts/
│   ├── extract_financials.py
│   ├── calculate_ratios.py
│   ├── generate_charts.py
│   └── fill_template.py
├── references/
│   ├── analysis_framework.md
│   └── financial_metrics.md
└── templates/
    ├── report_template.html
    └── report_template.md
```

## 适用场景

- 分析年报或季报
- 提取核心财务指标
- 计算盈利能力、偿债能力等指标
- 生成财务图表
- 输出专业 HTML 财务分析报告

## 核心工作流

1. 运行 `extract_financials.py`，将原始财报整理成结构化数据。
2. 运行 `calculate_ratios.py`，计算关键财务指标。
3. 运行 `generate_charts.py`，生成报告所需图表。
4. 编写 skill 要求的分析叙述内容。
5. 使用 `html_interpreter` 和自带模板渲染最终输出。

## 关键资源

| 资源 | 作用 |
|---|---|
| `scripts/extract_financials.py` | 从财报文件中提取核心财务数据 |
| `scripts/calculate_ratios.py` | 计算模板所需的关键比率字段 |
| `scripts/generate_charts.py` | 生成报告中使用的图表资源 |
| `references/financial_metrics.md` | 定义财务指标与公式 |
| `references/analysis_framework.md` | 定义分析结构和解释逻辑 |
| `templates/report_template.html` | 最终 HTML 报告模板 |

## 输出预期

这个 skill 重点支持以下结构化分析输出：

- 盈利能力
- 偿债能力与风险
- 运营效率
- 现金流与盈利质量
- 优势与风险
- 整体结论与评估
