import { CodePreview } from '@/components/chat/chat-content/code-preview';
import markdownComponents, { markdownPlugins, preprocessLaTeX } from '@/components/chat/chat-content/config';
import AdvancedChart, { createChartConfig } from '@/new-components/charts';
import MarkDownContext from '@/new-components/common/MarkdownContext';
import {
  AppstoreOutlined,
  BarChartOutlined,
  CheckCircleFilled,
  CheckOutlined,
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
  RightOutlined,
  SearchOutlined,
  SyncOutlined,
  TableOutlined,
  UpOutlined,
} from '@ant-design/icons';
import { GPTVis } from '@antv/gpt-vis';
import { Button, Table, Tooltip, message } from 'antd';
import classNames from 'classnames';
import React, { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import i18n from '@/app/i18n';
import { useTranslation } from 'react-i18next';
import { ArtifactItem, StepStatus, StepType } from './ManusLeftPanel';

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
  terminalTitle?: string;
  onCollapse?: () => void;
  isCollapsed?: boolean;
  artifacts?: ArtifactItem[];
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
}

export type PanelView = 'execution' | 'files' | 'html-preview' | 'image-preview' | 'skill-preview' | 'summary';

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
    file: i18n.t('artifact_type_file'),
    html: i18n.t('artifact_type_html'),
    table: i18n.t('artifact_type_table'),
    chart: i18n.t('artifact_type_chart'),
    image: i18n.t('artifact_type_image'),
    code: i18n.t('artifact_type_code'),
    markdown: i18n.t('artifact_type_markdown'),
    summary: i18n.t('ui_ffa2ad37'),
  };
  return map[type] || i18n.t('artifact_type_generic');
};

type FileFilterTab = 'all' | 'document' | 'image' | 'code' | 'link';

const getFileFilterTabs = (): { key: FileFilterTab; label: string }[] => [
  { key: 'all', label: i18n.t('all_models_evaluation') },
  { key: 'document', label: i18n.t('artifact_type_markdown') },
  { key: 'image', label: i18n.t('artifact_type_image') },
  { key: 'code', label: i18n.t('ui_e6fef350') },
  { key: 'link', label: i18n.t('ui_bfe68d58') },
];

const getFileFilterCategory = (artifact: ArtifactItem): FileFilterTab[] => {
  const categories: FileFilterTab[] = ['all'];
  const ext = artifact.name.toLowerCase().split('.').pop() || '';
  if (artifact.type === 'image' || ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(ext)) {
    categories.push('image');
  }
  if (artifact.type === 'code' || ['py', 'js', 'ts', 'tsx', 'jsx', 'sql', 'sh', 'json', 'yaml', 'yml'].includes(ext)) {
    categories.push('code');
  }
  if (
    artifact.type === 'html' ||
    artifact.type === 'markdown' ||
    artifact.type === 'summary' ||
    artifact.type === 'table' ||
    ['xlsx', 'xls', 'csv', 'doc', 'docx', 'pdf', 'ppt', 'pptx', 'md', 'txt', 'html', 'htm'].includes(ext)
  ) {
    categories.push('document');
  }
  if (artifact.type === 'file' && categories.length === 1) {
    categories.push('document');
  }
  return categories;
};

const formatArtifactDate = (timestamp: number): string => {
  const now = new Date();
  const date = new Date(timestamp);
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return i18n.t('ui_800dfdd9');
  if (diffDays === 1) return i18n.t('ui_2f8d6f15');
  if (diffDays < 7) {
    const dayNames = [
      i18n.t('ui_67b19578'),
      i18n.t('ui_5ce43821'),
      i18n.t('ui_34e5216b'),
      i18n.t('ui_711d996d'),
      i18n.t('ui_3df6af79'),
      i18n.t('ui_450ea3af'),
      i18n.t('ui_1ae72f68'),
    ];
    return dayNames[date.getDay()];
  }
  return i18n.t('artifact_date_md', { month: date.getMonth() + 1, day: date.getDate() });
};

