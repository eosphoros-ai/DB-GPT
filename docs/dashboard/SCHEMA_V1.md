# Dashboard Schema v1

## 1. Schema 的作用

`DashboardSchemaV1` 是看板的“说明书”。当前实现兼容 `1.0` 至 `1.4`：
`1.0` 表示基础单数据源看板，`1.1` 增加受控联邦查询，`1.2` 增加可选指标/维度口径与服务端数据血缘，
`1.3` 增加发布展示配置，`1.4` 增加可持久化的视觉主题与二创覆盖。
它不包含 React 组件实例，也不依赖某个图表库，而是回答：

- 这个看板分析什么；
- 数据来自哪里；
- 有哪些全局筛选器；
- 每个组件执行什么参数化 SQL；
- 查询结果的字段是什么；
- 字段如何映射到图表；
- 组件在 12 列网格中的位置；
- 看板由谁、在哪次会话中、用什么模型生成。

权威定义：

- Python：`packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/dashboard/schemas.py`
- JSON Schema：`packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/dashboard/schema/dashboard.schema.json`
- TypeScript：`web/types/dashboard.ts`

## 2. 顶层结构

```json
{
  "schema_version": "1.0",
  "dashboard": {},
  "metric_context": {},
  "filters": [],
  "widgets": [],
  "layouts": {},
  "metadata": {}
}
```

| 字段 | 作用 |
|---|---|
| `schema_version` | `1.0` 基础版；`1.1` 受控联邦；`1.2` 语义口径与 AST 血缘；`1.3` 发布展示；`1.4` 视觉主题 |
| `dashboard` | ID、标题、说明、数据源、状态、主题和时间 |
| `metric_context` | 数据粒度、时间范围、新鲜度、来源说明以及 1.2 指标/维度定义 |
| `filters` | 全局筛选器及默认值 |
| `widgets` | 组件、查询、输出字段、图表映射、样式和错误 |
| `layouts` | 桌面 12 列布局与移动端策略 |
| `metadata` | 会话、Agent 生成信息和兼容信息 |

所有模型都拒绝未知字段，避免模型拼错字段时被悄悄忽略。

## 3. 组件

支持五类：`kpi`、`line`、`bar`、`pie`、`table`。

```json
{
  "id": "monthly-sales",
  "type": "line",
  "title": "月度销售趋势",
  "description": "观察季节性变化",
  "query": {
    "data_source_id": "walmart_sales_demo",
    "sql": "SELECT SUBSTR(sale_date,1,7) AS month, SUM(weekly_sales) AS sales FROM walmart_sales WHERE sale_date BETWEEN :start_date AND :end_date GROUP BY SUBSTR(sale_date,1,7)",
    "filter_parameters": {
      "date": {
        "start_parameter": "start_date",
        "end_parameter": "end_date"
      }
    },
    "default_parameters": {},
    "output_fields": [
      {"name": "month", "type": "string", "label": "月份", "nullable": false},
      {"name": "sales", "type": "number", "label": "销售额", "nullable": true}
    ],
    "timeout_seconds": 15,
    "max_rows": 100,
    "grain": "月",
    "last_execution": {"status": "never"}
  },
  "encoding": {"x": "month", "y": "sales", "columns": []},
  "style": {"smooth": true}
}
```

### 3.1 字段映射要求

| 类型 | 必需映射 | 说明 |
|---|---|---|
| KPI | `value` | 展示一个数值 |
| 折线图 | `x`、`y` | 可选 `series` |
| 柱状图 | `x`、`y` | 可选 `series` |
| 饼图 | `angle` | `category`/`color` 指定分类 |
| 表格 | `columns` 可空 | 空时展示全部查询列 |

所有被映射字段必须在 `query.output_fields` 声明；真实查询结果也必须包含所有声明字段。

### 3.2 Schema 1.2 指标口径与血缘

- `metric_context.metrics` 声明指标 ID、业务定义、聚合方式、单位、粒度和口径来源；
- `metric_context.dimensions` 声明维度 ID、业务定义、物理字段和类型；
- Widget 用 `metric_ids` / `dimension_ids` 引用已定义口径；
- `query.lineage` 只接受服务端从 SQL AST 重算的表和字段，不信任模型自述。

没有指标目录时，Agent 可创建 `model_inferred` 口径，前端必须明确标注，不得冒充为企业标准指标。

### 3.3 查询绑定

- `data_source_id` 必须与看板级数据源一致；
- `sql` 只允许一条只读 SELECT/CTE；
- `filter_parameters` 把筛选器 ID 映射到 SQL 命名参数；
- `default_parameters` 只存固定参数，不接受字符串模板；
- `timeout_seconds` 范围 1–120 秒；
- `max_rows` 范围 1–5000，服务端额外取一行判断是否截断；
- `last_execution` 记录最近状态，不被当作权限依据。

