import {
  ArrowLeftOutlined,
  ClockCircleOutlined,
  EditOutlined,
  InfoCircleOutlined,
  LaptopOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { Button, Spin, Switch, message } from 'antd';
import dayjs from 'dayjs';
import { useRouter } from 'next/router';
import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { useConnectors } from '@/hooks/use-connector-api';
import { useScheduledTask } from '@/hooks/use-scheduled-task';
import ConstructLayout from '@/new-components/layout/Construct';
import EditScheduledTaskDrawer from '@/new-components/scheduled-task/EditScheduledTaskDrawer';
import TaskRunsTable from '@/new-components/scheduled-task/TaskRunsTable';
import type { TaskResponse } from '@/types/scheduled-task';

/** Format an ISO timestamp, strip timezone suffix, return a friendly string */
function fmtTime(iso?: string | null): string | null {
  if (!iso) return null;
  const d = dayjs(iso);
  return d.isValid() ? d.format('YYYY-MM-DD HH:mm:ss') : iso;
}

function ScheduledTaskDetail() {
  const router = useRouter();
  const { t } = useTranslation();
  const taskId = router.query.taskId as string | undefined;
  const { getTask, toggleTask } = useScheduledTask();
  const { connectors } = useConnectors();
  const [task, setTask] = useState<TaskResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [editOpen, setEditOpen] = useState(false);

  /** connector id → display_name map */
  const connectorNameMap = useMemo(() => {
    const m = new Map<string, string>();
    for (const c of connectors) {
      m.set(c.id, c.display_name);
    }
    return m;
  }, [connectors]);

  const loadTask = () => {
    if (!taskId) return;
    setLoading(true);
    getTask(taskId)
      .then(setTask)
      .catch((e: any) => message.error(e?.message ?? t('scheduled.msg.loadDetailFailed')))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadTask();
  }, [taskId, getTask]);

  const onToggle = async (enabled: boolean) => {
    if (!task) return;
    try {
      await toggleTask(task.task_id, enabled);
      message.success(enabled ? t('scheduled.msg.enabled') : t('scheduled.msg.paused'));
      loadTask();
    } catch (e: any) {
      message.error(e?.message ?? t('scheduled.msg.opFailed'));
    }
  };

  if (loading || !task) {
    return (
      <ConstructLayout className='scrollable-tabs'>
        <div className='flex items-center justify-center py-20'>
          <Spin size='large' />
        </div>
      </ConstructLayout>
    );
  }

  const ext = (task.payload?.ext_info ?? {}) as Record<string, any>;

  return (
    <ConstructLayout className='scrollable-tabs'>
      <div className='relative w-full bg-gradient-to-b from-[#f7f8fc] via-white to-[#f7f8fc] dark:from-[#1c2333] dark:via-[#1c2333] dark:to-[#161b29]'>
        <div className='max-w-[1400px] mx-auto p-4 md:p-6 lg:p-8'>
          {/* ── Back ── */}
          <Button
            icon={<ArrowLeftOutlined />}
            onClick={() => router.push('/construct/scheduled-tasks')}
            className='mb-5'
          >
            {t('scheduled.detail.back')}
          </Button>

          {/* ── HERO CARD ── */}
          <div className='rounded-2xl border border-white/80 bg-white/80 backdrop-blur-lg shadow-[0_2px_12px_-4px_rgba(15,23,42,0.08)] dark:border-[#3a4456] dark:bg-[#2b303d]/70 p-6 mb-5'>
            <div className='flex items-start justify-between gap-4 flex-wrap'>
              <div className='flex items-start gap-4'>
                <div
                  className={`flex-shrink-0 w-14 h-14 rounded-xl flex items-center justify-center text-white text-2xl shadow-[0_4px_14px_-4px_rgba(6,182,212,0.5)] ${
                    task.enabled
                      ? 'bg-gradient-to-br from-blue-500 to-cyan-600'
                      : 'bg-gradient-to-br from-gray-400 to-gray-500'
                  }`}
                >
                  <ClockCircleOutlined />
                </div>
                <div>
                  <div className='flex items-center gap-3 mb-1.5 flex-wrap'>
                    <h1 className='text-xl font-bold text-gray-900 dark:text-white m-0'>{task.task_name}</h1>
                    {task.enabled ? (
                      <span className='inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-100 dark:bg-emerald-900/30 dark:text-emerald-400 dark:border-emerald-800/40'>
                        <span className='w-1.5 h-1.5 rounded-full bg-emerald-500' />
                        {t('scheduled.status.enabled')}
                      </span>
                    ) : (
                      <span className='inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-gray-100 text-gray-500 border border-gray-200 dark:bg-gray-700/40 dark:text-gray-400 dark:border-gray-600/40'>
                        <span className='w-1.5 h-1.5 rounded-full bg-gray-400' />
                        {t('scheduled.status.disabled')}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <div className='flex items-center gap-2'>
                <Switch
                  checked={task.enabled}
                  onChange={onToggle}
                  className='scheduled-switch'
                  checkedChildren={t('scheduled.detail.enabledBtn')}
                  unCheckedChildren={t('scheduled.detail.pausedBtn')}
                />
                <Button
                  type='text'
                  icon={<EditOutlined />}
                  onClick={() => setEditOpen(true)}
                  className='text-gray-500 hover:!text-cyan-600 hover:!bg-cyan-50 dark:hover:!bg-cyan-900/30'
                >
                  {t('scheduled.detail.edit')}
                </Button>
              </div>
            </div>
          </div>

          {/* ── Basic info ── */}
          <div className='rounded-2xl border border-white/80 bg-white/80 backdrop-blur-lg shadow-[0_2px_12px_-4px_rgba(15,23,42,0.08)] dark:border-[#3a4456] dark:bg-[#2b303d]/70 p-6 mb-5'>
            <h3 className='text-[15px] font-semibold text-gray-800 dark:text-gray-100 mb-4 flex items-center gap-2'>
              <InfoCircleOutlined className='text-gray-400' />
              {t('scheduled.detail.basicInfo')}
            </h3>
            <div className='grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-8 gap-y-4'>
              <InfoField label={t('scheduled.detail.statusLabel')}>
                {task.enabled ? (
                  <span className='inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-100 dark:bg-emerald-900/30 dark:text-emerald-400 dark:border-emerald-800/40'>
                    <span className='w-1.5 h-1.5 rounded-full bg-emerald-500' />
                    {t('scheduled.status.enabled')}
                  </span>
                ) : (
                  <span className='inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-gray-100 text-gray-500 border border-gray-200 dark:bg-gray-700/40 dark:text-gray-400 dark:border-gray-600/40'>
                    <span className='w-1.5 h-1.5 rounded-full bg-gray-400' />
                    {t('scheduled.status.disabled')}
                  </span>
                )}
              </InfoField>
              <InfoField label={t('scheduled.detail.cronLabel')}>
                <code className='mono text-[14px] text-gray-800 dark:text-gray-200 bg-gray-50 dark:bg-gray-700/40 px-2 py-0.5 rounded border border-gray-100 dark:border-gray-600/40'>
                  {task.cron_expression}
                </code>
              </InfoField>
              <InfoField label={t('scheduled.detail.nextRunLabel')}>
                {fmtTime(task.next_run_time) ? (
                  <span className='text-[14px] text-cyan-600 dark:text-cyan-400 font-medium'>
                    {fmtTime(task.next_run_time)}
                  </span>
                ) : (
                  <span className='text-[14px] text-gray-400'>-</span>
                )}
              </InfoField>
              <InfoField label={t('scheduled.detail.creatorLabel')}>
                <span className='text-[14px] text-gray-800 dark:text-gray-200'>{task.user_name ?? '-'}</span>
              </InfoField>
              <InfoField label={t('scheduled.detail.createdAtLabel')}>
                <span className='text-[14px] text-gray-800 dark:text-gray-200'>{fmtTime(task.created_at) ?? '-'}</span>
              </InfoField>
              {task.description && (
                <InfoField label={t('scheduled.detail.descLabel')} className='sm:col-span-2 lg:col-span-3'>
                  <span className='text-[14px] text-gray-600 dark:text-gray-300'>{task.description}</span>
                </InfoField>
              )}
            </div>
          </div>

          {/* ── Task environment (read-only) ── */}
          <div className='rounded-2xl border border-white/80 bg-white/80 backdrop-blur-lg shadow-[0_2px_12px_-4px_rgba(15,23,42,0.08)] dark:border-[#3a4456] dark:bg-[#2b303d]/70 p-6 mb-5'>
            <h3 className='text-[15px] font-semibold text-gray-800 dark:text-gray-100 mb-4 flex items-center gap-2'>
              <LaptopOutlined className='text-gray-400' />
              {t('scheduled.detail.envTitle')}
              <span className='text-[11px] text-gray-400 dark:text-gray-500 font-normal ml-1'>
                {t('scheduled.detail.envReadonly')}
              </span>
            </h3>
            <div className='grid grid-cols-1 gap-y-4'>
              <InfoField label={t('scheduled.detail.rawQuestion')}>
                <div className='text-[14px] text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-[#1a1f2e] rounded-lg px-3 py-2 border border-gray-100 dark:border-gray-700/50'>
                  {task.payload?.user_input ?? '-'}
                </div>
              </InfoField>
              <div className='grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-8 gap-y-4'>
                <InfoField label={t('scheduled.detail.modelLabel')}>
                  <span className='text-[14px] text-gray-800 dark:text-gray-200'>
                    {task.payload?.model_name ?? t('scheduled.detail.modelDefault')}
                  </span>
                </InfoField>
                {ext.skill_id && (
                  <InfoField label={t('scheduled.detail.skillLabel')}>
                    <span className='inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium bg-blue-50 text-blue-600 border border-blue-100 dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-800/40'>
                      {String(ext.skill_name || ext.skill_id)}
                    </span>
                  </InfoField>
                )}
                {ext.database_name && (
                  <InfoField label={t('scheduled.detail.databaseLabel')}>
                    <span className='inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium bg-indigo-50 text-indigo-600 border border-indigo-100 dark:bg-indigo-900/30 dark:text-indigo-300 dark:border-indigo-800/40'>
                      {String(ext.database_name)}
                    </span>
                  </InfoField>
                )}
                {ext.file_path && (
                  <InfoField label={t('scheduled.detail.fileLabel')}>
                    <span
                      title={String(ext.file_path)}
                      className='inline-flex items-center max-w-full truncate px-2 py-0.5 rounded-md text-[11px] font-medium bg-green-50 text-green-600 border border-green-100 dark:bg-green-900/30 dark:text-green-300 dark:border-green-800/40'
                    >
                      {String(ext.file_path).split('/').pop()}
                    </span>
                  </InfoField>
                )}
                {ext.knowledge_space_name && (
                  <InfoField label={t('scheduled.detail.knowledgeLabel')}>
                    <span className='inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium bg-orange-50 text-orange-600 border border-orange-100 dark:bg-orange-900/30 dark:text-orange-300 dark:border-orange-800/40'>
                      {String(ext.knowledge_space_name)}
                    </span>
                  </InfoField>
                )}
                {(() => {
                  // Merge connector_ids and mcp_ids and display them together as MCP
                  const ids: string[] = [
                    ...(Array.isArray(ext.connector_ids) ? ext.connector_ids : []),
                    ...(Array.isArray(ext.mcp_ids) ? ext.mcp_ids : []),
                  ];
                  if (ids.length === 0) return null;
                  return (
                    <InfoField label={t('scheduled.detail.mcpLabel')}>
                      <div className='flex gap-1.5 flex-wrap'>
                        {ids.map((id: string) => (
                          <span
                            key={id}
                            className='inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium bg-emerald-50 text-emerald-600 border border-emerald-100 dark:bg-emerald-900/30 dark:text-emerald-300 dark:border-emerald-800/40'
                          >
                            {connectorNameMap.get(id) || id}
                          </span>
                        ))}
                      </div>
                    </InfoField>
                  );
                })()}
              </div>
            </div>
          </div>

          {/* ── Run history ── */}
          <div className='rounded-2xl border border-white/80 bg-white/80 backdrop-blur-lg shadow-[0_2px_12px_-4px_rgba(15,23,42,0.08)] dark:border-[#3a4456] dark:bg-[#2b303d]/70 p-6 mb-8'>
            <div className='flex items-center justify-between mb-4'>
              <h3 className='text-[15px] font-semibold text-gray-800 dark:text-gray-100 flex items-center gap-2 m-0'>
                <ReloadOutlined className='text-gray-400' />
                {t('scheduled.detail.historyTitle')}
                <span className='text-[11px] text-gray-400 dark:text-gray-500 font-normal ml-1'>
                  {t('scheduled.detail.historyRecent')}
                </span>
              </h3>
            </div>
            <TaskRunsTable taskId={task.task_id} />
          </div>
        </div>

        {/* ── Edit drawer ── */}
        <EditScheduledTaskDrawer open={editOpen} onClose={() => setEditOpen(false)} task={task} onSaved={loadTask} />
      </div>
    </ConstructLayout>
  );
}

/* ── Info field component ── */
interface InfoFieldProps {
  label: string;
  className?: string;
  children: React.ReactNode;
}

const InfoField: React.FC<InfoFieldProps> = ({ label, className, children }) => (
  <div className={className}>
    <div className='text-[11px] text-gray-400 dark:text-gray-500 mb-1 uppercase tracking-wide'>{label}</div>
    <div>{children}</div>
  </div>
);

export default ScheduledTaskDetail;
