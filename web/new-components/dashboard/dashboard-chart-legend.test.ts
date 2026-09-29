import type { ChartConfig } from '@/new-components/charts/AdvancedCharts';
import {
  dashboardColorField,
  dashboardLegendConfig,
  dashboardLegendPoptip,
} from '@/new-components/charts/dashboard-chart-legend';
import { describe, expect, it } from 'vitest';
import { dashboardContrastRatio, resolveDashboardTheme } from './dashboard-appearance';

const config: ChartConfig = {
  chartType: 'column',
  data: [{ year: 2024, revenue: 391035 }],
  yField: 'revenue',
  fieldLabels: { revenue: '收入' },
  width: 400,
};
describe('dashboard series legends', () => {
  it('names a single measure without a color column', () => {
    const field = dashboardColorField(config);
    if (typeof field !== 'function') throw Error('expected constant encoding');
    expect(field({})).toBe('收入');
  });
  it('keeps series names, including zero, and gives blanks a non-empty fallback', () => {
    const field = dashboardColorField({ ...config, seriesField: 'series' });
    if (typeof field !== 'function') throw Error('expected empty-name normalization');
    expect(field({ series: '利润' })).toBe('利润');
    expect(field({ series: 0 })).toBe('0');
    expect(field({ series: ' ' })).toBe('收入');
  });
  it('respects an explicitly hidden legend', () => {
    expect(dashboardLegendConfig({ ...config, showLegend: false }).legend).toBe(false);
  });
  it('constrains item width while keeping the untruncated name for hover', () => {
    const result = dashboardLegendConfig(config).legend;
    if (!result) throw Error('expected legend');
    expect(result.color.itemWidth).toBeLessThanOrEqual(180);
    expect(result.color.position).toBe('top');
    const long = '这是一个很长很长的收入系列名称';
    expect(result.color.labelFormatter(long)).toBe(long);
    expect(result.color.poptip.render({ label: long })).toContain(long);
  });
  it('does not turn untrusted names into poptip HTML', () => {
    const html = dashboardLegendPoptip({ label: '<img src=x onerror="alert(1)">&\'' });
    expect(html).not.toContain('<img');
    expect(html).toContain('&lt;img');
    expect(html).toContain('&amp;&#39;');
  });
  for (const preset of ['clarity', 'graphite', 'ocean', 'warm'] as const) {
    for (const mode of ['light', 'dark'] as const) {
      it(`${preset}/${mode} text uses the theme foreground`, () => {
        const theme = resolveDashboardTheme({ preset, mode, overrides: {} });
        const result = dashboardLegendConfig({
          ...config,
          visualTheme: {
            mode,
            text: theme.text,
            muted: theme.muted,
            card: theme.card,
            border: theme.border,
            grid: theme.chartGrid,
            primary: theme.primary,
          },
        }).legend;
        if (!result) throw Error('expected legend');
        expect(dashboardContrastRatio(result.color.itemLabelFill, theme.card)).toBeGreaterThanOrEqual(4.5);
      });
    }
  }
});
