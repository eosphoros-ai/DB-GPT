/**
 * AgentTimeline — DSH-conversation-style run view.
 *
 * Faithful to deepseek-harness's conversation design (not the
 * trajectory debug table): a flat flow of
 *   - assistant text blocks (markdown paragraphs), streamed live
 *   - 24px collapsible rows for tools / thinking
 *     ([icon 16] [title] · [summary truncated] [chevron])
 *   - running state = shimmer sweep across the row
 *   - thinking rows stay collapsed by default; while streaming,
 *     the summary line follows the latest non-blank line
 *
 * Consumes the same `step.*` SSE data as ManusLeftPanel.
 */
import {
  BulbOutlined,
  CodeOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  GlobalOutlined,
  Loading3QuartersOutlined,
  ReadOutlined,
  SearchOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import cls from 'classnames';
import { useMemo, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

import MarkdownContext from '@/new-components/common/MarkdownContext';
import { envelopeReadableText } from '@/utils/tool-envelope';

// ── types ──────────────────────────────────────────────────────────────

interface TimelineBlock {
  id: string;
  kind: 'text' | 'tool' | 'thinking' | 'question';
  /** text block content (markdown-ish, already streamed) */
  content?: string;
  /** tool/thinking row fields */
  title?: string;
  tool?: string;
  status?: 'running' | 'success' | 'failed';
  durationMs?: number;
  /** collapsed-body content */
  input?: string;
  output?: string;
  /** accumulated thinking text (drives the live summary) */
  thought?: string;
  /** is this block still streaming? */
  streaming?: boolean;
  /** grouped tool calls (consecutive same-tool steps) */
  children?: TimelineBlock[];
  count?: number;
  /** question recap pairs (question tool): question + user answer */
  pairs?: { question: string; answer: string }[];
  /** question dismissed / timed out (no answers available) */
  rejected?: boolean;
}

interface AgentTimelineProps {
  blocks: TimelineBlock[];
  isRunning?: boolean;
}

// ── helpers ────────────────────────────────────────────────────────────

/** Map a tool/action name to a leading icon (DSH uses 16px leading icons). */
function toolIcon(tool?: string, title?: string) {
  const key = (tool || title || '').toLowerCase();
  if (key.includes('sql') || key.includes('db') || key.includes('database')) return <DatabaseOutlined />;
  if (key.includes('code') || key.includes('python') || key.includes('interpreter')) return <CodeOutlined />;
  if (key.includes('search') || key.includes('grep') || key.includes('knowledge')) return <SearchOutlined />;
  if (key.includes('read') || key.includes('file')) return <ReadOutlined />;
  if (key.includes('report') || key.includes('html') || key.includes('visual')) return <FileTextOutlined />;
  if (key.includes('web') || key.includes('http') || key.includes('crawl')) return <GlobalOutlined />;
  return <ThunderboltOutlined />;
}

/** Latest non-blank line — the DSH live-summary rule for thinking rows. */
function latestLine(text: string): string {
  const lines = text.split('\n');
  for (let i = lines.length - 1; i >= 0; i--) {
    const line = lines[i].trim();
    if (line) return line;
  }
  return '';
}

function formatDuration(ms?: number): string {
  if (ms == null) return '';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/** DB-GPT tools answer with ``{"chunks": [...]}`` envelopes; pull the
 *  readable markdown/text payloads out so row bodies are not raw JSON.
 *  Tolerates multiple envelopes and non-envelope residue per output. */
function parseChunkEnvelope(output?: string): string | null {
  if (!output) return null;
  return envelopeReadableText(output);
}

function firstMeaningfulLine(text: string): string {
  for (const line of text.split('\n')) {
    const trimmed = line.trim();
    if (trimmed) return trimmed;
  }
  return '';
}

/** Flatten a JSON tool-input blob (``{"sql": "SELECT ..."}``) into
 *  readable ``key: value`` lines. */
function prettyInput(input?: string): string {
  if (!input) return '';
  const trimmed = input.trim();
  if (!trimmed.startsWith('{')) return input;
  try {
    const obj = JSON.parse(trimmed);
    if (obj && typeof obj === 'object' && !Array.isArray(obj)) {
      const lines = Object.entries(obj).map(
        ([key, value]) => `${key}: ${typeof value === 'string' ? value : JSON.stringify(value)}`,
      );
      if (lines.length) return lines.join('\n');
    }
  } catch {
    /* keep raw */
  }
  return input;
}

/** One-line summary for tool rows: the input gist (e.g. the SQL) or the
 *  first output line — never a repeat of the row title. */
function toolSummary(block: TimelineBlock): string {
  const input = prettyInput(block.input);
  if (input) return firstMeaningfulLine(input);
  const pretty = parseChunkEnvelope(block.output);
  if (pretty) return firstMeaningfulLine(pretty);
  if (block.output) return firstMeaningfulLine(block.output);
  return '';
}

// ── SQL syntax highlighting (mockup pre.sql tokens) ────────────────────

const SQL_TOKEN_RE =
  /('(?:[^'\\]|\\.)*')|(\b(?:SELECT|FROM|WHERE|GROUP|BY|ORDER|LIMIT|OFFSET|JOIN|LEFT|RIGHT|INNER|OUTER|FULL|ON|AS|AND|OR|NOT|NULL|DISTINCT|HAVING|UNION|ALL|ANY|INSERT|INTO|VALUES|UPDATE|SET|DELETE|CREATE|DROP|ALTER|TABLE|VIEW|INDEX|PRAGMA|CASE|WHEN|THEN|ELSE|END|ASC|DESC|IN|IS|LIKE|GLOB|BETWEEN|EXISTS|WITH|RECURSIVE|PRIMARY|KEY|FOREIGN|REFERENCES|DEFAULT|CHECK|UNIQUE|CONSTRAINT)\b)|(\b(?:COUNT|SUM|AVG|MIN|MAX|ROUND|STRFTIME|DATE|TIME|DATETIME|JULIANDAY|COALESCE|IFNULL|SUBSTR|LENGTH|TRIM|UPPER|LOWER|ABS|TOTAL|GROUP_CONCAT|ROW_NUMBER|RANK|DENSE_RANK|LAG|LEAD|CAST)\b(?=\s*\())|(\b\d+(?:\.\d+)?\b)/gi;

function renderSqlHighlighted(text: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let last = 0;
  let key = 0;
  for (const m of text.matchAll(SQL_TOKEN_RE)) {
    const idx = m.index ?? 0;
    if (idx > last) nodes.push(text.slice(last, idx));
    const [full, str, kw, fn, num] = m;
    if (str) {
      nodes.push(
        <span key={key++} className='text-[#15803d] dark:text-[#86efac]'>
          {full}
        </span>,
      );
    } else if (kw) {
      nodes.push(
        <span key={key++} className='text-[#7c3aed] dark:text-[#c4b5fd] font-semibold'>
          {full}
        </span>,
      );
    } else if (fn) {
      nodes.push(
        <span key={key++} className='text-[#0369a1] dark:text-[#7dd3fc]'>
          {full}
        </span>,
      );
    } else if (num) {
      nodes.push(
        <span key={key++} className='text-[#b45309] dark:text-[#fbbf24]'>
          {full}
        </span>,
      );
    }
    last = idx + full.length;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

/** SQL-ish inputs (sql_query tool / ``sql: ...`` payloads) get highlighting. */
function isSqlInput(block: TimelineBlock): boolean {
  const tool = (block.tool || '').toLowerCase();
  return tool.includes('sql') || (block.input || '').trimStart().toLowerCase().startsWith('sql:');
}

// ── shimmer sweep (DSH signature running animation) ────────────────────

const sweepKeyframes = `
@keyframes dsh-row-sweep {
  0% { left: -300px; }
  90%, 100% { left: 100%; }
}
`;

// ── row: 24px collapsible line (tools & thinking) ──────────────────────

function FlowRow({ block, sub = false }: { block: TimelineBlock; sub?: boolean }) {
  const { t } = useTranslation();
  // thinking rows start collapsed (DSH default); tool rows too.
  const [open, setOpen] = useState(false);
  const running = block.status === 'running' || block.streaming;
  const isGroup = Boolean(block.children && block.children.length > 0);

  const summary = useMemo(() => {
    if (block.kind === 'thinking') {
      // Completed reasoning shows its duration next to the title (mockup:
      // "思考 6s"); the summary slot stays empty to avoid duplication.
      if (running) return latestLine(block.thought || '') || (t('timeline_thinking_dots', '思考中…') as string);
      return '';
    }
    if (isGroup) return toolSummary(block.children![0]);
    return toolSummary(block);
  }, [block, running, isGroup]);

  const prettyOutput = useMemo(() => parseChunkEnvelope(block.output), [block.output]);
  const displayInput = useMemo(() => prettyInput(block.input), [block.input]);

  const hasBody = isGroup || Boolean(block.input || block.output || (block.kind === 'thinking' && block.thought));

  return (
    <div className={cls('select-none', sub && 'ml-5')} data-running={running || undefined}>
      <style>{sweepKeyframes}</style>
      <div
        className={cls(
          'relative overflow-hidden flex items-center gap-1.5 h-7 rounded-md px-1 -mx-1',
          hasBody && 'cursor-pointer hover:bg-[#f4f4f0] dark:hover:bg-white/[.05]',
        )}
        onClick={() => hasBody && setOpen(!open)}
      >
        {/* running shimmer sweep */}
        {running && (
          <span
            className='pointer-events-none absolute inset-y-0 w-[300px]'
            style={{
              background: 'linear-gradient(90deg, transparent 0%, rgba(128,134,148,.16) 55%, transparent 100%)',
              animation: 'dsh-row-sweep 2.6s ease-out infinite',
            }}
          />
        )}
        <span className='flex-none w-4 text-center text-[#8b8b84] dark:text-[#7c7972] text-xs'>
          {running ? (
            <Loading3QuartersOutlined className='animate-spin' />
          ) : block.kind === 'thinking' ? (
            <BulbOutlined />
          ) : (
            toolIcon(block.tool, block.title)
          )}
        </span>
        <span
          className={cls({
            'text-[12.5px] leading-7 text-[#8b8b84] dark:text-[#7c7972]': block.kind === 'thinking',
            'font-mono text-[12.5px] leading-7 font-medium': block.kind !== 'thinking',
            'text-[#55554f] dark:text-[#a8a59e]': block.kind !== 'thinking' && block.status === 'failed',
            'text-[#1c1c1a] dark:text-[#e6e4df]': block.kind !== 'thinking' && block.status !== 'failed',
          })}
        >
          {block.kind === 'thinking'
            ? block.streaming
              ? t('timeline_thinking_running', '思考中')
              : `${t('timeline_thinking', '思考')}${block.durationMs ? ` ${formatDuration(block.durationMs)}` : ''}`
            : block.title || block.tool}
        </span>
        {block.count != null && block.count > 1 && (
          <span className='flex-none text-[11px] leading-4 text-[#8b8b84] dark:text-[#7c7972] bg-[#efefeb] dark:bg-white/[.06] rounded-full px-1.5'>
            ×{block.count}
          </span>
        )}
        {summary ? (
          <>
            <span className='flex-none w-0.5 h-0.5 rounded-full bg-gray-300 dark:bg-gray-600 mx-2' />
            <span className='flex-1 min-w-0 truncate font-mono text-xs leading-7 text-[#8b8b84] dark:text-[#7c7972]'>
              {summary}
            </span>
          </>
        ) : (
          <span className='flex-1' />
        )}
        {block.kind !== 'thinking' && block.durationMs != null && block.durationMs > 0 && (
          <span className='flex-none text-xs text-[#8b8b84] dark:text-[#7c7972] tabular-nums'>
            {formatDuration(block.durationMs)}
          </span>
        )}
        {block.status === 'failed' && <span className='flex-none text-xs text-red-500'>失败</span>}
        {hasBody && (
          <span
            className={cls('flex-none text-[10px] text-[#8b8b84] dark:text-[#7c7972] transition-transform', {
              'rotate-90': open,
            })}
          >
            ▸
          </span>
        )}
      </div>
      {open && hasBody && (
        <div
          className={
            sub
              ? 'ml-6 mb-1 pl-3 py-1.5 space-y-2'
              : 'ml-6 mb-1 border-l-2 border-[#e6e6e2] dark:border-[#2a2925] pl-3 py-1.5 space-y-2'
          }
        >
          {isGroup ? (
            <div className='space-y-0.5'>
              {block.children!.map(child => (
                <FlowRow key={child.id} block={child} sub />
              ))}
            </div>
          ) : (
            <>
              {/* Raw reasoning belongs to the thinking row only — tool
                  rows show INPUT/OUTPUT, matching the mockup. */}
              {block.kind === 'thinking' && block.thought && (
                <pre className='text-xs leading-5 italic text-[#8b8b84] dark:text-[#7c7972] whitespace-pre-wrap break-words font-normal max-h-32 overflow-y-auto'>
                  {block.thought}
                </pre>
              )}
              {block.input && (
                <div>
                  <div className='text-[11px] text-gray-400 uppercase tracking-wide mb-0.5'>Input</div>
                  <pre className='text-xs leading-5 bg-[#efefeb] dark:bg-white/[.04] rounded-md p-2 text-[#55554f] dark:text-[#a8a59e] whitespace-pre-wrap break-all overflow-x-auto'>
                    {isSqlInput(block) ? renderSqlHighlighted(displayInput) : displayInput}
                  </pre>
                </div>
              )}
              {block.output && (
                <div>
                  <div className='text-[11px] text-gray-400 uppercase tracking-wide mb-0.5'>Output</div>
                  {prettyOutput ? (
                    <div className='text-xs leading-5 bg-[#efefeb] dark:bg-white/[.04] rounded-md p-2 text-[#3d3d38] dark:text-[#d4d2cc] max-h-56 overflow-y-auto'>
                      <MarkdownContext>{prettyOutput}</MarkdownContext>
                    </div>
                  ) : (
                    <pre className='text-xs leading-5 bg-[#efefeb] dark:bg-white/[.04] rounded-md p-2 text-[#55554f] dark:text-[#a8a59e] whitespace-pre-wrap break-all overflow-x-auto max-h-56 overflow-y-auto'>
                      {block.output}
                    </pre>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ── text block: plain streamed markdown paragraph ──────────────────────

function TextBlock({ block }: { block: TimelineBlock }) {
  return (
    <div className='text-sm leading-7 text-[#1c1c1a] dark:text-[#e6e4df] whitespace-pre-wrap mb-2'>
      {block.content}
      {block.streaming && <span className='inline-block w-2 h-4 bg-blue-500 align-[-2px] ml-0.5 animate-pulse' />}
    </div>
  );
}

/**
 * Question recap card: after the user answers (or skips) a `question` tool
 * call, the conversation flow keeps a readable Q&A record at the position
 * where the question was asked. Pending state shows "awaiting reply".
 */
function QuestionRecap({ block }: { block: TimelineBlock }) {
  const { t } = useTranslation();
  const pairs = block.pairs || [];
  if (!pairs.length) return null;
  return (
    <div className='my-2 rounded-xl border border-[#e6e6e2] bg-white px-4 py-3 shadow-[0_1px_2px_rgba(20,20,15,.05)] dark:border-[#33353b] dark:bg-[#1e1f24]'>
      {pairs.map((p, i) => (
        <div key={i} className={i > 0 ? 'mt-3' : undefined}>
          <div className='text-[13.5px] font-medium leading-6 text-[#1c1c1a] dark:text-[#e6e4df]'>
            {p.question}
          </div>
          <div className='mt-0.5 text-[13px] leading-6 text-[#8b8b84] dark:text-[#7c7972]'>
            {p.answer ? p.answer : block.rejected ? t('timeline_q_skipped') : t('timeline_q_awaiting')}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── main ───────────────────────────────────────────────────────────────

function AgentTimeline({ blocks, isRunning }: AgentTimelineProps) {
  if (blocks.length === 0 && !isRunning) {
    return <div className='text-sm text-[#8b8b84] dark:text-[#7c7972] italic py-2'>Waiting for agent to start…</div>;
  }
  return (
    <div className='py-1'>
      {blocks.map(block =>
        block.kind === 'text' ? (
          <TextBlock key={block.id} block={block} />
        ) : block.kind === 'question' ? (
          <QuestionRecap key={block.id} block={block} />
        ) : (
          <FlowRow key={block.id} block={block} />
        ),
      )}
    </div>
  );
}

export default AgentTimeline;
export { formatDuration, latestLine };
export type { AgentTimelineProps, TimelineBlock };

// ── adapter: ExecutionStep[] -> TimelineBlock[] ────────────────────────

/**
 * Shape-compatible bridge from the existing execution state
 * (the same data ManusLeftPanel renders as cards) to the
 * timeline view. Thinking steps (pi engine's "思考中" or any
 * step without an action) become collapsible thinking rows;
 * tool steps become collapsible tool rows.
 */
export interface TimelineSourceStep {
  id: string;
  title?: string;
  subtitle?: string;
  description?: string;
  status?: string;
  action?: string;
  actionInput?: unknown;
  startedAt?: number;
  endedAt?: number;
}

export function stepsToTimelineBlocks(
  steps: TimelineSourceStep[],
  stepThoughts: Record<string, string> | undefined,
  outputsByStep: Record<string, { output_type?: string; content?: unknown }[]> | undefined,
): TimelineBlock[] {
  const flat = steps.map(step => {
    const thought = stepThoughts?.[step.id] || '';
    const isThinking = !step.action && (step.title === '思考中' || (step.title || '').includes('思考'));
    const rawOutputs = outputsByStep?.[step.id] || [];
    const outputText = rawOutputs
      .filter(o => o.output_type === 'text' && o.content != null)
      .map(o => String(o.content))
      .join('\n');
    const status: TimelineBlock['status'] =
      step.status === 'completed' || step.status === 'done'
        ? 'success'
        : step.status === 'failed' || step.status === 'error'
          ? 'failed'
          : 'running';
    const durationMs =
      step.startedAt != null && step.endedAt != null ? Math.max(0, step.endedAt - step.startedAt) : undefined;
    const isQuestion = step.action === 'question';
    const recapChunk = rawOutputs.find(o => o.output_type === 'question_recap');
    const recap =
      recapChunk && typeof recapChunk.content === 'object' && recapChunk.content
        ? (recapChunk.content as {
            pairs?: { question: string; answer: string }[];
            rejected?: boolean;
            timed_out?: boolean;
          })
        : null;
    let pairs = recap?.pairs;
    let rejectedFlag = recap?.rejected || recap?.timed_out || undefined;
    if (!recap && isQuestion && outputText) {
      // pi engine: the recap travels as a fence inside the observation text.
      const fence = outputText.match(/```question_recap\n([\s\S]*?)\n```/);
      if (fence) {
        try {
          const parsed = JSON.parse(fence[1]) as {
            pairs?: { question: string; answer: string }[];
            rejected?: boolean;
            timed_out?: boolean;
          };
          if (Array.isArray(parsed.pairs)) {
            pairs = parsed.pairs;
            rejectedFlag = parsed.rejected || parsed.timed_out || undefined;
          }
        } catch {
          pairs = undefined;
        }
      } else if (status !== 'running') {
        // Legacy observations (pre-recap): parse "Q"="A" pairs as last resort.
        const legacy = [...outputText.matchAll(/"([^"]*)"="([^"]*)"/g)].map(m => ({
          question: m[1],
          answer: m[2] === 'Unanswered' ? '' : m[2],
        }));
        if (legacy.length) {
          pairs = legacy;
          rejectedFlag = /dismissed the question/i.test(outputText) || undefined;
        }
      }
    }
    if (!pairs && isQuestion && step.actionInput != null && status === 'running') {
      // Pending question (no recap yet): show the questions awaiting reply.
      try {
        const ai = typeof step.actionInput === 'string' ? JSON.parse(step.actionInput) : step.actionInput;
        const qs = (ai as { questions?: unknown })?.questions;
        if (Array.isArray(qs)) {
          pairs = qs.map((item: unknown) => {
            const text = typeof item === 'string' ? item : (item as { question?: string })?.question || '';
            return { question: text, answer: '' };
          });
        }
      } catch {
        pairs = undefined;
      }
    }
    return {
      id: step.id,
      kind: isThinking ? 'thinking' : isQuestion ? 'question' : 'tool',
      title: step.title,
      tool: step.action || step.title,
      status,
      durationMs,
      thought: thought || undefined,
      pairs,
      rejected: rejectedFlag,
      input:
        step.actionInput != null
          ? typeof step.actionInput === 'string'
            ? step.actionInput
            : JSON.stringify(step.actionInput, null, 2)
          : undefined,
      output: outputText || undefined,
      streaming: status === 'running',
    } as TimelineBlock;
  });

  // Collapse per-step thinking rows into a single turn-level reasoning
  // row (mockup: one "思考 Xs" disclosure). This also keeps tool blocks
  // consecutive so same-tool grouping spans reasoning gaps.
  const thinkingBlocks = flat.filter(b => b.kind === 'thinking');
  const restBlocks = flat.filter(b => b.kind !== 'thinking');
  const collapsed: TimelineBlock[] = thinkingBlocks.length
    ? [
        {
          id: `${thinkingBlocks[0].id}-reasoning`,
          kind: 'thinking',
          title: '思考',
          status: thinkingBlocks.some(b => b.status === 'running')
            ? 'running'
            : thinkingBlocks.some(b => b.status === 'failed')
              ? 'failed'
              : 'success',
          durationMs: thinkingBlocks.reduce((s, b) => s + (b.durationMs || 0), 0) || undefined,
          thought: thinkingBlocks
            .map(b => b.thought || '')
            .filter(Boolean)
            .join('\n\n'),
          streaming: thinkingBlocks.some(b => b.streaming),
        },
        ...restBlocks,
      ]
    : restBlocks;

  // Group consecutive same-tool calls into one collapsible row
  // (``sql_query ×8``) — Codex/OpenCode-style density for repetitive calls.
  const grouped: TimelineBlock[] = [];
  for (const block of collapsed) {
    const prev = grouped[grouped.length - 1];
    if (block.kind === 'tool' && prev && prev.kind === 'tool' && prev.tool === block.tool) {
      if (!prev.children) {
        const first = { ...prev };
        delete first.children;
        delete first.count;
        prev.children = [first];
      }
      prev.children.push(block);
      prev.count = prev.children.length;
      prev.durationMs = (prev.durationMs || 0) + (block.durationMs || 0);
      if (block.status === 'running') prev.status = 'running';
      else if (block.status === 'failed') prev.status = 'failed';
      prev.streaming = prev.status === 'running';
      continue;
    }
    grouped.push(block);
  }
  // A group of one is just a row — unwrap.
  for (const g of grouped) {
    if (g.children && g.children.length === 1) {
      const only = g.children[0];
      g.children = undefined;
      g.count = undefined;
      g.input = only.input;
      g.output = only.output;
      g.thought = only.thought;
      g.durationMs = only.durationMs;
      g.status = only.status;
      g.streaming = only.streaming;
    }
  }
  return grouped;
}
