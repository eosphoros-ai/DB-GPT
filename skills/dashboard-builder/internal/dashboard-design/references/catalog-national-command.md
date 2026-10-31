# 全国经营指挥大屏

蓝青科技大屏，以全国地图为中心，联动收入、交付、品类与省区排名。内置合成演示数据，支持全屏与明细放大。

Use this visual reference with dashboard-builder. Titles and chart kinds are suggestions; choose actual metrics and queries from the selected source. The reference contains no executable SQL or sample metric values.

```json
{
  "selection": "catalog:national-command",
  "title": "全国经营指挥大屏",
  "description": "蓝青科技大屏，以全国地图为中心，联动收入、交付、品类与省区排名。内置合成演示数据，支持全屏与明细放大。",
  "theme": {
    "preset": "graphite",
    "mode": "dark",
    "overrides": {
      "primary_color": null,
      "font_scale": null,
      "density": "compact",
      "card_radius": 3,
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
        "widget_id": "revenue",
        "x": 0,
        "y": 0,
        "w": 3,
        "h": 3,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": 40
      },
      {
        "widget_id": "orders",
        "x": 3,
        "y": 0,
        "w": 3,
        "h": 3,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": 40
      },
      {
        "widget_id": "units",
        "x": 6,
        "y": 0,
        "w": 3,
        "h": 3,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": 40
      },
      {
        "widget_id": "regions",
        "x": 9,
        "y": 0,
        "w": 3,
        "h": 3,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": 40
      },
      {
        "widget_id": "categories",
        "x": 0,
        "y": 3,
        "w": 3,
        "h": 7,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": 40
      },
      {
        "widget_id": "ranking",
        "x": 0,
        "y": 10,
        "w": 3,
        "h": 8,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": 40
      },
      {
        "widget_id": "map",
        "x": 3,
        "y": 3,
        "w": 6,
        "h": 10,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": 40
      },
      {
        "widget_id": "trend",
        "x": 3,
        "y": 13,
        "w": 6,
        "h": 5,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": 40
      },
      {
        "widget_id": "fulfillment",
        "x": 9,
        "y": 3,
        "w": 3,
        "h": 7,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": 40
      },
      {
        "widget_id": "mix",
        "x": 9,
        "y": 10,
        "w": 3,
        "h": 8,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": 40
      },
      {
        "widget_id": "ledger",
        "x": 0,
        "y": 18,
        "w": 12,
        "h": 6,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": 40
      }
    ],
    "mobile_strategy": "stack"
  },
  "compatibility": {
    "catalog_template_id": "national-command",
    "catalog_presentation": {
      "style": "command",
      "reference": "https://github.com/jeecgboot/jimureport#大屏设计效果"
    }
  },
  "widgets": [
    {
      "id": "revenue",
      "suggested_type": "kpi",
      "reference_title": "销售收入",
      "style": {},
      "colors": []
    },
    {
      "id": "orders",
      "suggested_type": "kpi",
      "reference_title": "订单总量",
      "style": {},
      "colors": []
    },
    {
      "id": "units",
      "suggested_type": "kpi",
      "reference_title": "销售件数",
      "style": {},
      "colors": []
    },
    {
      "id": "regions",
      "suggested_type": "kpi",
      "reference_title": "覆盖省区",
      "style": {},
      "colors": []
    },
    {
      "id": "categories",
      "suggested_type": "pie",
      "reference_title": "品类收入构成",
      "style": {},
      "colors": []
    },
    {
      "id": "ranking",
      "suggested_type": "bar",
      "reference_title": "省区销售 · Top 8",
      "style": {},
      "colors": []
    },
    {
      "id": "map",
      "suggested_type": "bar",
      "reference_title": "全国销售分布",
      "style": {},
      "colors": []
    },
    {
      "id": "trend",
      "suggested_type": "line",
      "reference_title": "收入月度走势",
      "style": {},
      "colors": []
    },
    {
      "id": "fulfillment",
      "suggested_type": "kpi",
      "reference_title": "准时交付率",
      "style": {},
      "colors": []
    },
    {
      "id": "mix",
      "suggested_type": "bar",
      "reference_title": "各品类订单量",
      "style": {},
      "colors": []
    },
    {
      "id": "ledger",
      "suggested_type": "table",
      "reference_title": "省区经营明细",
      "style": {},
      "colors": []
    }
  ]
}
```
