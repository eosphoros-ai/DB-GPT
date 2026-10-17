import type { ChartConfig } from './AdvancedCharts';

export const dashboardSeriesName = (config: ChartConfig, value: unknown) =>
  String(value ?? '').trim() || config.fieldLabels?.[config.yField || ''] || config.yField || '数值';

export const dashboardColorField = (config: ChartConfig) => {
  const field = config.colorField || config.seriesField;
  if (field && config.data.every(row => row[field] != null && String(row[field]).trim())) return field;
  return field
    ? (datum: Record<string, unknown>) => dashboardSeriesName(config, datum[field])
    : () => dashboardSeriesName(config, config.fieldLabels?.[config.yField || ''] || config.yField);
};

// Legend poptips accept HTML, so data-derived series names must be escaped.
export const dashboardLegendPoptip = ({ label }: { label: unknown }) => {
  const escaped = String(label ?? '').replace(
    /[&<>"']/g,
    character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]!,
  );
  return `<span data-dashboard-legend-full-name>${escaped}</span>`;
};

export const dashboardLegendConfig = (config: ChartConfig) => {
  if (config.showLegend === false) return { legend: false as const };
  const field = config.colorField || config.seriesField;
  const count = field ? new Set(config.data.map(row => dashboardSeriesName(config, row[field]))).size : 1;
  return {
    legend: {
      color: {
        position: 'top' as const,
        title: false,
        size: 28,
        gridRow: 1,
        colPadding: 10,
        itemWidth: Math.min(180, Math.max(40, ((config.width || 640) - 100) / Math.max(1, count) - 10)),
        itemLabelFill: config.visualTheme?.text || '#374151',
        itemLabelFontSize: 12,
        itemMarkerSize: 9,
        labelFormatter: (value: unknown) => dashboardSeriesName(config, value),
        poptip: {
          render: dashboardLegendPoptip,
          domStyles: {
            '.component-poptip-text': { 'max-width': '360px', 'white-space': 'normal', 'overflow-wrap': 'anywhere' },
          },
        },
      },
    },
  };
};
