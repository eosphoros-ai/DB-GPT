import { DashboardLayoutItem, DashboardSchemaV1, DashboardVisualTheme, DashboardWidget } from '@/types/dashboard';
import catalog from '../../../packages/dbgpt-app/src/dbgpt_app/openapi/api_v1/dashboard/schema/dashboard-layout-templates.json';

export type DashboardLayoutTemplateId = 'trend-focus' | 'metric-overview' | 'operations-detail';

export interface DashboardLayoutTemplate {
  id: DashboardLayoutTemplateId;
  title: string;
  eyebrow: string;
  source: string;
  source_url: string;
  description: string;
  structure: string;
  focus: 'trend' | 'metrics' | 'table';
  metric_columns: number;
  chart_columns: number;
  metric_height: number;
  chart_height: number;
  detail_height: number;
  theme: DashboardVisualTheme;
}

export const DASHBOARD_LAYOUT_TEMPLATES = catalog as DashboardLayoutTemplate[];
export const getDashboardLayoutTemplate = (id?: string | null) =>
  DASHBOARD_LAYOUT_TEMPLATES.find(item => item.id === id);

type LayoutWidget = Pick<DashboardWidget, 'id' | 'type' | 'presentation'>;
const visualization = (widget: LayoutWidget) => widget.presentation?.visualization || widget.type;

/** Keep this placement policy in sync with dashboard/layout_templates.py; both use the shared catalog. */
export function templateDashboardLayout(widgets: LayoutWidget[], id: DashboardLayoutTemplateId): DashboardLayoutItem[] {
  const template = getDashboardLayoutTemplate(id);
  if (!template) throw new Error(`Unknown dashboard layout template: ${id}`);
  const metrics = widgets.filter(widget => visualization(widget) === 'kpi');
  const tables = widgets.filter(widget => visualization(widget) === 'table');
  const charts = widgets.filter(widget => !['kpi', 'table'].includes(visualization(widget)));
  const items: DashboardLayoutItem[] = [];
  let y = 0;

  const row = (entries: LayoutWidget[], widths: number[], height: number) => {
    let x = 0;
    entries.forEach((widget, index) => {
      const kind = visualization(widget);
      items.push({
        widget_id: widget.id,
        x,
        y,
        w: widths[index],
        h: height,
        min_w: kind === 'kpi' ? 3 : kind === 'table' ? 6 : 4,
        min_h: kind === 'kpi' ? 3 : 4,
      });
      x += widths[index];
    });
    y += height;
  };
  const balancedRows = (entries: LayoutWidget[], columns: number, height: number) => {
    let offset = 0;
    let remainingRows = Math.ceil(entries.length / columns);
    while (offset < entries.length) {
      const count = Math.ceil((entries.length - offset) / remainingRows);
      row(entries.slice(offset, offset + count), Array(count).fill(12 / count), height);
      offset += count;
      remainingRows -= 1;
    }
  };

  balancedRows(metrics, template.metric_columns, template.metric_height);
  if (template.focus === 'trend' && charts.length) {
    const trendIndex = charts.findIndex(widget => ['line', 'area', 'dual_axis'].includes(visualization(widget)));
    const primary = charts.splice(Math.max(0, trendIndex), 1)[0];
    const secondary = charts.shift();
    row(secondary ? [primary, secondary] : [primary], secondary ? [8, 4] : [12], template.detail_height);
  } else if (template.focus === 'table' && tables.length) {
    const primary = tables.shift()!;
    const secondary = charts.shift();
    row(secondary ? [primary, secondary] : [primary], secondary ? [8, 4] : [12], template.detail_height);
  }
  balancedRows(charts, template.chart_columns, template.chart_height);
  tables.forEach(widget => row([widget], [12], template.detail_height));
  return items;
}

export function applyDashboardLayoutTemplate(
  schema: DashboardSchemaV1,
  id: DashboardLayoutTemplateId,
  withAppearance = true,
): DashboardSchemaV1 {
  const template = getDashboardLayoutTemplate(id);
  if (!template) throw new Error(`Unknown dashboard layout template: ${id}`);
  return {
    ...schema,
    schema_version: withAppearance ? '1.4' : schema.schema_version,
    dashboard: withAppearance
      ? {
          ...schema.dashboard,
          theme: {
            ...template.theme,
            mode: schema.dashboard.theme?.mode || 'light',
            overrides: { ...template.theme.overrides },
          },
        }
      : schema.dashboard,
    layouts: { ...schema.layouts, desktop: templateDashboardLayout(schema.widgets, id) },
  };
}
