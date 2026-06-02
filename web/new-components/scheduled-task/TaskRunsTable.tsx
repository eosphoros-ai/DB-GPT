import { EyeOutlined, ReloadOutlined } from '@ant-design/icons';
import { Button, Spin, Tooltip, message } from 'antd';
import dayjs from 'dayjs';
import { useRouter } from 'next/router';
import React, { useCallback, useEffect, useState } from 'react';

import { useScheduledTask } from '@/hooks/use-scheduled-task';
import type { RunResponse, ScheduledRunStatus } from '@/types/scheduled-task';

/** 格式化 ISO 时间字符串，去掉时区后缀，返回友好格式 */
function fmtTime(iso?: string | null): string | null {
  if (!iso) return null;
  const d = dayjs(iso);
  return d.isValid() ? d.format('YYYY-MM-DD HH:mm:ss') : iso;
}

interface TaskRunsTableProps {
  taskId: string;
}

/** 状态 → 样式映射(填充圆点芯片,与 ConnectorCard 风格统一) */
const STATUS_META: Record<ScheduledRunStatus, { label: string; dot: string; text: string; bg: string }> = {
  running: {
    label: '执行中',
    dot: 'bg-blue-500',
    text: 'text-blue-700 dark:text-blue-400',
    bg: 'bg-blue-50 dark:bg-blue-900/30',
  },
  success: {
    label: '成功',
    dot: 'bg-emerald-500',
    text: 'text-emerald-700 dark:text-emerald-400',
    bg: 'bg-emerald-50 dark:bg-emerald-900/30',
  },
  failed: {
    label: '失败',
    dot: 'bg-red-500',
    text: 'text-red-600 dark:text-red-400',
    bg: 'bg-red-50 dark:bg-red-900/30',
  },
  timeout: {
    label: '超时',
    dot: 'bg-amber-500',
    text: 'text-amber-600 dark:text-amber-400',
    bg: 'bg-amber-50 dark:bg-amber-900/30',
  },
};

const TaskRunsTable: React.FC<TaskRunsTableProps> = ({ taskId }) => {
  const router = useRouter();
  const { listRuns } = useScheduledTask();
  const [runs, setRuns] = useState<RunResponse[]>([]);
  const [loading, setLoading] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listRuns(taskId, 50, 0);
      setRuns(data);
    } catch (e: any) {
      message.error(e?.message ?? '加载执行历史失败');
    } finally {
      setLoading(false);
    }
  }, [taskId, listRuns]);

  useEffect(() => {
    reload();
  }, [reload]);

  const handleView = useCallback(
    (run: RunResponse) => {
      if (!run.output_conv_uid) {
        message.warning('该次执行未生成可查看的对话');
        return;
      }
      router.push(`/?id=${run.output_conv_uid}&from_task=${taskId}`);
    },
    [router, taskId],
  );

  if (loading && runs.length === 0) {
    return (
      <div className='flex items-center justify-center py-8'>
        <Spin size='small' />
      </div>
    );
  }

  if (runs.length === 0) {
    return (
      <div className='flex flex-col items-center justify-center py-8 text-gray-400 dark:text-gray-500'>
        <p className='text-sm'>暂无执行记录</p>
      </div>
    );
  }

  return (
    <div>
      <div className='flex justify-end mb-3'>
        <Button
          icon={<ReloadOutlined />}
          onClick={reload}
          loading={loading}
          size='small'
          className='text-gray-500'
        >
          刷新
        </Button>
      </div>

      <div className='overflow-hidden rounded-xl border border-gray-100 dark:border-gray-700/50'>
        {/* 表头 */}
        <div className='grid grid-cols-[80px_160px_70px_1fr_70px] gap-2 px-4 py-2.5 text-[12px] font-medium text-gray-400 dark:text-gray-500 uppercase tracking-wider bg-gray-50/60 dark:bg-[#1a1f2e]/60 border-b border-gray-100 dark:border-gray-700/50'>
          <div>状态</div>
          <div>开始时间</div>
          <div>耗时</div>
          <div>结果摘要</div>
          <div className='text-right'>操作</div>
        </div>

        {/* 行 */}
        {runs.map(run => {
          const meta = STATUS_META[run.status];
          const isFailed = run.status === 'failed' || run.status === 'timeout';
          const summaryText = isFailed
            ? (run.error_message ?? '').slice(0, 80)
            : (run.result_summary ?? '').slice(0, 80);
          const duration =
            run.finished_at && run.started_at
              ? `${Math.round((dayjs(run.finished_at).valueOf() - dayjs(run.started_at).valueOf()) / 1000)}s`
              : '-';

          return (
            <div
              key={run.run_id}
              className='grid grid-cols-[80px_160px_70px_1fr_70px] gap-2 px-4 py-3 items-center border-b border-gray-50 dark:border-gray-700/30 last:border-b-0 hover:bg-gray-50/50 dark:hover:bg-white/[0.02] transition-colors text-[13px]'
            >
              {/* 状态 */}
              <div>
                <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium ${meta.bg} ${meta.text}`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${meta.dot}`} />
                  {meta.label}
                </span>
              </div>

              {/* 开始时间 */}
              <div className='text-gray-600 dark:text-gray-400 truncate'>{fmtTime(run.started_at) ?? '-'}</div>

              {/* 耗时 */}
              <div className='text-gray-600 dark:text-gray-400'>{duration}</div>

              {/* 结果摘要 */}
              <div className='truncate'>
                {summaryText ? (
                  <Tooltip title={isFailed ? run.error_message : run.result_summary}>
                    <span className={isFailed ? 'text-red-500 dark:text-red-400' : 'text-gray-700 dark:text-gray-300'}>
                      {summaryText}
                    </span>
                  </Tooltip>
                ) : (
                  <span className='text-gray-400'>-</span>
                )}
              </div>

              {/* 操作 */}
              <div className='text-right'>
                <Button
                  type='link'
                  size='small'
                  icon={<EyeOutlined />}
                  disabled={!run.output_conv_uid}
                  onClick={() => handleView(run)}
                  className='!text-cyan-600 dark:!text-cyan-400 disabled:!text-gray-300 dark:disabled:!text-gray-600'
                >
                  查看
                </Button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default React.memo(TaskRunsTable);
