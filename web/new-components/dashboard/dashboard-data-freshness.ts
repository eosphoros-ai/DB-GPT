import type { DashboardSchemaV1, DashboardSnapshot } from '@/types/dashboard';

/** Only report dates present in returned business fields; never infer a database update time. */
export function dashboardDataThrough(schema: DashboardSchemaV1, snapshot: DashboardSnapshot): string | null {
  const dates: string[] = [];
  for (const widget of schema.widgets) {
    const result = snapshot.widgets[widget.id];
    if (!result || result.error) continue;
    for (const field of widget.query.output_fields) {
      const index = result.columns.indexOf(field.name);
      if (
        index < 0 ||
        !(/date|time/i.test(field.type) || /date|month|period|year|day|week|日期|时间|月份/i.test(field.name))
      )
        continue;
      for (const row of result.rows) {
        const raw = row[index];
        if (typeof raw !== 'string' || !/^\d{4}-\d{2}(?:-\d{2}(?:T| |$)|$)/.test(raw)) continue;
        const value = raw.slice(0, 10);
        const full = value.length === 7 ? `${value}-01` : value;
        const parsed = new Date(`${full}T00:00:00Z`);
        if (!Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === full) dates.push(value);
      }
    }
  }
  return dates.sort().at(-1) || null;
}
