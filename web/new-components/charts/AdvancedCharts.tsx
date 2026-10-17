/**
 * AdvancedCharts.tsx
 * A unified chart component that supports multiple chart types with a premium, clean design.
 * Uses @ant-design/plots (AntV) for rendering.
 * Enhanced with advanced interactions: zoom, pan, brush selection, and data point click handlers.
 */

import {
  FullscreenExitOutlined,
  FullscreenOutlined,
  ReloadOutlined,
  ZoomInOutlined,
  ZoomOutOutlined,
} from '@ant-design/icons';
import { Area, Bar, Column, DualAxes, Line, Pie, Scatter } from '@ant-design/plots';
import { Button, Tooltip } from 'antd';
import React, { useCallback, useMemo, useRef, useState } from 'react';
import { dashboardBarLabel } from './dashboard-chart-labels';
import { dashboardColorField, dashboardLegendConfig } from './dashboard-chart-legend';

// Chart type definitions
export type ChartType =
  | 'line'
  | 'column'
  | 'stacked-column'
  | 'bar'
  | 'pie'
  | 'area'
  | 'scatter'
  | 'donut'
  | 'dual-axes';

export interface ChartConfig {
  chartType: ChartType;
  data: any[];
  // Common fields
  xField?: string;
  yField?: string;
  seriesField?: string;
  colorField?: string;
  // Pie chart specific
  angleField?: string;
  innerRadius?: number;
  // Dual axes specific
  yFields?: [string, string];
  geometries?: any[];
  // Appearance
  title?: string;
  description?: string;
  smooth?: boolean;
  stacked?: boolean;
  autoFit?: boolean;
  height?: number;
  width?: number;
  /** Opt in only on persisted Dashboard/editor/public surfaces. */
  dashboardSurface?: boolean;
  fieldLabels?: Record<string, string>;
  measureFormat?: { unit: string; format: (value: unknown) => string; fullFormat?: (value: unknown) => string };
  colors?: string[];
  showLegend?: boolean;
  showGrid?: boolean;
  animate?: boolean;
  visualTheme?: {
    mode: 'light' | 'dark';
    text: string;
    muted: string;
    grid: string;
    card: string;
    border: string;
    primary: string;
    seriesDashes?: readonly (readonly number[])[];
    seriesShapes?: readonly string[];
  };
  // Interaction options
  enableZoom?: boolean;
  enableBrush?: boolean;
  enableTooltipCrosshairs?: boolean;
  onDataPointClick?: (data: any, event: any) => void;
  onBrushSelection?: (selectedData: any[]) => void;
  // Toolbar options
  showToolbar?: boolean;
  enableFullscreen?: boolean;
}

// Premium color palette - clean and professional
const PREMIUM_COLORS = [
  '#3B82F6', // Blue
  '#10B981', // Emerald
  '#F59E0B', // Amber
  '#EF4444', // Red
  '#8B5CF6', // Violet
  '#EC4899', // Pink
  '#06B6D4', // Cyan
  '#84CC16', // Lime
  '#F97316', // Orange
  '#6366F1', // Indigo
];

export const resolveAreaGradient = (colors?: string[]) => {
  const primary = colors?.find(color => typeof color === 'string' && color.trim()) || PREMIUM_COLORS[0];
  return primary;
};

const resolveChartPalette = (config: ChartConfig) =>
  config.colors?.filter(color => typeof color === 'string' && color.trim()) || PREMIUM_COLORS;

const resolvePrimaryChartColor = (config: ChartConfig) => resolveChartPalette(config)[0] || PREMIUM_COLORS[0];

