import { DashboardLayoutItem, DashboardWidget } from '@/types/dashboard';

const pack = (items: Array<Omit<DashboardLayoutItem, 'x' | 'y'>>): DashboardLayoutItem[] => {
  let x = 0;
  let y = 0;
  let rowHeight = 0;
  return items.map(item => {
    if (x + item.w > 12) {
      y += rowHeight;
      x = 0;
      rowHeight = 0;
    }
    const placed = { ...item, x, y };
    x += item.w;
    rowHeight = Math.max(rowHeight, item.h);
    if (x >= 12) {
      y += rowHeight;
      x = 0;
      rowHeight = 0;
    }
    return placed;
  });
};

export const recommendedDashboardLayout = (widgets: DashboardWidget[]): DashboardLayoutItem[] =>
  pack(
    widgets.map(widget => {
      const visualization = widget.presentation?.visualization || widget.type;
      if (visualization === 'kpi' || visualization === 'gauge') {
        return { widget_id: widget.id, w: 3, h: 3, min_w: 3, min_h: 3 };
      }
      if (visualization === 'table') {
        return { widget_id: widget.id, w: 12, h: 7, min_w: 6, min_h: 4 };
      }
      return { widget_id: widget.id, w: 6, h: 6, min_w: 4, min_h: 4 };
    }),
  );

export const compactDashboardLayout = (items: DashboardLayoutItem[]): DashboardLayoutItem[] =>
  pack(
    [...items]
      .sort((left, right) => left.y - right.y || left.x - right.x)
      .map(item => ({
        widget_id: item.widget_id,
        w: item.w,
        h: item.h,
        min_w: item.min_w,
        min_h: item.min_h,
        max_w: item.max_w,
        max_h: item.max_h,
      })),
  );
