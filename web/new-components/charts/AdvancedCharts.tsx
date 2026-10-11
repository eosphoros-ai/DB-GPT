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

// Chart type definitions
export type ChartType = 'line' | 'column' | 'bar' | 'pie' | 'area' | 'scatter' | 'donut' | 'dual-axes';

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
  // Dual axes specific
  yFields?: [string, string];
  geometries?: any[];
  // Appearance
  title?: string;
  description?: string;
  smooth?: boolean;
  autoFit?: boolean;
  height?: number;
  colors?: string[];
  showLegend?: boolean;
  showGrid?: boolean;
  animate?: boolean;
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

// Gradient colors for area charts
const GRADIENT_COLORS = {
  blue: 'l(270) 0:#ffffff 0.5:#3B82F6 1:#1E40AF',
  green: 'l(270) 0:#ffffff 0.5:#10B981 1:#065F46',
  amber: 'l(270) 0:#ffffff 0.5:#F59E0B 1:#B45309',
  purple: 'l(270) 0:#ffffff 0.5:#8B5CF6 1:#5B21B6',
};

// Common theme configuration for all charts
const getCommonConfig = (config: ChartConfig) => ({
  autoFit: config.autoFit ?? true,
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
    colors10: config.colors || PREMIUM_COLORS,
    colors20: config.colors || PREMIUM_COLORS,
  },
});

