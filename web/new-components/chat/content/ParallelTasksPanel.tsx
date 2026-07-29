import {
  ApartmentOutlined,
  ClockCircleOutlined,
  FileImageOutlined,
  InfoCircleOutlined,
  RightOutlined,
  ToolOutlined,
} from '@ant-design/icons';
import classNames from 'classnames';
import React, { CSSProperties, memo, useMemo } from 'react';
import { useTranslation } from 'react-i18next';

import MarkDownContext from '@/new-components/common/MarkdownContext';
import type { SubAgentState, SubAgentStatus } from '@/types/subagent';
import { Collapsible } from '../tools/Collapsible';
import SubAgentStatusBadge from './SubAgentStatusBadge';

type ParallelStepStatus = 'pending' | 'running' | 'completed' | 'error';

interface OutputLike {
  output_type: string;
  content: any;
}

interface DisplayTask extends SubAgentState {
  /** False for history-only rows recovered from the legacy Markdown summary. */
  structured: boolean;
}

export interface ParallelTasksPanelProps {
  status: ParallelStepStatus;
  subAgents?: Record<string, SubAgentState>;
  outputs?: OutputLike[];
  onSubAgentClick?: (agentId: string) => void;
}

const previewClampStyle: CSSProperties = {
  display: '-webkit-box',
  WebkitBoxOrient: 'vertical',
  WebkitLineClamp: 2,
};

const FALLBACK_HEADING_RE = /^#{2,4}\s+(.+?)\s+\[(done|running|timeout|failed)]\s*$/gim;

function readBalancedJson(source: string, start: number): string | null {
  if (source[start] !== '{') return null;
  let depth = 0;
  let inString = false;
  let escaped = false;

  for (let i = start; i < source.length; i += 1) {
    const char = source[i];
    if (inString) {
      if (escaped) {
        escaped = false;
      } else if (char === '\\') {
        escaped = true;
      } else if (char === '"') {
        inString = false;
      }
      continue;
    }
    if (char === '"') {
      inString = true;
    } else if (char === '{') {
      depth += 1;
    } else if (char === '}') {
      depth -= 1;
      if (depth === 0) return source.slice(start, i + 1);
    }
  }
  return null;
}

function readFinalValue(jsonText: string): string | null {
  try {
    const parsed = JSON.parse(jsonText);
    const value = parsed?.output ?? parsed?.result ?? parsed?.final_answer;
    if (typeof value === 'string') return value;
    if (value != null) return JSON.stringify(value, null, 2);
  } catch {
    // Legacy history can contain a partly escaped Action Input. Recover the
    // common string case without ever returning the surrounding ReAct trace.
    const valueMatch = jsonText.match(/"(?:output|result|final_answer)"\s*:\s*"((?:\\.|[^"\\])*)"/s);
    if (valueMatch) {
      try {
        return JSON.parse(`"${valueMatch[1]}"`);
      } catch {
        return valueMatch[1].replace(/\\n/g, '\n').replace(/\\"/g, '"');
      }
    }
  }
  return null;
}

/**
 * Return only user-facing result content from a legacy ReAct envelope.
 *
 * New responses are already cleaned by the backend. This compatibility layer
 * keeps refreshed/shared conversations readable without rendering Thought,
 * Action, Action Input, or vis-thinking markup.
 */
export function sanitizeSubAgentResult(raw: unknown): string {
  if (typeof raw !== 'string') return raw == null ? '' : String(raw);
  const withoutThinkingBlocks = raw.replace(/``````vis-thinking[\s\S]*?``````\s*/gi, '').trim();
  const terminateMatch = /Action:\s*terminate\b/i.exec(withoutThinkingBlocks);
  if (!terminateMatch) return withoutThinkingBlocks;

  const afterTerminate = withoutThinkingBlocks.slice(terminateMatch.index + terminateMatch[0].length);
  const inputMatch = /Action Input:\s*/i.exec(afterTerminate);
  if (!inputMatch) return '';
  const inputStart = terminateMatch.index + terminateMatch[0].length + inputMatch.index + inputMatch[0].length;
  const jsonStart = withoutThinkingBlocks.indexOf('{', inputStart);
  if (jsonStart < 0) return '';

  const jsonText = readBalancedJson(withoutThinkingBlocks, jsonStart);
  return jsonText ? readFinalValue(jsonText)?.trim() || '' : '';
}