### 3.4 Schema 1.4 视觉主题

视觉主题保存在 `dashboard.theme`，是看板合同的一部分，而不是浏览器本地偏好：

```json
{
  "preset": "clarity",
  "mode": "light",
  "overrides": {
    "primary_color": "#1D5FD1",
    "font_scale": "large",
    "density": "comfortable",
    "card_radius": 14,
    "card_shadow": "soft",
    "chart_palette": ["#1D5FD1", "#0F7B6C", "#7B4BA8"],
    "kpi_style": "accent",
    "table_style": "striped"
  }
}
```

- `preset` 使用中性命名：`clarity`、`ocean`、`warm`、`graphite`；每套均支持 `light` / `dark`；
- `overrides` 仅保存相对于主题默认值的二创项；“恢复默认”清空该对象；
- 自定义主色和图表色板必须通过服务端及浏览器端的对比度、重复色和色觉模拟检查；
- 多序列除颜色外还使用线型和点形区分，避免只依赖颜色传达含义；
- 旧值 `clean`、`business_blue` 读取时映射到 `clarity`，没有主题的历史看板回落到 `clarity/light`；
- 发布操作把整份 Schema 深拷贝到不可变修订，公开页只读取发布修订中的主题，不读取编辑草稿或本地状态。

## 4. 筛选器

### 4.1 日期范围

```json
{
  "id": "date",
  "type": "date_range",
  "label": "销售日期",
  "field": "sale_date",
  "default": ["2011-01-01", "2012-12-31"],
  "options": []
}
```

组件映射：

```json
{
  "date": {
    "start_parameter": "start_date",
    "end_parameter": "end_date"
  }
}
```

### 4.2 单选

```json
{
  "id": "year",
  "type": "select",
  "label": "财年",
  "field": "fiscal_year",
  "default": 2024,
  "options": [
    {"label": "FY2023", "value": 2023},
    {"label": "FY2024", "value": 2024}
  ]
}
```

组件映射：`{"year": "year"}`，SQL 使用 `:year`。

### 4.3 多选

```json
{
  "id": "stores",
  "type": "multi_select",
  "label": "门店",
  "field": "store",
  "default": [1, 2, 3],
  "options": []
}
```

SQL 写 `store IN (:stores)`。服务端把数组扩展成多个命名占位符，值仍通过数据库驱动绑定，不拼进 SQL 文本。

## 5. 布局

桌面布局使用 12 列网格：

```json
{
  "columns": 12,
  "desktop": [
    {"widget_id": "total-sales", "x": 0, "y": 0, "w": 4, "h": 3},
    {"widget_id": "monthly-sales", "x": 4, "y": 0, "w": 8, "h": 5}
  ],
  "mobile_strategy": "stack"
}
```

规则：

- `x + w` 不得超过 12；
- 一个组件只能出现一次；
- 每个组件都必须有布局；
- 移动端按 Schema 顺序单列堆叠；
- 编辑器将拖拽和缩放结果写回 `layouts.desktop`。

## 6. 错误状态

Agent 生成失败的组件仍保留：

```json
{
  "error": {
    "code": "planner_widget_failed",
    "message": "Query result is missing declared fields: sales.",
    "retryable": true
  }
}
```

前端显示错误、SQL 和重试入口；发布必须在错误清除且全部查询通过后才能进行。

## 7. 校验层次

```text
Pydantic / JSON Schema
  → 字段类型、范围、未知字段
跨字段规则
  → ID 唯一、布局、字段映射、筛选器参数
SQL AST
  → 单语句、只读、表/字段/函数允许范围
真实试运行
  → 数据库语法、结果字段、超时、空数据
发布前全量复验
  → 只有全部通过才生成快照
```

## 8. 版本策略

- 当前校验器接受 `schema_version = "1.0"` 至 `"1.4"`；
- `1.1` 是可选、向后兼容的受控联邦扩展，详细边界见
  [SCHEMA_1_1_FEDERATION.md](SCHEMA_1_1_FEDERATION.md)；
- 历史看板不会因为新版本存在而被批量改写；在编辑器保存新主题时才升级为 `1.4`；
- `1.4` 的主题配置位于既有 `schema_json`，不新增冗余版本列，也不需要数据库 DDL 迁移；
- 旧报告通过适配器生成 v1 草稿，不直接修改旧数据；
- 新版本应新增适配器，不在原字段上改变语义；
- `metadata.compatibility` 可记录原格式和迁移信息。
