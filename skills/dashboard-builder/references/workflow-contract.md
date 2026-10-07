# Dashboard Skill → Tool workflow contract

## Responsibility boundary

| Layer | Owns | Must not own |
|---|---|---|
| Dashboard Skill | intent, phase selection, tool order, stopping for confirmation | database writes, SQL safety decisions, revision bypasses |
| Dashboard Tools | plan persistence, query validation, trial execution, atomic draft changes | free-form user dialogue or hidden product decisions |
| Dashboard Service | authorization, optimistic concurrency, persistence, publication | model prompting |
| Editor | plan confirmation, proposal preview, manual edits, error recovery | trusting unvalidated model output |

## Phase sequence

```text
Natural-language goal
  -> sql_query (minimal discovery)
  -> plan_dashboard (no SQL)
  -> user confirmation
  -> create_dashboard_draft (parameterized SQL, at most two widgets per staged call)
  -> repair_dashboard_draft (failed widgets only, when needed)
  -> recoverable draft in the current task
```

Selection-aware annotations split into two capability sets:

```text
[修改组件] -> load persisted draft -> validate a stable-id proposal -> user applies/rejects
[指标解释] / [异常分析] -> load persisted context -> explain read-only evidence -> stop
```

The second path receives no SQL or Dashboard mutation tools. In anomaly mode the
program's stored evidence and conclusion are authoritative, including an
`indeterminate` result caused by missing data, insufficient samples, or a zero
denominator.

## Minimum plan example

```json
{
  "title": "门店经营看板",
  "description": "按门店和月份跟踪销售表现。",
  "business_theme": "门店经营复盘",
  "metrics": ["总销售额", "平均周销售额"],
  "dimensions": ["月份", "门店"],
  "filters": [
    {
      "id": "stores",
      "type": "multi_select",
      "label": "门店",
      "field": "Store",
      "default": [],
      "options": [{"label": "Store 1", "value": 1}]
    }
  ],
  "widgets": [
    {
      "id": "monthly-sales",
      "type": "line",
      "title": "月度销售趋势",
      "business_question": "销售额随月份如何变化？",
      "metric": "总销售额",
      "dimensions": ["月份"]
    }
  ]
}
```

The example is structural only. Values and options must be discovered from the
selected database rather than copied blindly.

## Failure policy

- Discovery failure: explain the missing table or field; do not invent it.
- Plan validation failure: correct the plan before asking for confirmation.
- One widget query failure: keep the other successful widgets and repair only
  the failed widget.
- Revision conflict: stop and reload the current revision; never overwrite.
- Unsafe SQL: accept the server rejection as authoritative and generate a new
  read-only query.
