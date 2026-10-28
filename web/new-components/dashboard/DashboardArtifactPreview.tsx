import { getDashboard, refreshDashboard } from '@/client/api/dashboard';
import type { DashboardRecord, DashboardSnapshot } from '@/types/dashboard';
import { Alert, Button, Spin } from 'antd';
import { useRouter } from 'next/router';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import ChatDashboardCard from './ChatDashboardCard';
import type { DashboardGenerationState } from './DashboardGenerationCard';
import DashboardWidgetCard from './DashboardWidgetCard';
import { dashboardThemeCssVariables, resolveDashboardTheme } from './dashboard-appearance';

export default function DashboardArtifactPreview({ state }: { state: DashboardGenerationState }) {
  const { t } = useTranslation();
  const router = useRouter();
  const [record, setRecord] = useState<DashboardRecord>();
  const [snapshot, setSnapshot] = useState<DashboardSnapshot>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    if (!state.dashboardId || state.status !== 'created') return;
    setLoading(true);
    setError('');
    setRecord(undefined);
    setSnapshot(undefined);
    void (async () => {
      try {
        const response = await getDashboard(state.dashboardId!);
        if (!response.data.success || !response.data.data)
          throw new Error(response.data.err_msg || t('dashboard_chat_preview_error'));
        if (cancelled) return;
        setRecord(response.data.data);
        const data = await refreshDashboard(state.dashboardId!, {});
        if (!data.data.success || !data.data.data)
          throw new Error(data.data.err_msg || t('dashboard_chat_preview_error'));
        if (!cancelled) setSnapshot(data.data.data);
      } catch (failure) {
        if (!cancelled) setError(failure instanceof Error ? failure.message : String(failure));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [state.dashboardId, state.status, state.currentRevision, refreshKey, t]);

  const openEditor = () => state.dashboardId && router.push(`/dashboards/${state.dashboardId}`);
  const theme = resolveDashboardTheme(record?.schema.dashboard?.theme);
  return (
    <div data-testid='dashboard-artifact-preview' className='space-y-3' style={dashboardThemeCssVariables(theme)}>
      {state.status !== 'created' ? (
        <ChatDashboardCard state={state} busy={false} onConfirm={() => {}} onRevise={() => {}} onOpen={openEditor} />
      ) : (
        <>
          <div className='text-sm text-gray-500'>{t('dashboard_chat_native_artifact')}</div>
          <div className='flex gap-2'>
            <Button type='primary' onClick={openEditor}>
              {t('dashboard_chat_edit')}
            </Button>
            <Button loading={loading} onClick={() => setRefreshKey(value => value + 1)}>
              {t('dashboard_chat_refresh')}
            </Button>
          </div>
          {error && <Alert type='error' showIcon message={error} />}
          {loading && <Spin />}
          {record?.schema.widgets.map(widget => (
            <div key={widget.id} style={{ height: widget.type === 'kpi' ? 200 : widget.type === 'table' ? 460 : 360 }}>
              <DashboardWidgetCard
                widget={widget}
                metricContext={record.schema.metric_context}
                result={snapshot?.widgets[widget.id]}
                loading={loading}
                theme={theme}
                onRetry={() => setRefreshKey(value => value + 1)}
              />
            </div>
          ))}
        </>
      )}
    </div>
  );
}
