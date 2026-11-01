# 门店营销沙盘

奶油底色、橙色重点与硬边阴影；从活动核销、渠道贡献到门店表现，串联营销全貌。内置合成演示数据，可替换自己的数据源。

Use this visual reference with dashboard-builder. Titles and chart kinds are suggestions; choose actual metrics and queries from the selected source. The reference contains no executable SQL or sample metric values.

```json
{
  "selection": "catalog:store-marketing",
  "title": "门店营销沙盘",
  "description": "奶油底色、橙色重点与硬边阴影；从活动核销、渠道贡献到门店表现，串联营销全貌。内置合成演示数据，可替换自己的数据源。",
  "theme": {
    "preset": "warm",
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
        "widget_id": "campaigns",
        "x": 0,
        "y": 0,
        "w": 3,
        "h": 4,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": 40
      },
      {
        "widget_id": "redemptions",
        "x": 3,
        "y": 0,
        "w": 3,
        "h": 4,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": 40
      },
      {
        "widget_id": "basket",
        "x": 6,
        "y": 0,
        "w": 3,
        "h": 4,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": 40
      },
      {
        "widget_id": "reach",
        "x": 9,
        "y": 0,
        "w": 3,
        "h": 4,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": 40
      },
      {
        "widget_id": "trend",
        "x": 0,
        "y": 4,
        "w": 8,
        "h": 8,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": 40
      },
      {
        "widget_id": "channels",
        "x": 8,
        "y": 4,
        "w": 4,
        "h": 8,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": 40
      },
      {
        "widget_id": "promotions",
        "x": 0,
        "y": 12,
        "w": 6,
        "h": 7,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": 40
      },
      {
        "widget_id": "revenue",
        "x": 6,
        "y": 12,
        "w": 6,
        "h": 7,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": 40
      },
      {
        "widget_id": "ledger",
        "x": 0,
        "y": 19,
        "w": 12,
        "h": 7,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": 40
      },
      {
        "widget_id": "venues",
        "x": 0,
        "y": 26,
        "w": 5,
        "h": 7,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": 40
      },
      {
        "widget_id": "conversion",
        "x": 5,
        "y": 26,
        "w": 3,
        "h": 7,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": 40
      },
      {
        "widget_id": "visits",
        "x": 8,
        "y": 26,
        "w": 4,
        "h": 7,
        "min_w": null,
        "min_h": null,
        "max_w": null,
        "max_h": 40
      }
    ],
    "mobile_strategy": "stack"
  },
  "compatibility": {
    "catalog_template_id": "store-marketing",
    "catalog_presentation": {
      "style": "marketing",
      "reference": "https://sive.antv.antgroup.com/bY0qQaJRMm5PRxG3KANM"
    }
  },
  "widgets": [
    {
      "id": "campaigns",
      "suggested_type": "kpi",
      "reference_title": "营销活动",
      "style": {},
      "colors": []
    },
    {
      "id": "redemptions",
      "suggested_type": "kpi",
      "reference_title": "活动核销",
      "style": {},
      "colors": []
    },
    {
      "id": "basket",
      "suggested_type": "kpi",
      "reference_title": "核销客单价",
      "style": {},
      "colors": []
    },
    {
      "id": "reach",
      "suggested_type": "kpi",
      "reference_title": "活动触达",
      "style": {},
      "colors": []
    },
    {
      "id": "trend",
      "suggested_type": "line",
      "reference_title": "活动核销趋势",
      "style": {},
      "colors": []
    },
    {
      "id": "channels",
      "suggested_type": "pie",
      "reference_title": "渠道贡献",
      "style": {},
      "colors": []
    },
    {
      "id": "promotions",
      "suggested_type": "bar",
      "reference_title": "热门营销活动",
      "style": {},
      "colors": []
    },
    {
      "id": "revenue",
      "suggested_type": "bar",
      "reference_title": "渠道收入趋势",
      "style": {},
      "colors": []
    },
    {
      "id": "ledger",
      "suggested_type": "table",
      "reference_title": "活动经营明细",
      "style": {},
      "colors": []
    },
    {
      "id": "venues",
      "suggested_type": "bar",
      "reference_title": "门店收入分布",
      "style": {},
      "colors": []
    },
    {
      "id": "conversion",
      "suggested_type": "kpi",
      "reference_title": "触达核销率",
      "style": {},
      "colors": []
    },
    {
      "id": "visits",
      "suggested_type": "bar",
      "reference_title": "各渠道到店次数",
      "style": {},
      "colors": []
    }
  ]
}
```
