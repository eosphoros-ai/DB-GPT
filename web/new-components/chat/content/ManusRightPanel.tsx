import { CodePreview } from '@/components/chat/chat-content/code-preview';
import markdownComponents, { markdownPlugins, preprocessLaTeX } from '@/components/chat/chat-content/config';
import type { SessionFileSnapshot } from '@/modules/session-files';
import AdvancedChart, { createChartConfig } from '@/new-components/charts';
import MarkDownContext from '@/new-components/common/MarkdownContext';
import type { SubAgentState, SubAgentStep } from '@/types/subagent';
import type { AgentCitation } from '@/utils/react-agent-final';
import {
  ApartmentOutlined,
  AppstoreOutlined,
  BarChartOutlined,
  BookOutlined,
  CheckCircleFilled,
  CheckOutlined,
  ClockCircleOutlined,
  CloseCircleFilled,
  CodeOutlined,
  ConsoleSqlOutlined,
  CopyOutlined,
  DatabaseOutlined,
  DesktopOutlined,
  DownOutlined,
  DownloadOutlined,
  EditOutlined,
  ExportOutlined,
  EyeOutlined,
  FileExcelOutlined,
  FileImageOutlined,
  FileOutlined,
  FilePptOutlined,
  FileSearchOutlined,
  FileTextOutlined,
  FolderOpenOutlined,
  LeftOutlined,
  LinkOutlined,
  LoadingOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  ProfileOutlined,
  RightOutlined,
  SearchOutlined,
  SyncOutlined,
  TableOutlined,
  UnorderedListOutlined,
  UpOutlined,
} from '@ant-design/icons';
import { GPTVis } from '@antv/gpt-vis';
import { Button, Table, Tooltip, message } from 'antd';
import classNames from 'classnames';
import React, { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Collapsible } from '../tools/Collapsible';
import ConversationTracePanel from './ConversationTracePanel';
import { ArtifactItem, StepStatus, StepType } from './ManusLeftPanel';
import ParallelTasksPanel from './ParallelTasksPanel';
import SubAgentStatusBadge from './SubAgentStatusBadge';
import type { TaskFileTab, TaskFileTabNavigationKey } from './task-files-view-model';
import { TASK_FILE_TABS, buildTaskFileView, getNextTaskFileTab, getTaskFileEmptyLabel } from './task-files-view-model';

