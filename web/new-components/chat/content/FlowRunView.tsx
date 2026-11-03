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
  DatabaseOutlined,
  DownloadOutlined,
  FileTextOutlined,
  Html5Outlined,
  LoadingOutlined,
  NodeIndexOutlined,
  RobotOutlined,
} from '@ant-design/icons';
import cls from 'classnames';
import { memo, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import MarkdownContext from '@/new-components/common/MarkdownContext';
import type { ITaskflowAgentStep, ITaskflowArtifact } from '@/types/taskflow';
import { stripFlowNarration } from '@/utils/taskflow';

import QueryArtifactBlock from './QueryArtifactBlock';
import TaskflowAgentTrace, { taskflowTraceBlocks } from './TaskflowAgentTrace';

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
  artifacts?: ITaskflowArtifact[];
}

interface FlowRunViewProps {
  label: string;
  rows: FlowRunRow[];
  running: boolean;
  doneCount: number;
  totalCount: number;
  onArtifactClick?: (artifact: ITaskflowArtifact) => void;
  onArtifactDownload?: (artifact: ITaskflowArtifact) => void;
  /** Edit & re-run for inline query artifacts (SQL result sets). */
  onQueryRerun?: (sql: string, dbName?: string) => Promise<any>;
}

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

function fmtSize(bytes?: number): string {
  if (bytes == null) return '';
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`;
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

const NodeCard: React.FC<{
  row: FlowRunRow;
  defaultOpen: boolean;
  onArtifactClick?: (artifact: ITaskflowArtifact) => void;
  onArtifactDownload?: (artifact: ITaskflowArtifact) => void;
  onQueryRerun?: (sql: string, dbName?: string) => Promise<any>;
}> = memo(({ row, defaultOpen, onArtifactClick, onArtifactDownload, onQueryRerun }) => {
  const { t } = useTranslation();
  const [open, setOpen] = useState(defaultOpen);
  useEffect(() => {
    if (defaultOpen) setOpen(true);
  }, [defaultOpen]);
  const isFail = row.status === 'failed';
  const isRun = row.status === 'running';
  const isPending = row.status === 'pending' || !row.status;
  const stepsRef = useMemo(() => row.steps ?? [], [row.steps]);
  const steps = stepsRef;
  const toolCount = useMemo(
    () =>
      taskflowTraceBlocks(steps, isRun, row.id).reduce(
        (n, block) => n + (block.kind === 'tool' ? block.count || 1 : 0),
        0,
      ),
    [steps, isRun, row.id],
  );
  const conclusion = isRun ? '' : stripFlowNarration(row.content || '');

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
        <span
          className={cls(
            'text-[13px] font-semibold truncate',
            isPending ? 'text-[#8b8b84] dark:text-[#7c7972]' : 'text-[#1c1c1a] dark:text-[#e6e4df]',
          )}
        >
          {row.title}
        </span>
        {isFail ? (
          <span className='h-[19px] px-2 rounded-md text-[11px] inline-flex items-center gap-1 bg-[#fef2f2] dark:bg-red-950/30 text-[#b91c1c] dark:text-red-400 border border-[#fecaca] dark:border-red-900 flex-none'>
            ✕ {t('flow_status_failed', '失败')}
          </span>
        ) : isRun ? (
          <span className='h-[19px] px-2 rounded-md text-[11px] inline-flex items-center gap-1 bg-[#fffbeb] dark:bg-amber-950/30 text-[#b45309] dark:text-amber-400 border border-[#fde68a] dark:border-amber-900 flex-none'>
            <LoadingOutlined spin className='text-[10px]' /> {t('flow_status_running', '运行中')}
          </span>
        ) : isPending ? (
          <span className='h-[19px] px-2 rounded-md text-[11px] inline-flex items-center gap-1 bg-[#f4f4f0] dark:bg-white/[.06] text-[#8b8b84] dark:text-[#7c7972] border border-dashed border-[#e6e6e2] dark:border-[#2a2925] flex-none'>
            ○ {t('flow_status_pending', '待执行')}
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
          {row.durationMs ? fmtDur(row.durationMs) : ''} {open ? '▴' : '▾'}
        </span>
      </button>
      {/* First-class artifacts of this node (mockup: flow-output-artifacts §2).
          Query artifacts (SQL result sets) render as full-width data blocks;
          file artifacts keep the compact chip row. */}
      {row.artifacts && row.artifacts.filter(a => a.type !== 'query').length > 0 && (
        <div className='px-3.5 py-2 flex items-center gap-2 flex-wrap border-b border-[#efefeb] dark:border-[#232220]'>
          {row.artifacts
            .filter(a => a.type !== 'query')
            .map(a => (
              <span
                key={a.path}
                className='inline-flex items-center gap-1.5 h-[26px] pl-2 pr-1 rounded-[8px] border border-[#e6e6e2] dark:border-[#2a2925] bg-[#f8f8f5] dark:bg-white/[.04] text-[11.5px] text-[#55554f] dark:text-[#a8a59e]'
              >
                {a.type === 'html' ? (
                  <Html5Outlined className='text-[#d97706] flex-none' />
                ) : (
                  <FileTextOutlined className='text-[#8b8b84] flex-none' />
                )}
                <button
                  type='button'
                  title={t('flow_artifact_preview', '预览')}
                  onClick={() => onArtifactClick?.(a)}
                  className='hover:text-[#0069fe] truncate max-w-[240px]'
                >
                  {a.name}
                </button>
                {fmtSize(a.size) && (
                  <span className='font-mono text-[10.5px] text-[#8b8b84] dark:text-[#7c7972] flex-none'>
                    {fmtSize(a.size)}
                  </span>
                )}
                <button
                  type='button'
                  title={t('flow_artifact_download', '下载')}
                  onClick={() => onArtifactDownload?.(a)}
                  className='w-[20px] h-[20px] rounded-[6px] inline-flex items-center justify-center flex-none text-[#8b8b84] hover:bg-[#efefeb] dark:hover:bg-white/[.08]'
                >
                  <DownloadOutlined className='text-[11px]' />
                </button>
              </span>
            ))}
        </div>
      )}
      {row.artifacts && row.artifacts.filter(a => a.type === 'query' && a.query).length > 0 && (
        <div className='px-3.5 py-2.5 flex flex-col gap-3 border-b border-[#efefeb] dark:border-[#232220]'>
          {row.artifacts
            .filter(a => a.type === 'query' && a.query)
            .map(a => (
              <QueryArtifactBlock key={a.name} payload={a.query!} fileName={a.name} onRerun={onQueryRerun} />
            ))}
        </div>
      )}
      {open && (
        <div className='px-3.5 py-2 flex flex-col'>
          {steps.length > 0 ? (
            <TaskflowAgentTrace steps={steps} running={isRun} nodeId={row.id} />
          ) : isPending ? (
            <div className='px-2 py-1 text-[12px] text-[#8b8b84] dark:text-[#7c7972]'>
              {t('flow_node_pending_hint', '等待上游节点完成后执行')}
            </div>
          ) : summaryLine ? (
            <div className='flex items-baseline gap-2 px-2 py-1 text-[12.5px]'>
              <span className='text-[#8b8b84] flex-none'>{t('flow_summary_label', '一句话结论:')}</span>
              <span className='text-[#55554f] dark:text-[#a8a59e]'>{summaryLine}</span>
            </div>
          ) : (
            <div className='px-2 py-1 text-[12px] text-[#8b8b84]'>{t('flow_no_output', '暂无输出')}</div>
          )}
          {conclusion && steps.length > 0 && (
            <div className='mt-3 pt-3 border-t border-[#efefeb] dark:border-[#232220] text-[13px]'>
              <MarkdownContext>{conclusion}</MarkdownContext>
            </div>
          )}
        </div>
      )}
    </div>
  );
});
NodeCard.displayName = 'NodeCard';

const FlowRunView: React.FC<FlowRunViewProps> = ({
  label,
  rows,
  running,
  doneCount,
  totalCount,
  onArtifactClick,
  onArtifactDownload,
  onQueryRerun,
}) => {
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
            onArtifactClick={onArtifactClick}
            onArtifactDownload={onArtifactDownload}
            onQueryRerun={onQueryRerun}
          />
        ))}
      </div>
    </div>
  );
};

export default FlowRunView;
