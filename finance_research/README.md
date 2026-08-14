# Finance Research — 公开财报采集分析与可追溯研究报告

基于 [DB-GPT](https://github.com/eosphoros-ai/DB-GPT) 构建的垂直能力包，打通
「公开资料发现 → 解析 → 指标抽取 → 来源追踪 → 分析 → 引用报告」完整链路。

## 目录结构

```
finance_research/
├── search/       # 可配置搜索接入层（Baidu / Mock / 可扩展 Tavily 等）
├── parse/        # HTML 网页表格解析 + PDF 财报解析
├── extract/      # 指标结构化抽取（LLM JSON + 规则兜底）
├── store/        # 来源追踪数据模型 + 仓储层
├── analyze/      # 趋势 / 同比 / 公司对比分析
├── report/       # 带数据引用的 Markdown 报告生成
├── pipeline.py   # 端到端编排
└── skill.py      # DB-GPT Skill 集成
```

## 快速开始（离线演示，无需 API key）

```bash
# 单公司财报分析
python examples/finance_single_company.py

# 多公司财务对比
python examples/finance_multi_company.py
```

## 接入真实搜索与 LLM

1. 设置 DeepSeek API key（用于 LLM 结构化抽取）：

```bash
export DEEPSEEK_API_KEY=sk-xxx
```

2. 在代码中把搜索 provider 换成 `BaiduSearchProvider` 或自行实现
   `SearchProvider` 接入 Tavily / SerpAPI 等。

## 来源追踪

每条指标都通过 `provenance_id` 关联到来源记录（URL / 文件 / 页码 / 表名 /
抽取时间 / 证据原文），报告末尾自动生成「数据引用」清单，使结论可回溯。
