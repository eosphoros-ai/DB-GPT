import Chart from '@/components/chart';
import VisDashboard from '@/components/chat/chat-content/vis-dashboard';
import type { ChartData } from '@/types/chat';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('@/components/chart/autoChart', () => ({ AutoChart: () => null, getChartType: () => [] }));
vi.mock('@berryv/g2-react', () => ({ Chart: () => null }));

const titles = (count: number) => Array.from({ length: count }, (_, i) => `Chart ${i + 1}`);
const visibleTitles = () => screen.queryAllByText(/^Chart \d+$/).map(element => element.textContent);
const agentCharts = (count: number) =>
  titles(count).map(title => ({ title, type: 'response_table' as const, data: [], sql: '', describe: '' }));

describe('chat dashboard chart rows', () => {
  it.each([5, 8, 10])('shows all %i agent charts once in source order', count => {
    const data = agentCharts(count);
    render(<VisDashboard data={{ title: null, display_strategy: 'default', chart_count: count, data }} />);
    expect(visibleTitles()).toEqual(titles(count));
  });

  it('uses the charts actually returned when the reported count is stale', () => {
    const data = agentCharts(5);
    const { container } = render(
      <VisDashboard data={{ title: null, display_strategy: 'default', chart_count: 2, data }} />,
    );
    expect(visibleTitles()).toEqual(titles(5));
    expect(Array.from(container.firstElementChild!.children, row => row.childElementCount)).toEqual([2, 1, 2]);
  });

  it('keeps the report indicator row and displays every table when there are more than eight', () => {
    const tables: ChartData[] = titles(10).map(chart_name => ({
      chart_name,
      chart_type: 'Table',
      chart_uid: chart_name,
      chart_sql: '',
      chart_desc: '',
      column_name: [],
      values: [],
    }));
    const indicator = {
      ...tables[0],
      chart_uid: 'indicator',
      chart_type: 'IndicatorValue',
      values: [{ name: 'Orders', value: 12, type: 'count' }],
    };
    const { container } = render(<Chart chartsData={[...tables, indicator]} />);
    expect(container.firstElementChild?.firstElementChild?.textContent).toContain('Orders');
    expect(visibleTitles()).toEqual(titles(10));
  });
});
