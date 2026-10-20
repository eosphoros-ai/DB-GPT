import type { Chart } from '@antv/g2';
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

// G2 5.1 (the upstream lockfile) has no legend poptip option. Use its
// component events so truncated names remain readable without upgrading G2.
export const attachDashboardLegendTooltip = (chart: Chart) => {
  const container = chart.getContainer();
  let tooltip: HTMLDivElement | undefined;
  const hide = () => {
    tooltip?.remove();
    tooltip = undefined;
  };
  const show = (event: { target: { style: { text?: unknown } }; clientX: number; clientY: number }) => {
    hide();
    tooltip = document.createElement('div');
    tooltip.setAttribute('role', 'tooltip');
    tooltip.innerHTML = dashboardLegendPoptip({ label: event.target.style.text });
    Object.assign(tooltip.style, {
      position: 'fixed',
      zIndex: '1000',
      pointerEvents: 'none',
      padding: '8px 12px',
      borderRadius: '6px',
      maxWidth: 'min(360px, calc(100vw - 16px))',
      whiteSpace: 'normal',
      overflowWrap: 'anywhere',
      fontSize: '12px',
      background: 'var(--dashboard-theme-card, #fff)',
      color: 'var(--dashboard-theme-text, #374151)',
      border: '1px solid var(--dashboard-theme-border, #E5E7EB)',
    });
    container.appendChild(tooltip);
    tooltip.style.left = `${Math.max(8, Math.min(event.clientX + 12, window.innerWidth - tooltip.offsetWidth - 8))}px`;
    tooltip.style.top = `${Math.max(8, Math.min(event.clientY + 12, window.innerHeight - tooltip.offsetHeight - 8))}px`;
  };
  chart.on('legend-category-item-label:pointerover', show);
  chart.on('legend-category-item-label:pointerout', hide);
  chart.on('beforerender', hide);
  chart.once('afterdestroy', () => {
    hide();
    chart.off('legend-category-item-label:pointerover', show);
    chart.off('legend-category-item-label:pointerout', hide);
    chart.off('beforerender', hide);
  });
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
      },
    },
  };
};
