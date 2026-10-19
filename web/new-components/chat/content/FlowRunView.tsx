/**
 * FlowRunView — workflow run display (mockup: workflow-display-redesign).
 *
 * Replaces the legacy vertical flow step cards with the redesign language:
 *   - run header: flow glyph + label + progress bar n/N + elapsed + (stop later)
 *   - horizontal node chain (success / running / failed / pending chips)
 *   - per-node cards carrying the ReAct trace rows (thinking / tool /
 *     observation / answer) with failure semantics: red accent row,
 *     collapsed raw error, "missing args / truncated" + retry badges.
 *
 * Data comes from the existing ``vis-flow-step`` markers merged with the
 * DSL-seeded execution steps (ManusLeftPanel builds the rows), so no wire
 * format change is required.
 */
import {
  BarChartOutlined,
  BulbOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  NodeIndexOutlined,
  RobotOutlined,
} from '@ant-design/icons';
import cls from 'classnames';
import { memo, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import type { ITaskflowAgentStep } from '@/types/taskflow';
import { stripFlowNarration } from '@/utils/taskflow';

export interface FlowRunRow {
  id: string;
  title: string;
  subtitle?: string;
  status: string; // pending | running | completed | failed
  durationMs?: number;
  summary?: string;
  content?: string;
  kind?: string;
  steps?: ITaskflowAgentStep[];
}

interface FlowRunViewProps {
  label: string;
  rows: FlowRunRow[];
  running: boolean;
  doneCount: number;
  totalCount: number;
}

const GUARD_RE = /no arguments|missing \d+ required|Action Input was missing|truncated/i;
const FAIL_RE = /execute failed|was called with no arguments|missing \d+ required positional/i;

function fmtDur(ms?: number): string {
  if (ms == null) return '';
  if (ms < 1000) return `${ms}ms`;
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(1)}s`;
  return `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}`;
}

function fmtElapsed(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

function isEmptyDetail(d?: string): boolean {
  const s = (d || '').trim();
  return !s || s === '``' || s === '```' || /^`+$/.test(s);
}

function kindIcon(kind?: string) {
  switch (kind) {
    case 'file_data':
      return <FileTextOutlined className='text-emerald-600' />;
    case 'db_query':
      return <DatabaseOutlined className='text-blue-600' />;
    case 'visualize':
    case 'report':
      return <BarChartOutlined className='text-orange-500' />;
    case 'agent':
      return <RobotOutlined className='text-indigo-500' />;
    default:
      return <NodeIndexOutlined className='text-[#8b8b84]' />;
  }
}

const KIND_BG: Record<string, string> = {
  file_data: 'bg-emerald-50 dark:bg-emerald-900/25',
  db_query: 'bg-blue-50 dark:bg-blue-900/25',
  visualize: 'bg-orange-50 dark:bg-orange-900/25',
  report: 'bg-orange-50 dark:bg-orange-900/25',
  agent: 'bg-indigo-50 dark:bg-indigo-900/25',
};

