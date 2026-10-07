import type { DashboardRefreshPayload } from '@/types/scheduled-task';
import { Alert, Typography } from 'antd';
import Link from 'next/link';

export default function DashboardTaskContext({ payload, title }: { payload: DashboardRefreshPayload; title?: string }) {
  return (
    <div className='space-y-3 text-sm'>
      <div>
        <Typography.Text type='secondary'>关联看板</Typography.Text>
        <div className='mt-1'>
          <Link href={`/dashboards/${encodeURIComponent(payload.dashboard_id)}/`}>{title || '打开关联看板'}</Link>
        </div>
      </div>
      <p className='text-gray-500 dark:text-gray-400'>
        按执行时已保存的看板查询数据，沿用创建任务时的筛选条件；相对日期会随执行时间更新。
      </p>
      {Object.keys(payload.filters).length > 0 && <p>已记录 {Object.keys(payload.filters).length} 项筛选条件。</p>}
      {payload.publish_after_refresh && <p>执行成功后同步发布新的看板快照。</p>}
      <Alert type='info' showIcon message='关闭网页后仍可执行，请保持本机 DB-GPT 服务运行。' />
    </div>
  );
}
