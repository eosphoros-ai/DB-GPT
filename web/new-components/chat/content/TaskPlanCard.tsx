/**
 * TaskPlanCard — Collapsible todo/task-plan card.
 *
 * Displays a live task list pushed by the agent's `todowrite` tool.
 * Mirrors the look of OpenCode's SessionTodoDock.
 */

import { CheckCircleFilled, ClockCircleOutlined, MinusCircleOutlined, UnorderedListOutlined } from '@ant-design/icons';
import React, { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

export interface TaskItem {
  content: string;
  status: 'pending' | 'in_progress' | 'completed' | 'cancelled';
  priority: 'high' | 'medium' | 'low';
}

interface TaskPlanCardProps {
  tasks: TaskItem[];
  defaultCollapsed?: boolean;
  embedded?: boolean;
}

const statusIcon = (status: string) => {
  switch (status) {
    case 'completed':
      return <CheckCircleFilled className='text-emerald-500 text-[11px]' />;
    case 'in_progress':
      return <ClockCircleOutlined className='text-sky-500 text-[11px] animate-pulse' />;
    case 'cancelled':
      return <MinusCircleOutlined className='text-slate-400 text-[11px]' />;
    default:
      return <span className='inline-block h-2.5 w-2.5 rounded-full border border-slate-300 dark:border-slate-600' />;
  }
};

const TaskPlanCard: React.FC<TaskPlanCardProps> = ({ tasks, defaultCollapsed = true, embedded = false }) => {
  const { t } = useTranslation();
  const [collapsed, setCollapsed] = useState(defaultCollapsed);

  const { total, done, currentTask } = useMemo(() => {
    const active = tasks.filter(t => t.status !== 'cancelled');
    return {
      total: active.length,
      done: active.filter(t => t.status === 'completed').length,
      currentTask: active.find(t => t.status === 'in_progress') || active.find(t => t.status === 'pending'),
    };
  }, [tasks]);

  if (tasks.length === 0) return null;

  const allDone = done === total && total > 0;

  return (
    <div
      className={`w-full overflow-hidden rounded-xl border text-sm ${
        embedded
          ? 'border-slate-200/70 bg-slate-50/80 shadow-none dark:border-white/10 dark:bg-white/[0.04]'
          : 'my-1 border-slate-200/80 bg-white/95 shadow-[0_14px_34px_rgba(15,23,42,0.10)] backdrop-blur-xl dark:border-white/10 dark:bg-[#1b1c22]/95 dark:shadow-[0_14px_34px_rgba(0,0,0,0.32)]'
      }`}
    >
      {/* Header */}
      <div
        className='flex cursor-pointer select-none items-center justify-between gap-3 px-3.5 py-2.5 transition-colors hover:bg-slate-50 dark:hover:bg-white/[0.03]'
        onClick={() => setCollapsed(c => !c)}
      >
        <div className='flex min-w-0 items-center gap-2.5 text-slate-700 dark:text-slate-200'>
          <span className='flex h-6 w-6 items-center justify-center rounded-md bg-slate-50 ring-1 ring-slate-200/80 dark:bg-white/5 dark:ring-white/10'>
            <UnorderedListOutlined className='text-[12px] text-slate-500 dark:text-slate-300' />
          </span>
          <div className='min-w-0'>
            <div className='font-semibold leading-5 tracking-tight'>
              {allDone ? t('task_plan_all_done', { total }) : t('task_plan_progress_summary', { total, done })}
            </div>
            {collapsed && currentTask && !allDone && (
              <div className='truncate text-[11px] leading-4 text-slate-400 dark:text-slate-500'>
                {t('task_plan_current', { task: currentTask.content })}
              </div>
            )}
          </div>
        </div>
        <span className='flex-shrink-0 text-[11px] text-slate-400'>{collapsed ? '▸' : '▾'}</span>
      </div>

      {/* Progress bar */}
      {total > 0 && (
        <div className='h-px bg-slate-100 dark:bg-white/10'>
          <div
            className={`h-full transition-all duration-500 ease-out ${
              allDone ? 'bg-emerald-500' : 'bg-gradient-to-r from-sky-400 via-indigo-400 to-emerald-400'
            }`}
            style={{ width: `${(done / total) * 100}%` }}
          />
        </div>
      )}

      {/* Task list */}
      {!collapsed && (
        <ul className='max-h-[220px] space-y-1 overflow-y-auto overscroll-contain px-3.5 py-2.5'>
          {tasks
            .filter(t => t.status !== 'cancelled')
            .map((task, i) => (
              <li
                key={i}
                className={`flex items-start gap-2.5 rounded-md px-1.5 py-1 leading-5 ${
                  task.status === 'completed'
                    ? 'text-slate-400 dark:text-slate-500'
                    : task.status === 'in_progress'
                      ? 'bg-sky-50/70 font-semibold text-slate-900 dark:bg-sky-500/10 dark:text-slate-100'
                      : 'text-slate-600 dark:text-slate-400'
                }`}
              >
                <span className='mt-1 flex-shrink-0'>{statusIcon(task.status)}</span>
                <span className={task.status === 'completed' ? 'line-through' : ''}>
                  {i + 1}. {task.content}
                </span>
              </li>
            ))}
        </ul>
      )}
    </div>
  );
};

export default TaskPlanCard;
