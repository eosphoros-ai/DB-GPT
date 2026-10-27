# 零售经营总览

门店、月份与节假日销售结构，定位经营变化。

Use this visual reference with dashboard-builder. Titles and chart kinds are suggestions; choose actual metrics and queries from the selected source. The reference contains no executable SQL or sample metric values.

```json
{
  "selection": "catalog:retail-overview",
  "title": "零售经营总览",
  "description": "门店、月份与节假日销售结构，定位经营变化。",
  "theme": {
    "preset": "clarity",
    "mode": "light",
    "overrides": {
      "primary_color": "#365C9B",
      "font_scale": null,
      "density": null,
      "card_radius": null,
      "card_shadow": null,
      "chart_palette": [
        "#365C9B",
        "#B6834C",
        "#748DA2",
        "#72917C"
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
        "w": 4,
        "h": 3,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": null
      },
      {
        "widget_id": "scope",
        "x": 4,
        "y": 0,
        "w": 4,
        "h": 3,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": null
      },
      {
        "widget_id": "trend",
        "x": 0,
        "y": 3,
        "w": 8,
        "h": 8,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": null
      },
      {
        "widget_id": "ranking",
        "x": 8,
        "y": 0,
        "w": 4,
        "h": 11,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": null
      },
      {
        "widget_id": "structure",
        "x": 0,
        "y": 11,
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
    "catalog_template_id": "retail-overview",
    "catalog_presentation": {}
  },
  "widgets": [
    {
      "id": "total",
      "suggested_type": "kpi",
      "reference_title": "销售额",
      "style": {},
      "colors": []
    },
    {
      "id": "scope",
      "suggested_type": "kpi",
      "reference_title": "覆盖门店",
      "style": {},
      "colors": []
    },
    {
      "id": "trend",
      "suggested_type": "line",
      "reference_title": "销售额月度趋势",
      "style": {},
      "colors": []
    },
    {
      "id": "ranking",
      "suggested_type": "bar",
      "reference_title": "门店销售排行",
      "style": {},
      "colors": []
    },
    {
      "id": "structure",
      "suggested_type": "bar",
      "reference_title": "普通周与节假日销售",
      "style": {},
      "colors": []
    }
  ]
}
```