export const buildDualAxesChildren = (config: ChartConfig) => {
  const [primaryField, secondaryField] = config.yFields || [config.yField || 'y1', 'y2'];
  const palette = resolveChartPalette(config);
  const primary = palette[0] || PREMIUM_COLORS[0];
  const secondary = palette[1] || PREMIUM_COLORS[1];
  const muted = config.visualTheme?.muted || '#6b7280';
  const grid = config.visualTheme?.grid || '#f3f4f6';

  return [
    {
      type: 'interval',
      yField: primaryField,
      ...(config.dashboardSurface
        ? { label: dashboardBarLabel({ ...config, chartType: 'column', yField: primaryField }) }
        : {}),
      ...getTooltipConfig({ ...config, yField: primaryField }),
      colorField: () => primaryField,
      scale: {
        y: { independent: true, nice: true },
        color: { range: [primary] },
      },
      axis: {
        x: config.dashboardSurface ? getDashboardAxisConfig(config).axis.x : { labelFill: muted },
        y: { position: 'left', labelFill: muted, gridStroke: grid, labelFormatter: config.measureFormat?.format },
      },
      style: {
        fill: primary,
        radiusTopLeft: 3,
        radiusTopRight: 3,
      },
    },
    {
      type: 'line',
      yField: secondaryField,
      ...getTooltipConfig({ ...config, yField: secondaryField }),
      colorField: () => secondaryField,
      scale: {
        y: { independent: true, nice: true },
        color: { range: [secondary] },
      },
      axis: {
        x: false,
        y: { position: 'right', labelFill: muted, grid: false, labelFormatter: config.measureFormat?.format },
      },
      style: {
        stroke: secondary,
        lineWidth: 2.5,
        lineDash: config.visualTheme?.seriesDashes?.[1] ? [...config.visualTheme.seriesDashes[1]] : [6, 3],
      },
      point: {
        size: 3,
        style: {
          fill: config.visualTheme?.card || '#ffffff',
          stroke: secondary,
          lineWidth: 2,
        },
      },
    },
  ];
};

const resolveSeriesIndex = (config: ChartConfig, datum: Record<string, unknown>) => {
  if (!config.seriesField) return 0;
  const values = Array.from(new Set(config.data.map(item => String(item?.[config.seriesField!] ?? ''))));
  return Math.max(0, values.indexOf(String(datum?.[config.seriesField] ?? '')));
};

const resolveSeriesLineStyle = (config: ChartConfig, datum: Record<string, unknown>) => {
  const dashes = config.visualTheme?.seriesDashes;
  const index = resolveSeriesIndex(config, datum);
  return {
    stroke: config.seriesField || config.colorField ? undefined : resolvePrimaryChartColor(config),
    lineWidth: 2.5,
    lineDash: dashes?.length ? [...dashes[index % dashes.length]] : [],
  };
};

/**
 * @ant-design/plots 2.x is based on G2 5.  Palette colors are supplied through
 * scale.color.range; the old top-level `color` option is silently ignored by
 * several plots.  Keep this helper in one place so every dashboard visual uses
 * the palette selected in the editor.
 */
const DASHBOARD_Y_TICK_COUNT = 4;

// G2 must nice the numeric domain with the same tick count used by its axis.
// Otherwise the axis can change the domain after mark positions are computed.
const dashboardNumericScale = (config: ChartConfig) =>
  config.dashboardSurface ? { y: { tickCount: DASHBOARD_Y_TICK_COUNT } } : {};

const getColorEncodingConfig = (config: ChartConfig) => ({
  colorField: config.dashboardSurface ? dashboardColorField(config) : config.colorField || config.seriesField,
  scale: {
    ...dashboardNumericScale(config),
    ...(config.dashboardSurface && config.chartType !== 'scatter'
      ? { x: { type: ['column', 'stacked-column', 'bar'].includes(config.chartType) ? 'band' : 'point' } }
      : {}),
    color: {
      range: resolveChartPalette(config),
    },
    ...(config.seriesField && config.visualTheme?.seriesShapes
      ? { shape: { range: [...config.visualTheme.seriesShapes] } }
      : {}),
  },
});

// Common theme configuration for all charts
const getCommonConfig = (config: ChartConfig) => ({
  autoFit: config.autoFit ?? true,
  ...(config.dashboardSurface && !['pie', 'donut'].includes(config.chartType)
    ? { paddingTop: 28, paddingBottom: config.chartType === 'bar' ? 42 : 76, paddingLeft: config.chartType === 'bar' ? Math.min(150, Math.max(92, (config.width || 600) * .28)) : 70, paddingRight: config.chartType === 'dual-axes' ? 70 : 24 }
    : {}),
  animation:
    config.animate !== false
      ? {
          appear: {
            animation: 'fade-in',
            duration: 500,
          },
        }
      : false,
  theme: {
    colors10: resolveChartPalette(config),
    colors20: resolveChartPalette(config),
  },
});

