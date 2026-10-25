import { useEffect, useState } from 'react';
import TaskPlanCard, { TaskItem } from './TaskPlanCard';

/** Public execution facts only: never model reasoning or tool arguments. */
export default function FinancialProgressPanel({
  tasks,
  isRunning,
  compact = false,
  updates = [],
  onOpenReport,
  reportPublished = false,
}: {
  tasks: TaskItem[];
  isRunning: boolean;
  compact?: boolean;
  updates?: string[];
  onOpenReport?: () => void;
  reportPublished?: boolean;
}) {
  const [now, setNow] = useState(Date.now);
  const current = tasks.find(task => task.status === 'in_progress' || task.status === 'error');
  const finished = tasks.length > 0 && tasks.every(task => task.status === 'completed');
  const running = isRunning && current?.status === 'in_progress';
  useEffect(() => {
    if (!running) return;
    setNow(Date.now());
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [running, current?.startedAt]);
  const start = Date.parse(current?.startedAt || '');
  const elapsed = Number.isFinite(start) ? Math.max(0, Math.floor((now - start) / 1000)) : 0;
  const updated = Date.parse(current?.updatedAt || '');
  const waiting = running && Number.isFinite(updated) && now - updated >= 30000;
  const title = finished ? '报告已生成' : running ? current?.content : '本次执行已结束';
  return (
    <section
      data-testid='financial-progress'
      className={`rounded-xl border border-gray-200 bg-white ${compact ? 'p-4' : 'p-6'} dark:border-gray-800 dark:bg-[#1a1b1e]`}
    >
      <div className='mb-5 flex items-center justify-between gap-4'>
        <h3 className='text-base font-semibold text-gray-900 dark:text-gray-100'>{title}</h3>
        {running && <span className='text-sm tabular-nums text-slate-500'>本阶段已用 {elapsed} 秒</span>}
      </div>
      <p role='status' className='mb-4 text-sm leading-6 text-slate-600 dark:text-slate-300'>
        {finished
          ? isRunning
            ? '报告已生成，正在整理回复。可以先查看报告和原文依据。'
            : tasks[tasks.length - 1]?.detail
          : running || current?.status === 'error'
            ? current?.detail
            : '以下为最后保存的进度，可查看已有内容或继续分析。'}
      </p>
      {waiting && (
        <p className='mb-4 text-xs text-slate-500'>尚未收到新的分析结果，仍在等待处理；进展更新后会自动显示。</p>
      )}
      {onOpenReport && (
        <button
          type='button'
          onClick={onOpenReport}
          className='mb-4 rounded-lg bg-sky-50 px-3 py-2 text-sm font-medium text-sky-700 hover:bg-sky-100 dark:bg-sky-500/10 dark:text-sky-300'
        >
          {reportPublished ? '查看报告与原文依据' : '查看已有分析内容'}
        </button>
      )}
      <TaskPlanCard tasks={tasks} defaultCollapsed={false} embedded showDetails={false} />
      <FinancialProgressUpdates updates={updates} published={finished} />
    </section>
  );
}

export function FinancialProgressUpdates({ updates, published = false }: { updates: string[]; published?: boolean }) {
  const visible = (
    published ? updates.filter(update => !update.startsWith('已校验的分析发现（待最终复核）：')) : updates
  ).slice(-3);
  if (!visible.length) return null;
  return (
    <div
      role='log'
      aria-label='财报分析进展'
      aria-live='polite'
      aria-relevant='additions text'
      className='mt-4 space-y-2'
    >
      <p className='text-xs font-medium text-slate-500'>{published ? '执行记录' : '最新进展'}</p>
      {visible.map(update => (
        <p key={update} className='border-l-2 border-sky-200 pl-3 text-sm leading-6 text-slate-600 dark:text-slate-300'>
          {update}
        </p>
      ))}
    </div>
  );
}

export function financialTasksForStep(tasks: TaskItem[], action?: string): TaskItem[] {
  const financial = tasks.filter(task => task.kind === 'financial-stage');
  // A selected unrelated tool or sub-agent retains its own execution view.
  return financial.length === 4 &&
    (!action || action === 'terminate' || !!action.match(/^(prepare|read|save|review|publish|get)_financial_/))
    ? financial
    : [];
}
