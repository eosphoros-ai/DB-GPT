import { DashboardWidget } from '@/types/dashboard';
import { describe, expect, it } from 'vitest';
import { compactDashboardLayout, recommendedDashboardLayout } from './dashboard-layout';

const widget = (id: string, type: DashboardWidget['type']): DashboardWidget =>
  ({ id, type, presentation: undefined }) as DashboardWidget;

describe('dashboard layout helpers', () => {
  it('places four KPI cards in one row and a chart below them', () => {
    const result = recommendedDashboardLayout([
      widget('a', 'kpi'),
      widget('b', 'kpi'),
      widget('c', 'kpi'),
      widget('d', 'kpi'),
      widget('chart', 'line'),
    ]);
    expect(result.slice(0, 4).map(item => [item.x, item.y, item.w])).toEqual([
      [0, 0, 3],
      [3, 0, 3],
      [6, 0, 3],
      [9, 0, 3],
    ]);
    expect(result[4]).toMatchObject({ x: 0, y: 3, w: 6, h: 6 });
  });

  it('removes gaps while preserving the current card sizes', () => {
    const result = compactDashboardLayout([
      { widget_id: 'later', x: 6, y: 20, w: 6, h: 5 },
      { widget_id: 'first', x: 0, y: 10, w: 6, h: 4 },
    ]);
    expect(result).toEqual([
      expect.objectContaining({ widget_id: 'first', x: 0, y: 0, w: 6, h: 4 }),
      expect.objectContaining({ widget_id: 'later', x: 6, y: 0, w: 6, h: 5 }),
    ]);
  });
});