/** Resolve image paths like `/images/xxx.png` to full backend URLs in dev mode */
const resolveImageUrl = (src: string): string => {
  if (!src) return src;
  if (/^https?:\/\//.test(src)) return src;
  if (src.startsWith('/images/')) {
    const base = process.env.API_BASE_URL || '';
    return base ? `${base}${src}` : src;
  }
  return src;
};

/** Replace `/images/...` references inside HTML content with full backend URLs */
const resolveHtmlImageUrls = (html: string): string => {
  const base = process.env.API_BASE_URL || '';
  if (!base || !html) return html;
  return html.replace(/(src\s*=\s*["'])\/images\//gi, `$1${base}/images/`);
};

export interface ExecutionOutput {
  output_type: 'code' | 'text' | 'markdown' | 'table' | 'chart' | 'json' | 'error' | 'thought' | 'html' | 'image';
  content: any;
  timestamp?: number;
}

type ExecutionOutputGroup =
  | { type: 'code-execution'; codes: ExecutionOutput[]; results: ExecutionOutput[]; images: ExecutionOutput[] }
  | { type: 'html-tabbed'; code?: ExecutionOutput; html: ExecutionOutput }
  | { type: 'single'; output: ExecutionOutput };

/**
 * Group outputs for one semantic step only.
 *
 * Keeping this pure lets the main execution view and the sub-agent timeline
 * share the same code/result rendering without merging adjacent sub-agent
 * steps into one visual block.
 */
const groupExecutionOutputs = (outputs: ExecutionOutput[]): ExecutionOutputGroup[] => {
  const groups: ExecutionOutputGroup[] = [];
  let i = 0;
  while (i < outputs.length) {
    if (outputs[i].output_type === 'code') {
      const codes: ExecutionOutput[] = [outputs[i]];
      i += 1;
      while (i < outputs.length && outputs[i].output_type === 'code') {
        codes.push(outputs[i]);
        i += 1;
      }
      if (i < outputs.length && outputs[i].output_type === 'html') {
        groups.push({
          type: 'html-tabbed',
          code: { ...codes[0], content: codes.map(c => String(c.content)).join('\n') },
          html: outputs[i],
        });
        i += 1;
      } else {
        const results: ExecutionOutput[] = [];
        while (i < outputs.length && outputs[i].output_type === 'text') {
          results.push(outputs[i]);
          i += 1;
        }
        const images: ExecutionOutput[] = [];
        while (i < outputs.length && outputs[i].output_type === 'image') {
          images.push(outputs[i]);
          i += 1;
        }
        groups.push({ type: 'code-execution', codes, results, images });
      }
    } else if (outputs[i].output_type === 'html') {
      groups.push({ type: 'html-tabbed', html: outputs[i] });
      i += 1;
    } else if (outputs[i].output_type === 'markdown') {
      const markdownParts: string[] = [String(outputs[i].content)];
      const firstMarkdown = outputs[i];
      i += 1;
      while (i < outputs.length && outputs[i].output_type === 'markdown') {
        markdownParts.push(String(outputs[i].content));
        i += 1;
      }
      groups.push({ type: 'single', output: { ...firstMarkdown, content: markdownParts.join('\n\n') } });
    } else if (outputs[i].output_type === 'text') {
      const textParts: string[] = [String(outputs[i].content)];
      const firstText = outputs[i];
      i += 1;
      while (i < outputs.length && outputs[i].output_type === 'text') {
        textParts.push(String(outputs[i].content));
        i += 1;
      }
      groups.push({ type: 'single', output: { ...firstText, content: textParts.join('\n\n') } });
    } else if (outputs[i].output_type === 'error') {
      const errorParts: string[] = [String(outputs[i].content)];
      const firstError = outputs[i];
      i += 1;
      while (i < outputs.length && outputs[i].output_type === 'error') {
        errorParts.push(String(outputs[i].content));
        i += 1;
      }
      groups.push({ type: 'single', output: { ...firstError, content: errorParts.join('') } });
    } else {
      groups.push({ type: 'single', output: outputs[i] });
      i += 1;
    }
  }
  return groups;
};

export interface ActiveStepInfo {
  id: string;
  type: StepType;
  title: string;
  subtitle?: string;
  status: StepStatus;
  detail?: string;
  action?: string;
  actionInput?: any;
}

export interface ManusRightPanelProps {
  activeStep?: ActiveStepInfo | null;
  outputs: ExecutionOutput[];
  isRunning?: boolean;
  onRerun?: () => void;
  onShare?: () => void;
  onSchedule?: () => void;
  terminalTitle?: string;
  isCollapsed?: boolean;
  artifacts?: ArtifactItem[];
  inputFiles?: readonly SessionFileSnapshot[];
  onArtifactClick?: (artifact: ArtifactItem) => void;
  /** Controlled panel view — when provided, overrides internal state */
  panelView?: PanelView;
  /** Callback when panel view changes (for lifting state) */
  onPanelViewChange?: (view: PanelView) => void;
  /** Artifact to preview in html-preview mode */
  previewArtifact?: ArtifactItem | null;
  /** Database type for SQL editor display (e.g. 'sqlite', 'mysql', 'postgres') */
  databaseType?: string;
  /** Database name for display */
  databaseName?: string;
  /** Skill name for the skill-preview tab (set when a skill is created/packaged) */
  skillName?: string | null;
  /** Summary content to display in the summary tab */
  summaryContent?: string;
  /** Whether the summary is currently streaming */
  isSummaryStreaming?: boolean;
  /** Structured knowledge sources retrieved or read during this answer. */
  citations?: AgentCitation[];
  /** Source currently selected in the references panel. */
  selectedCitationIndex?: number | null;
  /** Keep selection in sync when a reference card is clicked. */
  onCitationSelect?: (index: number) => void;
  /** Structured rows for the active dispatch_parallel_tasks step. */
  subAgents?: Record<string, SubAgentState>;
  /** Drill into one structured sub-agent from the parallel overview. */
  onSubAgentClick?: (agentId: string) => void;
  /**
   * When set, the right panel is showing a sub-agent's process view (not the
   * main agent's). Renders a "返回主 Agent" breadcrumb so the user can exit
   * the sub-agent view without clicking a main-agent step on the left.
   */
  subAgentContext?: SubAgentState | null;
  /** Exit the sub-agent process view (return to the main agent timeline). */
  onExitSubAgentView?: () => void;
  /**
   * Active conversation id used to query the observability trace for the
   * current conversation. When conversationId is provided, a "Trace" tab is
   * shown in the right panel.
   */
  conversationId?: string | null;
}

export type PanelView =
  | 'execution'
  | 'files'
  | 'html-preview'
  | 'image-preview'
  | 'skill-preview'
  | 'summary'
  | 'trace'
  | 'references';

// Get icon for step type
const getStepTypeIcon = (type: StepType) => {
  switch (type) {
    case 'read':
      return <FileSearchOutlined className='text-emerald-500' />;
    case 'edit':
    case 'write':
      return <EditOutlined className='text-amber-500' />;
    case 'bash':
      return <ConsoleSqlOutlined className='text-purple-500' />;
    case 'grep':
    case 'glob':
      return <SearchOutlined className='text-cyan-500' />;
    case 'python':
      return <CodeOutlined className='text-blue-500' />;
    case 'html':
      return <CodeOutlined className='text-orange-500' />;
    case 'task':
    case 'skill':
      return <PlayCircleOutlined className='text-indigo-500' />;
    case 'sql':
      return <ConsoleSqlOutlined className='text-emerald-600' />;
    case 'kb':
      return <FolderOpenOutlined className='text-teal-500' />;
    case 'code_graph':
      return <ApartmentOutlined className='text-violet-500' />;
    default:
      return <FileTextOutlined className='text-gray-500' />;
  }
};

// Get database type icon and label
const getDbTypeInfo = (dbType?: string): { icon: React.ReactNode; label: string } => {
  if (!dbType) return { icon: <DatabaseOutlined className='text-gray-500 text-sm' />, label: 'Database' };
  const lower = dbType.toLowerCase();
  if (lower.includes('mysql'))
    return { icon: <ConsoleSqlOutlined className='text-blue-500 text-sm' />, label: 'MySQL' };
  if (lower.includes('postgre'))
    return { icon: <DatabaseOutlined className='text-blue-400 text-sm' />, label: 'PostgreSQL' };
  if (lower.includes('sqlite'))
    return { icon: <DatabaseOutlined className='text-amber-500 text-sm' />, label: 'SQLite' };
  if (lower.includes('mongo'))
    return { icon: <DatabaseOutlined className='text-green-500 text-sm' />, label: 'MongoDB' };
  if (lower.includes('oracle')) return { icon: <DatabaseOutlined className='text-red-500 text-sm' />, label: 'Oracle' };
  if (lower.includes('mssql') || lower.includes('sqlserver'))
    return { icon: <DatabaseOutlined className='text-indigo-500 text-sm' />, label: 'SQL Server' };
  return { icon: <DatabaseOutlined className='text-gray-500 text-sm' />, label: dbType };
};

// Get status badge
const StatusBadge: React.FC<{ status: StepStatus }> = ({ status }) => {
  const { t } = useTranslation();
  switch (status) {
    case 'running':
      return (
        <div className='flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/50 text-blue-600 dark:text-blue-400 text-[10px] font-medium'>
          <LoadingOutlined spin className='text-xs' />
          <span>{t('Status')}</span>
        </div>
      );
    case 'completed':
      return (
        <div className='flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-900/50 text-emerald-600 dark:text-emerald-400 text-[10px] font-medium'>
          <CheckCircleFilled className='text-xs' />
          <span>{t('completed')}</span>
        </div>
      );
    case 'error':
      return (
        <div className='flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-red-100 dark:bg-red-900/50 text-red-600 dark:text-red-400 text-[10px] font-medium'>
          <CloseCircleFilled className='text-xs' />
          <span>{t('Error_Message')}</span>
        </div>
      );
    default:
      return (
        <div className='flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 text-[10px] font-medium'>
          <span>{t('Process')}</span>
        </div>
      );
  }
};

// Copy to clipboard helper
const copyToClipboard = (text: string, successText: string) => {
  navigator.clipboard.writeText(text);
  message.success(successText);
};

const getArtifactFileIcon = (artifact: ArtifactItem) => {
  switch (artifact.type) {
    case 'file': {
      const ext = artifact.name.toLowerCase().split('.').pop() || '';
      if (['xlsx', 'xls', 'csv'].includes(ext)) return <FileExcelOutlined className='text-green-600 text-lg' />;
      if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(ext))
        return <FileImageOutlined className='text-pink-500 text-lg' />;
      if (['ppt', 'pptx'].includes(ext)) return <FilePptOutlined className='text-orange-500 text-lg' />;
      return <FileTextOutlined className='text-blue-500 text-lg' />;
    }
    case 'html':
      return <DesktopOutlined className='text-blue-500 text-lg' />;
    case 'table':
      return <TableOutlined className='text-blue-500 text-lg' />;
    case 'chart':
      return <BarChartOutlined className='text-green-500 text-lg' />;
    case 'image':
      return <FileImageOutlined className='text-pink-500 text-lg' />;
    case 'code':
      return <CodeOutlined className='text-purple-500 text-lg' />;
    case 'markdown':
      return <FileTextOutlined className='text-orange-500 text-lg' />;
    case 'summary':
      return <FileTextOutlined className='text-emerald-500 text-lg' />;
    default:
      return <FileOutlined className='text-gray-500 text-lg' />;
  }
};

const getArtifactFileBg = (type: string): string => {
  const map: Record<string, string> = {
    file: 'bg-gray-50 dark:bg-gray-800',
    html: 'bg-blue-50 dark:bg-blue-900/20',
    table: 'bg-blue-50 dark:bg-blue-900/20',
    chart: 'bg-green-50 dark:bg-green-900/20',
    image: 'bg-pink-50 dark:bg-pink-900/20',
    code: 'bg-purple-50 dark:bg-purple-900/20',
    markdown: 'bg-orange-50 dark:bg-orange-900/20',
    summary: 'bg-emerald-50 dark:bg-emerald-900/20',
  };
  return map[type] || 'bg-gray-50 dark:bg-gray-800';
};

const getArtifactTypeLabel = (type: string): string => {
  const map: Record<string, string> = {
    file: '文件',
    html: '网页报告',
    table: '数据表',
    chart: '图表',
    image: '图片',
    code: '代码',
    markdown: '文档',
    summary: '分析总结',
  };
  return map[type] || '产物';
};

const formatArtifactDate = (timestamp: number): string => {
  const now = new Date();
  const date = new Date(timestamp);
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return '今天';
  if (diffDays === 1) return '昨天';
  if (diffDays < 7) {
    const dayNames = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六'];
    return dayNames[date.getDay()];
  }
  return `${date.getMonth() + 1}月${date.getDate()}日`;
};

const formatPanelFileSize = (bytes?: number): string => {
  if (!Number.isFinite(bytes ?? NaN)) return '';
  const value = bytes ?? 0;
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
};

const getInputFileIcon = (file: SessionFileSnapshot) => {
  const ext = file.name.toLowerCase().split('.').pop() || '';
  if (['xlsx', 'xls', 'csv', 'tsv', 'json', 'parquet'].includes(ext) || file.kind === 'table') {
    return <FileExcelOutlined className='text-emerald-600 dark:text-emerald-400' />;
  }
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(ext) || file.media_type.startsWith('image/')) {
    return <FileImageOutlined className='text-pink-500' />;
  }
  if (['ppt', 'pptx'].includes(ext)) {
    return <FilePptOutlined className='text-orange-500' />;
  }
  return <FileTextOutlined className='text-indigo-500 dark:text-indigo-400' />;
};

const InputFileListItem: React.FC<{ file: SessionFileSnapshot }> = memo(({ file }) => (
  <article className='group flex w-full items-center gap-3 rounded-xl border border-slate-200 bg-white px-3 py-3 text-left transition-colors duration-200 hover:border-emerald-200 hover:bg-emerald-50/30 dark:border-slate-800 dark:bg-[#17181b] dark:hover:border-emerald-800/60 dark:hover:bg-emerald-900/10'>
    <div className='flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-emerald-50 dark:bg-emerald-900/30'>
      {getInputFileIcon(file)}
    </div>
    <div className='min-w-0 flex-1'>
      <div className='truncate text-sm font-medium text-slate-800 dark:text-slate-100' title={file.name}>
        {file.name}
      </div>
      <div className='mt-0.5 flex min-w-0 items-center gap-1.5 text-[11px] text-slate-400 dark:text-slate-500'>
        <span>{file.kind || '资料'}</span>
        {file.size > 0 && (
          <>
            <span className='text-slate-300 dark:text-slate-600'>·</span>
            <span>{formatPanelFileSize(file.size)}</span>
          </>
        )}
      </div>
    </div>
  </article>
));

InputFileListItem.displayName = 'InputFileListItem';

const FileListItem: React.FC<{ artifact: ArtifactItem; onClick?: () => void }> = memo(({ artifact, onClick }) => {
  const isImage = artifact.type === 'image' || /\.(png|jpg|jpeg|gif|webp|svg)$/i.test(artifact.name);
  const imgSrc = isImage && typeof artifact.content === 'string' ? resolveImageUrl(artifact.content) : null;

  return (
    <button
      type='button'
      onClick={onClick}
      className='group flex w-full items-center gap-3 rounded-xl border border-indigo-100 bg-white px-3 py-3 text-left transition-all duration-200 hover:border-indigo-200 hover:bg-indigo-50/40 dark:border-indigo-900/40 dark:bg-[#17181b] dark:hover:border-indigo-800 dark:hover:bg-indigo-900/10'
    >
      {imgSrc ? (
        <img
          src={imgSrc}
          alt={artifact.name}
          className='h-9 w-9 flex-shrink-0 rounded-lg border border-gray-200 object-cover dark:border-gray-700'
        />
      ) : (
        <div
          className={classNames(
            'flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg',
            getArtifactFileBg(artifact.type),
          )}
        >
          {getArtifactFileIcon(artifact)}
        </div>
      )}
      <div className='min-w-0 flex-1'>
        <div className='text-sm font-medium text-gray-800 dark:text-gray-200 truncate'>{artifact.name}</div>
        <div className='text-[11px] text-gray-400 dark:text-gray-500 flex items-center gap-1.5 mt-0.5'>
          <span>{getArtifactTypeLabel(artifact.type)}</span>
          {artifact.size != null && (
            <>
              <span className='text-gray-300 dark:text-gray-600'>·</span>
              <span>
                {artifact.size < 1024
                  ? artifact.size + ' B'
                  : artifact.size < 1024 * 1024
                    ? (artifact.size / 1024).toFixed(1) + ' KB'
                    : (artifact.size / (1024 * 1024)).toFixed(1) + ' MB'}
              </span>
            </>
          )}
        </div>
      </div>
      <span className='rounded-full bg-indigo-100 px-2 py-0.5 text-[10px] font-medium text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300'>
        推理生成
      </span>
    </button>
  );
});

FileListItem.displayName = 'FileListItem';

// Repair markdown tables that an agent step squished onto a single line
// (e.g. `| a | b | | --- | --- | | 1 | 2 |### next`). Only rewrites a line
// that ALONE contains a `|---|` separator cell PLUS extra data cells — i.e.
// a whole table collapsed into one line. A normal multi-line table (separator
// on its own line) never matches, so this is a no-op for well-formed markdown.
function fixSquishedTables(text: string): string {
  if (!text || text.indexOf('|') === -1) return text;
  let t = text;
  // A. table row stuck to a following heading:  ...|### 2.  ->  ...|\n\n### 2.
  // Use [ \t] (not \s) so an already-correct newline before the heading is kept.
  t = t.replace(/\|[ \t]*(#{1,6}[ \t])/g, '|\n\n$1');
  // B. heading stuck to a following header row:  ### 2. 标题| col |  -> own line.
  // Only when heading and `|` are on the SAME physical line — [ \t] (not \s)
  // avoids swallowing the blank line above a well-formed `### 标题\n\n| ... |`.
  t = t.replace(/(^|\n)([ \t]*#{1,6}[^\n|]*?)[ \t]*\|/g, '$1$2\n|');
  // C. per-line: split a single-line-collapsed table back into rows
  return t
    .split('\n')
    .map(line => {
      const s = line.trim();
      if (!s.startsWith('|')) return line;
      if (!/\|\s*:?-{3,}:?\s*\|/.test(s)) return line; // must contain a separator cell
      const cells = s
        .split('|')
        .slice(1, -1)
        .map(c => c.trim());
      const isSep = (c: string) => /^:?-{3,}:?$/.test(c);
      const firstSep = cells.findIndex(isSep);
      if (firstSep < 0) return line;
      let sepEnd = firstSep;
      while (sepEnd < cells.length && isSep(cells[sepEnd])) sepEnd++;
      const n = sepEnd - firstSep;
      if (n < 1) return line;
      const hasDataBefore = firstSep > 0;
      const hasDataAfter = sepEnd < cells.length;
      // A genuine single-line-squished table has the header BEFORE and data
      // rows AFTER the separator cells, all on one line. Requiring BOTH avoids
      // touching a well-formed multi-line table whose own pure-separator row
      // (before-only) or a data row like `| --- | c |` (which is not both-sided
      // in a multi-line table) would otherwise be misread.
      if (!(hasDataBefore && hasDataAfter)) return line;
      let header = cells.slice(0, firstSep);
      if (header.length && header[header.length - 1] === '') header.pop();
      if (!header.length) header = Array(n).fill('');
      // If header width != separator count the parse is unreliable — leave the
      // line untouched rather than risk scrambling a real table.
      if (header.length !== n) return line;
      const rest = cells.slice(sepEnd);
      if (rest.length && rest[0] === '') rest.shift();
      const rows: string[][] = [];
      let j = 0;
      while (j < rest.length) {
        rows.push(rest.slice(j, j + n));
        j += n;
        if (j < rest.length && rest[j] === '') j++; // skip a single boundary blank
      }
      const wrap = (a: string[]) => '| ' + a.join(' | ') + ' |';
      const out = [wrap(header), wrap(Array(n).fill('---'))];
      rows.forEach(r => out.push(wrap(r)));
      return out.join('\n');
    })
    .join('\n');
}

// Auto-resizing iframe for HTML reports. Unlike a one-shot `onLoad` measure,
// this keeps a ResizeObserver on the iframe document body so the height tracks
// async content (charts / fonts / images that lay out after load). Falls back
// to a polling re-measure for the first second to catch late layout shifts.
const AutoHeightIframe: React.FC<{
  srcDoc: string;
  title?: string;
  minHeight?: number;
  maxHeight?: number;
}> = memo(({ srcDoc, title, minHeight = 500, maxHeight = 6000 }) => {
  const ref = useRef<HTMLIFrameElement>(null);

  // Neutralize viewport-relative full-height layouts. Reports authored with
  // `html,body{height:100vh}` / `height:100%` / a `min-height:100vh` hero pin
  // their height to the iframe's own viewport, so scrollHeight collapses to the
  // initial iframe height (a fixed point ResizeObserver can never grow out of —
  // the "only a purple gradient, cut off" symptom). Forcing auto height lets the
  // real content drive scrollHeight so measurement works.
  const patchedSrcDoc = useMemo(() => {
    const resetCss =
      '<style>html,body{height:auto!important;min-height:0!important;' + 'overflow:visible!important;}</style>';
    if (!srcDoc) return srcDoc;
    if (/<\/head>/i.test(srcDoc)) return srcDoc.replace(/<\/head>/i, resetCss + '</head>');
    if (/<body[^>]*>/i.test(srcDoc)) return srcDoc.replace(/(<body[^>]*>)/i, '$1' + resetCss);
    return resetCss + srcDoc;
  }, [srcDoc]);

  const measure = useCallback(() => {
    const iframe = ref.current;
    if (!iframe) return;
    try {
      const doc = iframe.contentDocument || iframe.contentWindow?.document;
      if (doc?.body) {
        const h = Math.max(doc.body.scrollHeight, doc.documentElement?.scrollHeight || 0, minHeight);
        iframe.style.height = `${Math.min(h, maxHeight)}px`;
      }
    } catch {
      // Cross-origin — keep current height
    }
  }, [minHeight, maxHeight]);

  const handleLoad = useCallback(() => {
    const iframe = ref.current;
    // Tear down any observer/timers from a previous load before re-arming, so
    // a re-fired onLoad (srcDoc change) does not leak observers/timers.
    (iframe as any)?.__cleanup?.();
    measure();
    let observer: ResizeObserver | null = null;
    try {
      const doc = iframe?.contentDocument || iframe?.contentWindow?.document;
      if (doc?.body && typeof ResizeObserver !== 'undefined') {
        observer = new ResizeObserver(() => measure());
        observer.observe(doc.body);
      }
    } catch {
      // ignore
    }
    // Catch late layout (charts/fonts) that may not trigger ResizeObserver.
    const timers = [120, 400, 1000].map(ms => setTimeout(measure, ms));
    (iframe as any).__cleanup = () => {
      observer?.disconnect();
      timers.forEach(clearTimeout);
    };
  }, [measure]);

  useEffect(() => {
    return () => {
      const iframe = ref.current as any;
      iframe?.__cleanup?.();
    };
  }, []);

  return (
    <iframe
      ref={ref}
      title={title || 'html-report'}
      srcDoc={patchedSrcDoc}
      sandbox='allow-scripts allow-same-origin'
      className='w-full bg-white'
      style={{ border: 'none', minHeight }}
      onLoad={handleLoad}
    />
  );
});

AutoHeightIframe.displayName = 'AutoHeightIframe';

// ── kb tool output rendering ────────────────────────────────────────────────
// kb_ls/kb_cat/kb_grep/kb_glob return plain-text observations; render them with
// structured viewers (file list / code viewer) instead of the raw terminal style.
const KB_TOOLS = new Set([
  'kb_ls',
  'kb_cat',
  'kb_grep',
  'kb_glob',
  'semantic_search',
  'kb_codegraph_explore',
  'kb_codegraph_call_chain',
  'kb_codegraph_class_hierarchy',
]);

// Friendly labels and icons for each kb tool action (used in the right-panel header card)
const KB_ACTION_LABELS: Record<string, string> = {
  kb_ls: 'List Files',
  kb_glob: 'Search by Name',
  kb_grep: 'Search Content',
  kb_cat: 'Read File',
  semantic_search: 'Semantic Search',
  kb_codegraph_explore: 'Code Graph Explore',
  kb_codegraph_call_chain: 'Call Chain',
  kb_codegraph_class_hierarchy: 'Class Hierarchy',
};
const KB_ACTION_ICONS: Record<string, React.ReactNode> = {
  kb_ls: <FolderOpenOutlined className='text-teal-500' />,
  kb_glob: <FileSearchOutlined className='text-teal-500' />,
  kb_grep: <SearchOutlined className='text-teal-500' />,
  kb_cat: <FileTextOutlined className='text-teal-500' />,
  semantic_search: <CodeOutlined className='text-teal-500' />,
  kb_codegraph_explore: <ApartmentOutlined className='text-violet-500' />,
  kb_codegraph_call_chain: <ApartmentOutlined className='text-violet-500' />,
  kb_codegraph_class_hierarchy: <ApartmentOutlined className='text-violet-500' />,
};

const KB_FILE_LINE_RE = /^(\S.*?)(?:\t(\S+))?$/;

/** Render kb_ls / kb_glob output as a file listing. Returns null if not parseable. */
function renderKbFileList(text: string, t: any): React.ReactNode {
  const lines = text.split('\n').filter(l => l.trim() && !l.startsWith('Directory:') && !l.startsWith('Matching'));
  if (lines.length === 0) return null;
  const entries = lines
    .map(line => {
      const m = line.match(KB_FILE_LINE_RE);
      if (!m) return null;
      const name = m[1]?.replace(/\/$/, '') || '';
      const isDir = line.trim().endsWith('/');
      return { name, isDir, lang: m[2] || '' };
    })
    .filter(Boolean) as { name: string; isDir: boolean; lang: string }[];
  if (entries.length === 0) return null;

  const sorted = [...entries].sort((a, b) => {
    if (a.isDir !== b.isDir) return a.isDir ? -1 : 1;
    return a.name.localeCompare(b.name);
  });

  return (
    <div className='rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden bg-white dark:bg-[#1a1d2e]'>
      <div className='flex items-center gap-2 px-3 py-2 bg-gradient-to-r from-gray-50 to-gray-100 dark:from-gray-800 dark:to-gray-800/70 border-b border-gray-200 dark:border-gray-700'>
        <FolderOpenOutlined style={{ color: '#1677FF', fontSize: 14 }} />
        <span className='text-xs font-semibold text-gray-600 dark:text-gray-300 uppercase tracking-wider'>
          {t('kb_ls') || 'Files'}
        </span>
        <span className='ml-auto text-[11px] text-gray-400'>{entries.length} entries</span>
      </div>
      <div className='font-mono text-[13px] leading-relaxed max-h-[400px] overflow-auto'>
        {sorted.map((e, i) => (
          <div
            key={i}
            className='flex items-center gap-2 py-1 px-3 hover:bg-blue-50/60 dark:hover:bg-blue-900/15 transition-colors'
          >
            {e.isDir ? (
              <FolderOpenOutlined style={{ color: '#1677FF', fontSize: 13 }} />
            ) : (
              <FileTextOutlined style={{ color: '#13C2C2', fontSize: 13 }} />
            )}
            <span
              className={e.isDir ? 'text-blue-600 dark:text-blue-400 font-medium' : 'text-gray-800 dark:text-gray-200'}
            >
              {e.name}
              {e.isDir ? '/' : ''}
            </span>
            {e.lang && (
              <span className='ml-auto text-[11px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400'>
                {e.lang}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/** Render kb_cat output as a code viewer with line numbers. Returns null if not parseable. */
function renderKbCat(text: string, t: any): React.ReactNode {
  const lines = text.split('\n');
  // Header: "path/to/file.py (python, 150 lines)"
  const headerMatch = lines[0]?.match(/^(.+?)\s*\((\w*)?,?\s*(\d+)\s*lines?\)/);
  if (!headerMatch) return null;
  const filePath = headerMatch[1].trim();
  const fileLang = headerMatch[2] || '';
  const fileLines = parseInt(headerMatch[3], 10);

  const truncationIdx = lines.findIndex(l => l.includes('truncated, use start_line='));
  const codeLines = truncationIdx >= 0 ? lines.slice(1, truncationIdx) : lines.slice(1);
  if (codeLines.length === 0) return null;

  return (
    <div className='rounded-lg overflow-hidden border border-gray-200 dark:border-gray-700 shadow-sm'>
      <div className='flex items-center gap-2 px-3 py-2 bg-gradient-to-r from-gray-50 to-gray-100 dark:from-gray-800 dark:to-gray-800/70 border-b border-gray-200 dark:border-gray-700'>
        <FileTextOutlined style={{ color: '#13C2C2', fontSize: 14 }} />
        <span className='text-sm font-mono font-medium text-gray-700 dark:text-gray-200 truncate'>{filePath}</span>
        {fileLang && (
          <span className='text-[11px] px-1.5 py-0.5 rounded bg-teal-50 dark:bg-teal-900/30 text-teal-600 dark:text-teal-400 font-mono border border-teal-100 dark:border-teal-800/50'>
            {fileLang}
          </span>
        )}
        <span className='ml-auto flex items-center gap-3 text-xs text-gray-400 dark:text-gray-500'>
          <span className='flex items-center gap-1'>
            <CodeOutlined style={{ fontSize: 11 }} />
            {fileLines} lines
          </span>
          <Tooltip title={t('Copy_Btn') || 'Copy'}>
            <button
              onClick={() => {
                const codeText = codeLines
                  .map(l => {
                    const m = l.match(/^\s*(\d+)\s*[|:]\s?(.*)/);
                    return m ? m[2] : l;
                  })
                  .join('\n');
                navigator.clipboard?.writeText(codeText);
                message.success(t('copy_to_clipboard_success'));
              }}
              className='text-gray-400 hover:text-teal-500 dark:hover:text-teal-400 transition-colors'
            >
              <CopyOutlined style={{ fontSize: 13 }} />
            </button>
          </Tooltip>
        </span>
      </div>
      <div className='font-mono text-[13px] leading-[1.65] overflow-x-auto bg-white dark:bg-[#1a1d2e] max-h-[500px] overflow-auto'>
        {codeLines.map((line, i) => {
          const m = line.match(/^\s*(\d+)\s*[|:]\s?(.*)/);
          const isEven = i % 2 === 1;
          const rowBg = isEven ? 'bg-gray-50/40 dark:bg-white/[0.015]' : 'bg-white dark:bg-transparent';
          if (m) {
            return (
              <div
                key={i}
                className={`flex ${rowBg} hover:bg-teal-50/60 dark:hover:bg-teal-900/15 transition-colors group`}
              >
                <span className='w-14 text-right pr-3 text-gray-300 dark:text-gray-600 select-none flex-shrink-0 border-r border-gray-100 dark:border-gray-700/40 group-hover:text-teal-500 dark:group-hover:text-teal-400 group-hover:bg-teal-50/50 dark:group-hover:bg-teal-900/20'>
                  {m[1]}
                </span>
                <span className='text-gray-800 dark:text-gray-200 whitespace-pre pl-3 flex-1 min-w-0'>
                  {m[2] || ' '}
                </span>
              </div>
            );
          }
          return (
            <div
              key={i}
              className={`flex ${rowBg} hover:bg-teal-50/60 dark:hover:bg-teal-900/15 transition-colors group`}
            >
              <span className='w-14 flex-shrink-0 border-r border-gray-100 dark:border-gray-700/40 group-hover:bg-teal-50/50 dark:group-hover:bg-teal-900/20' />
              <span className='text-gray-800 dark:text-gray-200 whitespace-pre pl-3 flex-1 min-w-0'>{line || ' '}</span>
            </div>
          );
        })}
      </div>
      {truncationIdx >= 0 && (
        <div className='px-3 py-2 bg-amber-50/60 dark:bg-amber-900/10 border-t border-amber-100 dark:border-amber-800/40 text-xs text-amber-600 dark:text-amber-400 italic'>
          {lines[truncationIdx]?.trim()}
        </div>
      )}
    </div>
  );
}

/** Render kb_grep output with file path headers and line numbers. Returns null if not parseable. */
function renderKbGrep(text: string, t: any): React.ReactNode {
  const lines = text.split('\n').filter(Boolean);
  if (lines.length === 0) return null;
  // Requires at least one matched-line pattern to treat as grep output
  const hasMatch = lines.some(l => /^\s*\d+\s*[|:]\s?/.test(l));
  if (!hasMatch) return null;

  return (
    <div className='rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden bg-white dark:bg-[#1a1d2e]'>
      <div className='flex items-center gap-2 px-3 py-2 bg-gradient-to-r from-amber-50 to-orange-50 dark:from-amber-900/20 dark:to-orange-900/10 border-b border-amber-100 dark:border-amber-800/40'>
        <SearchOutlined style={{ color: '#FA8C16', fontSize: 14 }} />
        <span className='text-xs font-semibold text-amber-700 dark:text-amber-400 uppercase tracking-wider'>
          {t('kb_grep') || 'Grep'}
        </span>
      </div>
      <div className='font-mono text-[13px] leading-relaxed max-h-[500px] overflow-auto'>
        {lines.map((line, i) => {
          // File path header (ends with ':')
          if (line.trim().endsWith(':') && !/^\s*\d+\s*[|:]/.test(line)) {
            const fp = line.trim().replace(/:$/, '');
            return (
              <div
                key={i}
                className='flex items-center gap-1.5 text-blue-600 dark:text-blue-400 font-semibold px-3 py-1.5 border-b border-gray-100 dark:border-gray-800 text-[12px] bg-gray-50/50 dark:bg-white/[0.02]'
              >
                <FileTextOutlined style={{ fontSize: 12 }} />
                {fp}
              </div>
            );
          }
          const m = line.match(/^\s*(\d+)\s*[|:]\s?(.*)/);
          if (m) {
            return (
              <div key={i} className='flex hover:bg-amber-50/40 dark:hover:bg-amber-900/10 transition-colors'>
                <span className='w-12 text-right pr-2 text-amber-500 dark:text-amber-400 select-none flex-shrink-0 text-[12px] border-r border-gray-100 dark:border-gray-700/40'>
                  {m[1]}
                </span>
                <span className='text-gray-800 dark:text-gray-200 whitespace-pre pl-3 flex-1 min-w-0'>{m[2]}</span>
              </div>
            );
          }
          return (
            <div key={i} className='text-gray-700 dark:text-gray-300 whitespace-pre px-3 py-0.5'>
              {line}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** Render code graph tool output (kb_codegraph_explore / call_chain / class_hierarchy) */
function renderKbCodeGraphOutput(action: string, text: string, _t: any): React.ReactNode {
  const actionLabel = KB_ACTION_LABELS[action] || 'Code Graph';
  const actionIcon = KB_ACTION_ICONS[action] || <ApartmentOutlined className='text-violet-500' />;

  // Try to parse structured JSON output; fall back to plain text
  let entries: { name: string; detail?: string; type?: string }[] = [];
  try {
    const parsed = JSON.parse(text);
    if (Array.isArray(parsed)) {
      entries = parsed.map((item: any) => ({
        name: item.name || item.function_name || item.class_name || item.entity || String(item),
        detail: item.detail || item.description || item.signature || item.docstring || '',
        type: item.type || item.kind || item.relationship || '',
      }));
    } else if (parsed.results && Array.isArray(parsed.results)) {
      entries = parsed.results.map((item: any) => ({
        name: item.name || item.function_name || item.class_name || item.entity || String(item),
        detail: item.detail || item.description || item.signature || item.docstring || '',
        type: item.type || item.kind || item.relationship || '',
      }));
    }
  } catch {
    // Not JSON — split by lines
    entries = text
      .split('\n')
      .filter(l => l.trim())
      .map(line => ({ name: line.trim() }));
  }

  return (
    <div className='rounded-lg border border-violet-200 dark:border-violet-800 overflow-hidden bg-white dark:bg-[#1a1d2e]'>
      <div className='flex items-center gap-2 px-3 py-2 bg-gradient-to-r from-violet-50 to-purple-50 dark:from-violet-900/30 dark:to-purple-900/30 border-b border-violet-200 dark:border-violet-800'>
        {React.cloneElement(actionIcon as React.ReactElement, { style: { fontSize: 14 } })}
        <span className='text-xs font-semibold text-violet-700 dark:text-violet-300 uppercase tracking-wider'>
          {actionLabel}
        </span>
        {entries.length > 0 && <span className='ml-auto text-[11px] text-gray-400'>{entries.length} results</span>}
      </div>
      <div className='font-mono text-[13px] leading-relaxed max-h-[400px] overflow-auto'>
        {entries.length > 0 ? (
          entries.map((entry, i) => (
            <div
              key={i}
              className='flex items-start gap-2 py-1.5 px-3 hover:bg-violet-50/60 dark:hover:bg-violet-900/15 transition-colors border-b border-gray-100 dark:border-gray-800 last:border-b-0'
            >
              <ApartmentOutlined style={{ color: '#8B5CF6', fontSize: 12, marginTop: 3, flexShrink: 0 }} />
              <div className='min-w-0 flex-1'>
                <div className='text-gray-800 dark:text-gray-200 font-medium truncate'>{entry.name}</div>
                {entry.type && (
                  <span className='inline-block text-[11px] px-1.5 py-0.5 rounded bg-violet-100 dark:bg-violet-900/40 text-violet-600 dark:text-violet-400 ml-1'>
                    {entry.type}
                  </span>
                )}
                {entry.detail && (
                  <div className='text-gray-500 dark:text-gray-400 text-[12px] mt-0.5 truncate'>{entry.detail}</div>
                )}
              </div>
            </div>
          ))
        ) : (
          <div className='px-3 py-2 text-gray-500 dark:text-gray-400 text-sm'>{text}</div>
        )}
      </div>
    </div>
  );
}

function renderKbToolOutput(action: string, text: string, t: any): React.ReactNode | null {
  if (action === 'kb_ls' || action === 'kb_glob') return renderKbFileList(text, t);
  if (action === 'kb_cat') return renderKbCat(text, t);
  if (action === 'kb_grep') return renderKbGrep(text, t);
  // Code graph tools: render as structured markdown-like output
  if (
    action === 'kb_codegraph_explore' ||
    action === 'kb_codegraph_call_chain' ||
    action === 'kb_codegraph_class_hierarchy'
  ) {
    return renderKbCodeGraphOutput(action, text, t);
  }
  return null;
}
// ── end kb tool output rendering ────────────────────────────────────────────

// Output Renderer Component
const OutputRenderer: React.FC<{ output: ExecutionOutput; index: number; action?: string }> = memo(
  ({ output, index: _index, action }) => {
    const { t } = useTranslation();
    const content = output.content;

    if (output.output_type === 'thought') {
      return null; // Don't render thoughts
    }

    // kb tools return plain text — render with a structured viewer when possible
    if (output.output_type === 'text' && action && KB_TOOLS.has(action)) {
      const text = typeof content === 'string' ? content : String(content ?? '');
      const rendered = renderKbToolOutput(action, text, t);
      if (rendered) return rendered;
    }

    return (
      <>
        {output.output_type === 'code' && (
          <CodePreview
            code={String(content)}
            language='python'
            customStyle={{ background: '#0f172a', margin: 0, borderRadius: 8 }}
          />
        )}

        {output.output_type === 'error' && (
          <div className='rounded-lg bg-red-50 dark:bg-red-900/20 px-4 py-3 text-sm text-red-600 dark:text-red-400 font-mono whitespace-pre overflow-x-auto'>
            {String(content)}
          </div>
        )}

        {output.output_type === 'text' && (
          <div className='rounded-lg bg-gray-900 px-4 py-3 text-sm text-green-400 font-mono whitespace-pre leading-relaxed overflow-x-auto'>
            {String(content)}
          </div>
        )}

        {output.output_type === 'markdown' && (
          <div className='prose prose-sm dark:prose-invert max-w-none'>
            <GPTVis components={markdownComponents} {...markdownPlugins}>
              {preprocessLaTeX(fixSquishedTables(String(content)))}
            </GPTVis>
          </div>
        )}

        {output.output_type === 'table' && (
          <Table
            size='small'
            pagination={{ pageSize: 10, showSizeChanger: true }}
            columns={(content?.columns || []).map((col: string | { title: string; dataIndex: string }) =>
              typeof col === 'string' ? { title: col, dataIndex: col, key: col, ellipsis: true } : col,
            )}
            dataSource={content?.rows || []}
            rowKey={(row, idx) => String(row?.id ?? idx)}
            scroll={{ x: 'max-content' }}
            className='border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden'
          />
        )}

        {output.output_type === 'chart' && (
          <div className='h-72'>
            <AdvancedChart
              config={createChartConfig(content?.data || [], {
                chartType: content?.chartType || 'line',
                xField: content?.xField || 'x',
                yField: content?.yField || 'y',
                seriesField: content?.seriesField,
                title: content?.title,
                smooth: true,
                height: 280,
              })}
            />
          </div>
        )}

        {output.output_type === 'json' && (
          <CodePreview
            code={typeof content === 'string' ? content : JSON.stringify(content, null, 2)}
            language='json'
            customStyle={{ background: '#0f172a', margin: 0, borderRadius: 8 }}
          />
        )}

        {output.output_type === 'html' && (
          <div className='rounded-lg overflow-hidden border border-gray-200 dark:border-gray-700'>
            {content?.title && (
              <div className='px-4 py-2 bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 flex items-center gap-2'>
                <FileTextOutlined className='text-blue-500 text-xs' />
                <span className='text-xs font-medium text-gray-600 dark:text-gray-300'>{content.title}</span>
              </div>
            )}
            <AutoHeightIframe
              srcDoc={resolveHtmlImageUrls(
                typeof content === 'string' ? content : content?.html || content?.content || String(content),
              )}
              title={content?.title}
            />
          </div>
        )}

        {output.output_type === 'image' && (
          <div className='rounded-lg overflow-hidden border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900'>
            <img
              src={resolveImageUrl(
                typeof content === 'string' ? content : content?.url || content?.src || String(content),
              )}
              alt='Generated chart'
              className='w-full h-auto object-contain'
              style={{ maxHeight: 600 }}
            />
          </div>
        )}
      </>
    );
  },
);

OutputRenderer.displayName = 'OutputRenderer';

// Parse get_skill_resource detail text to extract skill name, resource path, and content
const parseSkillResourceDetail = (
  detail?: string,
): { skillName: string; resourcePath: string; content: string } | null => {
  if (!detail) return null;
  try {
    // Extract Action Input JSON
    const inputMatch = detail.match(/Action Input:\s*({[\s\S]*?})(?:\n|$)/);
    if (!inputMatch) return null;
    const input = JSON.parse(inputMatch[1]);
    const skillName = input.skill_name || '';
    const resourcePath = input.resource_path || '';

    // Extract the observation/output JSON that contains the file content
    const afterInput = detail.slice(detail.indexOf(inputMatch[0]) + inputMatch[0].length);
    let content = '';
    const jsonMatch = afterInput.match(/{[\s\S]*}/);
    if (jsonMatch) {
      try {
        const output = JSON.parse(jsonMatch[0]);
        content = output.content || '';
      } catch {
        content = afterInput.trim();
      }
    }

    if (!skillName && !resourcePath) return null;
    return { skillName, resourcePath, content };
  } catch {
    return null;
  }
};

// Parse execute_skill_script_file detail text to extract script info and output
const parseSkillScriptDetail = (
  detail?: string,
): { skillName: string; scriptFileName: string; args: Record<string, any>; outputText: string } | null => {
  if (!detail) return null;
  try {
    const inputMatch = detail.match(/Action Input:\s*({[\s\S]*?})(?:\n|$)/);
    if (!inputMatch) return null;
    const input = JSON.parse(inputMatch[1]);
    const skillName = input.skill_name || '';
    const scriptFileName = input.script_file_name || '';
    const args = input.args || {};
    if (!skillName && !scriptFileName) return null;
    const afterInput = detail.slice(detail.indexOf(inputMatch[0]) + inputMatch[0].length);
    const outputText = afterInput.trim();
    return { skillName, scriptFileName, args, outputText };
  } catch {
    return null;
  }
};

// Parse load_skill detail text to extract skill name and description
// Handles both agent-selected (Action: load_skill) and pre-loaded (Pre-loaded skill from user selection) formats
// Also searches outputs for the "Skill: name — description" line when not found in detail
const parseLoadSkillDetail = (
  detail?: string,
  title?: string,
  outputs?: Array<{ output_type: string; content: any }>,
): { skillName: string; description: string } | null => {
  if (!detail && !title) return null;
  try {
    let skillName = '';
    let description = '';
    const inputMatch = detail?.match(/Action Input:\s*({[\s\S]*?})(?:\n|$)/);
    if (inputMatch) {
      try {
        const input = JSON.parse(inputMatch[1]);
        skillName = input.skill_name || '';
      } catch {
        // ignore parse error
      }
    }

    // Extract from "Skill: <name> <separator> <description>" observation line in detail
    // Support various separators: " - " (hyphen), " \u2014 " (em-dash), " \u2013 " (en-dash)
    const skillLineRegex = /Skill:\s*([\w-]+)\s+(?:-|\u2014|\u2013)\s+(.+)/;
    const obsMatch = detail?.match(skillLineRegex);
    if (obsMatch) {
      if (!skillName) skillName = obsMatch[1].trim();
      description = obsMatch[2].trim();
    }

    // Also search in outputs for the Skill line (it may come as step.chunk, not in detail)
    if (!description && outputs) {
      for (const output of outputs) {
        const content = typeof output.content === 'string' ? output.content.trim() : '';
        const outputMatch = content.match(skillLineRegex);
        if (outputMatch) {
          if (!skillName) skillName = outputMatch[1].trim();
          description = outputMatch[2].trim();
          break;
        }
      }
    }
    // Fallback: extract skill name from step title like "Load Skill: walmart-sales-analyzer"
    if (!skillName && title) {
      const titleMatch = title.match(/Load\s+Skill:\s*(.+)/i);
      if (titleMatch) skillName = titleMatch[1].trim();
    }
    if (!skillName && !description) return null;
    return { skillName, description };
  } catch {
    return null;
  }
};

/** Extract /images/ URLs from text */
const extractImageUrls = (text: string): string[] => {
  if (!text) return [];
  const matches = text.match(/\/images\/[^\s"')]+/g);
  return matches ? [...new Set(matches)] : [];
};

/** Split-pane renderer for execute_skill_script_file steps */
const SkillScriptRenderer: React.FC<{
  parsed: { skillName: string; scriptFileName: string; args: Record<string, any>; outputText: string };
  outputs: ExecutionOutput[];
}> = memo(({ parsed, outputs }) => {
  // Separate code outputs (script source) from other outputs — concatenate all
  // code chunks because the backend may split large code across multiple events.
  const codeOutputs = outputs.filter(o => o.output_type === 'code');
  const scriptSource = codeOutputs.length > 0 ? codeOutputs.map(o => String(o.content)).join('') : null;
  const imageOutputs = outputs.filter(o => o.output_type === 'image');
  const textOutputs = outputs.filter(o => o.output_type === 'text');
  // Also extract image URLs from outputText that may not be in outputs
  const inlineImageUrls = extractImageUrls(parsed.outputText);
  // Deduplicate: filter out URLs already in imageOutputs
  const existingUrls = new Set(
    imageOutputs.map(o => (typeof o.content === 'string' ? o.content : o.content?.url || '')),
  );
  const extraImageUrls = inlineImageUrls.filter(u => !existingUrls.has(u));
  const cleanTextOutputs = textOutputs
    .map(o => {
      const text = String(o.content);
      const cleaned = text
        .split('\n')
        .filter(line => !line.match(/^\s*[-\u2013]\s*\/images\//))
        .join('\n')
        .trim();
      return { ...o, content: cleaned };
    })
    .filter(o => o.content);
  const cleanOutputText = parsed.outputText
    .split('\n')
    .filter(line => !line.match(/^\s*[-\u2013]\s*\/images\//) && !line.match(/\u5df2\u751f\u6210\u7684\u56fe\u7247URL/))
    .join('\n')
    .trim();
  const htmlReportMatch = parsed.outputText.match(/HTML[_ ]report[_ ]generated[_ ]at:\s*(.+)/i);

  return (
    <div className='flex flex-1 min-h-0 overflow-hidden'>
      {/* Left Pane - Script Source Code */}
      <div className='w-[45%] flex-shrink-0 border-r border-gray-200 dark:border-gray-700 overflow-y-auto flex flex-col bg-[#0f172a]'>
        {/* Header */}
        <div className='px-4 py-3 border-b border-gray-700/50 bg-[#1e293b] flex-shrink-0'>
          <div className='flex items-center gap-2 mb-1.5'>
            <span className='inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium bg-indigo-900/40 text-indigo-300 border border-indigo-700/50'>
              {parsed.skillName}
            </span>
          </div>
          <div className='flex items-center gap-2'>
            <CodeOutlined className='text-blue-400 text-xs' />
            <span className='text-sm font-medium text-gray-200 break-all font-mono'>{parsed.scriptFileName}</span>
          </div>
        </div>

        {/* Script Source Code */}
        <div className='flex-1 min-h-0 overflow-auto'>
          {scriptSource ? (
            <CodePreview
              code={scriptSource}
              language='python'
              customStyle={{ background: '#0f172a', margin: 0, borderRadius: 0, padding: '12px 16px' }}
            />
          ) : (
            <div className='flex flex-col items-center justify-center py-12 text-gray-500'>
              <CodeOutlined className='text-2xl mb-2' />
              <span className='text-xs'>\u52A0\u8F7D\u811A\u672C\u4E2D...</span>
            </div>
          )}
        </div>
      </div>
      {/* Right Pane - Results */}
      <div className='flex-1 min-w-0 overflow-y-auto'>
        {/* HTML report badge */}
        {htmlReportMatch && (
          <div className='flex items-center gap-2 px-3 py-2 mx-3 mt-3 rounded-lg bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800'>
            <FileTextOutlined className='text-emerald-500' />
            <span className='text-xs font-medium text-emerald-700 dark:text-emerald-400 break-all'>
              {htmlReportMatch[1].trim()}
            </span>
          </div>
        )}
        {/* Text results */}
        {cleanTextOutputs.length > 0 &&
          cleanTextOutputs.map((o, idx) => (
            <div
              key={`text-${idx}`}
              className='rounded-lg bg-gray-900 mx-3 mt-2 px-4 py-3 text-sm text-green-400 font-mono whitespace-pre leading-relaxed overflow-x-auto'
            >
              {String(o.content)}
            </div>
          ))}
        {/* Fallback: if no text outputs but cleanOutputText has content */}
        {cleanTextOutputs.length === 0 && cleanOutputText && !htmlReportMatch && (
          <div className='rounded-lg bg-gray-900 mx-3 mt-2 px-4 py-3 text-sm text-green-400 font-mono whitespace-pre leading-relaxed overflow-x-auto'>
            {cleanOutputText}
          </div>
        )}
        {/* Images from outputs */}
        {imageOutputs.map((img, idx) => (
          <div key={`img-${idx}`} className='overflow-hidden bg-gray-50 dark:bg-gray-900'>
            <img
              src={resolveImageUrl(
                typeof img.content === 'string'
                  ? img.content
                  : img.content?.url || img.content?.src || String(img.content),
              )}
              alt={`Result ${idx + 1}`}
              className='w-full h-auto block'
            />
          </div>
        ))}
        {/* Extra images extracted from outputText */}
        {extraImageUrls.map((url, idx) => (
          <div key={`extra-img-${idx}`} className='overflow-hidden bg-gray-50 dark:bg-gray-900'>
            <img src={resolveImageUrl(url)} alt={`Generated ${idx + 1}`} className='w-full h-auto block' />
          </div>
        ))}
        {/* Empty state */}
        {imageOutputs.length === 0 &&
          extraImageUrls.length === 0 &&
          cleanTextOutputs.length === 0 &&
          !cleanOutputText &&
          !htmlReportMatch && (
            <div className='flex flex-col items-center justify-center py-8 text-gray-400'>
              <FileSearchOutlined className='text-2xl mb-2' />
              <span className='text-xs'>\u7B49\u5F85\u6267\u884C\u7ED3\u679C...</span>
            </div>
          )}
      </div>
    </div>
  );
});

SkillScriptRenderer.displayName = 'SkillScriptRenderer';

const HtmlTabbedRenderer: React.FC<{ code?: ExecutionOutput; html: ExecutionOutput }> = memo(({ code, html }) => {
  const [activeTab, setActiveTab] = useState<'preview' | 'source'>('preview');
  const htmlContent = html.content;
  const rawHtml =
    typeof htmlContent === 'string' ? htmlContent : htmlContent?.html || htmlContent?.content || String(htmlContent);
  const htmlString = resolveHtmlImageUrls(rawHtml);
  const sourceCode = code ? String(code.content) : rawHtml;

  return (
    <div className='rounded-xl overflow-hidden border border-gray-200 dark:border-gray-700'>
      <div className='flex items-center gap-0 bg-white dark:bg-[#111217] border-b border-gray-200 dark:border-gray-700'>
        <button
          onClick={() => setActiveTab('preview')}
          className={classNames(
            'px-4 py-2 text-xs font-medium transition-colors relative',
            activeTab === 'preview'
              ? 'text-gray-900 dark:text-gray-100'
              : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300',
          )}
        >
          <EyeOutlined className='mr-1.5' />
          渲染结果
          {activeTab === 'preview' && (
            <div className='absolute bottom-0 left-0 right-0 h-[2px] bg-gray-900 dark:bg-gray-100 rounded-full' />
          )}
        </button>
        <button
          onClick={() => setActiveTab('source')}
          className={classNames(
            'px-4 py-2 text-xs font-medium transition-colors relative',
            activeTab === 'source'
              ? 'text-gray-900 dark:text-gray-100'
              : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300',
          )}
        >
          <CodeOutlined className='mr-1.5' />
          源代码
          {activeTab === 'source' && (
            <div className='absolute bottom-0 left-0 right-0 h-[2px] bg-gray-900 dark:bg-gray-100 rounded-full' />
          )}
        </button>
      </div>

      {activeTab === 'preview' ? (
        <div>
          {htmlContent?.title && (
            <div className='px-4 py-2 bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 flex items-center gap-2'>
              <FileTextOutlined className='text-blue-500 text-xs' />
              <span className='text-xs font-medium text-gray-600 dark:text-gray-300'>{htmlContent.title}</span>
            </div>
          )}
          <AutoHeightIframe srcDoc={htmlString} title={htmlContent?.title} />
        </div>
      ) : (
        <CodePreview
          code={sourceCode}
          language='html'
          customStyle={{ background: '#0f172a', margin: 0, borderRadius: 0 }}
        />
      )}
    </div>
  );
});

HtmlTabbedRenderer.displayName = 'HtmlTabbedRenderer';

/** Tabbed code-execution renderer: shows images vs code+results as switchable tabs when images exist */
const CodeExecutionRenderer: React.FC<{
  group: { codes: ExecutionOutput[]; results: ExecutionOutput[]; images: ExecutionOutput[] };
}> = memo(({ group }) => {
  const hasImages = group.images.length > 0;
  const [activeTab, setActiveTab] = useState<'chart' | 'code'>(hasImages ? 'chart' : 'code');

  const codeContent = (
    <>
      <div className='relative overflow-auto flex-1 min-h-[100px]'>
        <span className='sticky top-0 right-0 float-right z-10 text-[10px] text-gray-400 bg-gray-800/80 px-2 py-0.5 rounded mr-2 mt-2'>
          代码
        </span>
        <CodePreview
          code={group.codes
            .map(c => String(c.content))
            .join('')
            .replace(/^\s*```[a-zA-Z]*\s*/m, '')
            .replace(/```\s*$/m, '')}
          language='python'
          customStyle={{ background: '#0f172a', margin: 0, borderRadius: 0 }}
        />
      </div>
      {group.results.length > 0 && (
        <>
          <div className='border-t border-gray-700/50 shrink-0' />
          <div className='relative overflow-auto bg-gray-900 flex-1 min-h-[60px]'>
            <span className='sticky top-0 right-0 float-right z-10 text-[10px] text-gray-400 bg-gray-800/80 px-2 py-0.5 rounded mr-2 mt-2'>
              执行结果
            </span>
            <div className='px-4 py-3 text-sm text-green-400 font-mono whitespace-pre leading-relaxed overflow-x-auto'>
              {group.results.map(r => String(r.content)).join('')}
            </div>
          </div>
        </>
      )}
    </>
  );

  const imageContent = (
    <div className='p-3 space-y-2 bg-gray-50 dark:bg-gray-900/50 flex-1 min-h-0 overflow-auto'>
      {group.images.map((img, imgIdx) => (
        <div key={`img-${imgIdx}`} className='rounded-lg overflow-hidden border border-gray-200 dark:border-gray-700'>
          <img
            src={resolveImageUrl(
              typeof img.content === 'string'
                ? img.content
                : img.content?.url || img.content?.src || String(img.content),
            )}
            alt='Generated chart'
            className='w-full h-auto object-contain'
            style={{ maxHeight: 600 }}
          />
        </div>
      ))}
    </div>
  );

  // No images — just code + results, no tabs
  if (!hasImages) {
    return (
      <div className='rounded-xl overflow-hidden border border-gray-700/50 flex flex-col flex-1 min-h-0'>
        {codeContent}
      </div>
    );
  }

  // Images exist — tabbed view
  return (
    <div className='rounded-xl overflow-hidden border border-gray-200 dark:border-gray-700 flex flex-col flex-1 min-h-0'>
      <div className='flex items-center gap-0 bg-white dark:bg-[#111217] border-b border-gray-200 dark:border-gray-700 shrink-0'>
        <button
          onClick={() => setActiveTab('chart')}
          className={classNames(
            'px-4 py-2 text-xs font-medium transition-colors relative',
            activeTab === 'chart'
              ? 'text-gray-900 dark:text-gray-100'
              : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300',
          )}
        >
          <FileImageOutlined className='mr-1.5' />
          图表
          {activeTab === 'chart' && (
            <div className='absolute bottom-0 left-0 right-0 h-[2px] bg-gray-900 dark:bg-gray-100 rounded-full' />
          )}
        </button>
        <button
          onClick={() => setActiveTab('code')}
          className={classNames(
            'px-4 py-2 text-xs font-medium transition-colors relative',
            activeTab === 'code'
              ? 'text-gray-900 dark:text-gray-100'
              : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300',
          )}
        >
          <CodeOutlined className='mr-1.5' />
          代码
          {activeTab === 'code' && (
            <div className='absolute bottom-0 left-0 right-0 h-[2px] bg-gray-900 dark:bg-gray-100 rounded-full' />
          )}
        </button>
      </div>
      {activeTab === 'chart' ? imageContent : codeContent}
    </div>
  );
});

CodeExecutionRenderer.displayName = 'CodeExecutionRenderer';

const formatSubAgentDuration = (elapsedMs?: number): string | null => {
  if (elapsedMs == null || elapsedMs < 0) return null;
  if (elapsedMs < 1000) return `${elapsedMs} ms`;
  const seconds = elapsedMs / 1000;
  if (seconds < 60) return `${seconds < 10 ? seconds.toFixed(1) : Math.round(seconds)} s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ${Math.round(seconds % 60)}s`;
};

const compactSubAgentIntention = (intention?: string): string =>
  (intention || '')
    .replace(/^Thought:\s*/i, '')
    .split(/\n(?:Action|Action Input|Observation):/i)[0]
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 240);

const getSubAgentDisplayName = (agent: SubAgentState): string => {
  const genericName = /^(?:子任务|subtask)\s*\d+$/i.test(agent.name.trim());
  return genericName && agent.goal ? agent.goal : agent.name;
};

const SubAgentHtmlOutputCard: React.FC<{
  content: any;
  onOpen?: () => void;
}> = ({ content, onOpen }) => {
  const { t } = useTranslation();
  const title = typeof content === 'object' && content?.title ? String(content.title) : 'Report.html';

  return (
    <div className='flex items-center justify-between gap-4 rounded-xl border border-blue-100 bg-blue-50/60 px-4 py-3 dark:border-blue-500/20 dark:bg-blue-500/[0.08]'>
      <div className='flex min-w-0 items-center gap-3'>
        <span className='flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-white text-blue-600 shadow-sm ring-1 ring-blue-100 dark:bg-blue-500/10 dark:text-blue-400 dark:ring-blue-500/20'>
          <DesktopOutlined aria-hidden />
        </span>
        <div className='min-w-0'>
          <div className='truncate text-sm font-medium text-slate-800 dark:text-slate-100'>{title}</div>
          <div className='mt-0.5 text-xs text-slate-500 dark:text-slate-400'>{t('subagent_report_ready')}</div>
        </div>
      </div>
      {onOpen && (
        <button
          type='button'
          onClick={onOpen}
          className='inline-flex min-h-[34px] flex-shrink-0 items-center gap-1.5 rounded-lg bg-white px-3 text-xs font-medium text-blue-600 shadow-sm ring-1 ring-blue-100 transition-colors hover:bg-blue-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40 dark:bg-white/[0.06] dark:text-blue-400 dark:ring-blue-500/20 dark:hover:bg-blue-500/10'
        >
          <EyeOutlined aria-hidden />
          {t('subagent_open_report')}
        </button>
      )}
    </div>
  );
};

const SubAgentSqlPreview: React.FC<{ sql: string }> = ({ sql }) => {
  const { t } = useTranslation();
  const compactSql = sql.replace(/\s+/g, ' ').trim();

  return (
    <Collapsible
      defaultOpen={false}
      className='overflow-hidden rounded-lg border border-slate-200 bg-slate-50/80 dark:border-white/10 dark:bg-white/[0.025]'
    >
      <Collapsible.Trigger className='group'>
        <div className='flex min-h-[42px] items-center gap-2.5 px-3 py-2'>
          <span className='flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-md bg-emerald-50 text-emerald-600 ring-1 ring-emerald-100 dark:bg-emerald-500/10 dark:text-emerald-400 dark:ring-emerald-500/20'>
            <ConsoleSqlOutlined aria-hidden />
          </span>
          <span className='flex-shrink-0 text-xs font-medium text-slate-600 dark:text-slate-300'>
            {t('subagent_executed_sql')}
          </span>
          <code className='min-w-0 flex-1 truncate text-[11px] text-slate-400 dark:text-slate-500'>{compactSql}</code>
          <Collapsible.Arrow className='flex-shrink-0' />
        </div>
      </Collapsible.Trigger>
      <Collapsible.Content>
        <div className='border-t border-slate-200 dark:border-white/10'>
          <CodePreview
            code={sql}
            language='sql'
            customStyle={{ background: '#0f172a', margin: 0, borderRadius: 0 }}
            codeStyle={{ background: 'transparent' }}
          />
        </div>
      </Collapsible.Content>
    </Collapsible>
  );
};

const SubAgentStepCard: React.FC<{
  step: SubAgentStep;
  index: number;
  autoOpen: boolean;
  isLast: boolean;
  onHtmlOpen?: (content: any, title: string, outputIndex: number) => void;
}> = ({ step, index, autoOpen, isLast, onHtmlOpen }) => {
  const { t } = useTranslation();
  const intention = compactSubAgentIntention(step.intention);
  const outputs = (step.chunks || [])
    .filter(chunk => chunk.output_type !== 'thought')
    .map<ExecutionOutput>(chunk => ({
      output_type: chunk.output_type as ExecutionOutput['output_type'],
      content: chunk.content,
    }));
  const groups = groupExecutionOutputs(outputs);
  const hasError = outputs.some(output => output.output_type === 'error');
  const [open, setOpen] = useState(autoOpen || hasError);
  const [manuallyChanged, setManuallyChanged] = useState(false);

  useEffect(() => {
    if (!manuallyChanged) setOpen(autoOpen || hasError);
  }, [autoOpen, hasError, manuallyChanged]);

  return (
    <li className='relative pl-8' data-testid={`subagent-step-${index + 1}`}>
      {!isLast && <span className='absolute bottom-[-12px] left-[11px] top-7 w-px bg-slate-200 dark:bg-white/10' />}
      <span
        className={classNames(
          'absolute left-[5px] top-[22px] z-10 flex h-[13px] w-[13px] items-center justify-center rounded-full ring-4 ring-[#f8f9fc] dark:ring-[#0d0e11]',
          hasError ? 'bg-red-500' : autoOpen ? 'bg-blue-500' : 'bg-emerald-500',
        )}
      >
        <CheckOutlined aria-hidden className='text-[7px] text-white' />
      </span>

      <Collapsible
        open={open}
        onOpenChange={next => {
          setOpen(next);
          setManuallyChanged(true);
        }}
        className={classNames(
          'overflow-hidden rounded-xl border bg-white shadow-sm transition-colors dark:bg-[#17181d]',
          hasError
            ? 'border-red-200 dark:border-red-500/30'
            : open
              ? 'border-blue-200 shadow-md shadow-blue-950/[0.04] dark:border-blue-500/30'
              : 'border-slate-200/80 dark:border-white/10',
        )}
      >
        <Collapsible.Trigger className='group'>
          <div className='flex min-h-[70px] items-start gap-3 px-4 py-3.5 transition-colors group-hover:bg-slate-50/70 dark:group-hover:bg-white/[0.025]'>
            <span className='mt-0.5 flex h-6 min-w-6 items-center justify-center rounded-md bg-slate-100 px-1.5 text-[11px] font-semibold text-slate-500 dark:bg-white/[0.06] dark:text-slate-400'>
              {index + 1}
            </span>
            <div className='min-w-0 flex-1'>
              <div className='flex flex-wrap items-center gap-2'>
                <h3 className='m-0 text-sm font-semibold leading-5 text-slate-800 dark:text-slate-100'>{step.label}</h3>
                <span className='max-w-full truncate rounded-md bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-500 dark:bg-white/[0.06] dark:text-slate-400'>
                  {step.action}
                </span>
              </div>
              {intention && (
                <p className='mt-1 line-clamp-2 text-xs leading-5 text-slate-500 dark:text-slate-400'>{intention}</p>
              )}
            </div>
            <div className='flex flex-shrink-0 items-center gap-2 pt-0.5'>
              {outputs.length > 0 && (
                <span className='text-[11px] text-slate-400 dark:text-slate-500'>
                  {t('subagent_output_count', { count: outputs.length })}
                </span>
              )}
              <Collapsible.Arrow />
            </div>
          </div>
        </Collapsible.Trigger>

        <Collapsible.Content>
          <div className='border-t border-blue-100 bg-blue-50/35 px-5 py-5 dark:border-blue-500/20 dark:bg-blue-500/[0.04]'>
            <div className='space-y-4 rounded-xl border border-slate-200/80 bg-white p-4 shadow-sm dark:border-white/10 dark:bg-[#111217]'>
              {step.sql && <SubAgentSqlPreview sql={step.sql} />}
              {step.sql && groups.length > 0 && (
                <div className='flex items-center gap-1.5 text-xs font-medium text-slate-500 dark:text-slate-400'>
                  <TableOutlined aria-hidden className='text-blue-500' />
                  {t('subagent_query_result')}
                </div>
              )}
              {groups.length > 0 ? (
                groups.map((group, groupIndex) => {
                  if (group.type === 'code-execution') {
                    return <CodeExecutionRenderer key={`code-${groupIndex}`} group={group} />;
                  }
                  if (group.type === 'html-tabbed') {
                    const htmlContent = group.html.content;
                    const title =
                      typeof htmlContent === 'object' && htmlContent?.title ? String(htmlContent.title) : 'Report.html';
                    return (
                      <SubAgentHtmlOutputCard
                        key={`html-${groupIndex}`}
                        content={htmlContent}
                        onOpen={onHtmlOpen ? () => onHtmlOpen(htmlContent, title, groupIndex) : undefined}
                      />
                    );
                  }
                  return <OutputRenderer key={`output-${groupIndex}`} output={group.output} index={groupIndex} />;
                })
              ) : (
                <div className='rounded-lg bg-slate-50 px-3 py-2.5 text-xs text-slate-400 ring-1 ring-slate-100 dark:bg-white/[0.03] dark:ring-white/10'>
                  {t('subagent_no_output')}
                </div>
              )}
            </div>
          </div>
        </Collapsible.Content>
      </Collapsible>
    </li>
  );
};

const SubAgentProcessView: React.FC<{
  agent: SubAgentState;
  onArtifactClick?: (artifact: ArtifactItem) => void;
}> = ({ agent, onArtifactClick }) => {
  const { t } = useTranslation();
  const hasResult = Boolean(agent.result?.trim());
  const [section, setSection] = useState<'activity' | 'result'>(
    agent.status === 'done' && hasResult ? 'result' : 'activity',
  );

  const openHtmlReport = useCallback(
    (content: any, title: string, stepIndex: number, outputIndex: number) => {
      onArtifactClick?.({
        id: `subagent-${agent.agentId}-${stepIndex}-${outputIndex}`,
        type: 'html',
        name: title,
        content,
        createdAt: Date.now(),
      });
    },
    [agent.agentId, onArtifactClick],
  );

  return (
    <div className='flex min-h-0 flex-1 flex-col overflow-hidden' data-testid='subagent-detail-view'>
      <div
        role='tablist'
        aria-label={t('subagent_detail_sections')}
        className='flex flex-shrink-0 items-center gap-1 border-b border-slate-200 bg-white px-5 py-2 dark:border-white/10 dark:bg-[#111217]'
      >
        <button
          type='button'
          role='tab'
          aria-selected={section === 'activity'}
          onClick={() => setSection('activity')}
          className={classNames(
            'inline-flex min-h-[34px] items-center gap-1.5 rounded-lg px-3 text-xs font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40',
            section === 'activity'
              ? 'bg-slate-100 text-slate-900 dark:bg-white/[0.08] dark:text-slate-100'
              : 'text-slate-500 hover:bg-slate-50 hover:text-slate-700 dark:text-slate-400 dark:hover:bg-white/[0.04] dark:hover:text-slate-200',
          )}
        >
          <UnorderedListOutlined aria-hidden />
          {t('subagent_activity')}
          <span className='text-[10px] text-slate-400'>{agent.steps.length}</span>
        </button>
        {hasResult && (
          <button
            type='button'
            role='tab'
            aria-selected={section === 'result'}
            onClick={() => setSection('result')}
            className={classNames(
              'inline-flex min-h-[34px] items-center gap-1.5 rounded-lg px-3 text-xs font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40',
              section === 'result'
                ? 'bg-slate-100 text-slate-900 dark:bg-white/[0.08] dark:text-slate-100'
                : 'text-slate-500 hover:bg-slate-50 hover:text-slate-700 dark:text-slate-400 dark:hover:bg-white/[0.04] dark:hover:text-slate-200',
            )}
          >
            <FileTextOutlined aria-hidden />
            {t('parallel_tasks_result_summary')}
          </button>
        )}
      </div>

      <div
        className='min-h-0 flex-1 overflow-y-auto overscroll-contain bg-[#f8f9fc] px-5 py-5 dark:bg-[#0d0e11]'
        data-testid='subagent-detail-scroll'
      >
        {section === 'result' && hasResult ? (
          <section className='mx-auto max-w-4xl rounded-xl border border-slate-200/80 bg-white px-5 py-5 shadow-sm dark:border-white/10 dark:bg-[#17181d]'>
            <div className='mb-4 flex items-center gap-2 text-sm font-semibold text-slate-800 dark:text-slate-100'>
              <CheckCircleFilled aria-hidden className='text-emerald-500' />
              {t('parallel_tasks_result_summary')}
            </div>
            <div className='prose prose-sm max-w-none dark:prose-invert'>
              <MarkDownContext>{agent.result || ''}</MarkDownContext>
            </div>
          </section>
        ) : agent.steps.length > 0 ? (
          <ol className='mx-auto max-w-4xl space-y-3'>
            {agent.steps.map((step, index) => (
              <SubAgentStepCard
                key={`${agent.agentId}-${index}-${step.action}`}
                step={step}
                index={index}
                autoOpen={false}
                isLast={index === agent.steps.length - 1}
                onHtmlOpen={(content, title, outputIndex) => openHtmlReport(content, title, index, outputIndex)}
              />
            ))}
          </ol>
        ) : (
          <div className='flex h-full min-h-[240px] flex-col items-center justify-center text-slate-400'>
            {agent.status === 'running' ? (
              <LoadingOutlined aria-hidden spin className='mb-3 text-2xl text-blue-500' />
            ) : (
              <UnorderedListOutlined aria-hidden className='mb-3 text-2xl text-slate-300 dark:text-slate-600' />
            )}
            <span className='text-sm'>{t('subagent_waiting_steps')}</span>
          </div>
        )}
      </div>
    </div>
  );
};

/** Parse shell command from step detail (Action Input JSON) */
const parseShellCommand = (detail?: string): string => {
  if (!detail) return '';
  const inputMatch = detail.match(/Action Input:\s*({[\s\S]*?})(?:\n|$)/);
  if (!inputMatch) return '';
  try {
    const parsed = JSON.parse(inputMatch[1]);
    return parsed.code || '';
  } catch {
    return '';
  }
};

/** Terminal-style renderer for shell/bash steps — mimics a real terminal session */
const TerminalRenderer: React.FC<{
  activeStep: ActiveStepInfo;
  outputs: ExecutionOutput[];
}> = memo(({ activeStep, outputs }) => {
  const command =
    parseShellCommand(activeStep.detail) ||
    outputs
      .filter(o => o.output_type === 'code')
      .map(o => String(o.content))
      .join('');
  const resultChunks = outputs.filter(o => o.output_type === 'text');
  const errorChunks = outputs.filter(o => o.output_type === 'error');
  const resultText = resultChunks.map(r => String(r.content)).join('');
  const errorText = errorChunks.map(e => String(e.content)).join('');
  const isRunning = activeStep.status === 'running';
  const _isError = activeStep.status === 'error' || errorChunks.length > 0;

  const allText = [command ? `$ ${command}` : '', resultText, errorText].filter(Boolean).join('\n');

  return (
    <div className='flex flex-col flex-1 min-h-0 overflow-hidden rounded-xl border border-gray-700/60'>
      {/* Terminal title bar */}
      <div className='flex items-center justify-between px-4 py-2.5 bg-[#1e2030] border-b border-gray-700/50 shrink-0'>
        <div className='flex items-center gap-3'>
          <div className='flex items-center gap-1.5'>
            <div className='w-3 h-3 rounded-full bg-[#ff5f57]' />
            <div className='w-3 h-3 rounded-full bg-[#febc2e]' />
            <div className='w-3 h-3 rounded-full bg-[#28c840]' />
          </div>
          <div className='flex items-center gap-2'>
            <ConsoleSqlOutlined className='text-gray-400 text-xs' />
            <span className='text-xs font-medium text-gray-400'>Terminal</span>
          </div>
        </div>
        <div className='flex items-center gap-2'>
          <StatusBadge status={activeStep.status} />
          {allText && (
            <Tooltip title='复制全部'>
              <button
                className='flex items-center gap-1 text-[11px] text-gray-500 hover:text-gray-300 transition-colors px-2 py-1 rounded hover:bg-gray-700/50'
                onClick={() => copyToClipboard(allText)}
              >
                <CopyOutlined className='text-xs' />
              </button>
            </Tooltip>
          )}
        </div>
      </div>

      {/* Terminal body */}
      <div className='flex-1 min-h-0 overflow-auto bg-[#0d1117] px-5 py-4 font-mono text-sm leading-relaxed'>
        {/* Command line */}
        {command && (
          <div className='whitespace-pre-wrap break-all'>
            <span className='text-[#3fb950] font-semibold'>dbgpt@sandbox</span>
            <span className='text-[#8b949e]'>:</span>
            <span className='text-[#58a6ff] font-semibold'>~</span>
            <span className='text-[#8b949e]'>$ </span>
            <span className='text-[#e6edf3]'>{command}</span>
          </div>
        )}

        {/* Output */}
        {resultText && <div className='text-[#c9d1d9] whitespace-pre mt-1 w-fit min-w-full'>{resultText}</div>}

        {/* Error output */}
        {errorText && <div className='text-[#f85149] whitespace-pre mt-1 w-fit min-w-full'>{errorText}</div>}

        {/* Next prompt line / cursor */}
        {(resultText || errorText || command) && (
          <div className='mt-1'>
            <span className='text-[#3fb950] font-semibold'>dbgpt@sandbox</span>
            <span className='text-[#8b949e]'>:</span>
            <span className='text-[#58a6ff] font-semibold'>~</span>
            <span className='text-[#8b949e]'>$ </span>
            {isRunning && <span className='inline-block w-2 h-4 bg-[#e6edf3] animate-pulse ml-0.5 align-text-bottom' />}
          </div>
        )}

        {/* Empty state while running */}
        {!command && !resultText && !errorText && isRunning && (
          <div>
            <span className='text-[#3fb950] font-semibold'>dbgpt@sandbox</span>
            <span className='text-[#8b949e]'>:</span>
            <span className='text-[#58a6ff] font-semibold'>~</span>
            <span className='text-[#8b949e]'>$ </span>
            <span className='inline-block w-2 h-4 bg-[#e6edf3] animate-pulse ml-0.5 align-text-bottom' />
          </div>
        )}
      </div>
    </div>
  );
});

TerminalRenderer.displayName = 'TerminalRenderer';

/** Parse skill name from skill-creator output (package_skill or init_skill steps) */
const _parseSkillCreatorOutput = (detail?: string, outputs?: ExecutionOutput[]): string | null => {
  // Collect all text to search
  const allTexts: string[] = [];
  if (detail) allTexts.push(detail);
  if (outputs) {
    for (const o of outputs) allTexts.push(String(o.content || ''));
  }
  const combined = allTexts.join('\n');

  // Priority 1: Explicit skill name patterns from init_skill/package_skill output
  // "Skill 'xxx' initialized" or "Skill 'xxx' packaged"
  const quotedSkill = combined.match(/[Ss]kill\s+['"]([\w-]+)['"]/);
  if (quotedSkill) return quotedSkill[1];

  // "Initializing skill: xxx" or "Packaging skill: xxx"
  const colonSkill = combined.match(/(?:Initializing|Packaging)\s+skill:\s*(?:skills\/)?([\w-]+)/);
  if (colonSkill) return colonSkill[1];

  // "Created skill directory: .../skills/xxx"
  const createdDir = combined.match(/Created skill directory:.*\/skills\/([\w-]+)/);
  if (createdDir) return createdDir[1];

  // Priority 2: Action Input JSON (for non-shell actions)
  if (detail) {
    const inputMatch = detail.match(/Action Input:\s*({[\s\S]*?})(?:\n|$)/);
    if (inputMatch) {
      try {
        const parsed = JSON.parse(inputMatch[1]);
        if (parsed.skill_name) return parsed.skill_name;
        if (parsed.name) return parsed.name;
      } catch {
        /* ignore */
      }
    }
  }

  // Priority 3: Last skills/xxx path (skip skill-creator which is the tool, not the created skill)
  const allPaths = [...combined.matchAll(/skills\/([\w-]+)/g)].map(m => m[1]).filter(name => name !== 'skill-creator');
  if (allPaths.length > 0) return allPaths[allPaths.length - 1];

  return null;
};

/** File tree node from /v1/skills/detail API */
interface SkillTreeNode {
  title: string;
  key: string;
  children?: SkillTreeNode[];
}

/** Recursive file tree component */
const FileTreeItem: React.FC<{
  node: SkillTreeNode;
  depth: number;
  selectedKey: string | null;
  onSelect: (key: string) => void;
}> = ({ node, depth, selectedKey, onSelect }) => {
  const [expanded, setExpanded] = useState(depth < 2);
  const isDir = !!node.children;
  const isSelected = selectedKey === node.key;

  return (
    <div>
      <div
        className={classNames(
          'flex items-center gap-1.5 py-1 px-2 rounded cursor-pointer text-xs transition-colors select-none',
          isSelected
            ? 'bg-indigo-50 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300 font-medium'
            : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800',
        )}
        style={{ paddingLeft: `${depth * 14 + 8}px` }}
        onClick={() => {
          if (isDir) {
            setExpanded(prev => !prev);
          } else {
            onSelect(node.key);
          }
        }}
      >
        {isDir ? (
          expanded ? (
            <DownOutlined className='text-[9px] text-gray-400' />
          ) : (
            <RightOutlined className='text-[9px] text-gray-400' />
          )
        ) : (
          <span className='w-[9px]' />
        )}
        {isDir ? (
          <FolderOpenOutlined className='text-amber-500 text-xs' />
        ) : node.title.endsWith('.md') ? (
          <FileTextOutlined className='text-blue-500 text-xs' />
        ) : node.title.endsWith('.py') ? (
          <CodeOutlined className='text-green-500 text-xs' />
        ) : (
          <FileOutlined className='text-gray-400 text-xs' />
        )}
        <span className='truncate'>{node.title}</span>
      </div>
      {isDir &&
        expanded &&
        node.children?.map(child => (
          <FileTreeItem key={child.key} node={child} depth={depth + 1} selectedKey={selectedKey} onSelect={onSelect} />
        ))}
    </div>
  );
};

/** Skill card renderer — shows skill detail with file tree and markdown content */
const SkillCardRenderer: React.FC<{
  skillName: string;
  outputs: ExecutionOutput[];
}> = memo(({ skillName, outputs: _outputs }) => {
  const { t } = useTranslation();
  const [detailData, setDetailData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<string>('');
  const [showDetail, setShowDetail] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const [isAdded, setIsAdded] = useState(false);
  // Fetch skill detail on mount
  useEffect(() => {
    const fetchDetail = async () => {
      try {
        setLoading(true);
        const base = process.env.API_BASE_URL || '';
        const res = await fetch(
          `${base}/api/v1/skills/detail?skill_name=${encodeURIComponent(skillName)}&file_path=${encodeURIComponent(skillName)}`,
        );
        const json = await res.json();
        if (json.success && json.data) {
          setDetailData(json.data);
          setFileContent(json.data.raw_content || json.data.instructions || '');
        } else {
          setError(json.err_msg || 'Failed to load skill detail');
        }
      } catch (_e) {
        setError('Network error');
      } finally {
        setLoading(false);
      }
    };
    fetchDetail();
  }, [skillName]);

  // Fetch individual file content when selected
  const handleFileSelect = useCallback(
    async (fileKey: string) => {
      setSelectedFile(fileKey);
      if (fileKey === 'SKILL.md' || fileKey === '.') {
        setFileContent(detailData?.raw_content || '');
        return;
      }
      try {
        const base = process.env.API_BASE_URL || '';
        const filePath = `${skillName}/${fileKey}`;
        const res = await fetch(
          `${base}/api/v1/skills/detail?skill_name=${encodeURIComponent(skillName)}&file_path=${encodeURIComponent(filePath)}`,
        );
        const json = await res.json();
        if (json.success && json.data) {
          setFileContent(json.data.raw_content || json.data.instructions || '(Empty file)');
        }
      } catch {
        setFileContent('(Failed to load file)');
      }
    },
    [skillName, detailData],
  );

  const handleDownload = useCallback(async () => {
    try {
      setDownloading(true);
      const base = process.env.API_BASE_URL || '';
      const res = await fetch(`${base}/api/v1/agent/skills/download?skill_name=${encodeURIComponent(skillName)}`);
      if (!res.ok) throw new Error('Download failed');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${skillName}.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      message.success('下载成功');
    } catch {
      message.error('下载失败');
    } finally {
      setDownloading(false);
    }
  }, [skillName]);

  const handleAddToSkills = useCallback(() => {
    if (!isAdded) {
      setIsAdded(true);
      message.success(t('skill_added_success', { skillName }));
    }
  }, [skillName, isAdded]);

  const displayName = detailData?.metadata?.name || detailData?.skill_name || skillName;
  const description = detailData?.metadata?.description || '';

  if (loading) {
    return (
      <div className='flex flex-col items-center justify-center py-16 text-gray-400'>
        <LoadingOutlined className='text-3xl text-indigo-500 mb-4' />
        <span className='text-sm'>{t('load_skill')}...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className='flex flex-col items-center justify-center py-16 text-gray-400'>
        <AppstoreOutlined className='text-3xl mb-4' />
        <span className='text-sm'>{error}</span>
      </div>
    );
  }

  // Compact card view
  if (!showDetail) {
    return (
      <div className='rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden bg-white dark:bg-[#1a1b1e]'>
        <div className='px-5 py-4'>
          <div className='flex items-center justify-between'>
            <div className='flex items-center gap-3 min-w-0 flex-1'>
              <div className='flex-shrink-0 w-10 h-10 rounded-lg bg-indigo-50 dark:bg-indigo-900/30 flex items-center justify-center'>
                <AppstoreOutlined className='text-lg text-indigo-500' />
              </div>
              <div className='min-w-0 flex-1'>
                <div className='flex items-center gap-2'>
                  <span className='text-sm font-semibold text-gray-800 dark:text-gray-200 truncate'>{displayName}</span>
                  <span className='flex-shrink-0 text-[10px] px-1.5 py-0.5 rounded bg-indigo-100 dark:bg-indigo-900/40 text-indigo-600 dark:text-indigo-400 font-medium'>
                    {t('skill_label')}
                  </span>
                </div>
                {description && (
                  <p className='text-xs text-gray-500 dark:text-gray-400 mt-0.5 truncate'>{description}</p>
                )}
              </div>
            </div>
            <div className='flex items-center gap-2 flex-shrink-0 ml-3'>
              <Tooltip title='下载为 ZIP'>
                <button
                  className='flex items-center justify-center w-8 h-8 rounded-lg border border-gray-200 dark:border-gray-600 text-gray-500 hover:text-indigo-600 hover:border-indigo-300 dark:hover:border-indigo-500 transition-colors'
                  onClick={handleDownload}
                  disabled={downloading}
                >
                  {downloading ? <LoadingOutlined className='text-sm' /> : <DownloadOutlined className='text-sm' />}
                </button>
              </Tooltip>
              <Button
                type='primary'
                size='small'
                className={`!rounded-lg !text-xs !font-medium !px-3 ${
                  isAdded
                    ? '!bg-green-50 !text-green-600 !border-green-200 dark:!bg-green-900/20 dark:!text-green-500 dark:!border-green-800'
                    : '!bg-gray-900 !border-gray-900 dark:!bg-gray-100 dark:!border-gray-100 dark:!text-gray-900 !text-white'
                }`}
                icon={isAdded ? <CheckOutlined className='text-[10px]' /> : <PlusOutlined className='text-[10px]' />}
                onClick={handleAddToSkills}
              >
                {isAdded ? t('added') : t('add_to_my_skills')}
              </Button>
            </div>
          </div>
        </div>
        {/* Clickable area to expand file tree detail */}
        <div
          className='border-t border-gray-100 dark:border-gray-800 px-5 py-3 cursor-pointer hover:bg-gray-50 dark:hover:bg-[#1f2025] transition-colors flex items-center justify-between'
          onClick={() => setShowDetail(true)}
        >
          <div className='flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400'>
            <FolderOpenOutlined className='text-amber-500' />
            <span>{t('view_skill_files')}</span>
            {detailData?.tree?.children && (
              <span className='text-gray-400'>({detailData.tree.children.length} 项)</span>
            )}
          </div>
          <RightOutlined className='text-[10px] text-gray-400' />
        </div>
      </div>
    );
  }

  // Expanded detail view with file tree + content
  return (
    <div className='rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden bg-white dark:bg-[#1a1b1e] flex-1 flex flex-col min-h-0'>
      {/* Header */}
      <div className='flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700 shrink-0'>
        <div className='flex items-center gap-3 min-w-0 flex-1'>
          <button
            className='flex items-center justify-center w-7 h-7 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors'
            onClick={() => setShowDetail(false)}
          >
            <LeftOutlined className='text-xs' />
          </button>
          <div className='flex-shrink-0 w-8 h-8 rounded-lg bg-indigo-50 dark:bg-indigo-900/30 flex items-center justify-center'>
            <AppstoreOutlined className='text-base text-indigo-500' />
          </div>
          <div className='min-w-0'>
            <div className='flex items-center gap-2'>
              <span className='text-sm font-semibold text-gray-800 dark:text-gray-200 truncate'>{displayName}</span>
              <span className='text-[10px] px-1.5 py-0.5 rounded bg-indigo-100 dark:bg-indigo-900/40 text-indigo-600 dark:text-indigo-400 font-medium'>
                {t('skill_label')}
              </span>
            </div>
          </div>
        </div>
        <div className='flex items-center gap-2 flex-shrink-0'>
          <Tooltip title='下载为 ZIP'>
            <button
              className='flex items-center justify-center w-8 h-8 rounded-lg border border-gray-200 dark:border-gray-600 text-gray-500 hover:text-indigo-600 hover:border-indigo-300 transition-colors'
              onClick={handleDownload}
              disabled={downloading}
            >
              {downloading ? <LoadingOutlined className='text-sm' /> : <DownloadOutlined className='text-sm' />}
            </button>
          </Tooltip>
          <Button
            type='primary'
            size='small'
            className={`!rounded-lg !text-xs !font-medium !px-3 ${
              isAdded
                ? '!bg-green-50 !text-green-600 !border-green-200 dark:!bg-green-900/20 dark:!text-green-500 dark:!border-green-800'
                : '!bg-gray-900 !border-gray-900 dark:!bg-gray-100 dark:!border-gray-100 dark:!text-gray-900 !text-white'
            }`}
            icon={isAdded ? <CheckOutlined className='text-[10px]' /> : <PlusOutlined className='text-[10px]' />}
            onClick={handleAddToSkills}
          >
            {isAdded ? t('added') : t('add_to_my_skills')}
          </Button>
        </div>
      </div>
      {/* Body: file tree + content */}
      <div className='flex flex-1 min-h-0 overflow-hidden'>
        {/* File tree sidebar */}
        <div className='w-[200px] flex-shrink-0 border-r border-gray-200 dark:border-gray-700 overflow-y-auto py-2 bg-gray-50 dark:bg-[#111217]'>
          {detailData?.tree && (
            <FileTreeItem node={detailData.tree} depth={0} selectedKey={selectedFile} onSelect={handleFileSelect} />
          )}
        </div>
        {/* Content area */}
        <div className='flex-1 min-w-0 overflow-auto p-4'>
          {fileContent ? (
            <div className='prose prose-sm dark:prose-invert max-w-none'>
              {fileContent.startsWith('---')
                ? (() => {
                    const parts = fileContent.split('---');
                    if (parts.length >= 3) {
                      return (
                        <>
                          <pre className='text-xs bg-gray-50 dark:bg-[#161719] rounded-lg px-4 py-3 text-gray-600 dark:text-gray-300 font-mono leading-relaxed mb-4 border border-gray-200 dark:border-gray-700'>
                            {parts[1].trim()}
                          </pre>
                          <MarkDownContext>{preprocessLaTeX(parts.slice(2).join('---').trim())}</MarkDownContext>
                        </>
                      );
                    }
                    return <MarkDownContext>{preprocessLaTeX(fileContent)}</MarkDownContext>;
                  })()
                : (() => {
                    const ext = selectedFile?.split('.').pop()?.toLowerCase();
                    const langMap: Record<string, string> = {
                      py: 'python',
                      sh: 'bash',
                      bash: 'bash',
                      zsh: 'bash',
                      js: 'javascript',
                      ts: 'typescript',
                      jsx: 'javascript',
                      tsx: 'typescript',
                      json: 'json',
                      yaml: 'yaml',
                      yml: 'yaml',
                      toml: 'toml',
                      sql: 'sql',
                      md: 'markdown',
                      html: 'html',
                      css: 'css',
                      xml: 'xml',
                      java: 'java',
                      go: 'go',
                      rs: 'rust',
                      rb: 'ruby',
                      c: 'c',
                      cpp: 'cpp',
                      h: 'c',
                      hpp: 'cpp',
                    };
                    const lang = ext ? langMap[ext] : undefined;
                    if (lang) {
                      return <CodePreview code={fileContent} language={lang} />;
                    }
                    return <MarkDownContext>{preprocessLaTeX(fileContent)}</MarkDownContext>;
                  })()}
            </div>
          ) : (
            <div className='flex flex-col items-center justify-center py-12 text-gray-400'>
              <FileTextOutlined className='text-2xl mb-2' />
              <span className='text-xs'>选择文件查看内容</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
});

SkillCardRenderer.displayName = 'SkillCardRenderer';

const getSafeReferenceUrl = (url?: string): string | null => {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:' ? parsed.toString() : null;
  } catch {
    return null;
  }
};

const formatReferenceScore = (score?: number | null): string | null => {
  if (typeof score !== 'number' || !Number.isFinite(score)) return null;
  if (score >= 0 && score <= 1) return `${(score * 100).toFixed(1)}%`;
  return score.toFixed(2);
};

const ReferencesPanel: React.FC<{
  citations: AgentCitation[];
  selectedCitationIndex?: number | null;
  onCitationSelect?: (index: number) => void;
}> = ({ citations, selectedCitationIndex, onCitationSelect }) => {
  const itemRefs = useRef<Map<number, HTMLDivElement>>(new Map());

  useEffect(() => {
    if (selectedCitationIndex == null) return;
    itemRefs.current.get(selectedCitationIndex)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [selectedCitationIndex]);

  return (
    <div className='space-y-3' data-testid='references-panel'>
      <div className='rounded-lg border border-blue-100 bg-blue-50/60 px-3 py-2 text-xs leading-5 text-blue-700 dark:border-blue-500/20 dark:bg-blue-500/10 dark:text-blue-300'>
        以下内容是回答过程中检索或读取的知识来源，不包含脚本执行回显、SQL 执行结果或其他工具输出。
      </div>
      {citations.map(citation => {
        const isSelected = citation.index === selectedCitationIndex;
        const score = formatReferenceScore(citation.score);
        const safeUrl = getSafeReferenceUrl(citation.url);
        return (
          <div
            key={`${citation.id}-${citation.index}`}
            ref={node => {
              if (node) itemRefs.current.set(citation.index, node);
              else itemRefs.current.delete(citation.index);
            }}
            role='button'
            tabIndex={0}
            onClick={() => onCitationSelect?.(citation.index)}
            onKeyDown={event => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                onCitationSelect?.(citation.index);
              }
            }}
            className={classNames(
              'w-full rounded-xl border bg-white p-4 text-left transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40 dark:bg-[#1a1b1e]',
              isSelected
                ? 'border-blue-400 ring-1 ring-blue-200 dark:border-blue-500 dark:ring-blue-500/20'
                : 'border-gray-200 hover:border-blue-300 dark:border-gray-800 dark:hover:border-blue-600',
            )}
            data-reference-index={citation.index}
          >
            <div className='flex items-start gap-3'>
              <span className='inline-flex h-6 min-w-6 flex-shrink-0 items-center justify-center rounded-md bg-blue-500 px-1.5 text-xs font-semibold text-white'>
                {citation.index}
              </span>
              <div className='min-w-0 flex-1'>
                <div className='flex flex-wrap items-center justify-between gap-2'>
                  <span className='min-w-0 break-words text-sm font-semibold text-gray-900 dark:text-gray-100'>
                    {citation.sourceName || citation.path || `来源 ${citation.index}`}
                  </span>
                  {score && (
                    <span className='flex-shrink-0 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300'>
                      相关度 {score}
                    </span>
                  )}
                </div>
                {citation.path && (
                  <div className='mt-1 break-all font-mono text-[11px] text-gray-400 dark:text-gray-500'>
                    {citation.path}
                  </div>
                )}
                {citation.excerpt && (
                  <div className='mt-3 whitespace-pre-wrap break-words text-xs leading-5 text-gray-600 dark:text-gray-300'>
                    {citation.excerpt}
                  </div>
                )}
                {safeUrl && (
                  <a
                    href={safeUrl}
                    target='_blank'
                    rel='noreferrer noopener'
                    onClick={event => event.stopPropagation()}
                    className='mt-3 inline-flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300'
                  >
                    <LinkOutlined aria-hidden />
                    打开来源
                  </a>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};

// Main Component
const ManusRightPanel: React.FC<ManusRightPanelProps> = ({
  activeStep,
  outputs,
  isRunning,
  onRerun,
  onShare,
  onSchedule,
  terminalTitle,
  artifacts,
  inputFiles,
  onArtifactClick,
  panelView: controlledPanelView,
  onPanelViewChange,
  previewArtifact,
  databaseType,
  databaseName,
  skillName,
  summaryContent,
  isSummaryStreaming,
  citations = [],
  selectedCitationIndex,
  onCitationSelect,
  subAgents,
  onSubAgentClick,
  subAgentContext,
  onExitSubAgentView,
  conversationId,
}) => {
  const { t } = useTranslation();
  const [inputCollapsed, setInputCollapsed] = useState(false);
  const [internalPanelView, setInternalPanelView] = useState<PanelView>('execution');
  const [fileFilter, setFileFilter] = useState<TaskFileTab>('all');
  const htmlPreviewRef = useRef<HTMLIFrameElement>(null);
  const panelView = controlledPanelView ?? internalPanelView;
  const setPanelView = (view: PanelView) => {
    setInternalPanelView(view);
    onPanelViewChange?.(view);
  };

  const handleExportPdf = () => {
    try {
      const iframe = htmlPreviewRef.current;
      if (iframe?.contentWindow) {
        iframe.contentWindow.focus();
        iframe.contentWindow.print();
        return;
      }
    } catch {
      /* fallback below */
    }
    if (previewArtifact) {
      const htmlStr =
        typeof previewArtifact.content === 'string'
          ? previewArtifact.content
          : previewArtifact.content?.html || previewArtifact.content?.content || String(previewArtifact.content);
      const win = window.open('', '_blank');
      if (win) {
        win.document.write(resolveHtmlImageUrls(htmlStr));
        win.document.close();
        win.focus();
        win.print();
      } else {
        message.error('浏览器阻止了弹出窗口，请允许后重试');
      }
    }
  };

  useEffect(() => {
    if (controlledPanelView !== undefined) {
      setInternalPanelView(controlledPanelView);
    }
  }, [controlledPanelView]);
  useEffect(() => {
    if (panelView === 'references' && citations.length === 0) {
      setInternalPanelView('execution');
      onPanelViewChange?.('execution');
    }
  }, [citations.length, onPanelViewChange, panelView]);
  const visibleOutputs = useMemo(() => outputs.filter(o => o.output_type !== 'thought'), [outputs]);

  const {
    counts: taskFileCounts,
    filteredArtifacts,
    visibleInputFiles,
  } = useMemo(() => buildTaskFileView(inputFiles, artifacts, fileFilter), [artifacts, fileFilter, inputFiles]);

  const handleTaskFileTabKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLButtonElement>) => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const nextTab = getNextTaskFileTab(fileFilter, event.key as TaskFileTabNavigationKey);
      setFileFilter(nextTab);
      window.requestAnimationFrame(() => document.getElementById(`task-file-tab-${nextTab}`)?.focus());
    },
    [fileFilter],
  );

  const dateGroupedArtifacts = useMemo(() => {
    const groups: { label: string; items: ArtifactItem[] }[] = [];
    const groupMap = new Map<string, ArtifactItem[]>();
    for (const a of filteredArtifacts) {
      const label = formatArtifactDate(a.createdAt);
      if (!groupMap.has(label)) groupMap.set(label, []);
      groupMap.get(label)!.push(a);
    }
    groupMap.forEach((items, label) => groups.push({ label, items }));
    return groups;
  }, [filteredArtifacts]);

  // Keep grouping inside one semantic step. Sub-agent details call the same
  // helper per timeline item so adjacent steps never get merged together.
  const outputGroups = useMemo(() => groupExecutionOutputs(visibleOutputs), [visibleOutputs]);
  const subAgentDisplayName = subAgentContext ? getSubAgentDisplayName(subAgentContext) : '';
  const subAgentDuration = formatSubAgentDuration(subAgentContext?.elapsedMs);
  const isSubAgentExecution = panelView === 'execution' && Boolean(subAgentContext);
  const totalFileCount = taskFileCounts.all;

  return (
    <div className='relative flex h-full min-h-0 flex-col overflow-hidden bg-[#f8f9fc] dark:bg-[#0d0e11]'>
      {/* Collapse button is rendered by the parent layout to avoid overflow clipping */}

      {/* Terminal Header */}
      <div className='flex flex-shrink-0 items-center justify-between border-b border-gray-200 bg-white px-5 py-3 dark:border-gray-800 dark:bg-[#111217]'>
        <div className='flex items-center gap-3'>
          <div className='flex items-center gap-2'>
            <div className='w-3 h-3 rounded-full bg-red-500' />
            <div className='w-3 h-3 rounded-full bg-yellow-500' />
            <div className='w-3 h-3 rounded-full bg-green-500' />
          </div>
          <div className='flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300 font-medium'>
            <DesktopOutlined className='text-gray-500' />
            <span>{terminalTitle || t('db_gpt_computer')}</span>
            {isRunning && <LoadingOutlined spin className='text-blue-500 ml-1' />}
          </div>
        </div>

        <div className='flex items-center gap-1'>
          {panelView === 'html-preview' && previewArtifact && (
            <Tooltip title={t('export_pdf')}>
              <Button
                type='text'
                size='small'
                icon={<ExportOutlined />}
                onClick={handleExportPdf}
                className='text-gray-500 hover:text-blue-500'
              >
                {t('export_pdf')}
              </Button>
            </Tooltip>
          )}

          {onSchedule && (
            <Tooltip title={t('scheduled.save.title')}>
              <Button
                type='text'
                size='small'
                icon={<ClockCircleOutlined />}
                onClick={onSchedule}
                className='text-gray-500 hover:text-blue-500'
              >
                {t('scheduled.save.title')}
              </Button>
            </Tooltip>
          )}

          {activeStep && onRerun && activeStep.status === 'completed' && (
            <Tooltip title={t('rerun')}>
              <Button
                type='text'
                size='small'
                icon={<SyncOutlined />}
                onClick={onRerun}
                className='text-gray-500 hover:text-blue-500'
              >
                {t('rerun')}
              </Button>
            </Tooltip>
          )}

          {onShare && (
            <Tooltip title={t('share_conversation_tooltip')}>
              <Button
                type='text'
                size='small'
                icon={<LinkOutlined />}
                onClick={onShare}
                className='text-blue-500 hover:text-blue-600'
              >
                {t('share_conversation')}
              </Button>
            </Tooltip>
          )}
        </div>
      </div>

      {/* Sub-agent breadcrumb — only when the right panel is showing a
          sub-agent's process view. Gives an explicit way back to the main
          agent timeline without clicking a left-side main step. */}
      {subAgentContext && onExitSubAgentView && (
        <div
          className='flex-shrink-0 border-b border-slate-200 bg-white px-5 py-3.5 dark:border-white/10 dark:bg-[#111217]'
          data-testid='subagent-detail-header'
        >
          <div className='flex items-start justify-between gap-4'>
            <div className='flex min-w-0 items-center gap-2'>
              <button
                type='button'
                onClick={onExitSubAgentView}
                className='flex min-h-[32px] flex-shrink-0 items-center gap-1 rounded-md px-1.5 text-xs font-medium text-blue-600 transition-colors hover:bg-blue-50 hover:text-blue-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40 dark:text-blue-400 dark:hover:bg-blue-500/10 dark:hover:text-blue-300'
              >
                <LeftOutlined aria-hidden className='text-[10px]' />
                {t('subagent_return_main')}
              </button>
              <span className='text-slate-300 dark:text-slate-700'>/</span>
              {subAgentDisplayName !== subAgentContext.name && (
                <span className='truncate rounded-md bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-500 dark:bg-white/[0.06] dark:text-slate-400'>
                  {subAgentContext.name}
                </span>
              )}
            </div>
            <SubAgentStatusBadge status={subAgentContext.status} showLabel />
          </div>
          <h2 className='mt-2 line-clamp-2 text-base font-semibold leading-6 text-slate-900 dark:text-slate-100'>
            {subAgentDisplayName}
          </h2>
          {subAgentContext.goal && subAgentDisplayName !== subAgentContext.goal && (
            <p className='mt-1 line-clamp-2 text-xs leading-5 text-slate-500 dark:text-slate-400'>
              {subAgentContext.goal}
            </p>
          )}
          <div className='mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-slate-400 dark:text-slate-500'>
            <span className='inline-flex items-center gap-1.5'>
              <UnorderedListOutlined aria-hidden />
              {t('subagent_verified_steps', { count: subAgentContext.steps.length })}
            </span>
            {subAgentDuration && (
              <span className='inline-flex items-center gap-1.5'>
                <ClockCircleOutlined aria-hidden />
                {t('parallel_tasks_elapsed', { time: subAgentDuration })}
              </span>
            )}
            {subAgentContext.artifactCount > 0 && (
              <span className='inline-flex items-center gap-1.5'>
                <FileImageOutlined aria-hidden />
                {t('parallel_tasks_artifacts', { count: subAgentContext.artifactCount })}
              </span>
            )}
          </div>
          {subAgentContext.status === 'running' && subAgentContext.currentAction && (
            <div className='mt-2.5 inline-flex max-w-full items-center gap-2 rounded-lg bg-blue-50 px-2.5 py-1.5 text-xs text-blue-700 dark:bg-blue-500/10 dark:text-blue-300'>
              <LoadingOutlined aria-hidden spin className='flex-shrink-0' />
              <span className='truncate'>{subAgentContext.currentAction}</span>
            </div>
          )}
        </div>
      )}

      {/* View Toggle Tabs */}
      {(totalFileCount > 0 ||
        previewArtifact ||
        skillName ||
        !!summaryContent ||
        !!conversationId ||
        citations.length > 0) && (
        <div className='flex flex-shrink-0 items-center gap-0 overflow-x-auto border-b border-gray-200 bg-white px-5 dark:border-gray-800 dark:bg-[#111217]'>
          <button
            onClick={() => setPanelView('execution')}
            className={classNames(
              'px-4 py-2.5 text-xs font-medium transition-colors relative',
              panelView === 'execution'
                ? 'text-gray-900 dark:text-gray-100'
                : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300',
            )}
          >
            <DesktopOutlined className='mr-1.5' />
            {t('execution_steps')}
            {panelView === 'execution' && (
              <div className='absolute bottom-0 left-0 right-0 h-[2px] bg-gray-900 dark:bg-gray-100 rounded-full' />
            )}
          </button>
          {conversationId && (
            <button
              onClick={() => setPanelView('trace')}
              className={classNames(
                'px-4 py-2.5 text-xs font-medium transition-colors relative',
                panelView === 'trace'
                  ? 'text-gray-900 dark:text-gray-100'
                  : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300',
              )}
            >
              <ProfileOutlined className='mr-1.5' />
              {t('observability_trace_tab') || 'Trace'}
              {panelView === 'trace' && (
                <div className='absolute bottom-0 left-0 right-0 h-[2px] bg-gray-900 dark:bg-gray-100 rounded-full' />
              )}
            </button>
          )}
          {totalFileCount > 0 && (
            <button
              onClick={() => setPanelView('files')}
              className={classNames(
                'px-4 py-2.5 text-xs font-medium transition-colors relative',
                panelView === 'files'
                  ? 'text-gray-900 dark:text-gray-100'
                  : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300',
              )}
            >
              <FolderOpenOutlined className='mr-1.5' />
              {t('task_files')}
              <span className='ml-1.5 text-[10px] bg-gray-100 dark:bg-gray-800 text-gray-500 px-1.5 py-0.5 rounded-full'>
                {totalFileCount}
              </span>
              {panelView === 'files' && (
                <div className='absolute bottom-0 left-0 right-0 h-[2px] bg-gray-900 dark:bg-gray-100 rounded-full' />
              )}
            </button>
          )}
          {skillName && (
            <button
              onClick={() => setPanelView('skill-preview')}
              className={classNames(
                'px-4 py-2.5 text-xs font-medium transition-colors relative',
                panelView === 'skill-preview'
                  ? 'text-gray-900 dark:text-gray-100'
                  : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300',
              )}
            >
              <AppstoreOutlined className='mr-1.5' />
              {skillName}
              {panelView === 'skill-preview' && (
                <div className='absolute bottom-0 left-0 right-0 h-[2px] bg-gray-900 dark:bg-gray-100 rounded-full' />
              )}
            </button>
          )}
          {!!summaryContent && (
            <button
              onClick={() => setPanelView('summary')}
              className={classNames(
                'px-4 py-2.5 text-xs font-medium transition-colors relative',
                panelView === 'summary'
                  ? 'text-gray-900 dark:text-gray-100'
                  : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300',
              )}
            >
              <FileTextOutlined className='mr-1.5' />
              {t('content_summary')}
              {panelView === 'summary' && (
                <div className='absolute bottom-0 left-0 right-0 h-[2px] bg-gray-900 dark:bg-gray-100 rounded-full' />
              )}
            </button>
          )}
          {citations.length > 0 && (
            <button
              onClick={() => setPanelView('references')}
              className={classNames(
                'px-4 py-2.5 text-xs font-medium transition-colors relative whitespace-nowrap',
                panelView === 'references'
                  ? 'text-gray-900 dark:text-gray-100'
                  : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300',
              )}
            >
              <BookOutlined className='mr-1.5' />
              参考来源
              <span className='ml-1.5 rounded-full bg-blue-50 px-1.5 py-0.5 text-[10px] text-blue-600 dark:bg-blue-500/10 dark:text-blue-300'>
                {citations.length}
              </span>
              {panelView === 'references' && (
                <div className='absolute bottom-0 left-0 right-0 h-[2px] rounded-full bg-gray-900 dark:bg-gray-100' />
              )}
            </button>
          )}
          {previewArtifact && (
            <button
              onClick={() => setPanelView(previewArtifact.type === 'image' ? 'image-preview' : 'html-preview')}
              className={classNames(
                'px-4 py-2.5 text-xs font-medium transition-colors relative',
                panelView === 'html-preview' || panelView === 'image-preview'
                  ? 'text-gray-900 dark:text-gray-100'
                  : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300',
              )}
            >
              <EyeOutlined className='mr-1.5' />
              {previewArtifact.name || t('web_preview')}
              {(panelView === 'html-preview' || panelView === 'image-preview') && (
                <div className='absolute bottom-0 left-0 right-0 h-[2px] bg-gray-900 dark:bg-gray-100 rounded-full' />
              )}
            </button>
          )}
        </div>
      )}

      {/* Content Area */}
      <div
        className={classNames(
          'flex min-h-0 flex-1 flex-col',
          isSubAgentExecution ? 'overflow-hidden' : 'overflow-y-auto',
          isSubAgentExecution ||
            panelView === 'html-preview' ||
            panelView === 'image-preview' ||
            panelView === 'skill-preview' ||
            panelView === 'trace'
            ? 'p-0'
            : 'p-5 space-y-4',
        )}
        data-testid='right-panel-content'
      >
        {panelView === 'trace' && conversationId ? (
          <ConversationTracePanel conversationId={conversationId} />
        ) : panelView === 'references' && citations.length > 0 ? (
          <ReferencesPanel
            citations={citations}
            selectedCitationIndex={selectedCitationIndex}
            onCitationSelect={onCitationSelect}
          />
        ) : panelView === 'skill-preview' && skillName ? (
          <div className='w-full h-full flex flex-col p-5 overflow-auto'>
            <SkillCardRenderer skillName={skillName} outputs={visibleOutputs} />
          </div>
        ) : panelView === 'html-preview' && previewArtifact ? (
          <div className='w-full h-full flex flex-col'>
            {(() => {
              const srcDoc = resolveHtmlImageUrls(
                typeof previewArtifact.content === 'string'
                  ? previewArtifact.content
                  : previewArtifact.content?.html ||
                      previewArtifact.content?.content ||
                      String(previewArtifact.content),
              );
              console.log(
                '[HTML Preview] artifact id:',
                previewArtifact.id,
                'srcDoc length:',
                srcDoc?.length,
                'first 300 chars:',
                srcDoc?.substring(0, 300),
              );
              return (
                <iframe
                  key={previewArtifact.id || 'html-preview'}
                  ref={htmlPreviewRef}
                  srcDoc={srcDoc}
                  sandbox='allow-scripts allow-same-origin allow-modals'
                  className='w-full flex-1 bg-white'
                  style={{ border: 'none', minHeight: 600 }}
                />
              );
            })()}
          </div>
        ) : panelView === 'image-preview' && previewArtifact ? (
          <div className='w-full h-full flex items-center justify-center bg-gray-50 dark:bg-gray-900 p-6'>
            <img
              src={(() => {
                const content = previewArtifact.content;
                if (typeof content === 'string') {
                  return resolveImageUrl(content);
                }
                const obj = content as Record<string, any>;
                if (obj?.file_path) {
                  const base = process.env.API_BASE_URL || '';
                  return `${base}/api/v1/agent/files/download?file_path=${encodeURIComponent(obj.file_path)}`;
                }
                return resolveImageUrl(obj?.url || obj?.src || String(content));
              })()}
              alt={previewArtifact.name || 'Image preview'}
              className='max-w-full max-h-full object-contain rounded-lg shadow-md'
              style={{ maxHeight: 'calc(100vh - 200px)' }}
            />
          </div>
        ) : panelView === 'summary' && summaryContent ? (
          <div className='prose prose-sm dark:prose-invert max-w-none text-gray-800 dark:text-gray-200 leading-relaxed'>
            {isSummaryStreaming ? (
              <span className='whitespace-pre-wrap break-words'>{summaryContent}</span>
            ) : (
              <MarkDownContext>{fixSquishedTables(summaryContent)}</MarkDownContext>
            )}
            {isSummaryStreaming && (
              <span className='inline-block w-1.5 h-4 bg-blue-500 animate-pulse ml-0.5 align-text-bottom' />
            )}
          </div>
        ) : panelView === 'files' ? (
          <div className='space-y-5'>
            <div
              role='tablist'
              aria-label='任务文件分类'
              className='flex w-fit max-w-full items-center gap-1 overflow-x-auto rounded-lg bg-gray-100/80 p-1 dark:bg-gray-800/60'
            >
              {TASK_FILE_TABS.map(tab => {
                const count = taskFileCounts[tab.key];
                return (
                  <button
                    type='button'
                    role='tab'
                    key={tab.key}
                    id={`task-file-tab-${tab.key}`}
                    onClick={() => setFileFilter(tab.key)}
                    onKeyDown={handleTaskFileTabKeyDown}
                    aria-controls='task-files-tabpanel'
                    aria-selected={fileFilter === tab.key}
                    tabIndex={fileFilter === tab.key ? 0 : -1}
                    className={classNames(
                      'flex-none whitespace-nowrap rounded-md px-3 py-1.5 text-xs font-medium transition-all duration-200 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40',
                      fileFilter === tab.key
                        ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm'
                        : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300',
                    )}
                  >
                    {tab.label}
                    {count > 0 && <span className='ml-1 text-[10px] tabular-nums text-gray-400'>{count}</span>}
                  </button>
                );
              })}
            </div>

            <div
              id='task-files-tabpanel'
              role='tabpanel'
              aria-labelledby={`task-file-tab-${fileFilter}`}
              className='space-y-5'
            >
              {visibleInputFiles.length > 0 && (
                <section className='space-y-3'>
                  {fileFilter === 'all' && (
                    <div className='px-1'>
                      <div className='text-[11px] font-semibold uppercase tracking-wider text-emerald-600/80 dark:text-emerald-400/80'>
                        上传资料 · {visibleInputFiles.length}
                      </div>
                      <div className='mt-0.5 text-[11px] text-slate-400 dark:text-slate-500'>
                        用户本轮带入的分析上下文
                      </div>
                    </div>
                  )}
                  <div className='space-y-2'>
                    {visibleInputFiles.map(file => (
                      <InputFileListItem key={file.file_id} file={file} />
                    ))}
                  </div>
                </section>
              )}

              {filteredArtifacts.length > 0 && (
                <section className='space-y-3'>
                  {fileFilter === 'all' && (
                    <div className='px-1'>
                      <div className='text-[11px] font-semibold uppercase tracking-wider text-indigo-600/80 dark:text-indigo-400/80'>
                        推理生成 · {filteredArtifacts.length}
                      </div>
                      <div className='mt-0.5 text-[11px] text-slate-400 dark:text-slate-500'>
                        Agent 在本轮推理过程中生成的文件
                      </div>
                    </div>
                  )}
                  <div className='space-y-3'>
                    {dateGroupedArtifacts.map(group => (
                      <div key={group.label} className='space-y-2'>
                        <div className='px-1 text-[10px] font-medium uppercase tracking-wider text-slate-400 dark:text-slate-500'>
                          {group.label}
                        </div>
                        <div className='space-y-2'>
                          {group.items.map(artifact => (
                            <FileListItem
                              key={artifact.id}
                              artifact={artifact}
                              onClick={() => onArtifactClick?.(artifact)}
                            />
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {visibleInputFiles.length === 0 && filteredArtifacts.length === 0 && (
                <div className='flex flex-col items-center justify-center py-16 text-gray-400'>
                  <FolderOpenOutlined className='text-3xl mb-4' />
                  <span className='text-sm'>{getTaskFileEmptyLabel(fileFilter)}</span>
                </div>
              )}
            </div>
          </div>
        ) : isSubAgentExecution && subAgentContext ? (
          <SubAgentProcessView
            key={subAgentContext.agentId}
            agent={subAgentContext}
            onArtifactClick={onArtifactClick}
          />
        ) : activeStep?.action === 'dispatch_parallel_tasks' ? (
          <ParallelTasksPanel
            status={activeStep.status}
            subAgents={subAgents}
            outputs={visibleOutputs}
            onSubAgentClick={onSubAgentClick}
          />
        ) : activeStep?.type === 'bash' ? (
          <TerminalRenderer activeStep={activeStep} outputs={visibleOutputs} />
        ) : activeStep ? (
          <div className='rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-[#1a1b1e] overflow-hidden flex-1 flex flex-col min-h-0'>
            {activeStep.type === 'python' || activeStep.type === 'html' ? (
              <div className='flex items-center justify-between px-4 py-3'>
                <div className='flex items-center gap-3 min-w-0 flex-1'>
                  <div
                    className={classNames(
                      'w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0',
                      activeStep.type === 'html'
                        ? 'bg-orange-50 dark:bg-orange-900/30'
                        : 'bg-blue-50 dark:bg-blue-900/30',
                    )}
                  >
                    {getStepTypeIcon(activeStep.type)}
                  </div>
                  <div className='text-sm font-semibold text-gray-800 dark:text-gray-200 truncate'>
                    {activeStep.title}
                  </div>
                </div>
                <div className='flex items-center gap-2 flex-shrink-0'>
                  <StatusBadge status={activeStep.status} />
                </div>
              </div>
            ) : (
              <>
                <div
                  className='flex items-center justify-between px-4 py-3 cursor-pointer select-none hover:bg-gray-50 dark:hover:bg-[#1f2025] transition-colors'
                  onClick={() => setInputCollapsed(prev => !prev)}
                >
                  <div className='flex items-center gap-3 min-w-0 flex-1'>
                    <div
                      className={classNames('w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0', {
                        'bg-emerald-50 dark:bg-emerald-900/30': activeStep.type === 'read' || activeStep.type === 'sql',
                        'bg-amber-50 dark:bg-amber-900/30':
                          activeStep.type === 'edit' || activeStep.type === 'write' || activeStep.type === 'question',
                        'bg-cyan-50 dark:bg-cyan-900/30': activeStep.type === 'grep' || activeStep.type === 'glob',
                        'bg-indigo-50 dark:bg-indigo-900/30': activeStep.type === 'task' || activeStep.type === 'skill',
                        'bg-teal-50 dark:bg-teal-900/30': activeStep.type === 'kb',
                        'bg-violet-50 dark:bg-violet-900/30': activeStep.type === 'code_graph',
                        'bg-gray-50 dark:bg-gray-800': activeStep.type === 'other',
                      })}
                    >
                      {getStepTypeIcon(activeStep.type)}
                    </div>
                    <div className='text-sm font-semibold text-gray-800 dark:text-gray-200 truncate'>
                      {activeStep.title}
                    </div>
                  </div>
                  <div className='flex items-center gap-2 flex-shrink-0'>
                    <StatusBadge status={activeStep.status} />
                    <span className='text-gray-400 text-xs transition-transform duration-200'>
                      {inputCollapsed ? <DownOutlined /> : <UpOutlined />}
                    </span>
                  </div>
                </div>

                {/* Expanded detail */}
                {!inputCollapsed && activeStep.detail && (
                  <div
                    className={
                      activeStep.detail.includes('Action: execute_skill_script_file')
                        ? 'flex-1 min-h-0 flex flex-col'
                        : 'px-4 pb-3'
                    }
                  >
                    {(activeStep.detail.includes('Action: execute_skill_script_file') &&
                      (() => {
                        const parsed = parseSkillScriptDetail(activeStep.detail);
                        if (parsed) {
                          return <SkillScriptRenderer parsed={parsed} outputs={visibleOutputs} />;
                        }
                        return null;
                      })()) ||
                      (activeStep.detail.includes('Action: get_skill_resource') &&
                        (() => {
                          const parsed = parseSkillResourceDetail(activeStep.detail);
                          if (parsed) {
                            // Extract frontmatter name/description from SKILL.md content
                            let skillDisplayName = parsed.skillName;
                            let skillDescription = '';
                            if (parsed.content) {
                              const fmMatch = parsed.content.match(/^---\n([\s\S]*?)\n---/);
                              if (fmMatch) {
                                const nameMatch = fmMatch[1].match(/^name:\s*(.+)$/m);
                                const descMatch = fmMatch[1].match(/^description:\s*(.+)$/m);
                                if (nameMatch) skillDisplayName = nameMatch[1].trim();
                                if (descMatch) skillDescription = descMatch[1].trim();
                              }
                              // Fallback: use first heading + first paragraph if no frontmatter
                              if (!skillDescription) {
                                const headingMatch = parsed.content.match(/^#\s+(.+)$/m);
                                const paraMatch = parsed.content.match(/^(?!#|---|\s*$)(.+)/m);
                                if (!skillDisplayName && headingMatch) skillDisplayName = headingMatch[1].trim();
                                if (paraMatch) skillDescription = paraMatch[1].trim();
                              }
                            }
                            return (
                              <div className='rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden bg-white dark:bg-[#1a1b1e]'>
                                <div className='px-5 py-4'>
                                  <div className='flex items-center gap-2.5 mb-2'>
                                    <div className='flex-shrink-0 w-9 h-9 rounded-lg bg-indigo-50 dark:bg-indigo-900/30 flex items-center justify-center'>
                                      <PlayCircleOutlined className='text-base text-indigo-500' />
                                    </div>
                                    <div className='min-w-0'>
                                      <div className='text-sm font-semibold text-gray-800 dark:text-gray-200 truncate'>
                                        {skillDisplayName}
                                      </div>
                                      <div className='text-[11px] text-gray-400 dark:text-gray-500'>
                                        {t('skill_label')}
                                      </div>
                                    </div>
                                  </div>
                                  {skillDescription && (
                                    <p className='text-sm text-gray-600 dark:text-gray-400 leading-relaxed mt-2'>
                                      {skillDescription}
                                    </p>
                                  )}
                                </div>
                              </div>
                            );
                          }
                          return null;
                        })()) ||
                      (activeStep.type === 'skill' &&
                        !activeStep.detail.includes('Action: get_skill_resource') &&
                        !activeStep.detail.includes('Action: execute_skill_script_file') &&
                        (() => {
                          const parsed = parseLoadSkillDetail(activeStep.detail, activeStep.title, visibleOutputs);
                          if (parsed) {
                            return (
                              <div className='rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden bg-white dark:bg-[#1a1b1e]'>
                                <div className='px-4 py-3'>
                                  <span className='inline-block text-[11px] font-medium text-gray-400 dark:text-gray-500 bg-gray-100 dark:bg-gray-800 rounded px-1.5 py-0.5 mb-3'>
                                    YAML
                                  </span>
                                  <pre className='text-sm text-gray-800 dark:text-gray-200 whitespace-pre-wrap font-mono leading-relaxed m-0'>{`name: ${parsed.skillName}${parsed.description ? `\ndescription: ${parsed.description}` : ''}`}</pre>
                                </div>
                              </div>
                            );
                          }
                          return null;
                        })()) ||
                      (activeStep.type === 'sql' &&
                        (activeStep.action === 'sql_query' ||
                          (activeStep.detail && activeStep.detail.includes('Action: sql_query'))) &&
                        (() => {
                          let sql = '';
                          if (activeStep.actionInput) {
                            try {
                              const parsed =
                                typeof activeStep.actionInput === 'string'
                                  ? JSON.parse(activeStep.actionInput)
                                  : activeStep.actionInput;
                              sql = parsed?.sql || '';
                            } catch {
                              const rawMatch = String(activeStep.actionInput).match(/"sql"\s*:\s*"([\s\S]*?)"/);
                              if (rawMatch) sql = rawMatch[1].replace(/\\n/g, '\n').replace(/\\"/g, '"');
                            }
                          }

                          if (!sql && activeStep.detail) {
                            // Parse SQL from Action Input JSON
                            const inputMatch = activeStep.detail.match(/Action Input:\s*({[\s\S]*?})(?:\n|$)/);
                            if (inputMatch) {
                              try {
                                const parsed = JSON.parse(inputMatch[1]);
                                sql = parsed.sql || '';
                              } catch {
                                // fallback: extract raw sql string
                                const rawMatch = inputMatch[1].match(/"sql"\s*:\s*"([\s\S]*?)"/);
                                if (rawMatch) sql = rawMatch[1].replace(/\\n/g, '\n').replace(/\\"/g, '"');
                              }
                            }
                          }

                          if (!sql) return null;

                          // Simple SQL keyword highlighting
                          const highlightSQL = (sqlStr: string) => {
                            const parts: { text: string; type: 'keyword' | 'string' | 'number' | 'plain' }[] = [];
                            let remaining = sqlStr;
                            let safetyCounter = 0;

                            while (remaining.length > 0 && safetyCounter < 10000) {
                              safetyCounter++;
                              // Check for string literal first
                              const strMatch = remaining.match(/^('[^']*')/);
                              if (strMatch) {
                                parts.push({ text: strMatch[1], type: 'string' });
                                remaining = remaining.slice(strMatch[1].length);
                                continue;
                              }
                              // Check for keyword
                              const kwMatch = remaining.match(
                                /^\b(SELECT|FROM|WHERE|JOIN|LEFT|RIGHT|INNER|OUTER|FULL|CROSS|ON|AND|OR|NOT|IN|EXISTS|BETWEEN|LIKE|IS|NULL|AS|CASE|WHEN|THEN|ELSE|END|GROUP\s+BY|ORDER\s+BY|HAVING|LIMIT|OFFSET|UNION|ALL|DISTINCT|COUNT|SUM|AVG|MIN|MAX|COALESCE|CAST|DESC|ASC)\b/i,
                              );
                              if (kwMatch) {
                                parts.push({ text: kwMatch[1].toUpperCase(), type: 'keyword' });
                                remaining = remaining.slice(kwMatch[1].length);
                                continue;
                              }
                              // Check for number
                              const numMatch = remaining.match(/^\b(\d+\.?\d*)\b/);
                              if (numMatch) {
                                parts.push({ text: numMatch[1], type: 'number' });
                                remaining = remaining.slice(numMatch[1].length);
                                continue;
                              }
                              // Plain character
                              parts.push({ text: remaining[0], type: 'plain' });
                              remaining = remaining.slice(1);
                            }

                            return parts.map((p, i) => {
                              switch (p.type) {
                                case 'keyword':
                                  return (
                                    <span key={i} className='text-[#569cd6] font-semibold'>
                                      {p.text}
                                    </span>
                                  );
                                case 'string':
                                  return (
                                    <span key={i} className='text-[#ce9178]'>
                                      {p.text}
                                    </span>
                                  );
                                case 'number':
                                  return (
                                    <span key={i} className='text-[#b5cea8]'>
                                      {p.text}
                                    </span>
                                  );
                                default:
                                  return <span key={i}>{p.text}</span>;
                              }
                            });
                          };

                          return (
                            <div className='rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden bg-white dark:bg-[#1a1b1e]'>
                              {/* Header bar */}
                              <div className='flex items-center justify-between px-4 py-2.5 bg-gray-50 dark:bg-[#252629] border-b border-gray-200 dark:border-gray-700'>
                                <div className='flex items-center gap-2'>
                                  {getDbTypeInfo(databaseType).icon}
                                  <span className='text-xs font-semibold text-gray-600 dark:text-gray-300'>
                                    SQL Query
                                  </span>
                                  {databaseType && (
                                    <span className='text-[10px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 font-medium'>
                                      {getDbTypeInfo(databaseType).label}
                                    </span>
                                  )}
                                  {databaseName && (
                                    <span className='text-[10px] px-1.5 py-0.5 rounded bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400 font-medium'>
                                      {databaseName}
                                    </span>
                                  )}
                                  <span className='text-[10px] px-1.5 py-0.5 rounded bg-emerald-100 dark:bg-emerald-900/40 text-emerald-600 dark:text-emerald-400 font-medium'>
                                    READ ONLY
                                  </span>
                                </div>
                                <Tooltip title='复制SQL'>
                                  <button
                                    className='flex items-center gap-1 text-[11px] text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors px-2 py-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700'
                                    onClick={() => {
                                      navigator.clipboard.writeText(sql);
                                      message.success('SQL已复制到剪贴板');
                                    }}
                                  >
                                    <CopyOutlined className='text-xs' />
                                    <span>Copy</span>
                                  </button>
                                </Tooltip>
                              </div>
                              {/* SQL code area */}
                              <div
                                className='bg-[#1e1e2e] dark:bg-[#0d0d11] overflow-auto'
                                style={{ maxHeight: '400px' }}
                              >
                                <pre className='text-[13px] leading-6 font-mono text-gray-200 p-4 m-0 whitespace-pre-wrap break-words'>
                                  <code>{highlightSQL(sql)}</code>
                                </pre>
                              </div>
                            </div>
                          );
                        })()) ||
                      (activeStep.type === 'kb' &&
                        activeStep.action &&
                        KB_TOOLS.has(activeStep.action) &&
                        (() => {
                          const kbLabel = KB_ACTION_LABELS[activeStep.action!] || activeStep.action;
                          const kbIcon = KB_ACTION_ICONS[activeStep.action!] || (
                            <FolderOpenOutlined className='text-teal-500' />
                          );
                          // Parse action input params
                          let params: Record<string, any> = {};
                          if (activeStep.actionInput) {
                            try {
                              params =
                                typeof activeStep.actionInput === 'string'
                                  ? JSON.parse(activeStep.actionInput)
                                  : activeStep.actionInput;
                            } catch {
                              params = {};
                            }
                          }
                          const paramEntries = Object.entries(params).filter(([, v]) => v !== '' && v != null);
                          return (
                            <div className='rounded-xl border border-teal-200 dark:border-teal-800/40 overflow-hidden bg-white dark:bg-[#1a1b1e]'>
                              <div className='flex items-center gap-2.5 px-4 py-2.5 bg-gradient-to-r from-teal-50 to-cyan-50 dark:from-teal-900/20 dark:to-cyan-900/10 border-b border-teal-100 dark:border-teal-800/40'>
                                <div className='flex-shrink-0 w-7 h-7 rounded-md bg-teal-100 dark:bg-teal-900/40 flex items-center justify-center'>
                                  {kbIcon}
                                </div>
                                <span className='text-sm font-semibold text-teal-700 dark:text-teal-400'>
                                  {kbLabel}
                                </span>
                              </div>
                              {paramEntries.length > 0 && (
                                <div className='px-4 py-3 space-y-1.5'>
                                  {paramEntries.map(([k, v]) => (
                                    <div key={k} className='flex items-start gap-2 text-sm'>
                                      <span className='text-[11px] font-mono text-gray-400 dark:text-gray-500 mt-0.5 min-w-[80px] flex-shrink-0'>
                                        {k}:
                                      </span>
                                      <span className='font-mono text-gray-800 dark:text-gray-200 break-all'>
                                        {typeof v === 'string' ? v : JSON.stringify(v)}
                                      </span>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          );
                        })()) || (
                        <div className='text-xs text-gray-500 dark:text-gray-400 font-mono whitespace-pre-wrap bg-gray-50 dark:bg-[#161719] rounded-lg px-3 py-2'>
                          {activeStep.detail}
                        </div>
                      )}
                  </div>
                )}
              </>
            )}

            {/* Divider + Outputs (hide for get_skill_resource since content is already shown above) */}
            {visibleOutputs.length > 0 &&
              !activeStep?.detail?.includes('Action: get_skill_resource') &&
              !activeStep?.detail?.includes('Action: execute_skill_script_file') && (
                <>
                  <div className='border-t border-gray-100 dark:border-gray-800 shrink-0' />
                  <div
                    className='min-h-0 flex-1 space-y-3 overflow-y-auto overscroll-contain p-4'
                    data-testid='execution-output-scroll'
                  >
                    {outputGroups.map((group, gIdx) => {
                      // For skill-type steps, skip the "Skill: name — description" text output (shown in YAML card above)
                      if (activeStep?.type === 'skill' && group.type === 'single') {
                        const c = group.output.content;
                        const text = typeof c === 'string' ? c.trim() : '';
                        if (/^Skill:\s*[\w-]+\s+(?:-|\u2014|\u2013)\s+/.test(text)) return null;
                      }
                      return group.type === 'code-execution' ? (
                        <CodeExecutionRenderer key={`group-${gIdx}`} group={group} />
                      ) : group.type === 'html-tabbed' ? (
                        <HtmlTabbedRenderer key={`html-tabbed-${gIdx}`} code={group.code} html={group.html} />
                      ) : (
                        <OutputRenderer
                          key={`output-${gIdx}`}
                          output={group.output}
                          index={gIdx}
                          action={activeStep?.action}
                        />
                      );
                    })}
                  </div>
                </>
              )}

            {/* Running / Empty output states */}
            {visibleOutputs.length === 0 && (
              <>
                <div className='border-t border-gray-100 dark:border-gray-800' />
                {isRunning ? (
                  <div className='flex flex-col items-center justify-center py-12 text-gray-400'>
                    <LoadingOutlined className='text-3xl text-blue-500 mb-4' />
                    <span className='text-sm'>正在执行...</span>
                    <span className='text-xs text-gray-500 mt-1'>请稍候，结果即将显示</span>
                  </div>
                ) : (
                  <div className='flex flex-col items-center justify-center py-12 text-gray-400'>
                    <FileTextOutlined className='text-3xl mb-4' />
                    <span className='text-sm'>暂无输出结果</span>
                  </div>
                )}
              </>
            )}
          </div>
        ) : (
          // Empty State
          <div className='flex flex-col items-center justify-center h-full py-20 text-gray-400'>
            <div className='w-20 h-20 rounded-2xl bg-gray-100 dark:bg-gray-800 flex items-center justify-center mb-4'>
              <ConsoleSqlOutlined className='text-3xl text-gray-400' />
            </div>
            <span className='text-sm font-medium mb-1'>选择一个步骤查看详情</span>
            <span className='text-xs text-gray-500'>点击左侧的步骤卡片以显示执行结果</span>
          </div>
        )}
      </div>

      {/* Footer Status Bar */}
      <div className='flex-shrink-0 border-t border-gray-200 bg-white px-5 py-2 dark:border-gray-800 dark:bg-[#111217]'>
        <div className='flex items-center justify-between text-[10px] text-gray-400'>
          <div className='flex items-center gap-4'>
            <span className='flex items-center gap-1'>
              <span className={`w-2 h-2 rounded-full ${isRunning ? 'bg-blue-500 animate-pulse' : 'bg-emerald-500'}`} />
              {isRunning ? '执行中' : '就绪'}
            </span>
            {subAgentContext ? (
              <span>{t('subagent_verified_steps', { count: subAgentContext.steps.length })}</span>
            ) : (
              visibleOutputs.length > 0 && <span>{visibleOutputs.length} 个输出</span>
            )}
          </div>
          {subAgentContext ? (
            <span>Agent ID: {subAgentContext.agentId}</span>
          ) : (
            activeStep && <span>Step ID: {activeStep.id}</span>
          )}
        </div>
      </div>
    </div>
  );
};

export default memo(ManusRightPanel);