/** One ReAct trace row inside a node card. */
const TraceRow: React.FC<{
  step: ITaskflowAgentStep;
  failInfo?: { guard: boolean; errorText: string; retries: number } | null;
}> = memo(({ step, failInfo }) => {
  const { t } = useTranslation();
  if (step.kind === 'thinking') {
    if (isEmptyDetail(step.detail)) return null;
    return (
      <div className='flex items-baseline gap-2 h-7 px-2 rounded-md text-[12.5px] hover:bg-[#f4f4f0] dark:hover:bg-white/[.04]'>
        <BulbOutlined className='text-[#8b8b84] flex-none text-xs' />
        <span className='text-[#8b8b84] dark:text-[#7c7972] flex-none'>{t('flow_trace_thinking', '思考')}</span>
        <span className='font-mono text-[11.5px] text-[#8b8b84] dark:text-[#7c7972] truncate flex-1'>
          {step.detail}
        </span>
      </div>
    );
  }
  if (step.kind === 'action') {
    const gist = (step.detail || '').replace(/\s*\n\s*/g, ' ');
    if (failInfo) {
      return (
        <div className='my-1 px-2 py-1.5 rounded-md bg-[#fef2f2] dark:bg-red-950/25 border-l-2 border-[#b91c1c]'>
          <div className='flex items-baseline gap-2 flex-wrap'>
            <span className='text-[#b91c1c] flex-none text-xs'>⚠</span>
            <span className='font-mono text-[12px] font-semibold text-[#b91c1c] dark:text-red-400'>{step.title}</span>
            <span className='h-[18px] px-1.5 rounded-[5px] text-[10.5px] inline-flex items-center bg-[#fef2f2] dark:bg-red-950/40 border border-[#fecaca] dark:border-red-900 text-[#b91c1c] dark:text-red-400'>
              {failInfo.guard
                ? t('flow_badge_missing_args', '缺参数 · 输出被截断')
                : t('flow_badge_failed', '执行失败')}
            </span>
            {failInfo.retries > 0 && (
              <span className='h-[18px] px-1.5 rounded-[5px] text-[10.5px] inline-flex items-center bg-[#fffbeb] border border-[#fde68a] text-[#b45309]'>
                {t('flow_badge_retry', '重试 ×{{n}}', { n: failInfo.retries })}
              </span>
            )}
          </div>
          <details className='mt-1 ml-5 border border-[#fecaca] dark:border-red-900 rounded-lg bg-white dark:bg-[#111217]'>
            <summary className='cursor-pointer px-2.5 py-1.5 text-[11.5px] text-[#b91c1c] dark:text-red-400 list-none'>
              ▸ {(failInfo.errorText || '').slice(0, 64)}
              {(failInfo.errorText || '').length > 64 ? '…' : ''}
            </summary>
            <pre className='px-2.5 py-2 border-t border-[#fecaca] dark:border-red-900 font-mono text-[11px] text-[#7f1d1d] dark:text-red-300 whitespace-pre-wrap break-all max-h-[150px] overflow-auto'>
              {failInfo.errorText}
            </pre>
          </details>
        </div>
      );
    }
    return (
      <div className='flex items-baseline gap-2 h-7 px-2 rounded-md text-[12.5px] hover:bg-[#f4f4f0] dark:hover:bg-white/[.04]'>
        <span className='font-mono text-[12px] font-semibold text-[#1c1c1a] dark:text-[#e6e4df] flex-none'>
          {step.title}
        </span>
        <span className='font-mono text-[11.5px] text-[#8b8b84] dark:text-[#7c7972] truncate flex-1'>{gist}</span>
        <span className='text-[10.5px] text-[#15803d] flex-none'>✓</span>
      </div>
    );
  }
  if (step.kind === 'observation') {
    // Failed observations are folded into the action row above; the rest
    // stay collapsible so long tool outputs never flood the card.
    if (FAIL_RE.test(step.detail || '') || GUARD_RE.test(step.detail || '')) return null;
    return (
      <details className='ml-5 mb-1'>
        <summary className='cursor-pointer text-[11.5px] text-[#8b8b84] dark:text-[#7c7972] list-none'>
          ▸ {t('flow_trace_observation', '观察')} · {(step.detail || '').slice(0, 48)}
        </summary>
        <pre className='mt-1 px-2.5 py-2 border border-[#efefeb] dark:border-[#2a2925] rounded-lg bg-[#f4f4f0] dark:bg-white/[.04] font-mono text-[11px] text-[#55554f] dark:text-[#a8a59e] whitespace-pre-wrap break-all max-h-[150px] overflow-auto'>
          {step.detail}
        </pre>
      </details>
    );
  }
  if (step.kind === 'answer') {
    return (
      <div className='flex items-baseline gap-2 h-7 px-2 text-[12.5px]'>
        <span className='text-[#15803d] flex-none text-xs'>✓</span>
        <span className='text-[#55554f] dark:text-[#a8a59e] truncate flex-1'>{step.detail || step.title}</span>
      </div>
    );
  }
  return null;
});
TraceRow.displayName = 'TraceRow';

