import { getDashboard } from '@/client/api';
import { DashboardEditor } from '@/new-components/dashboard';
import { describeDashboardError } from '@/new-components/dashboard/dashboard-errors';
import { rememberDashboardVisit } from '@/new-components/dashboard/dashboard-visits';
import type { DashboardRecord } from '@/types/dashboard';
import { useRequest } from 'ahooks';
import { Alert, Button, Spin } from 'antd';
import Head from 'next/head';
import { useRouter } from 'next/router';

export default function DashboardEditorPage() {
  const router = useRouter();
  const dashboardId = typeof router.query.id === 'string' ? router.query.id : null;
  const initialPanel =
    router.query.panel === 'access' || router.query.panel === 'lifecycle' || router.query.panel === 'schedule'
      ? router.query.panel
      : null;
  const {
    data: record,
    error,
    refresh,
    mutate: setRecord,
  } = useRequest(
    async (): Promise<DashboardRecord> => {
      const response = await getDashboard(dashboardId!);
      if (!response.data.success || !response.data.data) throw new Error(response.data.err_msg || '看板加载失败');
      rememberDashboardVisit(dashboardId!);
      return response.data.data;
    },
    { ready: !!dashboardId, refreshDeps: [dashboardId] },
  );

  if (error)
    return (
      <div className='m-auto max-w-lg'>
        <Alert
          type='error'
          showIcon
          message='无法打开看板'
          description={describeDashboardError(error, '看板加载失败')}
          action={
            <div className='flex flex-wrap gap-2'>
              <Button onClick={refresh}>重试</Button>
              <Button onClick={() => router.push('/dashboards')}>返回列表</Button>
            </div>
          }
        />
      </div>
    );
  if (!record || record.id !== dashboardId)
    return (
      <div className='m-auto'>
        <div className='flex items-center gap-2 text-sm text-[var(--app-muted)]'>
          <Spin size='large' />
          <span>正在加载看板…</span>
        </div>
      </div>
    );

  return (
    <>
      <Head>
        <title>{record.schema.dashboard.title} · DB-GPT</title>
      </Head>
      <DashboardEditor key={record.id} initialRecord={record} initialPanel={initialPanel} onRecordChange={setRecord} />
    </>
  );
}
