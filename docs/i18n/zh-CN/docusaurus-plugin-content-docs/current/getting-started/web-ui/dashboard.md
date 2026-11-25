---
sidebar_position: 3
title: 仪表盘
---

# 仪表盘

使用自然语言创建数据可视化和报告。DB-GPT 会将你的问题转换为 SQL 查询，并将结果渲染为交互式图表。

## 工作原理

```mermaid
graph LR
  Q[Natural Language Question] --> SQL[Text2SQL]
  SQL --> DB[(Database)]
  DB --> Data[Query Results]
  Data --> Chart[Chart Rendering]
```

1. 你使用自然语言提出与数据相关的问题
2. DB-GPT 自动生成对应的 SQL 查询
3. 查询在已连接的数据库上执行
4. 查询结果会被渲染为图表、表格或报告

## 快速开始

### 前置条件

- 已连接一个 DB-GPT 支持的数据库（参考 [Data Sources](/docs/getting-started/concepts/data-sources)）
- 已加载测试数据（可选，也可以使用内置示例）

### 使用 Dashboard

1. 在侧边栏进入 **Chat**
2. 选择 **Chat Dashboard** 模式（或新建一个 Dashboard 会话）
3. 从下拉菜单中选择目标数据库
4. 针对数据提出问题

**示例问题：**

```
Show me monthly sales trends as a line chart
What are the top 5 products by revenue? Show as a bar chart
Create a pie chart of customer distribution by region
```

## 图表类型

DB-GPT 的可视化引擎（[GPT-Vis](https://github.com/antvis/GPT-Vis)）支持以下图表：

| 图表类型 | 适用场景 |
|---|---|
| **Bar Chart** | 对比不同类别 |
| **Line Chart** | 展示时间趋势 |
| **Pie Chart** | 展示占比与分布 |
| **Table** | 查看详细数据 |
| **Scatter Plot** | 分析变量之间的相关性 |
| **Area Chart** | 展示累计趋势 |

:::tip 指定图表类型
在问题中明确写出你想要的图表类型，可以获得更精确的结果，例如：*"Show monthly revenue as a line chart"*。
:::

## 加载测试数据

DB-GPT 内置了可用于测试的示例数据：

```bash
# Linux / macOS
bash ./scripts/examples/load_examples.sh

# Windows
.\scripts\examples\load_examples.bat
```

这会将示例数据集导入 SQLite，你可以立即开始查询。

## 提升效果的建议

- **问题尽量具体**：例如 “Show the total order amount per month for 2024” 会比 “Show me some data” 更有效
- **明确图表类型**：在问题中写出 “bar chart”、“line chart” 等，有助于定向生成可视化
- **引用字段名**：如果你知道表结构，直接使用真实字段名可以提高准确性
- **逐步迭代**：可根据初次结果不断优化问题

## 下一步

| 主题 | 链接 |
|---|---|
| 连接更多数据库 | [Data Sources](/docs/getting-started/concepts/data-sources) |
| 查看聊天模式概览 | [Chat](/docs/getting-started/web-ui/chat) |
| Text2SQL 微调 | [Fine-Tuning](/docs/application/fine_tuning_manual/text_to_sql) |
