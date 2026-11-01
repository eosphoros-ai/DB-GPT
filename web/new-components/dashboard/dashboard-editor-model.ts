import type {
  DashboardChartEncoding,
  DashboardVisualization,
  DashboardWidget,
  DashboardWidgetType,
} from '@/types/dashboard';

export const UNCONFIGURED_WIDGET_SQL = {
  kpi: 'SELECT NULL AS value WHERE 1 = 0',
  chart: 'SELECT NULL AS category, NULL AS value WHERE 1 = 0',
} as const;

const widgetNames: Record<DashboardWidgetType, string> = {
  kpi: '指标卡',
  line: '折线图',
  bar: '柱状图',
  pie: '饼图',
  table: '明细表',
};

export const unconfiguredWidgetSql = (type: DashboardWidgetType) =>
  type === 'kpi' ? UNCONFIGURED_WIDGET_SQL.kpi : UNCONFIGURED_WIDGET_SQL.chart;

const normalizedSql = (sql?: string | null) => (sql || '').trim().replace(/\s+/g, ' ').toLowerCase();

const LEGACY_FAILED_WIDGET_SQL = [
  'SELECT 0 AS value',
  "SELECT 'Unavailable' AS category, 0 AS value",
  "SELECT 'Query generation failed' AS message",
];

const legacyFailedSql = new Set(LEGACY_FAILED_WIDGET_SQL.map(normalizedSql));

export const isWidgetQueryUnconfigured = (widget: DashboardWidget) =>
  !widget.query.federation &&
  (normalizedSql(widget.query.sql) === normalizedSql(unconfiguredWidgetSql(widget.type)) ||
    legacyFailedSql.has(normalizedSql(widget.query.sql)));

export const hasConfiguredDashboardWidgets = (widgets: DashboardWidget[]) =>
  widgets.some(widget => !isWidgetQueryUnconfigured(widget));

export const makeUnconfiguredWidget = (
  type: DashboardWidgetType,
  dataSourceId: string,
  id = `${type}-${Date.now().toString(36)}`,
): DashboardWidget => {
  const categoryFields = [
    { name: 'category', type: 'string' as const, label: '分类', nullable: true },
    { name: 'value', type: 'number' as const, label: '数值', nullable: true },
  ];
  if (type === 'kpi') {
    return {
      id,
      type,
      title: '新指标',
      description: '',
      metric_ids: [],
      dimension_ids: [],
      query: {
        data_source_id: dataSourceId,
        sql: unconfiguredWidgetSql(type),
        filter_parameters: {},
        default_parameters: {},
        output_fields: [{ name: 'value', type: 'number', label: '数值', nullable: true }],
        timeout_seconds: 30,
        max_rows: 10,
        last_execution: { status: 'never' },
      },
      encoding: { value: 'value', columns: [] },
      style: {},
    };
  }
  return {
    id,
    type,
    title: `新${widgetNames[type]}`,
    description: '',
    metric_ids: [],
    dimension_ids: [],
    query: {
      data_source_id: dataSourceId,
      sql: unconfiguredWidgetSql(type),
      filter_parameters: {},
      default_parameters: {},
      output_fields: categoryFields,
      timeout_seconds: 30,
      max_rows: type === 'table' ? 1000 : 200,
      last_execution: { status: 'never' },
    },
    encoding:
      type === 'pie'
        ? { category: 'category', color: 'category', angle: 'value', columns: [] }
        : type === 'table'
          ? { columns: ['category', 'value'] }
          : { x: 'category', y: 'value', columns: [] },
    style: {},
  };
};

const widgetTypeForVisualization = (visualization: DashboardVisualization): DashboardWidgetType => {
  if (visualization === 'kpi' || visualization === 'gauge') return 'kpi';
  if (visualization === 'table') return 'table';
  if (visualization === 'pie' || visualization === 'donut') return 'pie';
  if (visualization === 'line' || visualization === 'area') return 'line';
  return 'bar';
};

/**
 * Create a zero-row draft that is both recognisably unconfigured and
 * semantically valid for the selected Schema 1.3 visualisation.  This matters
 * because annotation mode auto-saves a newly added widget before sending the
 * user's request to the Agent.  A missing heatmap/dual-axis encoding would make
 * that save fail with 422 before the Agent was ever called.
 */
