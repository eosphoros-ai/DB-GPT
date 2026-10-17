import { AdvancedChart } from '@/new-components/charts';
import {
  DashboardSelectionTarget,
  DashboardSortDirection,
  DashboardVisualization,
  DashboardWidget,
  DashboardWidgetResult,
  MetricContext,
} from '@/types/dashboard';
import {
  AppstoreOutlined,
  CalendarOutlined,
  CaretDownOutlined,
  CaretUpOutlined,
  CodeOutlined,
  CommentOutlined,
  DollarCircleOutlined,
  EditOutlined,
  ExpandOutlined,
  GlobalOutlined,
  HolderOutlined,
  ReloadOutlined,
  ShoppingOutlined,
  SwapOutlined,
  TeamOutlined,
} from '@ant-design/icons';
import { Alert, Button, ConfigProvider, Empty, Spin, Table, Tag, Tooltip } from 'antd';
import { CSSProperties, MouseEvent, useMemo, useRef, useState } from 'react';
import DashboardAnomalyEvidence from './DashboardAnomalyEvidence';
import DashboardCohortMatrix from './DashboardCohortMatrix';
import DashboardExtendedChart from './DashboardExtendedChart';
import DashboardWallChart from './DashboardWallChart';
import styles from './DashboardWorkspace.module.css';
import { DashboardThemeTokens } from './dashboard-appearance';
import { isWidgetQueryUnconfigured } from './dashboard-editor-model';
import { dashboardNumberFormat, dashboardTableFieldFormat, isDashboardMeasure } from './dashboard-number-format';
import { useWidgetContentSize } from './use-widget-content-size';

interface DashboardWidgetCardProps {
  widget: DashboardWidget;
  metricContext?: MetricContext;
  result?: DashboardWidgetResult;
  loading?: boolean;
  editable?: boolean;
  compact?: boolean;
  selected?: boolean;
  editorMode?: 'visual' | 'query';
  onSelect?: () => void;
  onExpand?: () => void;
  onSelectData?: (datum: Record<string, unknown>) => void;
  onEditWidget?: () => void;
  onOpenQueryEditor?: () => void;
  onRequestAgentConfiguration?: (anchor: DOMRect) => void;
  agentConfigurationDisabled?: boolean;
  onRetry?: () => void;
  annotationMode?: boolean;
  annotationMarkers?: Array<{ id: string; number: number; content: string }>;
  onEditAnnotationDraft?: (id: string, anchor: DOMRect) => void;
  onSelectAnnotationTarget?: (target: DashboardSelectionTarget, anchor: DOMRect) => void;
  theme?: DashboardThemeTokens;
}

const chartAppearance = (style: Record<string, unknown>) => ({
  colors: Array.isArray(style.colors)
    ? style.colors.filter((color): color is string => typeof color === 'string')
    : undefined,
  showLegend: typeof style.showLegend === 'boolean' ? style.showLegend : undefined,
  showGrid: typeof style.showGrid === 'boolean' ? style.showGrid : undefined,
  animate: typeof style.animate === 'boolean' ? style.animate : undefined,
});

const legacyVisualization = (widget: DashboardWidget): DashboardVisualization => {
  if (widget.type === 'bar') return 'column';
  if (widget.type === 'pie') return 'donut';
  return widget.type;
};

const visualizationLabels: Record<DashboardVisualization, string> = {
  kpi: '指标卡',
  line: '折线图',
  area: '面积图',
  column: '柱状图',
  bar: '条形图',
  stacked_column: '堆叠图',
  pie: '饼图',
  donut: '环形图',
  scatter: '散点图',
  dual_axis: '双轴图',
  heatmap: '热力图',
  cohort: '留存矩阵',
  gauge: '仪表盘',
  funnel: '漏斗图',
  treemap: '矩形树图',
  radar: '雷达图',
  waterfall: '瀑布图',
  geo_map: '地理分布图',
  table: '明细表',
};
const metricIcons = {
  team: <TeamOutlined />,
  global: <GlobalOutlined />,
  shopping: <ShoppingOutlined />,
  calendar: <CalendarOutlined />,
  revenue: <DollarCircleOutlined />,
  appstore: <AppstoreOutlined />,
};

export function rowsToObjects(result?: DashboardWidgetResult): Record<string, unknown>[] {
  if (!result) return [];
  return result.rows.map(row =>
    result.columns.reduce<Record<string, unknown>>((record, column, index) => {
      record[column] = row[index];
      return record;
    }, {}),
  );
}

