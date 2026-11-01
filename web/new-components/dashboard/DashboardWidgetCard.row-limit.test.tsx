import type { DashboardWidget, DashboardWidgetResult } from '@/types/dashboard';
import { render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import snapshot from '../../../examples/dashboard/snapshots/walmart-sales.public.json';
import DashboardWidgetCard from './DashboardWidgetCard';

vi.mock('@/new-components/charts', () => ({ AdvancedChart: () => <div>chart</div> }));

it('keeps the explicit truncated-result label visible with the unchanged row limit', () => {
  const widget = snapshot.schema.widgets[0] as unknown as DashboardWidget;
  const original = snapshot.snapshot.widgets[widget.id as keyof typeof snapshot.snapshot.widgets];
  const result = { ...original, row_count: 5000, truncated: true } as DashboardWidgetResult;
  render(<DashboardWidgetCard widget={widget} result={result} />);
  expect(screen.getByText(/已截断/)).toBeTruthy();
});
