# 品牌营收驾驶舱

品牌侧栏与场景主视觉，结合收入指标、全球市场地图、覆盖仪表盘和品类贡献。使用 Northwind 实际订单明细；不推算缺失的转化率或同比。

Use this visual reference with dashboard-builder. Titles and chart kinds are suggestions; choose actual metrics and queries from the selected source. The reference contains no executable SQL or sample metric values.

```json
{
  "selection": "catalog:brand-revenue",
  "title": "品牌营收驾驶舱",
  "description": "品牌侧栏与场景主视觉，结合收入指标、全球市场地图、覆盖仪表盘和品类贡献。使用 Northwind 实际订单明细；不推算缺失的转化率或同比。",
  "theme": {
    "preset": "ocean",
    "mode": "light",
    "overrides": {
      "primary_color": null,
      "font_scale": null,
      "density": "comfortable",
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
        "widget_id": "hero",
        "x": 0,
        "y": 0,
        "w": 5,
        "h": 6,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": null
      },
      {
        "widget_id": "customers",
        "x": 5,
        "y": 0,
        "w": 3,
        "h": 3,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": null
      },
      {
        "widget_id": "regions",
        "x": 8,
        "y": 0,
        "w": 2,
        "h": 3,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": null
      },
      {
        "widget_id": "units",
        "x": 10,
        "y": 0,
        "w": 2,
        "h": 3,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": null
      },
      {
        "widget_id": "months",
        "x": 5,
        "y": 3,
        "w": 3,
        "h": 3,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": null
      },
      {
        "widget_id": "average",
        "x": 8,
        "y": 3,
        "w": 2,
        "h": 3,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": null
      },
      {
        "widget_id": "categories",
        "x": 10,
        "y": 3,
        "w": 2,
        "h": 3,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": null
      },
      {
        "widget_id": "world",
        "x": 0,
        "y": 6,
        "w": 6,
        "h": 8,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": null
      },
      {
        "widget_id": "coverage",
        "x": 6,
        "y": 6,
        "w": 3,
        "h": 8,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": null
      },
      {
        "widget_id": "activity",
        "x": 9,
        "y": 6,
        "w": 3,
        "h": 8,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": null
      },
      {
        "widget_id": "contribution",
        "x": 0,
        "y": 14,
        "w": 5,
        "h": 8,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": null
      },
      {
        "widget_id": "trend",
        "x": 5,
        "y": 14,
        "w": 7,
        "h": 8,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": null
      }
    ],
    "mobile_strategy": "stack"
  },
  "compatibility": {
    "catalog_template_id": "brand-revenue",
    "catalog_presentation": {
      "style": "brand",
      "reference": "用户提供的 PitchSide Pro 品牌经营驾驶舱参考图"
    }
  },
  "widgets": [
    {
      "id": "hero",
      "suggested_type": "kpi",
      "reference_title": "商品净收入",
      "style": {
        "hero_image": "/dashboard-templates/assets/brand-revenue-hero.png"
      },
      "colors": []
    },
    {
      "id": "customers",
      "suggested_type": "kpi",
      "reference_title": "下单客户",
      "style": {
        "metric_icon": "team"
      },
      "colors": []
    },
    {
      "id": "regions",
      "suggested_type": "kpi",
      "reference_title": "覆盖市场",
      "style": {
        "metric_icon": "global"
      },
      "colors": []
    },
    {
      "id": "units",
      "suggested_type": "kpi",
      "reference_title": "销售件数",
      "style": {
        "metric_icon": "shopping"
      },
      "colors": []
    },
    {
      "id": "months",
      "suggested_type": "kpi",
      "reference_title": "有销售月份",
      "style": {
        "metric_icon": "calendar"
      },
      "colors": []
    },
    {
      "id": "average",
      "suggested_type": "kpi",
      "reference_title": "平均明细净额",
      "style": {
        "metric_icon": "revenue"
      },
      "colors": []
    },
    {
      "id": "categories",
      "suggested_type": "kpi",
      "reference_title": "在售品类",
      "style": {
        "metric_icon": "appstore"
      },
      "colors": []
    },
    {
      "id": "world",
      "suggested_type": "bar",
      "reference_title": "全球市场 · 商品净收入",
      "style": {},
      "colors": []
    },
    {
      "id": "coverage",
      "suggested_type": "kpi",
      "reference_title": "市场覆盖范围",
      "style": {},
      "colors": []
    },
    {
      "id": "activity",
      "suggested_type": "table",
      "reference_title": "最近日期 · 市场收入",
      "style": {},
      "colors": []
    },
    {
      "id": "contribution",
      "suggested_type": "bar",
      "reference_title": "品类收入贡献",
      "style": {},
      "colors": []
    },
    {
      "id": "trend",
      "suggested_type": "line",
      "reference_title": "收入月度趋势",
      "style": {},
      "colors": []
    }
  ]
}
```