const NodeCard: React.FC<{ row: FlowRunRow; defaultOpen: boolean }> = memo(({ row, defaultOpen }) => {
  const { t } = useTranslation();
  const [open, setOpen] = useState(defaultOpen);
  useEffect(() => {
    if (defaultOpen) setOpen(true);
  }, [defaultOpen]);
  const isFail = row.status === 'failed';
  const isRun = row.status === 'running';
  const stepsRef = useMemo(() => row.steps ?? [], [row.steps]);
  const steps = stepsRef;
  const toolCount = steps.filter(s => s.kind === 'action').length;

  // Failure bookkeeping: pair each failed action with its observation and
  // count same-tool retries that follow it.
  const failInfoByIndex = useMemo(() => {
    const map = new Map<number, { guard: boolean; errorText: string; retries: number }>();
    const all = stepsRef;
    all.forEach((s, i) => {
      if (s.kind !== 'action') return;
      const obs = all.slice(i + 1).find(x => x.kind === 'observation');
      const errText = obs?.detail || '';
      const failed = FAIL_RE.test(errText) && !/is_exe_success.*true/i.test(errText);
      if (!failed) return;
      const retries = all.slice(i + 1).filter(x => x.kind === 'action' && x.title === s.title).length;
      map.set(i, { guard: GUARD_RE.test(errText), errorText: errText, retries });
    });
    return map;
  }, [stepsRef]);

  const summaryLine = useMemo(() => {
    if (row.summary) return row.summary;
    const ans = [...stepsRef].reverse().find(s => s.kind === 'answer' || s.kind === 'thinking');
    if (ans && !isEmptyDetail(ans.detail)) return (ans.detail || '').slice(0, 120);
    const first = stripFlowNarration(row.content || '')
      .split('\n')
      .map(x => x.trim())
      .find(Boolean);
    return first ? first.slice(0, 120) : '';
  }, [row.summary, row.content, stepsRef]);

  return (
    <div className='border border-[#e6e6e2] dark:border-[#2a2925] rounded-xl overflow-hidden bg-white dark:bg-[#111217]'>
      <button
        type='button'
        onClick={() => setOpen(o => !o)}
        className='w-full flex items-center gap-2.5 px-3.5 py-2.5 bg-[#f4f4f0] dark:bg-white/[.04] border-b border-[#efefeb] dark:border-[#232220] text-left'
      >
        <span
          className={cls(
            'w-6 h-6 rounded-[7px] flex items-center justify-center flex-none text-[13px]',
            KIND_BG[row.kind || ''] || 'bg-[#efefeb] dark:bg-white/[.06]',
          )}
        >
          {kindIcon(row.kind)}
        </span>
        <span className='text-[13px] font-semibold text-[#1c1c1a] dark:text-[#e6e4df] truncate'>{row.title}</span>
        {isFail ? (
          <span className='h-[19px] px-2 rounded-md text-[11px] inline-flex items-center gap-1 bg-[#fef2f2] dark:bg-red-950/30 text-[#b91c1c] dark:text-red-400 border border-[#fecaca] dark:border-red-900 flex-none'>
            ✕ {t('flow_status_failed', '失败')}
          </span>
        ) : isRun ? (
          <span className='h-[19px] px-2 rounded-md text-[11px] inline-flex items-center gap-1 bg-[#fffbeb] dark:bg-amber-950/30 text-[#b45309] dark:text-amber-400 border border-[#fde68a] dark:border-amber-900 flex-none'>
            ● {t('flow_status_running', '运行中')}
          </span>
        ) : (
          <span className='h-[19px] px-2 rounded-md text-[11px] inline-flex items-center gap-1 bg-[#f0fdf4] dark:bg-emerald-950/30 text-[#15803d] dark:text-emerald-400 border border-[#bbf7d0] dark:border-emerald-900 flex-none'>
            ✓ {t('flow_status_success', '成功')}
          </span>
        )}
        {toolCount > 0 && (
          <span className='h-[18px] px-1.5 rounded-[5px] text-[10.5px] inline-flex items-center bg-[#efefeb] dark:bg-white/[.06] border border-[#e6e6e2] dark:border-[#2a2925] text-[#55554f] dark:text-[#a8a59e] flex-none'>
            {t('flow_tool_count', '{{n}} 次工具调用', { n: toolCount })}
          </span>
        )}
        <span className='ml-auto font-mono text-[11px] text-[#8b8b84] dark:text-[#7c7972] flex-none'>
          {fmtDur(row.durationMs)} {open ? '▴' : '▾'}
        </span>
      </button>
      {open && (
        <div className='px-3.5 py-2 flex flex-col'>
          {steps.length > 0 ? (
            steps.map((s, i) => <TraceRow key={`${row.id}-${i}`} step={s} failInfo={failInfoByIndex.get(i) || null} />)
          ) : summaryLine ? (
            <div className='flex items-baseline gap-2 px-2 py-1 text-[12.5px]'>
              <span className='text-[#8b8b84] flex-none'>{t('flow_summary_label', '一句话结论:')}</span>
              <span className='text-[#55554f] dark:text-[#a8a59e]'>{summaryLine}</span>
            </div>
          ) : (
            <div className='px-2 py-1 text-[12px] text-[#8b8b84]'>{t('flow_no_output', '暂无输出')}</div>
          )}
        </div>
      )}
    </div>
  );
});
NodeCard.displayName = 'NodeCard';

