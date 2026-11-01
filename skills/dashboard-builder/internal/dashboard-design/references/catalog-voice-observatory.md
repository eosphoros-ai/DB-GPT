# AI 语音趋势实验室

黑底玫红科技看板，结合响应延迟、表达评测、会话增长与交互构成。内置可查询的合成演示数据，可替换业务数据源。

Use this visual reference with dashboard-builder. Titles and chart kinds are suggestions; choose actual metrics and queries from the selected source. The reference contains no executable SQL or sample metric values.

```json
{
  "selection": "catalog:voice-observatory",
  "title": "AI 语音趋势实验室",
  "description": "黑底玫红科技看板，结合响应延迟、表达评测、会话增长与交互构成。内置可查询的合成演示数据，可替换业务数据源。",
  "theme": {
    "preset": "graphite",
    "mode": "dark",
    "overrides": {
      "primary_color": null,
      "font_scale": null,
      "density": "compact",
      "card_radius": 16,
      "card_shadow": "none",
      "chart_palette": null,
      "kpi_style": "quiet",
      "table_style": null
    }
  },
  "layouts": {
    "columns": 12,
    "desktop": [
      {
        "widget_id": "latency",
        "x": 0,
        "y": 0,
        "w": 3,
        "h": 4,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": 60
      },
      {
        "widget_id": "expression",
        "x": 3,
        "y": 0,
        "w": 3,
        "h": 4,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": 60
      },
      {
        "widget_id": "sessions",
        "x": 6,
        "y": 0,
        "w": 3,
        "h": 4,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": 60
      },
      {
        "widget_id": "voice_share",
        "x": 9,
        "y": 0,
        "w": 3,
        "h": 4,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": 60
      },
      {
        "widget_id": "latency_trend",
        "x": 0,
        "y": 4,
        "w": 6,
        "h": 8,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": 60
      },
      {
        "widget_id": "expression_ring",
        "x": 6,
        "y": 4,
        "w": 6,
        "h": 8,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": 60
      },
      {
        "widget_id": "growth",
        "x": 0,
        "y": 12,
        "w": 6,
        "h": 8,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": 60
      },
      {
        "widget_id": "interaction",
        "x": 6,
        "y": 12,
        "w": 6,
        "h": 8,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": 60
      }
    ],
    "mobile_strategy": "stack"
  },
  "compatibility": {
    "catalog_template_id": "voice-observatory",
    "catalog_presentation": {
      "style": "voice_observatory",
      "reference": "https://sive.antv.antgroup.com/NADVaGQL9OGp91pYxvm6"
    }
  },
  "widgets": [
    {
      "id": "latency",
      "suggested_type": "kpi",
      "reference_title": "平均语音响应",
      "style": {},
      "colors": []
    },
    {
      "id": "expression",
      "suggested_type": "kpi",
      "reference_title": "表达评测通过率",
      "style": {},
      "colors": []
    },
    {
      "id": "sessions",
      "suggested_type": "kpi",
      "reference_title": "累计交互会话",
      "style": {},
      "colors": []
    },
    {
      "id": "voice_share",
      "suggested_type": "kpi",
      "reference_title": "语音交互占比",
      "style": {},
      "colors": []
    },
    {
      "id": "latency_trend",
      "suggested_type": "line",
      "reference_title": "响应延迟变化",
      "style": {},
      "colors": []
    },
    {
      "id": "expression_ring",
      "suggested_type": "kpi",
      "reference_title": "表达评测表现",
      "style": {},
      "colors": []
    },
    {
      "id": "growth",
      "suggested_type": "line",
      "reference_title": "月度交互增长",
      "style": {},
      "colors": []
    },
    {
      "id": "interaction",
      "suggested_type": "pie",
      "reference_title": "交互方式构成",
      "style": {},
      "colors": []
    }
  ]
}
```