// Common axis configuration
const getAxisConfig = (showGrid: boolean = true) => ({
  xAxis: {
    line: {
      style: {
        stroke: '#e5e7eb',
        lineWidth: 1,
      },
    },
    tickLine: {
      style: {
        stroke: '#e5e7eb',
      },
    },
    label: {
      style: {
        fill: '#6b7280',
        fontSize: 11,
      },
    },
    grid: showGrid
      ? {
          line: {
            style: {
              stroke: '#f3f4f6',
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
        stroke: '#e5e7eb',
        lineWidth: 1,
      },
    },
    tickLine: {
      style: {
        stroke: '#e5e7eb',
      },
    },
    label: {
      style: {
        fill: '#6b7280',
        fontSize: 11,
      },
    },
    grid: showGrid
      ? {
          line: {
            style: {
              stroke: '#f3f4f6',
              lineWidth: 1,
              lineDash: [4, 4],
            },
          },
        }
      : null,
  },
});

// Legend configuration
const getLegendConfig = (showLegend: boolean = true) => ({
  legend: showLegend
    ? {
        position: 'top-right' as const,
        itemName: {
          style: {
            fill: '#374151',
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
const getTooltipConfig = (config: ChartConfig) => ({
  tooltip: {
    showTitle: true,
    showMarkers: true,
    showCrosshairs: config.enableTooltipCrosshairs ?? true,
    crosshairs: {
      type: 'xy' as const,
      line: {
        style: {
          stroke: '#9CA3AF',
          lineWidth: 1,
          lineDash: [4, 4],
        },
      },
    },
    domStyles: {
      'g2-tooltip': {
        backgroundColor: '#ffffff',
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
        borderRadius: '8px',
        padding: '12px 16px',
        border: '1px solid #e5e7eb',
      },
      'g2-tooltip-title': {
        color: '#111827',
        fontWeight: '600',
        fontSize: '13px',
        marginBottom: '8px',
      },
      'g2-tooltip-list-item': {
        color: '#4b5563',
        fontSize: '12px',
      },
    },
    customContent: (title: string, items: any[]) => {
      if (!items?.length) return '';
      const xField = config.xField || 'x';
      const yField = config.yField || 'y';

      return `
        <div style="padding: 12px 16px; min-width: 160px;">
          <div style="font-weight: 600; font-size: 13px; color: #111827; margin-bottom: 8px; border-bottom: 1px solid #e5e7eb; padding-bottom: 8px;">
            ${title}
          </div>
          ${items
            .map(
              item => `
            <div style="display: flex; align-items: center; justify-content: space-between; margin: 6px 0;">
              <div style="display: flex; align-items: center; gap: 6px;">
                <span style="width: 8px; height: 8px; border-radius: 50%; background: ${item.color};"></span>
                <span style="color: #6b7280; font-size: 12px;">${item.name || yField}</span>
              </div>
              <span style="font-weight: 600; font-size: 12px; color: #111827;">${typeof item.value === 'number' ? item.value.toLocaleString() : item.value}</span>
            </div>
          `,
            )
            .join('')}
          <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #f3f4f6; font-size: 11px; color: #9CA3AF;">
            Click for details • Scroll to zoom
          </div>
        </div>
      `;
    },
  },
});

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
      smooth: config.smooth ?? true,
      ...getCommonConfig(config),
      ...getAxisConfig(config.showGrid),
      ...getLegendConfig(config.showLegend),
      ...getTooltipConfig(config),
      ...getInteractionConfig(config),
      ...getClickHandlerConfig(config, chartRef),
      point: {
        size: 3,
        shape: 'circle',
        style: {
          fill: '#ffffff',
          stroke: config.colors?.[0] || PREMIUM_COLORS[0],
          lineWidth: 2,
          cursor: 'pointer',
        },
      },
      lineStyle: {
        lineWidth: 2.5,
      },
      color: config.colors || PREMIUM_COLORS,
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
  const chartConfig = useMemo(
    () => ({
      data: config.data,
      xField: config.xField || 'x',
      yField: config.yField || 'y',
      seriesField: config.seriesField,
      ...getCommonConfig(config),
      ...getAxisConfig(config.showGrid),
      ...getLegendConfig(config.showLegend),
      ...getTooltipConfig(config),
      ...getInteractionConfig(config),
      ...getClickHandlerConfig(config, chartRef),
      columnWidthRatio: 0.6,
      columnStyle: {
        radius: [4, 4, 0, 0],
        cursor: 'pointer',
      },
      color: config.colors || PREMIUM_COLORS,
      label: {
        position: 'top' as const,
        style: {
          fill: '#6b7280',
          fontSize: 10,
        },
      },
      scrollbar: config.data.length > 12 ? { type: 'horizontal' as const } : undefined,
    }),
    [config, chartRef],
  );

  return <Column {...chartConfig} height={config.height || 300} />;
};

// Bar Chart Component (Horizontal Bar)
const BarChart: React.FC<{ config: ChartConfig; chartRef: React.MutableRefObject<any> }> = ({ config, chartRef }) => {
  const chartConfig = useMemo(
    () => ({
      data: config.data,
      xField: config.yField || 'y', // For horizontal bars, x is the value
      yField: config.xField || 'x', // y is the category
      seriesField: config.seriesField,
      ...getCommonConfig(config),
      ...getAxisConfig(config.showGrid),
      ...getLegendConfig(config.showLegend),
      ...getTooltipConfig(config),
      ...getInteractionConfig(config),
      ...getClickHandlerConfig(config, chartRef),
      barWidthRatio: 0.6,
      barStyle: {
        radius: [0, 4, 4, 0],
        cursor: 'pointer',
      },
      color: config.colors || PREMIUM_COLORS,
      label: {
        position: 'right' as const,
        style: {
          fill: '#6b7280',
          fontSize: 10,
        },
      },
      scrollbar: config.data.length > 10 ? { type: 'vertical' as const } : undefined,
    }),
    [config, chartRef],
  );

  return <Bar {...chartConfig} height={config.height || 300} />;
};

// Pie Chart Component
const PieChart: React.FC<{ config: ChartConfig; chartRef: React.MutableRefObject<any> }> = ({ config, chartRef }) => {
  const isDonut = config.chartType === 'donut';

  const chartConfig = useMemo(
    () => ({
      data: config.data,
      angleField: config.angleField || config.yField || 'value',
      colorField: config.colorField || config.xField || 'type',
      ...getCommonConfig(config),
      ...getLegendConfig(config.showLegend),
      ...getTooltipConfig(config),
      ...getClickHandlerConfig(config, chartRef),
      radius: 0.9,
      innerRadius: isDonut ? 0.6 : 0,
      color: config.colors || PREMIUM_COLORS,
      label: {
        type: 'outer',
        content: '{name}: {percentage}',
        style: {
          fill: '#6b7280',
          fontSize: 11,
        },
      },
      pieStyle: {
        lineWidth: 2,
        stroke: '#ffffff',
        cursor: 'pointer',
      },
      statistic: isDonut
        ? {
            title: {
              style: {
                fontSize: '14px',
                color: '#6b7280',
              },
              content: 'Total',
            },
            content: {
              style: {
                fontSize: '24px',
                fontWeight: '600',
                color: '#111827',
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
    }),
    [config, isDonut, chartRef],
  );

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
      smooth: config.smooth ?? true,
      ...getCommonConfig(config),
      ...getAxisConfig(config.showGrid),
      ...getLegendConfig(config.showLegend),
      ...getTooltipConfig(config),
      ...getInteractionConfig(config),
      ...getClickHandlerConfig(config, chartRef),
      areaStyle: () => ({
        fill: GRADIENT_COLORS.blue,
        fillOpacity: 0.25,
      }),
      line: {
        style: {
          lineWidth: 2,
        },
      },
      color: config.colors || PREMIUM_COLORS,
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
      colorField: config.colorField || config.seriesField,
      ...getCommonConfig(config),
      ...getAxisConfig(config.showGrid),
      ...getLegendConfig(config.showLegend),
      ...getTooltipConfig(config),
      ...getInteractionConfig(config),
      ...getClickHandlerConfig(config, chartRef),
      size: 5,
      shape: 'circle',
      pointStyle: {
        fillOpacity: 0.8,
        stroke: '#ffffff',
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
  const chartConfig = useMemo(
    () => ({
      data: [config.data, config.data],
      xField: config.xField || 'x',
      yField: config.yFields || [config.yField || 'y1', 'y2'],
      ...getCommonConfig(config),
      ...getTooltipConfig(config),
      ...getClickHandlerConfig(config, chartRef),
      geometryOptions: config.geometries || [
        {
          geometry: 'column',
          columnWidthRatio: 0.4,
          color: config.colors?.[0] || PREMIUM_COLORS[0],
        },
        {
          geometry: 'line',
          smooth: true,
          lineStyle: {
            lineWidth: 2,
          },
          color: config.colors?.[1] || PREMIUM_COLORS[1],
        },
      ],
      legend: {
        position: 'top-right' as const,
      },
      interactions: [{ type: 'element-active' }, { type: 'element-highlight' }],
      slider: config.enableZoom !== false ? { start: 0, end: 1 } : undefined,
    }),
    [config, chartRef],
  );

  return <DualAxes {...chartConfig} height={config.height || 300} />;
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