/** G2 5 axes: never auto-hide categorical ticks to accommodate the plot. */
export const getDashboardAxisConfig = (config: ChartConfig) => {
  const horizontal = config.chartType === 'bar';
  const xField = config.xField || 'x';
  const categories = Array.from(new Set(config.data.map(row => row[xField])));
  const longest = Math.max(0, ...categories.map(value => String(value ?? '').length));
  const slot = Math.max(1, (config.width || 600) - 94) / Math.max(1, categories.length);
  return {
    axis: {
      x: {
        title: false,
        line: true,
        tick: true,
        label: true,
        labelFill: config.visualTheme?.text || '#374151',
        labelFontSize: 11,
        labelFormatter: (value: unknown) => String(value ?? '—'),
        labelAutoHide: false,
        labelAutoEllipsis: false,
        labelAutoRotate: false,
        labelTransform: !horizontal && slot < 40 && slot < longest * 7 ? 'rotate(-65)' : undefined,
        labelWordWrap: horizontal || slot >= 40,
        labelWordWrapWidth: horizontal ? Math.min(150, Math.max(92, (config.width || 600) * .28)) - 16 : Math.max(40, slot - 8),
        labelMaxLines: 3,
        tickFilter: () => true,
        labelFilter: () => true,
        grid: false,
      },
      y: {
        title: false,
        labelFormatter: config.measureFormat?.format,
        line: true,
        tick: true,
        label: true,
        labelFill: config.visualTheme?.text || '#374151',
        labelFontSize: 11,
        grid: config.showGrid !== false,
        gridStroke: config.visualTheme?.grid || '#f3f4f6',
        tickCount: DASHBOARD_Y_TICK_COUNT,
      },
    },
  };
};

// Non-Dashboard consumers retain their existing appearance.
const getAxisConfig = (config: ChartConfig) =>
  config.dashboardSurface
    ? getDashboardAxisConfig(config)
    : {
        xAxis: {
          line: {
            style: {
              stroke: config.visualTheme?.border || '#e5e7eb',
              lineWidth: 1,
            },
          },
          tickLine: {
            style: {
              stroke: config.visualTheme?.border || '#e5e7eb',
            },
          },
          label: {
            style: {
              fill: config.visualTheme?.muted || '#6b7280',
              fontSize: 11,
            },
          },
          grid:
            config.showGrid !== false
              ? {
                  line: {
                    style: {
                      stroke: config.visualTheme?.grid || '#f3f4f6',
                      lineWidth: 1,
                      lineDash: [4, 4],
                    },
                  },
                }
              : null,
        },
        yAxis: {
          line: {
            style: {
              stroke: config.visualTheme?.border || '#e5e7eb',
              lineWidth: 1,
            },
          },
          tickLine: {
            style: {
              stroke: config.visualTheme?.border || '#e5e7eb',
            },
          },
          label: {
            style: {
              fill: config.visualTheme?.muted || '#6b7280',
              fontSize: 11,
            },
          },
          grid:
            config.showGrid !== false
              ? {
                  line: {
                    style: {
                      stroke: config.visualTheme?.grid || '#f3f4f6',
                      lineWidth: 1,
                      lineDash: [4, 4],
                    },
                  },
                }
              : null,
        },
      };

// Legend configuration
const getLegendConfig = (config: ChartConfig) => config.dashboardSurface ? dashboardLegendConfig(config) : ({
  legend:
    config.showLegend !== false
      ? {
          position: 'top-right' as const,
          itemName: {
            style: {
              fill: config.visualTheme?.text || '#374151',
              fontSize: 12,
            },
          },
          marker: {
            symbol: 'circle',
          },
        }
      : false,
});

