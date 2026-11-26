# 美业预约管理

用梅色导航、轻盈的周历与鼠尾草色状态，串起预约、房间安排和会员经营。

Use this visual reference with dashboard-builder. Titles and chart kinds are suggestions; choose actual metrics and queries from the selected source. The reference contains no executable SQL or sample metric values.

```json
{
  "selection": "design:serenityspa-viz-design",
  "title": "美业预约管理",
  "description": "用梅色导航、轻盈的周历与鼠尾草色状态，串起预约、房间安排和会员经营。",
  "guidance": "serenityspa-viz-design",
  "theme": {
    "preset": "warm",
    "mode": "light",
    "overrides": {}
  },
  "layouts": {
    "desktop": [
      {
        "widget_id": "schedule",
        "x": 0,
        "y": 0,
        "w": 8,
        "h": 7,
        "min_w": 3,
        "min_h": 3
      },
      {
        "widget_id": "occupancy",
        "x": 8,
        "y": 0,
        "w": 4,
        "h": 7,
        "min_w": 3,
        "min_h": 3
      },
      {
        "widget_id": "appointments",
        "x": 0,
        "y": 7,
        "w": 4,
        "h": 3,
        "min_w": 3,
        "min_h": 3
      },
      {
        "widget_id": "attendance",
        "x": 4,
        "y": 7,
        "w": 4,
        "h": 3,
        "min_w": 3,
        "min_h": 3
      },
      {
        "widget_id": "revenue",
        "x": 8,
        "y": 7,
        "w": 4,
        "h": 3,
        "min_w": 3,
        "min_h": 3
      }
    ]
  },
  "compatibility": {
    "gallery_style": "serenityspa-viz-design"
  },
  "widgets": [
    {
      "id": "schedule",
      "suggested_type": "table",
      "reference_title": "schedule",
      "style": {},
      "colors": []
    },
    {
      "id": "occupancy",
      "suggested_type": "bar",
      "reference_title": "occupancy",
      "style": {},
      "colors": []
    },
    {
      "id": "appointments",
      "suggested_type": "kpi",
      "reference_title": "appointments",
      "style": {},
      "colors": []
    },
    {
      "id": "attendance",
      "suggested_type": "kpi",
      "reference_title": "attendance",
      "style": {},
      "colors": []
    },
    {
      "id": "revenue",
      "suggested_type": "kpi",
      "reference_title": "revenue",
      "style": {},
      "colors": []
    }
  ]
}
```
