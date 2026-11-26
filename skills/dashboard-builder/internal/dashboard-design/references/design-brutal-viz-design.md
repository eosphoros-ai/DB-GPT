# 海报式营销

用醒目的标题、明确的块面和硬边结构，突出营销活动的关键结果与贡献。

Use this visual reference with dashboard-builder. Titles and chart kinds are suggestions; choose actual metrics and queries from the selected source. The reference contains no executable SQL or sample metric values.

```json
{
  "selection": "design:brutal-viz-design",
  "title": "海报式营销",
  "description": "用醒目的标题、明确的块面和硬边结构，突出营销活动的关键结果与贡献。",
  "guidance": "brutal-viz-design",
  "theme": {
    "preset": "warm",
    "mode": "light",
    "overrides": {}
  },
  "layouts": {
    "desktop": [
      {
        "widget_id": "reach",
        "x": 0,
        "y": 0,
        "w": 7,
        "h": 10,
        "min_w": 3,
        "min_h": 3
      },
      {
        "widget_id": "performance",
        "x": 7,
        "y": 0,
        "w": 5,
        "h": 5,
        "min_w": 3,
        "min_h": 3
      },
      {
        "widget_id": "breakdown",
        "x": 7,
        "y": 5,
        "w": 5,
        "h": 5,
        "min_w": 3,
        "min_h": 3
      }
    ]
  },
  "compatibility": {
    "gallery_style": "brutal-viz-design"
  },
  "widgets": [
    {
      "id": "reach",
      "suggested_type": "kpi",
      "reference_title": "reach",
      "style": {},
      "colors": []
    },
    {
      "id": "performance",
      "suggested_type": "kpi",
      "reference_title": "performance",
      "style": {},
      "colors": []
    },
    {
      "id": "breakdown",
      "suggested_type": "bar",
      "reference_title": "breakdown",
      "style": {},
      "colors": []
    }
  ]
}
```