// Enhanced tooltip configuration with crosshairs
const getTooltipConfig = (config: ChartConfig) =>
  config.dashboardSurface
    ? {
        tooltip: {
          title: (datum: Record<string, unknown>) => String(datum[config.xField || config.colorField || 'x'] ?? ''),
          items: [
            (datum: Record<string, unknown>) => {
              const field = config.yField || config.angleField || 'y';
              const value = config.measureFormat?.format(datum[field]) ?? String(datum[field] ?? '—');
              const full = config.measureFormat?.fullFormat?.(datum[field]) ?? value;
              return {
                name: String(datum[config.seriesField || config.colorField || ''] ?? field),
                value: value === full ? value : `${value}（完整值：${full}）`,
              };
            },
          ],
        },
      }
    : {
        tooltip: {
          showTitle: true,
          showMarkers: true,
          showCrosshairs: config.enableTooltipCrosshairs ?? true,
          crosshairs: {
            type: 'xy' as const,
            line: {
              style: {
                stroke: config.visualTheme?.muted || '#9CA3AF',
                lineWidth: 1,
                lineDash: [4, 4],
              },
            },
          },
          domStyles: {
            'g2-tooltip': {
              backgroundColor: config.visualTheme?.card || '#ffffff',
              boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
              borderRadius: '8px',
              padding: '12px 16px',
              border: `1px solid ${config.visualTheme?.border || '#e5e7eb'}`,
            },
            'g2-tooltip-title': {
              color: config.visualTheme?.text || '#111827',
              fontWeight: '600',
              fontSize: '13px',
              marginBottom: '8px',
            },
            'g2-tooltip-list-item': {
              color: config.visualTheme?.muted || '#4b5563',
              fontSize: '12px',
            },
          },
          customContent: (title: string, items: any[]) => {
            if (!items?.length) return '';
            const yField = config.yField || 'y';

            return `
        <div style="padding: 12px 16px; min-width: 160px;">
          <div style="font-weight: 600; font-size: 13px; color: ${config.visualTheme?.text || '#111827'}; margin-bottom: 8px; border-bottom: 1px solid ${config.visualTheme?.border || '#e5e7eb'}; padding-bottom: 8px;">
            ${title}
          </div>
          ${items
            .map(
              item => `
            <div style="display: flex; align-items: center; justify-content: space-between; margin: 6px 0;">
              <div style="display: flex; align-items: center; gap: 6px;">
                <span style="width: 8px; height: 8px; border-radius: 50%; background: ${item.color};"></span>
                <span style="color: ${config.visualTheme?.muted || '#6b7280'}; font-size: 12px;">${item.name || yField}</span>
              </div>
              <span style="font-weight: 600; font-size: 12px; color: ${config.visualTheme?.text || '#111827'};">${typeof item.value === 'number' ? item.value.toLocaleString() : item.value}</span>
            </div>
          `,
            )
            .join('')}
          <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid ${config.visualTheme?.grid || '#f3f4f6'}; font-size: 11px; color: ${config.visualTheme?.muted || '#9CA3AF'};">
            Click for details • Scroll to zoom
          </div>
        </div>
      `;
          },
        },
      };

export const makePieLabelFormatter = (data: Record<string, any>[], colorField: string, angleField: string) => {
  const total = data.reduce((sum, item) => {
    const value = Number(item[angleField]);
    return Number.isFinite(value) ? sum + value : sum;
  }, 0);

  return (datum: Record<string, any>) => {
    const value = Number(datum[angleField]);
    const percentage = Number.isFinite(value) && total !== 0 ? (value / total) * 100 : 0;
    return `${String(datum[colorField] ?? '')}: ${percentage.toFixed(1)}%`;
  };
};

// Get interaction configuration
const getInteractionConfig = (config: ChartConfig) => {
  const interactions: any[] = [{ type: 'element-active' }, { type: 'element-highlight' }];

  if (config.enableZoom !== false) {
    interactions.push(
      { type: 'view-zoom' },
      {
        type: 'element-single-selected',
        cfg: {
          start: [{ trigger: 'element:click', action: 'element-single-selected:toggle' }],
        },
      },
    );
  }

  if (config.enableBrush) {
    interactions.push({
      type: 'brush-x',
      cfg: {
        showEnable: [
          { trigger: 'plot:mouseenter', action: 'cursor:crosshair' },
          { trigger: 'plot:mouseleave', action: 'cursor:default' },
        ],
      },
    });
  }

  return { interactions };
};

// Get click handler config
const getClickHandlerConfig = (config: ChartConfig, chartRef: React.MutableRefObject<any>) => {
  if (!config.onDataPointClick) return {};

  return {
    onReady: (plot: any) => {
      chartRef.current = plot;
      plot.on('element:click', (evt: any) => {
        const { data } = evt;
        config.onDataPointClick?.(data?.data, evt);
      });
    },
  };
};

// Chart Toolbar Component
interface ChartToolbarProps {
  onZoomIn: () => void;
  onZoomOut: () => void;
  onReset: () => void;
  onToggleFullscreen: () => void;
  isFullscreen: boolean;
  showZoom?: boolean;
  showFullscreen?: boolean;
}

const ChartToolbar: React.FC<ChartToolbarProps> = ({
  onZoomIn,
  onZoomOut,
  onReset,
  onToggleFullscreen,
  isFullscreen,
  showZoom = true,
  showFullscreen = true,
}) => (
  <div className='chart-toolbar flex items-center gap-1 absolute top-2 right-2 z-10 bg-white/90 dark:bg-gray-800/90 backdrop-blur-sm rounded-lg px-1.5 py-1 shadow-sm border border-gray-200 dark:border-gray-700'>
    {showZoom && (
      <>
        <Tooltip title='Zoom In'>
          <Button type='text' size='small' icon={<ZoomInOutlined />} onClick={onZoomIn} className='!w-7 !h-7 !p-0' />
        </Tooltip>
        <Tooltip title='Zoom Out'>
          <Button type='text' size='small' icon={<ZoomOutOutlined />} onClick={onZoomOut} className='!w-7 !h-7 !p-0' />
        </Tooltip>
        <Tooltip title='Reset View'>
          <Button type='text' size='small' icon={<ReloadOutlined />} onClick={onReset} className='!w-7 !h-7 !p-0' />
        </Tooltip>
      </>
    )}
    {showFullscreen && (
      <>
        <div className='w-px h-4 bg-gray-200 dark:bg-gray-700 mx-0.5' />
        <Tooltip title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}>
          <Button
            type='text'
            size='small'
            icon={isFullscreen ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
            onClick={onToggleFullscreen}
            className='!w-7 !h-7 !p-0'
          />
        </Tooltip>
      </>
    )}
  </div>
);