function plainTextPreview(markdown: string): string {
  return markdown
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/!\[[^\]]*]\([^)]*\)/g, ' ')
    .replace(/\[([^\]]+)]\([^)]*\)/g, '$1')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/[>*_`~|]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function parseLegacyTasks(outputs: OutputLike[]): DisplayTask[] {
  const summary = outputs
    .filter(output => output.output_type === 'markdown' || output.output_type === 'text')
    .map(output => String(output.content || ''))
    .join('\n\n');
  const matches = [...summary.matchAll(FALLBACK_HEADING_RE)];

  return matches.map((match, index) => {
    const start = (match.index || 0) + match[0].length;
    const end = matches[index + 1]?.index ?? summary.length;
    const rawStatus = match[2].toLowerCase() as SubAgentStatus;
    return {
      agentId: `legacy-subagent-${index}`,
      name: match[1].trim(),
      status: rawStatus,
      lane: index,
      batchId: 0,
      artifactCount: 0,
      result: sanitizeSubAgentResult(summary.slice(start, end)),
      steps: [],
      structured: false,
    };
  });
}

function formatDuration(elapsedMs?: number): string | null {
  if (elapsedMs == null || elapsedMs < 0) return null;
  if (elapsedMs < 1_000) return `${elapsedMs} ms`;
  const seconds = elapsedMs / 1_000;
  if (seconds < 60) return `${seconds < 10 ? seconds.toFixed(1) : Math.round(seconds)} s`;
  const minutes = Math.floor(seconds / 60);
  const remaining = Math.round(seconds % 60);
  return `${minutes}m ${remaining}s`;
}

function compactIntention(intention?: string): string {
  if (!intention) return '';
  return intention
    .replace(/^Thought:\s*/i, '')
    .split(/\n(?:Action|Action Input|Observation):/i)[0]
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 240);
}

const TaskCard: React.FC<{
  task: DisplayTask;
  onSubAgentClick?: (agentId: string) => void;
}> = ({ task, onSubAgentClick }) => {
  const { t } = useTranslation();
  const safeResult = sanitizeSubAgentResult(task.result);
  const fullResultPreview = plainTextPreview(safeResult);
  const resultPreview =
    fullResultPreview.length > 220 ? `${fullResultPreview.slice(0, 220).trimEnd()}…` : fullResultPreview;
  const duration = formatDuration(task.elapsedMs);
  const isRunning = task.status === 'running';
  const hasDetails = Boolean(task.goal || safeResult || task.steps.length > 0);
  const defaultOpen = isRunning || task.status === 'failed' || task.status === 'timeout';
  const subline = isRunning
    ? task.currentAction || t('parallel_tasks_preparing')
    : resultPreview || task.goal || t(`subagent_status_${task.status}`);

  return (
    <Collapsible
      defaultOpen={defaultOpen}
      className={classNames(
        'overflow-hidden rounded-xl border bg-white transition-colors dark:bg-[#191a1f]',
        task.status === 'failed' && 'border-red-200 dark:border-red-500/30',
        task.status === 'timeout' && 'border-amber-200 dark:border-amber-500/30',
        task.status === 'running' && 'border-blue-200 shadow-sm dark:border-blue-500/30',
        task.status === 'done' && 'border-slate-200/80 dark:border-white/10',
      )}
    >
      <Collapsible.Trigger className='group'>
        <div className='flex min-h-[76px] items-start gap-3 px-4 py-3.5 transition-colors group-hover:bg-slate-50/70 dark:group-hover:bg-white/[0.025]'>
          <div className='pt-0.5'>
            <SubAgentStatusBadge status={task.status} />
          </div>
          <div className='min-w-0 flex-1'>
            <div className='flex items-start justify-between gap-3'>
              <h3
                className='truncate text-sm font-semibold leading-5 text-slate-900 dark:text-slate-100'
                title={task.name}
              >
                {task.name}
              </h3>
              <SubAgentStatusBadge status={task.status} showLabel />
            </div>
            <p
              className={classNames(
                'mt-1 overflow-hidden text-xs leading-5',
                isRunning ? 'text-blue-600 dark:text-blue-400' : 'text-slate-500 dark:text-slate-400',
              )}
              style={previewClampStyle}
            >
              {subline}
            </p>
            <div className='mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-slate-400 dark:text-slate-500'>
              {task.steps.length > 0 && (
                <span className='inline-flex items-center gap-1'>
                  <ToolOutlined aria-hidden />
                  {t('parallel_tasks_steps', { count: task.steps.length })}
                </span>
              )}
              {task.artifactCount > 0 && (
                <span className='inline-flex items-center gap-1'>
                  <FileImageOutlined aria-hidden />
                  {t('parallel_tasks_artifacts', { count: task.artifactCount })}
                </span>
              )}
              {duration && (
                <span className='inline-flex items-center gap-1'>
                  <ClockCircleOutlined aria-hidden />
                  {t('parallel_tasks_elapsed', { time: duration })}
                </span>
              )}
            </div>
          </div>
          {hasDetails && <Collapsible.Arrow className='mt-1 flex-shrink-0' />}
        </div>
      </Collapsible.Trigger>

      {hasDetails && (
        <Collapsible.Content>
          <div className='border-t border-slate-100 px-4 py-4 dark:border-white/10'>
            {task.goal && (
              <section className='mb-4'>
                <div className='mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-400'>
                  {t('subagent_goal')}
                </div>
                <p className='m-0 text-sm leading-6 text-slate-600 dark:text-slate-300'>{task.goal}</p>
              </section>
            )}

            {safeResult && (
              <section className='mb-4'>
                <div className='mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400'>
                  {t('parallel_tasks_result_summary')}
                </div>
                <div className='max-h-[320px] overflow-y-auto rounded-lg bg-slate-50 px-3.5 py-3 text-sm dark:bg-white/[0.035]'>
                  <MarkDownContext>{safeResult}</MarkDownContext>
                </div>
              </section>
            )}

            {task.steps.length > 0 && (
              <section>
                <div className='mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400'>
                  {t('parallel_tasks_execution_trace')}
                </div>
                <ol className='space-y-0'>
                  {task.steps.map((step, index) => {
                    const intention = compactIntention(step.intention);
                    return (
                      <li key={`${task.agentId}-${index}`} className='relative flex gap-3 pb-3 last:pb-0'>
                        {index < task.steps.length - 1 && (
                          <span className='absolute bottom-0 left-[5px] top-3 w-px bg-slate-200 dark:bg-white/10' />
                        )}
                        <span className='relative mt-1.5 h-[11px] w-[11px] flex-shrink-0 rounded-full border-2 border-white bg-blue-500 ring-1 ring-blue-200 dark:border-[#191a1f] dark:ring-blue-500/30' />
                        <div className='min-w-0 flex-1'>
                          <div className='text-sm font-medium leading-5 text-slate-700 dark:text-slate-200'>
                            {step.label}
                          </div>
                          {intention && (
                            <p className='mt-0.5 text-xs leading-5 text-slate-500 dark:text-slate-400'>{intention}</p>
                          )}
                        </div>
                      </li>
                    );
                  })}
                </ol>
              </section>
            )}

            {task.structured && onSubAgentClick && (
              <button
                type='button'
                className='mt-4 inline-flex min-h-[36px] items-center gap-1.5 rounded-lg border border-slate-200 px-3 text-xs font-medium text-slate-600 transition-colors hover:border-blue-200 hover:bg-blue-50 hover:text-blue-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40 dark:border-white/10 dark:text-slate-300 dark:hover:border-blue-500/30 dark:hover:bg-blue-500/10 dark:hover:text-blue-400'
                onClick={() => onSubAgentClick(task.agentId)}
              >
                {t('parallel_tasks_view_details')}
                <RightOutlined aria-hidden className='text-[10px]' />
              </button>
            )}
          </div>
        </Collapsible.Content>
      )}
    </Collapsible>
  );
};

const ParallelTasksPanel: React.FC<ParallelTasksPanelProps> = ({
  status,
  subAgents,
  outputs = [],
  onSubAgentClick,
}) => {
  const { t } = useTranslation();
  const legacyTasks = useMemo(() => parseLegacyTasks(outputs), [outputs]);
  const tasks = useMemo<DisplayTask[]>(() => {
    const structured = Object.values(subAgents || {}).sort((a, b) => a.batchId - b.batchId || a.lane - b.lane);
    if (structured.length === 0) return legacyTasks;
    const legacyResultByTitle = new Map(legacyTasks.map(task => [task.name, task.result]));
    return structured.map(task => ({
      ...task,
      result: task.result || legacyResultByTitle.get(task.name),
      structured: true,
    }));
  }, [legacyTasks, subAgents]);

  const total = tasks.length;
  const doneCount = tasks.filter(task => task.status === 'done').length;
  const runningCount = tasks.filter(task => task.status === 'running').length;
  const attentionCount = tasks.filter(task => task.status === 'failed' || task.status === 'timeout').length;
  const settledCount = total - runningCount;
  const isSummarizing = total > 0 && runningCount === 0 && status === 'running';
  const progress = total > 0 ? Math.round((settledCount / total) * 100) : 0;
  const description =
    total === 0
      ? t('parallel_tasks_empty')
      : runningCount > 0
        ? t('parallel_tasks_description', { count: total })
        : attentionCount > 0
          ? t('parallel_tasks_description_attention', { count: total, attention: attentionCount })
          : t('parallel_tasks_description_done', { count: total });

  return (
    <div className='flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-slate-200/80 bg-white dark:border-white/10 dark:bg-[#17181d]'>
      <header className='border-b border-slate-100 px-5 py-4 dark:border-white/10'>
        <div className='flex items-start justify-between gap-4'>
          <div className='flex min-w-0 items-start gap-3'>
            <span className='flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600 ring-1 ring-indigo-100 dark:bg-indigo-500/10 dark:text-indigo-400 dark:ring-indigo-500/20'>
              <ApartmentOutlined aria-hidden className='text-lg' />
            </span>
            <div className='min-w-0'>
              <div className='flex flex-wrap items-center gap-2'>
                <h2 className='m-0 text-base font-semibold tracking-tight text-slate-900 dark:text-slate-100'>
                  {t('parallel_tasks_title')}
                </h2>
                <span className='rounded-md bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-500 dark:bg-white/[0.06] dark:text-slate-400'>
                  dispatch_parallel_tasks
                </span>
              </div>
              <p className='mt-1 text-xs text-slate-500 dark:text-slate-400'>{description}</p>
            </div>
          </div>
          {total > 0 && (
            <span className='flex-shrink-0 text-xs font-medium text-slate-500 dark:text-slate-400'>
              {t('parallel_tasks_progress', { done: settledCount, total })}
            </span>
          )}
        </div>

        {total > 0 && (
          <>
            <div
              className='mt-4 h-1.5 overflow-hidden rounded-full bg-slate-100 dark:bg-white/10'
              role='progressbar'
              aria-valuemin={0}
              aria-valuemax={total}
              aria-valuenow={settledCount}
              aria-label={t('parallel_tasks_progress', { done: settledCount, total })}
            >
              <div
                className={classNames(
                  'h-full rounded-full transition-all duration-500 ease-out',
                  attentionCount > 0 && runningCount === 0
                    ? 'bg-amber-500'
                    : doneCount === total
                      ? 'bg-emerald-500'
                      : 'bg-gradient-to-r from-blue-500 via-indigo-500 to-emerald-400',
                )}
                style={{ width: `${progress}%` }}
              />
            </div>
            <div className='mt-3 flex flex-wrap items-center gap-2'>
              {doneCount > 0 && (
                <span className='rounded-full bg-emerald-50 px-2 py-1 text-[11px] font-medium text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400'>
                  {t('parallel_tasks_completed', { count: doneCount })}
                </span>
              )}
              {runningCount > 0 && (
                <span className='rounded-full bg-blue-50 px-2 py-1 text-[11px] font-medium text-blue-700 dark:bg-blue-500/10 dark:text-blue-400'>
                  {t('parallel_tasks_running', { count: runningCount })}
                </span>
              )}
              {attentionCount > 0 && (
                <span className='rounded-full bg-amber-50 px-2 py-1 text-[11px] font-medium text-amber-700 dark:bg-amber-500/10 dark:text-amber-400'>
                  {t('parallel_tasks_attention', { count: attentionCount })}
                </span>
              )}
            </div>
            {isSummarizing && (
              <div className='mt-3 rounded-lg bg-blue-50/70 px-3 py-2 text-xs text-blue-700 dark:bg-blue-500/10 dark:text-blue-300'>
                {t('parallel_tasks_summarizing')}
              </div>
            )}
          </>
        )}
      </header>

      <div className='min-h-0 flex-1 overflow-y-auto bg-slate-50/50 px-4 py-4 dark:bg-black/10'>
        {tasks.length > 0 ? (
          <div className='space-y-3'>
            {tasks.map(task => (
              <TaskCard key={task.agentId} task={task} onSubAgentClick={onSubAgentClick} />
            ))}
          </div>
        ) : (
          <div className='flex h-full min-h-[220px] flex-col items-center justify-center text-slate-400'>
            <ApartmentOutlined aria-hidden className='mb-3 text-3xl text-slate-300 dark:text-slate-600' />
            <span className='text-sm'>{t('parallel_tasks_empty')}</span>
          </div>
        )}
      </div>

      <footer className='flex items-start gap-2 border-t border-slate-100 bg-white px-5 py-3 text-[11px] leading-5 text-slate-400 dark:border-white/10 dark:bg-[#17181d] dark:text-slate-500'>
        <InfoCircleOutlined aria-hidden className='mt-0.5 flex-shrink-0' />
        <span>{t('parallel_tasks_transparency_note')}</span>
      </footer>
    </div>
  );
};

export default memo(ParallelTasksPanel);
