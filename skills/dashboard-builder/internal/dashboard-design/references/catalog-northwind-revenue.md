# 品类收入与市场

按国家和品类查看扣除折扣后的商品净收入。

Use this visual reference with dashboard-builder. Titles and chart kinds are suggestions; choose actual metrics and queries from the selected source. The reference contains no executable SQL or sample metric values.

```json
{
  "selection": "catalog:northwind-revenue",
  "title": "品类收入与市场",
  "description": "按国家和品类查看扣除折扣后的商品净收入。",
  "theme": {
    "preset": "warm",
    "mode": "light",
    "overrides": {
      "primary_color": "#A34564",
      "font_scale": null,
      "density": null,
      "card_radius": null,
      "card_shadow": null,
      "chart_palette": [
        "#A34564",
        "#AE7D67",
        "#649296",
        "#98865B"
      ],
      "kpi_style": "quiet",
      "table_style": null
    }
  },
  "layouts": {
    "columns": 12,
    "desktop": [
      {
        "widget_id": "total",
        "x": 0,
        "y": 0,
        "w": 5,
        "h": 5,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": null
      },
      {
        "widget_id": "ranking",
        "x": 0,
        "y": 5,
        "w": 5,
        "h": 10,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": null
      },
      {
        "widget_id": "markets",
        "x": 5,
        "y": 0,
        "w": 7,
        "h": 8,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": null
      },
      {
        "widget_id": "trend",
        "x": 5,
        "y": 8,
        "w": 7,
        "h": 7,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": null
      },
      {
        "widget_id": "details",
        "x": 0,
        "y": 15,
        "w": 12,
        "h": 7,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": null
      }
    ],
    "mobile_strategy": "stack"
  },
  "compatibility": {
    "catalog_template_id": "northwind-revenue",
    "catalog_presentation": {}
  },
  "widgets": [
    {
      "id": "total",
      "suggested_type": "kpi",
      "reference_title": "商品净收入",
      "style": {},
      "colors": []
    },
    {
      "id": "ranking",
      "suggested_type": "bar",
      "reference_title": "品类净收入排行",
      "style": {},
      "colors": []
    },
    {
      "id": "markets",
      "suggested_type": "bar",
      "reference_title": "国家与品类收入",
      "style": {},
      "colors": []
    },
    {
      "id": "trend",
      "suggested_type": "line",
      "reference_title": "商品净收入月度趋势",
      "style": {},
      "colors": []
    },
    {
      "id": "details",
      "suggested_type": "table",
      "reference_title": "市场收入明细",
      "style": {},
      "colors": []
    }
  ]
}
```