// Line Chart Component
const LineChart: React.FC<{ config: ChartConfig; chartRef: React.MutableRefObject<any> }> = ({ config, chartRef }) => {
  const chartConfig = useMemo(
    () => ({
      data: config.data,
      xField: config.xField || 'x',
      yField: config.yField || 'y',
      seriesField: config.seriesField,
      ...getColorEncodingConfig(config),
      isStack: config.stacked || config.chartType === 'stacked-column',
      smooth: config.smooth ?? true,
      ...getCommonConfig(config),
      ...getAxisConfig(config),
      ...getLegendConfig(config),
      ...getTooltipConfig(config),
      ...getInteractionConfig(config),
      ...getClickHandlerConfig(config, chartRef),
      point: {
        size: 3,
        scale: dashboardNumericScale(config),
        ...(config.dashboardSurface ? getLegendConfig(config) : {}),
        shapeField: config.seriesField,
        shape: config.seriesField ? undefined : 'circle',
        style: {
          fill: config.visualTheme?.card || '#ffffff',
          stroke: resolvePrimaryChartColor(config),
          lineWidth: 2,
          cursor: 'pointer',
        },
      },
      style: config.seriesField
        ? (datum: Record<string, unknown>) => resolveSeriesLineStyle(config, datum)
        : resolveSeriesLineStyle(config, {}),
      slider: config.enableZoom !== false ? { start: 0, end: 1 } : undefined,
    }),
    [config, chartRef],
  );

  return <Line {...chartConfig} height={config.height || 300} />;
};

// Column Chart Component (Vertical Bar)
const ColumnChart: React.FC<{ config: ChartConfig; chartRef: React.MutableRefObject<any> }> = ({
  config,
  chartRef,
}) => {
  const stacked = config.stacked || config.chartType === 'stacked-column';
  const chartConfig = useMemo(
    () => ({
      data: config.data,
      xField: config.xField || 'x',
      yField: config.yField || 'y',
      // In Plot 2.x the series channel offsets bars horizontally, even with stack enabled.
      // Stacks use the color channel; ordinary columns retain their grouped series.
      seriesField: stacked ? undefined : config.seriesField,
      stack: stacked,
      ...getColorEncodingConfig(config),
      ...getCommonConfig(config),
      ...getAxisConfig(config),
      ...getLegendConfig(config),
      ...getTooltipConfig(config),
      ...getInteractionConfig(config),
      ...getClickHandlerConfig(config, chartRef),
      columnWidthRatio: 0.6,
      style: {
        fill: config.seriesField || config.colorField ? undefined : resolvePrimaryChartColor(config),
        radiusTopLeft: 4,
        radiusTopRight: 4,
        cursor: 'pointer',
      },
      label: {
        position: 'top' as const,
        ...(config.dashboardSurface
          ? { text: (datum: Record<string, unknown>) => config.measureFormat?.format(datum[config.yField || 'y']) }
          : {}),
        style: {
          fill: config.visualTheme?.muted || '#6b7280',
          fontSize: 10,
        },
      },
      ...(config.dashboardSurface ? { label: dashboardBarLabel(config) } : {}),
      scrollbar: !config.dashboardSurface && config.data.length > 12 ? { type: 'horizontal' as const } : undefined,
    }),
    [config, chartRef, stacked],
  );

  return <Column {...chartConfig} height={config.height || 300} />;
};