export default function DashboardWidgetCard({
  widget,
  metricContext,
  result,
  loading,
  editable,
  compact = false,
  selected,
  editorMode = 'visual',
  onSelect,
  onExpand,
  onSelectData,
  onEditWidget,
  onOpenQueryEditor,
  onRequestAgentConfiguration,
  agentConfigurationDisabled = false,
  onRetry,
  annotationMode = false,
  annotationMarkers = [],
  onEditAnnotationDraft,
  onSelectAnnotationTarget,
  theme,
}: DashboardWidgetCardProps) {
  const cardRef = useRef<HTMLElement>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const contentSize = useWidgetContentSize(bodyRef);
  const data = useMemo(() => rowsToObjects(result), [result]);
  const fieldFormats = useMemo(
    () =>
      new Map(
        (result?.columns || []).map(field => {
          const values = data.map(row => row[field]);
          const metric = metricContext?.metrics?.find(item =>
            [item.id, item.name, item.source_field?.split('.').at(-1)].includes(field),
          );
          return [
            field,
            isDashboardMeasure(field, widget, values, metricContext)
              ? dashboardTableFieldFormat(values, widget, field, metric?.unit)
              : { unit: '', format: (value: unknown) => (value == null ? '—' : String(value)) },
          ];
        }),
      ),
    [data, metricContext, result?.columns, widget],
  );
  const formatField = (value: unknown, field: string) => fieldFormats.get(field)?.format(value) ?? String(value ?? '—');
  const encoding = widget.encoding;
  const appearance = {
    ...chartAppearance(widget.style),
    dashboardSurface: true,
    fieldLabels: Object.fromEntries(widget.query.output_fields.map(field => [field.name, field.label || field.name])),
    height: Math.max(1, contentSize.height),
    width: contentSize.width,
    enableZoom: false,
  };
  const chartColors = widget.presentation?.colors.length
    ? widget.presentation.colors
    : appearance.colors || theme?.chartPalette;
  const chartVisualTheme = theme
    ? {
        mode: theme.mode,
        text: theme.text,
        muted: theme.muted,
        grid: theme.chartGrid,
        card: theme.card,
        border: theme.border,
        primary: theme.primary,
        seriesDashes: theme.seriesDashes,
        seriesShapes: theme.seriesShapes,
      }
    : undefined;
  const unconfigured = isWidgetQueryUnconfigured(widget);
  const visualization = widget.presentation?.visualization || legacyVisualization(widget);
  const anomalyEvidence = result?.anomalies || [];
  const hasAnomaly = anomalyEvidence.some(item => item.status === 'anomaly');
  const renderData = useMemo(() => {
    const topN = widget.presentation?.top_n;
    if (!topN || data.length <= topN) return data;
    const valueField = encoding.y || encoding.value || encoding.angle || result?.columns[1];
    if (!valueField) return data.slice(0, topN);
    return [...data]
      .sort((left, right) => Number(right[valueField] || 0) - Number(left[valueField] || 0))
      .slice(0, topN);
  }, [data, encoding.angle, encoding.value, encoding.y, result?.columns, widget.presentation?.top_n]);
  const chartFormat = useMemo(() => {
    const fields = (result?.columns || []).filter(field =>
      isDashboardMeasure(
        field,
        widget,
        data.map(row => row[field]),
        metricContext,
      ),
    );
    const units = [
      ...new Set(
        metricContext?.metrics
          ?.filter(item =>
            fields.some(field => [item.id, item.name, item.source_field?.split('.').at(-1)].includes(field)),
          )
          .map(item => item.unit)
          .filter(Boolean),
      ),
    ];
    const values = renderData.flatMap(row => fields.map(field => row[field]));
    const sourceUnit = units.length === 1 ? units[0] : undefined;
    return {
      ...dashboardNumberFormat(values, widget, true, sourceUnit),
      fullFormat: dashboardNumberFormat(values, widget, false, sourceUnit).format,
    };
  }, [data, metricContext, renderData, result?.columns, widget]);
  const [tableSort, setTableSort] = useState<{ field: string | null; direction: DashboardSortDirection }>(() => ({
    field: widget.presentation?.default_sort.field || null,
    direction: widget.presentation?.default_sort.direction || 'default',
  }));

  const selectAnnotationTarget = (target: DashboardSelectionTarget, event?: MouseEvent<HTMLElement>) => {
    if (!annotationMode || !onSelectAnnotationTarget) return;
    const anchor = event?.currentTarget.getBoundingClientRect() || cardRef.current?.getBoundingClientRect();
    if (!anchor) return;
    onSelectAnnotationTarget(target, anchor);
  };

  const widgetTarget = (): DashboardSelectionTarget => ({
    kind: 'widget',
    widget_id: widget.id,
    label: `组件：${widget.title}`,
    datum_key: {},
    row_key: {},
  });

  const chartDatumTarget = (datum: Record<string, unknown>): DashboardSelectionTarget => {
    const xField = encoding.x || encoding.category || encoding.color || result?.columns[0];
    const seriesField = encoding.series || undefined;
    const datumKey: Record<string, unknown> = {};
    if (xField && datum[xField] !== undefined) datumKey[xField] = datum[xField];
    if (seriesField && datum[seriesField] !== undefined) datumKey[seriesField] = datum[seriesField];
    const valueField = encoding.y || encoding.value || encoding.angle || result?.columns[1] || result?.columns[0];
    return {
      kind: 'chart_datum',
      widget_id: widget.id,
      label: `数据点：${xField ? String(datum[xField] ?? '') : widget.title}`,
      datum_key: datumKey,
      series: seriesField ? String(datum[seriesField] ?? '') || null : null,
      row_key: {},
      value: valueField ? datum[valueField] : undefined,
    };
  };

  const cycleSort = (field: string) => {
    setTableSort(current => {
      if (current.field !== field || current.direction === 'default') return { field, direction: 'ascending' };
      if (current.direction === 'ascending') return { field, direction: 'descending' };
      return { field: null, direction: 'default' };
    });
  };

  const tableData = useMemo<
    Array<Record<string, unknown> & { __dbgpt_dashboard_row_key: string; __dbgpt_dashboard_original_index: number }>
  >(() => {
    const keyed: Array<
      Record<string, unknown> & {
        __dbgpt_dashboard_row_key: string;
        __dbgpt_dashboard_original_index: number;
      }
    > = data.map((row, index) => ({
      ...row,
      __dbgpt_dashboard_row_key: `${index}-${result?.rows[index]?.map(value => String(value)).join('|') || ''}`,
      __dbgpt_dashboard_original_index: index,
    }));
    if (!tableSort.field || tableSort.direction === 'default') return keyed;
    const field = tableSort.field;
    const direction = tableSort.direction === 'ascending' ? 1 : -1;
    return [...keyed].sort((left, right) => {
      const leftValue = left[field];
      const rightValue = right[field];
      const leftEmpty = leftValue == null || leftValue === '';
      const rightEmpty = rightValue == null || rightValue === '';
      if (leftEmpty || rightEmpty) {
        if (leftEmpty && rightEmpty)
          return left.__dbgpt_dashboard_original_index - right.__dbgpt_dashboard_original_index;
        return leftEmpty ? 1 : -1;
      }
      let comparison = 0;
      if (typeof leftValue === 'number' && typeof rightValue === 'number') comparison = leftValue - rightValue;
      else {
        const leftDate = Date.parse(String(leftValue));
        const rightDate = Date.parse(String(rightValue));
        comparison =
          Number.isFinite(leftDate) && Number.isFinite(rightDate)
            ? leftDate - rightDate
            : String(leftValue).localeCompare(String(rightValue), 'zh-CN', { numeric: true });
      }
      return comparison === 0
        ? left.__dbgpt_dashboard_original_index - right.__dbgpt_dashboard_original_index
        : comparison * direction;
    });
  }, [data, result?.rows, tableSort]);

  const content = () => {
    if (loading) {
      return (
        <div className='flex h-full items-center justify-center gap-2 text-sm text-[var(--app-muted)]'>
          <Spin size='small' />
          <span>正在查询数据…</span>
        </div>
      );
    }
    if (unconfigured) {
      return (
        <div
          data-testid='dashboard-widget-unconfigured'
          className='flex h-full min-h-44 items-center justify-center px-4 py-5 text-center'
        >
          <div className='w-full max-w-sm rounded-xl border border-dashed border-[var(--app-border)] bg-[var(--app-accent-soft)] px-4 py-5'>
            <div className='mx-auto flex h-9 w-9 items-center justify-center rounded-full bg-[var(--app-surface)] text-[var(--app-accent)] shadow-sm'>
              <CodeOutlined />
            </div>
            <div className='mt-3 text-sm font-medium text-[var(--app-text)]'>
              {widget.error ? '查询生成失败，等待配置' : '尚未配置查询'}
            </div>
            <div className='mx-auto mt-1 max-w-xs text-xs leading-5 text-[var(--app-muted)]'>
              选择数据助理自动生成查询与字段映射，或直接手动编写 SQL。
            </div>
            {editable && (onRequestAgentConfiguration || onOpenQueryEditor) && (
              <div className='mt-4 flex flex-wrap justify-center gap-2'>
                {onRequestAgentConfiguration && (
                  <Button
                    size='small'
                    type='primary'
                    aria-label='让数据助理配置'
                    icon={<CommentOutlined />}
                    disabled={agentConfigurationDisabled}
                    onClick={event => {
                      event.stopPropagation();
                      onRequestAgentConfiguration(event.currentTarget.getBoundingClientRect());
                    }}
                  >
                    让数据助理配置
                  </Button>
                )}
                {onOpenQueryEditor && (
                  <Button
                    size='small'
                    aria-label='手动配置 SQL'
                    icon={<CodeOutlined />}
                    onClick={event => {
                      event.stopPropagation();
                      onOpenQueryEditor();
                    }}
                  >
                    手动配置 SQL
                  </Button>
                )}
              </div>
            )}
            {editable && agentConfigurationDisabled && onRequestAgentConfiguration && (
              <div className='mt-2 text-[11px] text-[var(--app-muted)]'>
                此看板没有可续接的数据助理任务，请手动配置 SQL。
              </div>
            )}
          </div>
        </div>
      );
    }
    const error = result?.error || widget.error;
    if (error) {
      return (
        <Alert
          type='error'
          showIcon
          message='这个组件暂时不可用'
          description={error.message}
          action={
            error.retryable && onRetry ? (
              <Button size='small' icon={<ReloadOutlined />} onClick={onRetry}>
                重试
              </Button>
            ) : undefined
          }
        />
      );
    }
    if (!result || !data.length) return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description='暂无数据' />;

    if (visualization === 'kpi') {
      const valueField = encoding.value || result.columns[0];
      const rawValue = data[0]?.[valueField];
      const displayValue = compact
        ? dashboardNumberFormat(
            [rawValue],
            {
              ...widget,
              presentation: widget.presentation
                ? { ...widget.presentation, precision: Number(rawValue) >= 1e5 ? 1 : widget.presentation.precision }
                : widget.presentation,
            },
            true,
          ).format(rawValue)
        : formatField(rawValue, valueField);
      const textUnits = [...String(displayValue)].reduce((sum, char) => sum + (char.charCodeAt(0) > 255 ? 1 : 0.64), 0);
      const kpiFontSize = contentSize.width
        ? Math.min(theme?.kpiSize || 34, Math.max(14, (contentSize.width - 30) / Math.max(1, textUnits)))
        : theme?.kpiSize;
      const hero =
        typeof widget.style.hero_image === 'string' &&
        widget.style.hero_image.startsWith('/dashboard-templates/assets/');
      const icon = metricIcons[widget.style.metric_icon as keyof typeof metricIcons];
      return (
        <div
          data-dashboard-kpi-style={theme?.kpiStyle || 'quiet'}
          data-kpi-hero={hero || undefined}
          className={`${styles.kpiContent} ${
            theme?.kpiStyle === 'solid'
              ? styles.kpiSolid
              : theme?.kpiStyle === 'accent'
                ? styles.kpiAccent
                : styles.kpiQuiet
          }`}
          style={{
            ...(hero
              ? {
                  backgroundImage: `linear-gradient(0deg, #172c12ed 0%, #172c1220 90%), url("${widget.style.hero_image}")`,
                  backgroundSize: 'cover',
                  backgroundPosition: 'center',
                  justifyContent: 'flex-end',
                  color: '#fff',
                }
              : {}),
            backgroundColor:
              theme?.kpiStyle === 'solid'
                ? theme.primary
                : theme?.kpiStyle === 'accent'
                  ? theme.primarySoft
                  : 'transparent',
            borderColor: theme?.kpiStyle === 'accent' ? theme.primary : 'transparent',
            color: hero ? '#fff' : theme?.kpiStyle === 'solid' ? theme.card : theme?.text,
          }}
        >
          <div data-dashboard-kpi-value className={styles.kpiValue} style={{ fontSize: kpiFontSize, color: 'inherit' }}>
            {displayValue}
          </div>
          <div
            className={styles.kpiContext}
            style={{ color: hero ? '#eef3eb' : theme?.kpiStyle === 'solid' ? theme.card : theme?.muted }}
          >
            {widget.query.grain || '当前筛选范围'}
          </div>
          {icon && (
            <span className={styles.kpiIcon} aria-hidden='true'>
              {icon}
            </span>
          )}
        </div>
      );
    }

    if (
      compact &&
      ['gauge', 'donut', 'pie', 'bar', 'column', 'area', 'line'].includes(visualization) &&
      !renderData.some(d => Number(d[encoding.y || encoding.value || encoding.angle || 'value']) < 0)
    ) {
      return (
        <DashboardWallChart
          kind={visualization}
          data={renderData}
          xField={encoding.x || encoding.category || result.columns[0]}
          yField={encoding.y || encoding.value || encoding.angle || 'value'}
          seriesField={encoding.series}
          format={chartFormat.format}
          colors={chartColors || ['#65D8EF']}
          width={contentSize.width}
          height={contentSize.height}
          onSelect={annotationMode ? datum => selectAnnotationTarget(chartDatumTarget(datum)) : onSelectData}
        />
      );
    }
    if (visualization === 'gauge') {
      const valueField = encoding.value || result.columns[0];
      const targetField = encoding.target || undefined;
      const current = Number(data[0]?.[valueField]);
      const configuredTarget = targetField ? Number(data[0]?.[targetField]) : Number(widget.style.target);
      const target =
        Number.isFinite(configuredTarget) && configuredTarget > 0 ? configuredTarget : Math.max(current, 100);
      const ratio = Number.isFinite(current) && target > 0 ? Math.max(0, Math.min(1, current / target)) : 0;
      const gaugeFormat = dashboardNumberFormat([current, target], widget);
      return (
        <button
          type='button'
          className={`flex h-full w-full flex-col items-center justify-center bg-transparent ${annotationMode ? 'cursor-crosshair' : 'cursor-default'}`}
          onClick={event => {
            event.stopPropagation();
            selectAnnotationTarget(chartDatumTarget(data[0] || {}), event);
          }}
        >
          <div
            className='relative flex h-40 w-40 items-center justify-center rounded-full'
            style={{
              background: `conic-gradient(${widget.presentation?.colors?.[0] || theme?.primary || 'var(--app-accent)'} ${ratio * 360}deg, ${theme?.border || 'var(--app-border)'} 0deg)`,
            }}
          >
            <div
              className='flex h-28 w-28 flex-col items-center justify-center rounded-full'
              style={{ backgroundColor: theme?.card, color: theme?.text }}
            >
              <span className='text-2xl font-semibold'>{gaugeFormat.format(current)}</span>
              <span className='mt-1 text-xs' style={{ color: theme?.muted }}>
                {(ratio * 100).toFixed(1)}% {String(widget.style.progress_label || '目标')}
              </span>
            </div>
          </div>
          <span className='mt-3 text-xs' style={{ color: theme?.muted }}>
            {String(widget.style.target_label || '目标')}：{gaugeFormat.format(target)}
          </span>
        </button>
      );
    }

    if (visualization === 'cohort') {
      return <DashboardCohortMatrix widget={widget} data={data} theme={theme} />;
    }

    if (visualization === 'heatmap') {
      const rowField = encoding.row || encoding.y || result.columns[0];
      const columnField = encoding.column || encoding.x || result.columns[1];
      const valueField = encoding.value || result.columns[2];
      const rows = Array.from(new Set(renderData.map(item => String(item[rowField] ?? '—'))));
      const columns = Array.from(new Set(renderData.map(item => String(item[columnField] ?? '—'))));
      const values = renderData.map(item => Number(item[valueField])).filter(Number.isFinite);
      const min = values.length ? Math.min(...values) : 0;
      const max = values.length ? Math.max(...values) : 1;
      const lookup = new Map(
        renderData.map(item => [`${String(item[rowField] ?? '—')}\u0000${String(item[columnField] ?? '—')}`, item]),
      );
      return (
        <div className='h-full overflow-auto text-xs'>
          <div
            className='grid min-w-max gap-1'
            style={{ gridTemplateColumns: `minmax(90px, auto) repeat(${columns.length}, minmax(54px, 1fr))` }}
          >
            <div />
            {columns.map(column => (
              <div
                key={column}
                className='truncate px-1 py-2 text-center'
                style={{ color: theme?.muted }}
                title={column}
              >
                {column}
              </div>
            ))}
            {rows.flatMap(row => {
              const rowItems = [
                <div
                  key={`${row}-label`}
                  className='truncate px-1 py-3 font-medium'
                  style={{ color: theme?.text }}
                  title={row}
                >
                  {row}
                </div>,
              ];
              columns.forEach(column => {
                const datum = lookup.get(`${row}\u0000${column}`);
                const value = datum ? Number(datum[valueField]) : Number.NaN;
                const intensity = Number.isFinite(value)
                  ? 0.08 + ((value - min) / Math.max(1e-9, max - min)) * 0.3
                  : 0.05;
                const heatColor = widget.presentation?.colors?.[0] || theme?.primary || 'var(--app-accent)';
                rowItems.push(
                  <button
                    key={`${row}-${column}`}
                    type='button'
                    title={
                      datum
                        ? `${row} / ${column}: ${formatField(datum[valueField], valueField)}`
                        : `${row} / ${column}: 无数据`
                    }
                    className='min-h-10 rounded border border-[var(--app-border)] px-1 text-center text-xs hover:ring-2 hover:ring-[var(--app-accent)]'
                    style={{
                      backgroundColor: `color-mix(in srgb, ${heatColor} ${intensity * 100}%, transparent)`,
                      color: intensity > 0.55 ? 'var(--app-on-accent)' : theme?.text || 'var(--app-text)',
                    }}
                    onClick={event => {
                      event.stopPropagation();
                      if (datum) selectAnnotationTarget(chartDatumTarget(datum), event);
                    }}
                  >
                    {datum ? formatField(datum[valueField], valueField) : '—'}
                  </button>,
                );
              });
              return rowItems;
            })}
          </div>
        </div>
      );
    }

    if (visualization === 'table') {
      const fields = encoding.columns.length ? encoding.columns : result.columns;
      return (
        <div
          className={styles.dashboardTable}
          data-dashboard-table-style={theme?.tableStyle || 'plain'}
          style={{ '--dashboard-table-stripe': theme?.cardMuted } as CSSProperties}
        >
          <ConfigProvider
            theme={
              theme
                ? {
                    token: {
                      colorBgContainer: theme.card,
                      colorFillAlter: theme.cardMuted,
                      colorText: theme.text,
                      colorTextSecondary: theme.muted,
                      colorBorderSecondary: theme.border,
                      colorPrimary: theme.primary,
                    },
                    components: {
                      Table: {
                        headerBg: theme.cardMuted,
                        headerColor: theme.text,
                        rowHoverBg: theme.primarySoft,
                        borderColor: theme.border,
                      },
                    },
                  }
                : undefined
            }
          >
            <Table
              size='small'
              rowKey='__dbgpt_dashboard_row_key'
              pagination={
                typeof widget.style.pageSize === 'number'
                  ? { pageSize: Math.max(1, Math.floor(widget.style.pageSize)), hideOnSinglePage: true }
                  : false
              }
              scroll={{ x: compact ? '100%' : true, y: compact ? Math.max(70, contentSize.height - 48) : 220 }}
              dataSource={tableData}
              columns={fields.map(field => {
                const output = widget.query.output_fields.find(item => item.name === field);
                const activeSort = tableSort.field === field ? tableSort.direction : 'default';
                return {
                  key: field,
                  dataIndex: field,
                  title: (
                    <div
                      className={`flex items-center gap-1 ${annotationMode ? 'cursor-crosshair' : ''}`}
                      onClick={event => {
                        event.stopPropagation();
                        selectAnnotationTarget(
                          {
                            kind: 'table_column',
                            widget_id: widget.id,
                            label: `表格列：${output?.label || field}`,
                            datum_key: {},
                            column: field,
                            row_key: {},
                          },
                          event,
                        );
                      }}
                    >
                      <span className='min-w-0 flex-1 truncate'>{output?.label || field}</span>
                      <Tooltip
                        title={
                          activeSort === 'default'
                            ? '按此列升序'
                            : activeSort === 'ascending'
                              ? '改为降序'
                              : '恢复默认顺序'
                        }
                      >
                        <Button
                          aria-label={`${output?.label || field}排序`}
                          type='text'
                          size='small'
                          className='!h-6 !w-6 !p-0'
                          icon={
                            activeSort === 'ascending' ? (
                              <CaretUpOutlined />
                            ) : activeSort === 'descending' ? (
                              <CaretDownOutlined />
                            ) : (
                              <SwapOutlined rotate={90} className='text-[var(--app-muted)]' />
                            )
                          }
                          onClick={event => {
                            event.stopPropagation();
                            cycleSort(field);
                          }}
                        />
                      </Tooltip>
                    </div>
                  ),
                  ellipsis: true,
                  align:
                    output?.type === 'number' || output?.type === 'integer' ? ('right' as const) : ('left' as const),
                  onCell: (row: Record<string, unknown>) => ({
                    className: annotationMode ? 'cursor-crosshair hover:!bg-[var(--app-accent-soft)]' : undefined,
                    onClick: (event: MouseEvent<HTMLElement>) => {
                      event.stopPropagation();
                      selectAnnotationTarget(
                        {
                          kind: 'table_cell',
                          widget_id: widget.id,
                          label: `单元格：${output?.label || field} = ${String(row[field] ?? '')}`,
                          datum_key: {},
                          column: field,
                          row_key: { __row_index: row.__dbgpt_dashboard_original_index },
                          value: row[field],
                        },
                        event,
                      );
                    },
                  }),
                  render: (value: unknown) => formatField(value, field),
                };
              })}
            />
          </ConfigProvider>
        </div>
      );
    }

    if (['funnel', 'treemap', 'radar', 'waterfall', 'geo_map'].includes(visualization)) {
      return (
        <DashboardExtendedChart
          visualization={visualization}
          mapRegion={widget.style.map_region === 'china' ? 'china' : undefined}
          data={renderData}
          categoryField={encoding.x || result.columns[0]}
          valueField={encoding.y || result.columns[1]}
          format={chartFormat.format}
          colors={chartColors}
          theme={theme}
          onSelect={annotationMode ? datum => selectAnnotationTarget(chartDatumTarget(datum)) : onSelectData}
        />
      );
    }

    if (visualization === 'pie' || visualization === 'donut') {
      return (
        <AdvancedChart
          config={{
            chartType: visualization,
            data: renderData,
            angleField: encoding.angle || encoding.y || result.columns[1],
            colorField: encoding.color || encoding.category || encoding.x || result.columns[0],
            ...appearance,
            colors: chartColors,
            visualTheme: chartVisualTheme,
            measureFormat: chartFormat,
            showLegend: widget.presentation?.show_legend ?? appearance.showLegend,
            innerRadius:
              visualization === 'donut'
                ? typeof widget.style.innerRadius === 'number'
                  ? widget.style.innerRadius
                  : 0.6
                : 0,
            showToolbar: false,
            onDataPointClick: annotationMode
              ? datum => selectAnnotationTarget(chartDatumTarget(datum || {}))
              : undefined,
          }}
        />
      );
    }

    const chartType =
      visualization === 'area'
        ? 'area'
        : visualization === 'column'
          ? 'column'
          : visualization === 'bar'
            ? 'bar'
            : visualization === 'stacked_column'
              ? 'stacked-column'
              : visualization === 'scatter'
                ? 'scatter'
                : visualization === 'dual_axis'
                  ? 'dual-axes'
                  : 'line';
    return (
      <AdvancedChart
        config={{
          chartType,
          data: renderData,
          xField: encoding.x || result.columns[0],
          yField: encoding.y || result.columns[1],
          yFields:
            chartType === 'dual-axes' ? [encoding.y || result.columns[1], encoding.y2 || result.columns[2]] : undefined,
          colorField: encoding.color || undefined,
          seriesField: encoding.series || undefined,
          ...appearance,
          colors: chartColors,
          visualTheme: chartVisualTheme,
          measureFormat: chartFormat,
          showLegend: widget.presentation?.show_legend ?? appearance.showLegend,
          showGrid: widget.presentation?.show_grid ?? appearance.showGrid,
          showToolbar: false,
          smooth:
            widget.presentation?.smooth ?? (typeof widget.style.smooth === 'boolean' ? widget.style.smooth : true),
          stacked: visualization === 'stacked_column' || widget.presentation?.stacked,
          onDataPointClick: annotationMode ? datum => selectAnnotationTarget(chartDatumTarget(datum || {})) : undefined,
        }}
      />
    );
  };

  return (
    <section
      ref={cardRef}
      data-dashboard-widget-id={widget.id}
      onClick={event => {
        if (annotationMode) {
          selectAnnotationTarget(widgetTarget(), event);
          return;
        }
        onSelect?.();
      }}
      className={`${styles.widgetCard} ${visualization === 'kpi' ? styles.metricWidgetCard : ''} ${
        selected ? styles.widgetSelected : ''
      } ${annotationMode ? 'cursor-crosshair hover:border-[var(--app-accent)]' : ''} ${hasAnomaly ? '!border-[var(--app-danger)] ring-1 ring-[var(--app-danger-soft)]' : ''}`}
      style={{
        ...(theme
          ? {
              backgroundColor: theme.card,
              borderColor: hasAnomaly ? theme.danger : selected ? undefined : theme.border,
              borderRadius: theme.radius,
              boxShadow: theme.shadow,
              color: theme.text,
              fontSize: theme.fontSize,
            }
          : {}),
        fontFamily: typeof widget.style.fontFamily === 'string' ? widget.style.fontFamily : undefined,
      }}
    >
      <header className={`dashboard-widget-drag-handle ${styles.widgetHeader}`}>
        {editable && <HolderOutlined className='cursor-move text-[var(--app-muted)]' />}
        {!!annotationMarkers.length && (
          <div className='flex max-w-24 shrink-0 flex-wrap gap-1'>
            {annotationMarkers.map(item => (
              <button
                key={item.id}
                type='button'
                aria-label={'编辑批注 ' + item.number}
                title={item.content}
                className='flex h-6 min-w-6 items-center justify-center rounded-full bg-[var(--app-accent)] px-1 text-xs font-semibold text-white'
                onClick={event => {
                  event.stopPropagation();
                  onEditAnnotationDraft?.(item.id, event.currentTarget.getBoundingClientRect());
                }}
              >
                {item.number}
              </button>
            ))}
          </div>
        )}
        <div className={styles.widgetTitleBlock}>
          <h3
            className={styles.widgetTitle}
            style={{
              color: theme?.text,
              fontSize: typeof widget.style.fontSize === 'number' ? widget.style.fontSize : undefined,
            }}
          >
            {widget.title}
          </h3>
          {widget.description && (
            <p className={styles.widgetSubtitle} style={{ color: theme?.muted }}>
              {widget.description}
            </p>
          )}
          {!['kpi', 'table', 'gauge', 'heatmap'].includes(visualization) && chartFormat.unit && (
            <p className={styles.widgetSubtitle} style={{ color: theme?.muted }}>
              单位：{chartFormat.unit}
            </p>
          )}
        </div>
        <Tag bordered={false} className={styles.widgetTypeTag}>
          {visualizationLabels[visualization]}
        </Tag>
        {onExpand && (
          <Tooltip title='放大图表与明细'>
            <Button
              aria-label={`查看明细：${widget.title}`}
              size='small'
              type='text'
              icon={<ExpandOutlined />}
              onClick={event => {
                event.stopPropagation();
                onExpand();
              }}
            />
          </Tooltip>
        )}
        {editable && (
          <Tooltip title={annotationMode ? '批注此组件' : '编辑可视化设置'}>
            <Button
              aria-label={annotationMode ? '批注此组件' : '编辑可视化设置'}
              size='small'
              type={!annotationMode && selected && editorMode === 'visual' ? 'primary' : 'text'}
              icon={annotationMode ? <CommentOutlined /> : <EditOutlined />}
              onClick={event => {
                event.stopPropagation();
                if (annotationMode) {
                  selectAnnotationTarget(widgetTarget(), event);
                  return;
                }
                (onEditWidget || onSelect)?.();
              }}
            />
          </Tooltip>
        )}
        {editable && !annotationMode && onSelectAnnotationTarget && (
          <Tooltip title='批注此组件'>
            <Button
              aria-label='批注此组件'
              size='small'
              type='text'
              icon={<CommentOutlined />}
              onClick={event => {
                event.stopPropagation();
                onSelectAnnotationTarget(widgetTarget(), event.currentTarget.getBoundingClientRect());
              }}
            />
          </Tooltip>
        )}
        {editable && !annotationMode && onOpenQueryEditor && (
          <Tooltip title='SQL 与参数设置'>
            <Button
              aria-label='SQL 与参数设置'
              size='small'
              type={selected && editorMode === 'query' ? 'primary' : 'text'}
              icon={<CodeOutlined />}
              onClick={event => {
                event.stopPropagation();
                onOpenQueryEditor();
              }}
            />
          </Tooltip>
        )}
      </header>
      <DashboardAnomalyEvidence evidence={anomalyEvidence} />
      <div ref={bodyRef} className={styles.widgetBody} data-dashboard-widget-body>
        {content()}
      </div>
      {result && !result.error && (
        <footer className={styles.widgetFooter}>
          <span>{result.row_count} 行</span>
          <span>
            {result.duration_ms} ms{result.truncated ? ' · 已截断' : ''}
          </span>
        </footer>
      )}
    </section>
  );
}