const FileListItem: React.FC<{ artifact: ArtifactItem; onClick?: () => void }> = memo(({ artifact, onClick }) => {
  const isImage = artifact.type === 'image' || /\.(png|jpg|jpeg|gif|webp|svg)$/i.test(artifact.name);
  const imgSrc = isImage && typeof artifact.content === 'string' ? resolveImageUrl(artifact.content) : null;

  return (
    <div
      onClick={onClick}
      className='flex items-center gap-3 px-4 py-3.5 cursor-pointer hover:bg-gray-50 dark:hover:bg-[#1f2025] transition-colors border-b border-gray-100 dark:border-gray-800 last:border-b-0'
    >
      {imgSrc ? (
        <img
          src={imgSrc}
          alt={artifact.name}
          className='w-10 h-10 rounded-lg object-cover flex-shrink-0 border border-gray-200 dark:border-gray-700'
        />
      ) : (
        <div
          className={classNames(
            'w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0',
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
    </div>
  );
});

FileListItem.displayName = 'FileListItem';

// Output Renderer Component
const OutputRenderer: React.FC<{ output: ExecutionOutput; index: number }> = memo(({ output, index: _index }) => {
  const content = output.content;

  if (output.output_type === 'thought') {
    return null; // Don't render thoughts
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
            {preprocessLaTeX(String(content))}
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
          <iframe
            srcDoc={resolveHtmlImageUrls(
              typeof content === 'string' ? content : content?.html || content?.content || String(content),
            )}
            sandbox='allow-scripts allow-same-origin'
            className='w-full bg-white'
            style={{ border: 'none', minHeight: 500 }}
            onLoad={e => {
              // Auto-resize iframe to content height
              try {
                const iframe = e.target as HTMLIFrameElement;
                const doc = iframe.contentDocument || iframe.contentWindow?.document;
                if (doc?.body) {
                  const height = Math.max(doc.body.scrollHeight, 500);
                  iframe.style.height = `${Math.min(height, 1200)}px`;
                }
              } catch {
                // Cross-origin restriction — keep default height
              }
            }}
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
});

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
          {t('ui_e70988e6')}
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
          {t('ui_81cb1f5d')}
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
          <iframe
            srcDoc={htmlString}
            sandbox='allow-scripts allow-same-origin'
            className='w-full bg-white'
            style={{ border: 'none', minHeight: 500 }}
            onLoad={e => {
              try {
                const iframe = e.target as HTMLIFrameElement;
                const doc = iframe.contentDocument || iframe.contentWindow?.document;
                if (doc?.body) {
                  const height = Math.max(doc.body.scrollHeight, 500);
                  iframe.style.height = `${Math.min(height, 1200)}px`;
                }
              } catch {
                // Cross-origin restriction
              }
            }}
          />
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
        <span className='sticky top-0 right-0 float-right z-10 text-[10px] text-gray-400 bg-gray-800/80 px-2 py-0.5 rounded mr-2 mt-2'>{t('artifact_type_code')}</span>
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
            <span className='sticky top-0 right-0 float-right z-10 text-[10px] text-gray-400 bg-gray-800/80 px-2 py-0.5 rounded mr-2 mt-2'>{t('ui_adaf94c0')}</span>
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
          {t('artifact_type_chart')}
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
          {t('artifact_type_code')}
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
            <Tooltip title={t('ui_2733a243')}>
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
      message.success(t('ui_50940ed7'));
    } catch {
      message.error(t('ui_65e200d3'));
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
              <Tooltip title={t('download_as_zip')}>
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
              <span className='text-gray-400'>({detailData.tree.children.length} {{detailData?.tree?.children && (
              <span className='text-gray-400'>({detailData.tree.children.length}}{t('ui_49ae0e5e')}</span>
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
          <Tooltip title={t('download_as_zip')}>
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
              <span className='text-xs'>{t('skills_select_file_tip')}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
});

SkillCardRenderer.displayName = 'SkillCardRenderer';

// Main Component
const ManusRightPanel: React.FC<ManusRightPanelProps> = ({
  activeStep,
  outputs,
  isRunning,
  onRerun,
  onShare,
  terminalTitle,
  onCollapse,
  artifacts,
  onArtifactClick,
  panelView: controlledPanelView,
  onPanelViewChange,
  previewArtifact,
  databaseType,
  databaseName,
  skillName,
  summaryContent,
  isSummaryStreaming,
}) => {
  const { t } = useTranslation();
  const [inputCollapsed, setInputCollapsed] = useState(false);
  const [internalPanelView, setInternalPanelView] = useState<PanelView>('execution');
  const [fileFilter, setFileFilter] = useState<FileFilterTab>('all');
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
        message.error(t('ui_4a3073e3'));
      }
    }
  };

  useEffect(() => {
    if (controlledPanelView !== undefined) {
      setInternalPanelView(controlledPanelView);
    }
  }, [controlledPanelView]);
  const visibleOutputs = useMemo(() => outputs.filter(o => o.output_type !== 'thought'), [outputs]);

  const filteredArtifacts = useMemo(() => {
    if (!artifacts) return [];
    if (fileFilter === 'all') return artifacts;
    return artifacts.filter(a => getFileFilterCategory(a).includes(fileFilter));
  }, [artifacts, fileFilter]);

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

  // Group consecutive code+text pairs into notebook-cell units,
  // and code+html pairs into tabbed views (渲染结果 / 源代码)
  const outputGroups = useMemo(() => {
    const groups: Array<
      | { type: 'code-execution'; codes: ExecutionOutput[]; results: ExecutionOutput[]; images: ExecutionOutput[] }
      | { type: 'html-tabbed'; code?: ExecutionOutput; html: ExecutionOutput }
      | { type: 'single'; output: ExecutionOutput }
    > = [];
    let i = 0;
    while (i < visibleOutputs.length) {
      if (visibleOutputs[i].output_type === 'code') {
        const codes: ExecutionOutput[] = [visibleOutputs[i]];
        i += 1;
        while (i < visibleOutputs.length && visibleOutputs[i].output_type === 'code') {
          codes.push(visibleOutputs[i]);
          i += 1;
        }
        if (i < visibleOutputs.length && visibleOutputs[i].output_type === 'html') {
          groups.push({
            type: 'html-tabbed',
            code: { ...codes[0], content: codes.map(c => String(c.content)).join('\n') },
            html: visibleOutputs[i],
          });
          i += 1;
        } else {
          const results: ExecutionOutput[] = [];
          while (i < visibleOutputs.length && visibleOutputs[i].output_type === 'text') {
            results.push(visibleOutputs[i]);
            i += 1;
          }
          const images: ExecutionOutput[] = [];
          while (i < visibleOutputs.length && visibleOutputs[i].output_type === 'image') {
            images.push(visibleOutputs[i]);
            i += 1;
          }
          groups.push({ type: 'code-execution', codes, results, images });
        }
      } else if (visibleOutputs[i].output_type === 'html') {
        groups.push({ type: 'html-tabbed', html: visibleOutputs[i] });
        i += 1;
      } else if (visibleOutputs[i].output_type === 'markdown') {
        const mds: string[] = [String(visibleOutputs[i].content)];
        const firstMd = visibleOutputs[i];
        i += 1;
        while (i < visibleOutputs.length && visibleOutputs[i].output_type === 'markdown') {
          mds.push(String(visibleOutputs[i].content));
          i += 1;
        }
        groups.push({ type: 'single', output: { ...firstMd, content: mds.join('') } });
      } else if (visibleOutputs[i].output_type === 'text') {
        const texts: string[] = [String(visibleOutputs[i].content)];
        const firstText = visibleOutputs[i];
        i += 1;
        while (i < visibleOutputs.length && visibleOutputs[i].output_type === 'text') {
          texts.push(String(visibleOutputs[i].content));
          i += 1;
        }
        groups.push({ type: 'single', output: { ...firstText, content: texts.join('') } });
      } else if (visibleOutputs[i].output_type === 'error') {
        const errs: string[] = [String(visibleOutputs[i].content)];
        const firstErr = visibleOutputs[i];
        i += 1;
        while (i < visibleOutputs.length && visibleOutputs[i].output_type === 'error') {
          errs.push(String(visibleOutputs[i].content));
          i += 1;
        }
        groups.push({ type: 'single', output: { ...firstErr, content: errs.join('') } });
      } else {
        groups.push({ type: 'single', output: visibleOutputs[i] });
        i += 1;
      }
    }
    return groups;
  }, [visibleOutputs]);

  return (
    <div className='relative flex flex-col h-full bg-[#f8f9fc] dark:bg-[#0d0e11]'>
      {/* Collapse button is rendered by the parent layout to avoid overflow clipping */}

      {/* Terminal Header */}
      <div className='flex items-center justify-between px-5 py-3 bg-white dark:bg-[#111217] border-b border-gray-200 dark:border-gray-800'>
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

      {/* View Toggle Tabs */}
      {((artifacts && artifacts.length > 0) || previewArtifact || skillName || !!summaryContent) && (
        <div className='flex items-center gap-0 px-5 bg-white dark:bg-[#111217] border-b border-gray-200 dark:border-gray-800'>
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
          {artifacts && artifacts.length > 0 && (
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
                {artifacts.length}
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
          'flex-1 overflow-y-auto flex flex-col min-h-0',
          panelView === 'html-preview' || panelView === 'image-preview' || panelView === 'skill-preview' ? 'p-0' : 'p-5 space-y-4',
        )}
      >
        {panelView === 'skill-preview' && skillName ? (
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
            <MarkDownContext>{summaryContent}</MarkDownContext>
            {isSummaryStreaming && (
              <span className='inline-block w-1.5 h-4 bg-blue-500 animate-pulse ml-0.5 align-text-bottom' />
            )}
          </div>
        ) : panelView === 'files' ? (
          <div className='space-y-0'>
            <div className='flex items-center gap-1 mb-4 bg-gray-100/80 dark:bg-gray-800/60 rounded-lg p-1'>
              {getFileFilterTabs().map(tab => {
                const count =
                  tab.key === 'all'
                    ? artifacts?.length || 0
                    : (artifacts || []).filter(a => getFileFilterCategory(a).includes(tab.key)).length;
                if (tab.key !== 'all' && count === 0) return null;
                return (
                  <button
                    key={tab.key}
                    onClick={() => setFileFilter(tab.key)}
                    className={classNames(
                      'px-3 py-1.5 text-xs font-medium rounded-md transition-all',
                      fileFilter === tab.key
                        ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm'
                        : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300',
                    )}
                  >
                    {tab.label}
                    {tab.key === 'all' && count > 0 && <span className='ml-1 text-[10px] text-gray-400'>{count}</span>}
                  </button>
                );
              })}
            </div>

            {dateGroupedArtifacts.length > 0 ? (
              dateGroupedArtifacts.map(group => (
                <div key={group.label}>
                  <div className='px-1 py-2 text-[11px] font-medium text-gray-400 dark:text-gray-500 uppercase tracking-wider'>
                    {group.label}
                  </div>
                  <div className='rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-[#1a1b1e] overflow-hidden mb-3'>
                    {group.items.map(artifact => (
                      <FileListItem key={artifact.id} artifact={artifact} onClick={() => onArtifactClick?.(artifact)} />
                    ))}
                  </div>
                </div>
              ))
            ) : (
              <div className='flex flex-col items-center justify-center py-16 text-gray-400'>
                <FolderOpenOutlined className='text-3xl mb-4' />
                <span className='text-sm'>{t('ui_4b78b2cb')}</span>
              </div>
            )}
          </div>
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
                        'bg-amber-50 dark:bg-amber-900/30': activeStep.type === 'edit' || activeStep.type === 'write',
                        'bg-purple-50 dark:bg-purple-900/30': activeStep.type === 'bash',
                        'bg-cyan-50 dark:bg-cyan-900/30': activeStep.type === 'grep' || activeStep.type === 'glob',
                        'bg-blue-50 dark:bg-blue-900/30': activeStep.type === 'python',
                        'bg-orange-50 dark:bg-orange-900/30': activeStep.type === 'html',
                        'bg-indigo-50 dark:bg-indigo-900/30': activeStep.type === 'task' || activeStep.type === 'skill',
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
                                <Tooltip title={t('ui_03d1a910')}>
                                  <button
                                    className='flex items-center gap-1 text-[11px] text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors px-2 py-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700'
                                    onClick={() => {
                                      navigator.clipboard.writeText(sql);
                                      message.success(t('ui_c58160df'));
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
                  <div className='flex-1 min-h-0 p-4 flex flex-col space-y-3 overflow-y-auto'>
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
                        <OutputRenderer key={`output-${gIdx}`} output={group.output} index={gIdx} />
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
                    <span className='text-sm'>{t('ui_71b56fd8')}</span>
                    <span className='text-xs text-gray-500 mt-1'>{t('ui_6c9a2f83')}</span>
                  </div>
                ) : (
                  <div className='flex flex-col items-center justify-center py-12 text-gray-400'>
                    <FileTextOutlined className='text-3xl mb-4' />
                    <span className='text-sm'>{t('ui_ceae59fd')}</span>
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
            <span className='text-sm font-medium mb-1'>{t('ui_a4e57fb0')}</span>
            <span className='text-xs text-gray-500'>{t('ui_84beb792')}</span>
          </div>
        )}
      </div>

      {/* Footer Status Bar */}
      <div className='px-5 py-2 border-t border-gray-200 dark:border-gray-800 bg-white dark:bg-[#111217]'>
        <div className='flex items-center justify-between text-[10px] text-gray-400'>
          <div className='flex items-center gap-4'>
            <span className='flex items-center gap-1'>
              <span className={`w-2 h-2 rounded-full ${isRunning ? 'bg-blue-500 animate-pulse' : 'bg-emerald-500'}`} />
              {isRunning ? t('Running') : t('ui_c0d2181d')}
            </span>
            {visibleOutputs.length > 0 && <span>{visibleOutputs.length} {{visibleOutputs.length > 0 && <span>{visibleOutputs.length}}{t('ui_792c9d0d')}</span>}
          </div>
          {activeStep && <span>Step ID: {activeStep.id}</span>}
        </div>
      </div>
    </div>
  );
};

export default memo(ManusRightPanel);