// Bar Chart Component (Horizontal Bar)
const BarChart: React.FC<{ config: ChartConfig; chartRef: React.MutableRefObject<any> }> = ({ config, chartRef }) => {
  const chartConfig = useMemo(
    () => ({
      data: config.data,
      xField: config.dashboardSurface ? config.xField || 'x' : config.yField || 'y',
      yField: config.dashboardSurface ? config.yField || 'y' : config.xField || 'x',
      seriesField: config.seriesField,
      ...getColorEncodingConfig(config),
      ...getCommonConfig(config),
      ...getAxisConfig(config),
      ...getLegendConfig(config),
      ...getTooltipConfig(config),
      ...getInteractionConfig(config),
      ...getClickHandlerConfig(config, chartRef),
      barWidthRatio: 0.6,
      style: {
        fill: config.seriesField || config.colorField ? undefined : resolvePrimaryChartColor(config),
        radiusTopRight: 4,
        radiusBottomRight: 4,
        cursor: 'pointer',
      },
      label: {
        position: 'right' as const,
        ...(config.dashboardSurface
          ? { text: (datum: Record<string, unknown>) => config.measureFormat?.format(datum[config.yField || 'y']) }
          : {}),
        style: {
          fill: config.visualTheme?.muted || '#6b7280',
          fontSize: 10,
        },
      },
      ...(config.dashboardSurface ? { label: dashboardBarLabel(config) } : {}),
      scrollbar: !config.dashboardSurface && config.data.length > 10 ? { type: 'vertical' as const } : undefined,
    }),
    [config, chartRef],
  );

  return <Bar {...chartConfig} height={config.height || 300} />;
};

// Pie Chart Component
const PieChart: React.FC<{ config: ChartConfig; chartRef: React.MutableRefObject<any> }> = ({ config, chartRef }) => {
  const isDonut = config.chartType === 'donut';

  const chartConfig = useMemo(() => {
    const angleField = config.angleField || config.yField || 'value';
    const colorField = config.colorField || config.xField || 'type';
    return {
      data: config.data,
      angleField,
      colorField,
      scale: {
        color: {
          range: resolveChartPalette(config),
        },
      },
      ...getCommonConfig(config),
      ...getLegendConfig(config),
      ...getTooltipConfig(config),
      ...getClickHandlerConfig(config, chartRef),
      radius: 0.9,
      innerRadius: isDonut ? Math.min(0.9, Math.max(0, config.innerRadius ?? 0.6)) : 0,
      label: {
        text:
          config.dashboardSurface && config.measureFormat
            ? (datum: Record<string, unknown>) =>
                `${String(datum[colorField] ?? '')}: ${config.measureFormat!.format(datum[angleField])}`
            : makePieLabelFormatter(config.data, colorField, angleField),
        position: 'outside',
        connector: true,
        style: {
          fill: config.visualTheme?.muted || '#6b7280',
          fontSize: 11,
        },
      },
      style: {
        lineWidth: 2,
        stroke: config.visualTheme?.card || '#ffffff',
        cursor: 'pointer',
      },
      statistic: isDonut
        ? {
            title: {
              style: {
                fontSize: '14px',
                color: config.visualTheme?.muted || '#6b7280',
              },
              content: 'Total',
            },
            content: {
              style: {
                fontSize: '24px',
                fontWeight: '600',
                color: config.visualTheme?.text || '#111827',
              },
            },
          }
        : undefined,
      interactions: [
        { type: 'element-active' },
        { type: 'element-selected' },
        { type: 'pie-legend-active' },
        { type: 'pie-statistic-active' },
      ],
    };
  }, [config, isDonut, chartRef]);

  return <Pie {...chartConfig} height={config.height || 300} />;
};

// Area Chart Component
const AreaChart: React.FC<{ config: ChartConfig; chartRef: React.MutableRefObject<any> }> = ({ config, chartRef }) => {
  const chartConfig = useMemo(
    () => ({
      data: config.data,
      xField: config.xField || 'x',
      yField: config.yField || 'y',
      seriesField: config.seriesField,
      ...getColorEncodingConfig(config),
      smooth: config.smooth ?? true,
      ...getCommonConfig(config),
      ...getAxisConfig(config),
      ...getLegendConfig(config),
      ...getTooltipConfig(config),
      ...getInteractionConfig(config),
      ...getClickHandlerConfig(config, chartRef),
      style: {
        fill: resolveAreaGradient(config.colors),
        fillOpacity: 0.25,
      },
      line: {
        scale: dashboardNumericScale(config),
        ...(config.dashboardSurface ? getLegendConfig(config) : {}),
        style: config.seriesField
          ? (datum: Record<string, unknown>) => resolveSeriesLineStyle(config, datum)
          : { ...resolveSeriesLineStyle(config, {}), lineWidth: 2 },
      },
      slider: config.enableZoom !== false ? { start: 0, end: 1 } : undefined,
    }),
    [config, chartRef],
  );

  return <Area {...chartConfig} height={config.height || 300} />;
};