export const makeUnconfiguredVisualizationWidget = (
  visualization: DashboardVisualization,
  dataSourceId: string,
  id?: string,
): DashboardWidget => {
  const widget = makeUnconfiguredWidget(widgetTypeForVisualization(visualization), dataSourceId, id);
  const categoryValue = { x: 'category', y: 'value', columns: [] };

  switch (visualization) {
    case 'kpi':
      widget.encoding = { value: 'value', columns: [] };
      break;
    case 'gauge':
      widget.encoding = { value: 'value', target: 'value', columns: [] };
      break;
    case 'pie':
    case 'donut':
      widget.encoding = { category: 'category', color: 'category', angle: 'value', columns: [] };
      break;
    case 'table':
      widget.encoding = { columns: ['category', 'value'] };
      break;
    case 'dual_axis':
      widget.encoding = { ...categoryValue, y2: 'value' };
      break;
    case 'heatmap':
      widget.encoding = { row: 'category', column: 'category', value: 'value', columns: [] };
      break;
    case 'cohort':
      widget.encoding = {
        row: 'category',
        column: 'category',
        value: 'value',
        target: 'value',
        color: 'value',
        columns: [],
      };
      break;
    default:
      widget.encoding = categoryValue;
      break;
  }
  return widget;
};

/**
 * Repair drafts created by older editor builds before they are persisted.
 * Only zero-row/unconfigured widgets are touched, so a user's real SQL and
 * field mappings are never rewritten behind their back.
 */
export const normalizeUnconfiguredVisualizationWidget = (widget: DashboardWidget): DashboardWidget => {
  const visualization = widget.presentation?.visualization;
  if (!visualization || !isWidgetQueryUnconfigured(widget)) return widget;

  const normalized = makeUnconfiguredVisualizationWidget(visualization, widget.query.data_source_id, widget.id);
  return {
    ...widget,
    type: normalized.type,
    query: {
      ...widget.query,
      output_fields: normalized.query.output_fields,
      max_rows: normalized.query.max_rows,
    },
    encoding: normalized.encoding,
  };
};

export const encodingForWidgetType = (widget: DashboardWidget, type: DashboardWidgetType): DashboardChartEncoding => {
  const names = widget.query.output_fields.map(field => field.name);
  const has = (value?: string | null) => !!value && names.includes(value);
  const first = names[0];
  const second = names[1] || first;

  if (type === 'kpi') {
    return { value: has(widget.encoding.value) ? widget.encoding.value : first, columns: [] };
  }
  if (type === 'line' || type === 'bar') {
    return {
      x: has(widget.encoding.x) ? widget.encoding.x : first,
      y: has(widget.encoding.y) ? widget.encoding.y : second,
      series: has(widget.encoding.series) ? widget.encoding.series : undefined,
      columns: [],
    };
  }
  if (type === 'pie') {
    const category = has(widget.encoding.category)
      ? widget.encoding.category
      : has(widget.encoding.color)
        ? widget.encoding.color
        : first;
    return {
      category,
      color: category,
      angle: has(widget.encoding.angle) ? widget.encoding.angle : second,
      columns: [],
    };
  }
  const selected = widget.encoding.columns.filter(name => names.includes(name));
  return { columns: selected.length ? selected : names };
};

export const changeWidgetType = (widget: DashboardWidget, type: DashboardWidgetType): DashboardWidget => ({
  ...widget,
  type,
  encoding: encodingForWidgetType(widget, type),
});

export const updateWidgetOutputFields = (widget: DashboardWidget, rawNames: string[]): DashboardWidget => {
  const names = Array.from(new Set(rawNames.map(name => name.trim()).filter(Boolean)));
  const nextWidget: DashboardWidget = {
    ...widget,
    query: {
      ...widget.query,
      output_fields: names.map(
        name =>
          widget.query.output_fields.find(field => field.name === name) || {
            name,
            type: 'unknown',
            nullable: true,
          },
      ),
    },
  };
  return {
    ...nextWidget,
    encoding: encodingForWidgetType(nextWidget, nextWidget.type),
  };
};
