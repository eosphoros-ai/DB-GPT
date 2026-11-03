import { ChatContext } from '@/app/chat-context';
import type { ChartConfig } from '@/new-components/charts/AdvancedCharts';
import { Column, Line } from '@ant-design/plots';
import React, { useContext } from 'react';

/** Local presentation adapter for the installed Ant Design Plots v2 components. */
const FinancialChart: React.FC<{ config: ChartConfig }> = ({ config }) => {
  const { mode } = useContext(ChatContext);
  const dark = mode === 'dark';
  const series = config.seriesField;
  const colors = config.colors || ['#0069fe', '#94a3b8'];
  const options = {
    data: config.data,
    xField: config.xField,
    yField: config.yField,
    colorField: series,
    height: config.height || 280,
    autoFit: true,
    animate: false,
    theme: dark ? 'classicDark' : 'classic',
    scale: {
      color: { range: dark ? colors.map(color => (color === '#0069fe' ? '#6aa8ff' : color)) : colors },
      // Amount and expense-rate plots must retain a zero baseline, including
      // negative operating cash flow. No smoothing of annual observations.
      y: { zero: true, nice: true },
    },
    axis: {
      x: { title: false, grid: false, tick: false, labelFontSize: 12, labelFill: dark ? '#9ba5b4' : '#697586' },
      y: { title: false, grid: false, tickCount: 4, labelFontSize: 12, labelFill: dark ? '#9ba5b4' : '#697586' },
    },
    legend: {
      color:
        series && config.showLegend !== false ? { position: 'top' as const, itemLabelFontSize: 12 } : (false as const),
    },
    interaction: { tooltip: { shared: true } },
  };
  return config.chartType === 'column' ? (
    <Column
      {...options}
      group={Boolean(series)}
      style={{ maxWidth: 36, ...(series ? {} : { fill: dark ? '#6aa8ff' : '#0069fe' }) }}
    />
  ) : (
    <Line {...options} style={{ lineWidth: 2 }} point={{ shapeField: 'point', sizeField: 3 }} />
  );
};

export default FinancialChart;