const FlowRunView: React.FC<FlowRunViewProps> = ({ label, rows, running, doneCount, totalCount }) => {
  const { t } = useTranslation();
  const completedMs = useMemo(
    () => rows.reduce((sum, r) => sum + (r.status === 'completed' || r.status === 'failed' ? r.durationMs || 0 : 0), 0),
    [rows],
  );
  const [liveMs, setLiveMs] = useState(0);
  useEffect(() => {
    if (!running) return undefined;
    const started = Date.now();
    const timer = setInterval(() => setLiveMs(Date.now() - started), 1000);
    return () => clearInterval(timer);
  }, [running]);

  const total = totalCount || rows.length;
  const pct = total > 0 ? Math.round((doneCount / total) * 100) : 0;

  return (
    <div className='border border-[#e6e6e2] dark:border-[#2a2925] rounded-[14px] overflow-hidden bg-white dark:bg-[#111217] shadow-[0_1px_2px_rgba(20,20,15,.05),0_8px_28px_rgba(20,20,15,.05)]'>
      {/* run header */}
      <div className='flex items-center gap-3 px-4 py-2.5 border-b border-[#efefeb] dark:border-[#232220] bg-gradient-to-b from-[#fbfbf9] to-[#f6f6f2] dark:from-white/[.03] dark:to-transparent'>
        <span className='w-[30px] h-[30px] rounded-lg bg-[#1c1c1a] dark:bg-[#e6e4df] text-white dark:text-[#1c1c1a] flex items-center justify-center flex-none'>
          <svg width='15' height='15' viewBox='0 0 16 16' fill='none' stroke='currentColor' strokeWidth='1.5'>
            <rect x='1.5' y='1.5' width='5' height='4' rx='1' />
            <rect x='9.5' y='1.5' width='5' height='4' rx='1' />
            <rect x='5.5' y='10.5' width='5' height='4' rx='1' />
            <path d='M4 5.5v2h8v-2M8 7.5v3' />
          </svg>
        </span>
        <span className='min-w-0'>
          <span className='block text-[13.5px] font-semibold text-[#1c1c1a] dark:text-[#e6e4df] truncate'>{label}</span>
        </span>
        <span className='flex-1 max-w-[240px] h-[5px] rounded-[3px] bg-[#efefeb] dark:bg-white/[.08] overflow-hidden'>
          <span
            className='block h-full bg-[#1c1c1a] dark:bg-[#e6e4df] rounded-[3px] transition-all'
            style={{ width: `${pct}%` }}
          />
        </span>
        <span className='font-mono text-[11.5px] text-[#55554f] dark:text-[#a8a59e] flex-none'>
          {doneCount} / {total} {t('flow_nodes_unit', '节点')}
        </span>
        <span className='font-mono text-[11.5px] text-[#8b8b84] dark:text-[#7c7972] flex-none'>
          ⏱ {fmtElapsed(completedMs + (running ? liveMs : 0))}
        </span>
      </div>

      {/* node chain */}
      <div className='flex items-center gap-0 px-4 py-3 overflow-x-auto border-b border-[#efefeb] dark:border-[#232220]'>
        {rows.map((row, idx) => (
          <span key={row.id} className='flex items-center flex-none'>
            {idx > 0 && (
              <span className='w-[22px] h-px bg-[#e6e6e2] dark:bg-[#2a2925] relative flex-none'>
                <span className='absolute right-0 top-[-2.5px] w-0 h-0 border-l-[5px] border-l-[#e6e6e2] dark:border-l-[#2a2925] border-y-[3px] border-y-transparent' />
              </span>
            )}
            <span
              className={cls(
                'flex items-center gap-1.5 h-[30px] px-2.5 rounded-[9px] border text-[12px] whitespace-nowrap',
                row.status === 'completed' &&
                  'border-[#bbf7d0] dark:border-emerald-900 bg-[#f0fdf4] dark:bg-emerald-950/25 text-[#15803d] dark:text-emerald-400',
                row.status === 'running' &&
                  'border-[#fde68a] dark:border-amber-900 bg-[#fffbeb] dark:bg-amber-950/25 text-[#b45309] dark:text-amber-400 font-semibold',
                row.status === 'failed' &&
                  'border-[#fecaca] dark:border-red-900 bg-[#fef2f2] dark:bg-red-950/25 text-[#b91c1c] dark:text-red-400',
                (row.status === 'pending' || !row.status) &&
                  'border-dashed border-[#e6e6e2] dark:border-[#2a2925] bg-transparent text-[#8b8b84] dark:text-[#7c7972]',
              )}
            >
              <span
                className={cls(
                  'w-[7px] h-[7px] rounded-full flex-none',
                  row.status === 'completed' && 'bg-[#15803d]',
                  row.status === 'running' && 'bg-[#b45309] animate-pulse',
                  row.status === 'failed' && 'bg-[#b91c1c]',
                  (row.status === 'pending' || !row.status) && 'bg-[#d4d4ce] dark:bg-[#3a3936]',
                )}
              />
              {row.title}
              {row.durationMs != null && row.status !== 'pending' && (
                <span className='font-mono text-[10.5px] opacity-75'>{fmtDur(row.durationMs)}</span>
              )}
            </span>
          </span>
        ))}
      </div>

      {/* node cards */}
      <div className='px-4 py-3 flex flex-col gap-3'>
        {rows.map(row => (
          <NodeCard
            key={row.id}
            row={row}
            defaultOpen={row.status === 'running' || row.status === 'failed' || rows.length <= 2}
          />
        ))}
      </div>
    </div>
  );
};

export default FlowRunView;