// Scatter Chart Component
const ScatterChart: React.FC<{ config: ChartConfig; chartRef: React.MutableRefObject<any> }> = ({
  config,
  chartRef,
}) => {
  const chartConfig = useMemo(
    () => ({
      data: config.data,
      xField: config.xField || 'x',
      yField: config.yField || 'y',
      shapeField: config.seriesField,
      ...getColorEncodingConfig(config),
      ...getCommonConfig(config),
      ...getAxisConfig(config),
      ...getLegendConfig(config),
      ...getTooltipConfig(config),
      ...getInteractionConfig(config),
      ...getClickHandlerConfig(config, chartRef),
      size: 5,
      shape: config.seriesField ? undefined : 'circle',
      pointStyle: {
        fillOpacity: 0.8,
        stroke: config.visualTheme?.card || '#ffffff',
        lineWidth: 1,
        cursor: 'pointer',
      },
      color: config.colors || PREMIUM_COLORS,
      brush: config.enableBrush
        ? {
            enabled: true,
            type: 'rect' as const,
          }
        : undefined,
    }),
    [config, chartRef],
  );

  return <Scatter {...chartConfig} height={config.height || 300} />;
};

// Dual Axes Chart Component
const DualAxesChart: React.FC<{ config: ChartConfig; chartRef: React.MutableRefObject<any> }> = ({
  config,
  chartRef,
}) => {
  const [primaryField, secondaryField] = config.yFields || [config.yField || 'y1', 'y2'];
  const palette = resolveChartPalette(config);
  const primary = palette[0] || PREMIUM_COLORS[0];
  const secondary = palette[1] || PREMIUM_COLORS[1];
  const chartHeight = config.height || 300;
  const chartConfig = useMemo(() => {
    const xField = config.xField || 'x';

    return {
      data: config.data,
      xField,
      ...getCommonConfig(config),
      ...getTooltipConfig(config),
      ...getClickHandlerConfig(config, chartRef),
      children: buildDualAxesChildren(config),
      ...(config.dashboardSurface ? { scale: { x: { type: 'band' } } } : {}),
      legend: false,
      interactions: [{ type: 'element-active' }, { type: 'element-highlight' }],
      slider: config.enableZoom !== false ? { start: 0, end: 1 } : undefined,
    };
  }, [config, chartRef]);

  return (
    <div style={{ position: 'relative', height: chartHeight }}>
      {config.showLegend !== false && (
        <div
          aria-label='双轴图图例'
          style={{
            position: 'absolute',
            zIndex: 2,
            top: 5,
            left: 26,
            display: 'flex',
            alignItems: 'center',
            gap: 16,
            color: config.visualTheme?.muted || '#6b7280',
            fontSize: 11,
            maxWidth: 'calc(100% - 52px)',
            pointerEvents: 'auto',
          }}
        >
          <span title={config.fieldLabels?.[primaryField] || primaryField} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
            <span aria-hidden style={{ flexShrink: 0, width: 9, height: 9, borderRadius: 2, background: primary }} />
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{config.fieldLabels?.[primaryField] || primaryField}</span>
          </span>
          <span title={config.fieldLabels?.[secondaryField] || secondaryField} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
            <span aria-hidden style={{ flexShrink: 0, width: 15, height: 0, borderTop: `2px dashed ${secondary}` }} />
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{config.fieldLabels?.[secondaryField] || secondaryField}</span>
          </span>
        </div>
      )}
      <DualAxes {...chartConfig} height={chartHeight} />
    </div>
  );
};

// Main AdvancedChart Component
export interface AdvancedChartProps {
  config: ChartConfig;
  className?: string;
  style?: React.CSSProperties;
}

