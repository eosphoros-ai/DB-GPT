import type { DashboardSchemaV1, DashboardSnapshot } from '@/types/dashboard';
import { dashboardDataThrough } from './dashboard-data-freshness';

export default function DashboardDataFreshness({
  schema,
  snapshot,
}: {
  schema: DashboardSchemaV1;
  snapshot: DashboardSnapshot;
}) {
  const through = dashboardDataThrough(schema, snapshot);
  return (
    <span className='flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-[var(--app-muted)]' aria-label='数据时效'>
      <span>查询时间：{new Date(snapshot.refreshed_at).toLocaleString('zh-CN')}</span>
      <span title='当前筛选结果中可识别的最新业务日期；不代表整个数据库的更新时间。'>
        数据截止（当前结果）：{through || '未提供日期字段'}
      </span>
    </span>
  );
}