const AdvancedChart: React.FC<AdvancedChartProps> = ({ config, className, style }) => {
  const chartRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [zoomLevel, setZoomLevel] = useState(1);

  const handleZoomIn = useCallback(() => {
    setZoomLevel(prev => Math.min(prev * 1.2, 3));
    // If the chart has zoom interactions, trigger them
    if (chartRef.current?.chart) {
      const chart = chartRef.current.chart;
      try {
        chart.zoom(1.2);
      } catch {
        // Some charts don't support direct zoom
      }
    }
  }, []);

  const handleZoomOut = useCallback(() => {
    setZoomLevel(prev => Math.max(prev / 1.2, 0.5));
    if (chartRef.current?.chart) {
      const chart = chartRef.current.chart;
      try {
        chart.zoom(0.8);
      } catch {
        // Some charts don't support direct zoom
      }
    }
  }, []);

  const handleReset = useCallback(() => {
    setZoomLevel(1);
    if (chartRef.current?.chart) {
      const chart = chartRef.current.chart;
      try {
        chart.resetZoom?.();
        chart.render();
      } catch {
        // Fallback: just re-render
        chart.render();
      }
    }
  }, []);

  const handleToggleFullscreen = useCallback(() => {
    if (!containerRef.current) return;

    if (!isFullscreen) {
      if (containerRef.current.requestFullscreen) {
        containerRef.current.requestFullscreen();
      }
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen();
      }
    }
    setIsFullscreen(!isFullscreen);
  }, [isFullscreen]);

  // Listen for fullscreen changes
  React.useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  const renderChart = () => {
    switch (config.chartType) {
      case 'line':
        return <LineChart config={config} chartRef={chartRef} />;
      case 'column':
      case 'stacked-column':
        return <ColumnChart config={config} chartRef={chartRef} />;
      case 'bar':
        return <BarChart config={config} chartRef={chartRef} />;
      case 'pie':
      case 'donut':
        return <PieChart config={config} chartRef={chartRef} />;
      case 'area':
        return <AreaChart config={config} chartRef={chartRef} />;
      case 'scatter':
        return <ScatterChart config={config} chartRef={chartRef} />;
      case 'dual-axes':
        return <DualAxesChart config={config} chartRef={chartRef} />;
      default:
        // Default to line chart
        return <LineChart config={config} chartRef={chartRef} />;
    }
  };

  const showToolbar = config.showToolbar !== false && config.chartType !== 'pie' && config.chartType !== 'donut';

  return (
    <div
      ref={containerRef}
      className={`advanced-chart-container relative ${isFullscreen ? 'fixed inset-0 z-50 bg-white dark:bg-gray-900 p-6' : ''} ${className || ''}`}
      style={style}
    >
      {config.title && (
        <div className='chart-header mb-3'>
          <h3 className='chart-title text-sm font-semibold text-gray-800 dark:text-gray-200'>{config.title}</h3>
          {config.description && (
            <p className='chart-description text-xs text-gray-500 dark:text-gray-400 mt-1'>{config.description}</p>
          )}
        </div>
      )}

      {showToolbar && (
        <ChartToolbar
          onZoomIn={handleZoomIn}
          onZoomOut={handleZoomOut}
          onReset={handleReset}
          onToggleFullscreen={handleToggleFullscreen}
          isFullscreen={isFullscreen}
          showZoom={config.enableZoom !== false}
          showFullscreen={config.enableFullscreen !== false}
        />
      )}

      <div
        className='chart-body transition-transform duration-200'
        style={{
          transform: `scale(${zoomLevel})`,
          transformOrigin: 'center center',
        }}
      >
        {renderChart()}
      </div>

      {/* Zoom indicator */}
      {zoomLevel !== 1 && (
        <div className='absolute bottom-2 left-2 text-xs text-gray-400 bg-white/80 dark:bg-gray-800/80 px-2 py-1 rounded'>
          {Math.round(zoomLevel * 100)}%
        </div>
      )}
    </div>
  );
};

// Helper function to auto-detect best chart type based on data
export const detectChartType = (data: any[], xField: string, yField: string): ChartType => {
  if (!data || data.length === 0) return 'line';

  const uniqueXValues = new Set(data.map(d => d[xField])).size;
  const hasNegativeValues = data.some(d => d[yField] < 0);
  const isTimeSeries = data.some(d => {
    const val = d[xField];
    return val instanceof Date || !isNaN(Date.parse(val));
  });

  // If time series data, use line or area
  if (isTimeSeries) {
    return 'area';
  }

  // If few categories (< 6), pie chart might be good
  if (uniqueXValues <= 5 && !hasNegativeValues && data.length <= 10) {
    return 'pie';
  }

  // If many categories with comparison, use column
  if (uniqueXValues > 5 && uniqueXValues <= 15) {
    return 'column';
  }

  // Default to line for continuous data
  return 'line';
};

// Helper to convert simple data to chart config
export const createChartConfig = (data: any[], options: Partial<ChartConfig> = {}): ChartConfig => {
  const xField = options.xField || 'x';
  const yField = options.yField || 'y';
  const chartType = options.chartType || detectChartType(data, xField, yField);

  return {
    chartType,
    data,
    xField,
    yField,
    smooth: true,
    autoFit: true,
    showLegend: true,
    showGrid: true,
    animate: true,
    enableZoom: true,
    enableTooltipCrosshairs: true,
    showToolbar: true,
    enableFullscreen: true,
    ...options,
  };
};

// Export individual chart components for direct use
export { AreaChart, BarChart, ColumnChart, DualAxesChart, LineChart, PieChart, ScatterChart };

export default AdvancedChart;
