import MarkdownContext from '@/new-components/common/MarkdownContext';
import { AttachedConnector } from '@/new-components/connector/types';
import {
  ApiOutlined,
  AppstoreOutlined,
  BarChartOutlined,
  BookOutlined,
  CaretDownOutlined,
  CaretRightOutlined,
  CheckCircleFilled,
  CheckCircleOutlined,
  CheckOutlined,
  ClockCircleOutlined,
  CodeOutlined,
  ConsoleSqlOutlined,
  DatabaseOutlined,
  DesktopOutlined,
  DownloadOutlined,
  EditOutlined,
  ExclamationCircleOutlined,
  FileExcelOutlined,
  FileImageOutlined,
  FileOutlined,
  FilePptOutlined,
  FileSearchOutlined,
  FileTextOutlined,
  FolderOpenOutlined,
  LoadingOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  QuestionCircleOutlined,
  SearchOutlined,
  TableOutlined,
} from '@ant-design/icons';
import { Button, Tooltip, message } from 'antd';
import classNames from 'classnames';
import React, { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import ObservationFormatter from './ObservationFormatter';
import TaskPlanCard, { TaskItem } from './TaskPlanCard';

export type StepStatus = 'pending' | 'running' | 'completed' | 'error';

export type StepType =
  | 'read'
  | 'edit'
  | 'write'
  | 'bash'
  | 'grep'
  | 'glob'
  | 'task'
  | 'skill'
  | 'python'
  | 'html'
  | 'sql'
  | 'question'
  | 'other';

export interface ExecutionStep {
  id: string;
  type: StepType;
  title: string;
  subtitle?: string;
  description?: string;
  phase?: string;
  status: StepStatus;
  output?: any;
  todoMeta?: {
    state?: 'init' | 'progress' | 'done';
    done?: number;
    total?: number;
  };
}

export interface ThinkingSection {
  id: string;
  title: string;
  content?: string;
  isCompleted: boolean;
  steps: ExecutionStep[];
}

export interface ArtifactItem {
  id: string;
  type: 'file' | 'table' | 'chart' | 'image' | 'code' | 'markdown' | 'summary' | 'html';
  name: string;
  content: any;
  createdAt: number;
  downloadable?: boolean;
  mimeType?: string;
  size?: number;
  filePath?: string;
}

export interface ManusLeftPanelProps {
  sections: ThinkingSection[];
  activeStepId?: string | null;
  onStepClick?: (stepId: string, sectionId: string) => void;
  isWorking?: boolean;
  userQuery?: string;
  assistantText?: string;
  modelName?: string;
  stepThoughts?: Record<string, string>;
  artifacts?: ArtifactItem[];
  onArtifactClick?: (artifact: ArtifactItem) => void;
  onArtifactDownload?: (artifact: ArtifactItem) => void;
  onViewAllFiles?: () => void;
  onShare?: () => void;
  isCollapsed?: boolean;
  onExpand?: () => void;
  attachedFile?: {
    name: string;
    size: number;
    type: string;
  };
  attachedKnowledge?: {
    id: number;
    name: string;
    vector_type: string;
    desc?: string;
    owner?: string;
  };
  attachedSkill?: {
    name: string;
    id: string;
  };
  attachedDb?: {
    db_name: string;
    db_type: string;
  };
  attachedConnectors?: AttachedConnector[];
  createdSkillName?: string;
  onSkillCardClick?: (skillName: string) => void;
  onSkillDownload?: (skillName: string) => void;
  taskPlan?: TaskItem[];
}

// Get step icon based on type and status
const getStepIcon = (type: StepType, status: StepStatus) => {
  const iconClass = 'text-sm';

  if (status === 'running') {
    return <LoadingOutlined spin className={classNames(iconClass, 'text-blue-500')} />;
  }

  switch (type) {
    case 'read':
      return <FileSearchOutlined className={classNames(iconClass, 'text-emerald-500')} />;
    case 'edit':
    case 'write':
      return <EditOutlined className={classNames(iconClass, 'text-amber-500')} />;
    case 'bash':
      return <ConsoleSqlOutlined className={classNames(iconClass, 'text-purple-500')} />;
    case 'grep':
    case 'glob':
      return <SearchOutlined className={classNames(iconClass, 'text-cyan-500')} />;
    case 'python':
      return <CodeOutlined className={classNames(iconClass, 'text-blue-500')} />;
    case 'html':
      return <CodeOutlined className={classNames(iconClass, 'text-orange-500')} />;
    case 'task':
    case 'skill':
      return <PlayCircleOutlined className={classNames(iconClass, 'text-indigo-500')} />;
    case 'question':
      return <QuestionCircleOutlined className={classNames(iconClass, 'text-amber-500')} />;
    case 'sql':
      return <ConsoleSqlOutlined className={classNames(iconClass, 'text-emerald-600')} />;
    default:
      return <FileTextOutlined className={classNames(iconClass, 'text-gray-500')} />;
  }
};

const getTypeLabel = (type: StepType, t: any): string => {
  const labels: Record<StepType, string> = {
    read: t('step_type_read'),
    edit: t('step_type_edit'),
    write: t('step_type_write'),
    bash: t('step_type_bash'),
    grep: t('step_type_grep'),
    glob: t('step_type_glob'),
    task: t('step_type_task'),
    skill: t('load_skill'),
    sql: t('step_type_sql'),
    python: t('step_type_python'),
    html: t('step_type_html'),
    question: t('step_type_question') || 'Ask User',
    other: t('step_type_other'),
  };
  return labels[type] || t('step_type_other');
};

// Get icon background color based on type
const getIconBgClass = (type: StepType): string => {
  const bgClasses: Record<StepType, string> = {
    read: 'bg-emerald-50 dark:bg-emerald-900/30',
    edit: 'bg-amber-50 dark:bg-amber-900/30',
    write: 'bg-amber-50 dark:bg-amber-900/30',
    bash: 'bg-purple-50 dark:bg-purple-900/30',
    grep: 'bg-cyan-50 dark:bg-cyan-900/30',
    glob: 'bg-cyan-50 dark:bg-cyan-900/30',
    python: 'bg-blue-50 dark:bg-blue-900/30',
    html: 'bg-orange-50 dark:bg-orange-900/30',
    task: 'bg-indigo-50 dark:bg-indigo-900/30',
    skill: 'bg-indigo-50 dark:bg-indigo-900/30',
    sql: 'bg-emerald-50 dark:bg-emerald-900/30',
    question: 'bg-amber-50 dark:bg-amber-900/30',
    other: 'bg-gray-50 dark:bg-gray-800',
  };
  return bgClasses[type] || 'bg-gray-50 dark:bg-gray-800';
};

const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
};

const getFileTypeLabel = (fileName: string, t: any, mimeType?: string): string => {
  const ext = fileName.toLowerCase().split('.').pop() || '';
  if (['xlsx', 'xls'].includes(ext) || mimeType?.includes('spreadsheet') || mimeType?.includes('excel'))
    return t('file_type_spreadsheet');
  if (ext === 'csv' || mimeType?.includes('csv')) return t('file_type_spreadsheet');
  if (ext === 'pdf' || mimeType?.includes('pdf')) return t('file_type_pdf');
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(ext) || mimeType?.includes('image'))
    return t('file_type_image');
  if (['doc', 'docx'].includes(ext) || mimeType?.includes('word')) return t('file_type_word');
  if (['txt', 'md'].includes(ext) || mimeType?.includes('text')) return t('file_type_text');
  return t('file_type_generic');
};

const getFileIconElement = (fileName: string, mimeType?: string) => {
  const ext = fileName.toLowerCase().split('.').pop() || '';
  if (
    ['xlsx', 'xls', 'csv'].includes(ext) ||
    mimeType?.includes('spreadsheet') ||
    mimeType?.includes('excel') ||
    mimeType?.includes('csv')
  ) {
    return <FileExcelOutlined className='text-green-600 text-base' />;
  }
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(ext) || mimeType?.includes('image')) {
    return <FileImageOutlined className='text-pink-500 text-base' />;
  }
  if (['ppt', 'pptx'].includes(ext)) {
    return <FilePptOutlined className='text-orange-500 text-base' />;
  }
  return <FileTextOutlined className='text-blue-500 text-base' />;
};

// Get icon for artifact type
const getArtifactIcon = (artifact: ArtifactItem) => {
  switch (artifact.type) {
    case 'file':
      return getFileIconElement(artifact.name, artifact.mimeType);
    case 'html':
      return <DesktopOutlined className='text-blue-500 text-base' />;
    case 'table':
      return <TableOutlined className='text-blue-500 text-base' />;
    case 'chart':
      return <BarChartOutlined className='text-green-500 text-base' />;
    case 'image':
      return <FileImageOutlined className='text-pink-500 text-base' />;
    case 'code':
      return <CodeOutlined className='text-purple-500 text-base' />;
    case 'markdown':
      return <FileTextOutlined className='text-orange-500 text-base' />;
    case 'summary':
      return <FileTextOutlined className='text-emerald-500 text-base' />;
    default:
      return <FileOutlined className='text-gray-500 text-base' />;
  }
};

const getArtifactTypeLabel = (artifact: ArtifactItem, t: any): string => {
  const labels: Record<string, string> = {
    file: t('artifact_type_file'),
    html: t('artifact_type_html'),
    table: t('artifact_type_table'),
    chart: t('artifact_type_chart'),
    image: t('artifact_type_image'),
    code: t('artifact_type_code'),
    markdown: t('artifact_type_markdown'),
    summary: t('artifact_type_summary'),
  };
  return labels[artifact.type] || t('artifact_type_generic');
};

// Get icon background for artifact type
const getArtifactIconBg = (type: string): string => {
  const bgs: Record<string, string> = {
    file: 'bg-gray-50 dark:bg-gray-800',
    html: 'bg-blue-50 dark:bg-blue-900/30',
    table: 'bg-blue-50 dark:bg-blue-900/30',
    chart: 'bg-green-50 dark:bg-green-900/30',
    image: 'bg-pink-50 dark:bg-pink-900/30',
    code: 'bg-purple-50 dark:bg-purple-900/30',
    markdown: 'bg-orange-50 dark:bg-orange-900/30',
    summary: 'bg-emerald-50 dark:bg-emerald-900/30',
  };
  return bgs[type] || 'bg-gray-50 dark:bg-gray-800';
};

// Artifact Card Component
const ArtifactCard: React.FC<{
  artifact: ArtifactItem;
  onClick?: () => void;
  onDownload?: () => void;
}> = memo(({ artifact, onClick, onDownload }) => {
  const { t } = useTranslation();
  return (
    <div
      onClick={onClick}
      className='group flex items-center gap-3 px-3.5 py-3 rounded-xl border border-gray-200 dark:border-gray-700/60 bg-white dark:bg-[#1a1b1e] cursor-pointer hover:border-gray-300 dark:hover:border-gray-600 hover:shadow-sm transition-all duration-200'
    >
      <div
        className={classNames(
          'w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0',
          getArtifactIconBg(artifact.type),
        )}
      >
        {getArtifactIcon(artifact)}
      </div>
      <div className='min-w-0 flex-1'>
        <div className='text-sm font-medium text-gray-800 dark:text-gray-200 truncate'>{artifact.name}</div>
        <div className='text-[11px] text-gray-400 dark:text-gray-500 flex items-center gap-1.5'>
          <span>{getArtifactTypeLabel(artifact, t)}</span>
          {artifact.size != null && (
            <>
              <span className='text-gray-300 dark:text-gray-600'>·</span>
              <span>{formatFileSize(artifact.size)}</span>
            </>
          )}
        </div>
      </div>
      {artifact.downloadable && (
        <Tooltip title={t('download')}>
          <Button
            type='text'
            size='small'
            icon={<DownloadOutlined />}
            className='text-gray-400 hover:text-blue-500 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0'
            onClick={e => {
              e.stopPropagation();
              onDownload?.();
            }}
          />
        </Tooltip>
      )}
    </div>
  );
});

ArtifactCard.displayName = 'ArtifactCard';

/** Compact skill card for left panel — shows skill name, download, add-to-skills */
const SkillCompactCard: React.FC<{
  skillName: string;
  onClick?: () => void;
  onDownload?: () => void;
}> = memo(({ skillName, onClick, onDownload }) => {
  const { t } = useTranslation();
  const [downloading, _setDownloading] = useState(false);
  const [isAdded, setIsAdded] = useState(false);
  return (
    <div
      onClick={onClick}
      className='group flex items-center gap-3 px-4 py-3.5 rounded-xl border border-gray-200 dark:border-gray-700/60 bg-white dark:bg-[#1a1b1e] cursor-pointer hover:border-gray-300 dark:hover:border-gray-600 hover:shadow-sm transition-all duration-200 w-full'
    >
      <div className='w-10 h-10 rounded-lg bg-gray-100 dark:bg-gray-800 flex items-center justify-center flex-shrink-0'>
        <AppstoreOutlined className='text-lg text-gray-500 dark:text-gray-400' />
      </div>
      <div className='min-w-0 flex-1'>
        <div className='flex items-center gap-2'>
          <span className='text-sm font-semibold text-gray-800 dark:text-gray-200 truncate'>{skillName}</span>
          <span className='flex-shrink-0 text-[10px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 font-medium'>
            {t('skill_label')}
          </span>
        </div>
      </div>
      <div className='flex items-center gap-2 flex-shrink-0'>
        <Tooltip title={t('download_as_zip')}>
          <button
            className='flex items-center justify-center w-9 h-9 rounded-lg border border-gray-200 dark:border-gray-700 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:border-gray-400 dark:hover:border-gray-500 transition-colors'
            onClick={e => {
              e.stopPropagation();
              onDownload?.();
            }}
            disabled={downloading}
          >
            {downloading ? <LoadingOutlined className='text-sm' /> : <DownloadOutlined className='text-sm' />}
          </button>
        </Tooltip>
        <button
          className={`flex items-center gap-1.5 rounded-lg text-xs font-medium px-4 py-2 transition-all duration-200 ${
            isAdded
              ? 'bg-green-50 text-green-600 border border-green-200 dark:bg-green-900/20 dark:text-green-500 dark:border-green-800'
              : 'bg-gray-900 dark:bg-gray-100 text-white dark:text-gray-900 hover:opacity-90'
          }`}
          onClick={e => {
            e.stopPropagation();
            if (!isAdded) {
              setIsAdded(true);
              message.success(t('skill_added_success', { skillName }));
            }
          }}
        >
          {isAdded ? (
            <>
              <CheckOutlined className='text-[10px]' />
              {t('added')}
            </>
          ) : (
            <>
              <PlusOutlined className='text-[10px]' />
              {t('add')}
            </>
          )}
        </button>
      </div>
    </div>
  );
});

SkillCompactCard.displayName = 'SkillCompactCard';

const StreamingText: React.FC<{ text: string }> = memo(({ text }) => {
  const [displayed, setDisplayed] = useState('');
  const prevLenRef = useRef(0);
  const rafRef = useRef<number | null>(null);
  const queueRef = useRef('');
  const idxRef = useRef(0);

  useEffect(() => {
    if (text.length <= prevLenRef.current) {
      prevLenRef.current = text.length;
      setDisplayed(text);
      return;
    }
    const newChars = text.slice(prevLenRef.current);
    prevLenRef.current = text.length;
    queueRef.current += newChars;

    if (rafRef.current !== null) return;

    const flush = () => {
      const batch = Math.max(1, Math.ceil(queueRef.current.length / 12));
      const chunk = queueRef.current.slice(0, batch);
      queueRef.current = queueRef.current.slice(batch);
      idxRef.current += chunk.length;
      setDisplayed(prev => prev + chunk);
      if (queueRef.current.length > 0) {
        rafRef.current = requestAnimationFrame(flush);
      } else {
        rafRef.current = null;
      }
    };
    rafRef.current = requestAnimationFrame(flush);

    return () => {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };
  }, [text]);

  useEffect(() => {
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
  }, []);

  return <>{displayed}</>;
});

StreamingText.displayName = 'StreamingText';

const getTodoStepTitle = (t: (key: string, options?: Record<string, any>) => string, step: ExecutionStep): string => {
  const todoMeta = step.todoMeta;
  if (!todoMeta) return step.title;
  const done = todoMeta.done ?? 0;
  const total = todoMeta.total ?? 0;
  if (todoMeta.state === 'init') return t('task_plan_init_title');
  if (todoMeta.state === 'done') return t('task_plan_done_title', { total });
  return t('task_plan_update_title', { done, total });
};

const getTodoStepBadge = (t: (key: string, options?: Record<string, any>) => string, step: ExecutionStep): string => {
  const todoMeta = step.todoMeta;
  if (!todoMeta) return '';
  if ((todoMeta.total ?? 0) > 0) {
    return `${todoMeta.done ?? 0}/${todoMeta.total}`;
  }
  return todoMeta.state === 'init' ? t('task_plan_new_badge') : '';
};

const StepCard: React.FC<{
  step: ExecutionStep;
  isActive: boolean;
  onClick: () => void;
}> = memo(({ step, isActive, onClick }) => {
  const { t } = useTranslation();
  const [isVisible, setIsVisible] = useState(false);
  const detailLine = step.description ? step.description.split('\n')[0] : '';
  const isTodoStep = detailLine.toLowerCase() === 'todowrite' || step.title.startsWith('TODO::') || !!step.todoMeta;

  React.useEffect(() => {
    const timer = setTimeout(() => setIsVisible(true), 50);
    return () => clearTimeout(timer);
  }, []);
  const isThinkingStep =
    step.status === 'running' &&
    (step.title === t('thinking') ||
      step.title === '思考中' ||
      step.title === '正在思考中' ||
      step.title?.toLowerCase() === 'thinking');
  if (isThinkingStep) {
    return (
      <div
        onClick={onClick}
        className={classNames(
          'inline-flex items-center gap-2 px-3 py-1.5 rounded-full cursor-pointer transition-all duration-200',
          'bg-gray-100 dark:bg-gray-800',
          'transform',
          {
            'opacity-0 translate-y-1': !isVisible,
            'opacity-100 translate-y-0': isVisible,
          },
        )}
        style={{ transition: 'opacity 0.2s ease-out, transform 0.2s ease-out' }}
      >
        <span className='relative flex h-2.5 w-2.5'>
          <span className='animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75' />
          <span className='relative inline-flex rounded-full h-2.5 w-2.5 bg-gradient-to-r from-blue-400 to-cyan-400' />
        </span>
        <span className='text-sm text-gray-700 dark:text-gray-300'>{t('thinking')}</span>
      </div>
    );
  }
  const isQuestionStep = step.type === 'question' || step.title === 'question';
  if (isQuestionStep) {
    const isWaiting = step.status === 'running';
    return (
      <div
        onClick={onClick}
        className={classNames(
          'group relative cursor-pointer rounded-lg border transition-all duration-200',
          'px-3 py-2.5',
          'transform',
          {
            'opacity-0 translate-y-1': !isVisible,
            'opacity-100 translate-y-0': isVisible,
            'bg-gradient-to-r from-amber-50/80 via-orange-50/50 to-white dark:from-amber-900/20 dark:via-orange-900/10 dark:to-[#1a1b1e]':
              true,
            'border-amber-300/80 dark:border-amber-500/30 shadow-[0_4px_16px_rgba(245,158,11,0.12)] ring-1 ring-amber-200/50 dark:ring-amber-500/20':
              isActive || isWaiting,
            'border-amber-200/60 dark:border-amber-600/20 hover:border-amber-300 hover:shadow-[0_4px_12px_rgba(245,158,11,0.08)]':
              !isActive && !isWaiting,
          },
        )}
        style={{ transition: 'opacity 0.2s ease-out, transform 0.2s ease-out' }}
      >
        {isWaiting && (
          <div className='absolute left-0 top-2 bottom-2 w-[3px] rounded-r-full bg-gradient-to-b from-amber-400 to-orange-400 animate-pulse' />
        )}
        <div className='flex items-center gap-3'>
          <div className='flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-amber-100 to-orange-100 shadow-sm ring-1 ring-amber-200/80 dark:from-amber-500/15 dark:to-orange-500/15 dark:ring-amber-400/30'>
            <QuestionCircleOutlined className='text-[13px] text-amber-600 dark:text-amber-400' />
          </div>
          <div className='flex flex-col min-w-0 flex-1'>
            <span className='text-[10px] font-semibold uppercase tracking-wider text-amber-600/80 dark:text-amber-400/80'>
              {isWaiting ? t('waiting_for_user') || 'Waiting for User' : t('step_type_question') || 'Ask User'}
            </span>
            <span className='text-sm font-medium text-slate-800 dark:text-slate-200 truncate'>
              {step.title === 'question' ? t('user_confirmation') || '需要您的确认' : step.title}
            </span>
          </div>
          <div className='flex-shrink-0'>
            {isWaiting ? (
              <span className='relative flex h-3 w-3'>
                <span className='animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-60' />
                <span className='relative inline-flex rounded-full h-3 w-3 bg-amber-500' />
              </span>
            ) : step.status === 'completed' ? (
              <CheckCircleOutlined className='text-xs text-emerald-500' />
            ) : step.status === 'error' ? (
              <ExclamationCircleOutlined className='text-xs text-red-500' />
            ) : null}
          </div>
        </div>
      </div>
    );
  }
  if (isTodoStep) {
    const tFn = t as (key: string, options?: Record<string, any>) => string;
    const progressText = getTodoStepBadge(tFn, step);
    const todoTitle = getTodoStepTitle(tFn, step);

    return (
      <div
        onClick={onClick}
        className={classNames(
          'group relative cursor-pointer rounded-lg border transition-all duration-200',
          'bg-gradient-to-r from-slate-50/95 via-white to-white dark:from-[#202127] dark:via-[#1a1b1e] dark:to-[#1a1b1e]',
          'border-slate-200/80 dark:border-white/10',
          'px-3 py-2.5',
          'transform',
          {
            'opacity-0 translate-y-1': !isVisible,
            'opacity-100 translate-y-0': isVisible,
            'shadow-[0_10px_24px_rgba(15,23,42,0.07)] ring-1 ring-slate-200/80 dark:ring-white/10': isActive,
            'hover:border-slate-300/90 dark:hover:border-white/20 hover:shadow-[0_8px_20px_rgba(15,23,42,0.06)]':
              !isActive,
          },
        )}
        style={{ transition: 'opacity 0.2s ease-out, transform 0.2s ease-out' }}
      >
        <div className='absolute left-0 top-2 bottom-2 w-[3px] rounded-r-full bg-gradient-to-b from-sky-400 via-indigo-400 to-emerald-400' />
        <div className='flex items-center gap-3 pl-1'>
          <div className='flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-md bg-gradient-to-br from-sky-50 to-emerald-50 shadow-[0_1px_0_rgba(15,23,42,0.04),0_8px_18px_rgba(14,165,233,0.10)] ring-1 ring-sky-100/80 dark:from-sky-500/10 dark:to-emerald-500/10 dark:ring-sky-400/20'>
            <div className='flex h-4 w-4 flex-col justify-center gap-[3px]'>
              <div className='flex items-center gap-1'>
                <span className='flex h-2.5 w-2.5 items-center justify-center rounded-full bg-sky-500 text-white shadow-sm'>
                  <CheckOutlined className='text-[7px]' />
                </span>
                <span className='h-[2px] w-2.5 rounded-full bg-slate-300 dark:bg-slate-500' />
              </div>
              <div className='flex items-center gap-1'>
                <span className='h-2.5 w-2.5 rounded-full border border-emerald-300 bg-white/80 dark:border-emerald-400/50 dark:bg-white/10' />
                <span className='h-[2px] w-2 rounded-full bg-slate-200 dark:bg-slate-600' />
              </div>
            </div>
          </div>

          <div className='min-w-0 flex-1'>
            <div className='mb-0.5 flex items-center gap-2'>
              <span className='text-[10px] font-semibold tracking-[0.08em] text-slate-400 dark:text-slate-500'>
                {t('task_plan_label')}
              </span>
              {progressText && (
                <span className='rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-500 dark:bg-white/5 dark:text-slate-400'>
                  {progressText}
                </span>
              )}
            </div>
            <div className='truncate text-sm font-semibold text-slate-900 dark:text-slate-100'>{todoTitle}</div>
          </div>

          <div className='flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-emerald-50 ring-1 ring-emerald-100 dark:bg-emerald-500/10 dark:ring-emerald-500/20'>
            {step.status === 'running' ? (
              <LoadingOutlined spin className='text-[11px] text-sky-500' />
            ) : step.status === 'error' ? (
              <ExclamationCircleOutlined className='text-[11px] text-red-500' />
            ) : (
              <CheckCircleOutlined className='text-[11px] text-emerald-500' />
            )}
          </div>
        </div>
      </div>
    );
  }
  return (
    <div
      onClick={onClick}
      className={classNames(
        'group flex items-center gap-2.5 px-3 py-2 rounded-lg cursor-pointer transition-all duration-200',
        'border bg-white dark:bg-[#1a1b1e]',
        'transform',
        {
          'opacity-0 translate-y-1': !isVisible,
          'opacity-100 translate-y-0': isVisible,
          'border-blue-300 dark:border-blue-700 shadow-sm ring-1 ring-blue-200/50 dark:ring-blue-800/50': isActive,
          'border-gray-200 dark:border-gray-700/50 hover:border-gray-300 dark:hover:border-gray-600 hover:shadow-sm':
            !isActive,
          'border-l-[3px] border-l-blue-500': step.status === 'running',
          'border-l-[3px] border-l-emerald-500': step.status === 'completed' && isActive,
          'border-l-[3px] border-l-red-500': step.status === 'error',
        },
      )}
      style={{
        transition: 'opacity 0.2s ease-out, transform 0.2s ease-out',
      }}
    >
      <div
        className={classNames(
          'flex-shrink-0 w-6 h-6 rounded-md flex items-center justify-center',
          getIconBgClass(step.type),
        )}
      >
        {getStepIcon(step.type, step.status)}
      </div>

      <span
        className={classNames('text-[10px] font-medium tracking-wide flex-shrink-0', {
          'text-emerald-600 dark:text-emerald-400': step.type === 'read',
          'text-amber-600 dark:text-amber-400': step.type === 'edit' || step.type === 'write',
          'text-purple-600 dark:text-purple-400': step.type === 'bash',
          'text-cyan-600 dark:text-cyan-400': step.type === 'grep' || step.type === 'glob',
          'text-blue-600 dark:text-blue-400': step.type === 'python',
          'text-orange-600 dark:text-orange-400': step.type === 'html' || step.type === 'question',
          'text-indigo-600 dark:text-indigo-400': step.type === 'task' || step.type === 'skill',
          'text-gray-500': step.type === 'other',
        })}
      >
        {getTypeLabel(step.type, t)}
      </span>
      <div className='flex flex-col min-w-0 flex-1'>
        <span className='text-sm font-medium text-gray-800 dark:text-gray-200 truncate'>{step.title}</span>
        {detailLine && <span className='text-[11px] text-gray-500 dark:text-gray-400 truncate'>{detailLine}</span>}
      </div>
      <div className='flex-shrink-0'>
        {step.status === 'pending' && <ClockCircleOutlined className='text-xs text-gray-400' />}
        {step.status === 'running' && <LoadingOutlined spin className='text-xs text-blue-500' />}
        {step.status === 'completed' && <CheckCircleOutlined className='text-xs text-emerald-500' />}
        {step.status === 'error' && <ExclamationCircleOutlined className='text-xs text-red-500' />}
      </div>
    </div>
  );
});

StepCard.displayName = 'StepCard';

// Parse get_skill_resource step description to extract skill name, resource path, and content
const parseSkillResourceDescription = (
  description?: string,
): { skillName: string; resourcePath: string; content: string } | null => {
  if (!description) return null;
  try {
    // Extract Action Input JSON
    const inputMatch = description.match(/Action Input:\s*({[\s\S]*?})(?:\n|$)/);
    if (!inputMatch) return null;
    const input = JSON.parse(inputMatch[1]);
    const skillName = input.skill_name || '';
    const resourcePath = input.resource_path || '';

    // Extract the observation/output JSON that contains the file content
    const afterInput = description.slice(description.indexOf(inputMatch[0]) + inputMatch[0].length);
    let content = '';
    // Try to find JSON output with content field
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

// Component to render get_skill_resource step with skill name, resource name, and markdown content
const SkillResourceCard: React.FC<{
  step: ExecutionStep;
  isActive: boolean;
  onClick: () => void;
}> = memo(({ step, isActive, onClick }) => {
  const { t } = useTranslation();
  const [isVisible, setIsVisible] = useState(false);
  const parsed = useMemo(() => parseSkillResourceDescription(step.description), [step.description]);

  React.useEffect(() => {
    const timer = setTimeout(() => setIsVisible(true), 50);
    return () => clearTimeout(timer);
  }, []);

  if (!parsed) {
    return <StepCard step={step} isActive={isActive} onClick={onClick} />;
  }

  const resourceName = parsed.resourcePath.split('/').pop() || parsed.resourcePath;

  return (
    <div
      className={classNames(
        'rounded-lg border bg-white dark:bg-[#1a1b1e] transition-all duration-200 overflow-hidden',
        'transform',
        {
          'opacity-0 translate-y-1': !isVisible,
          'opacity-100 translate-y-0': isVisible,
          'border-blue-300 dark:border-blue-700 shadow-sm ring-1 ring-blue-200/50 dark:ring-blue-800/50': isActive,
          'border-gray-200 dark:border-gray-700/50 hover:border-gray-300 dark:hover:border-gray-600 hover:shadow-sm':
            !isActive,
          'border-l-[3px] border-l-blue-500': step.status === 'running',
          'border-l-[3px] border-l-emerald-500': step.status === 'completed' && isActive,
          'border-l-[3px] border-l-red-500': step.status === 'error',
        },
      )}
      style={{ transition: 'opacity 0.2s ease-out, transform 0.2s ease-out' }}
    >
      {/* Header row - clickable for right panel */}
      <div className='flex items-center gap-2.5 px-3 py-2 cursor-pointer' onClick={onClick}>
        <div
          className={classNames(
            'flex-shrink-0 w-6 h-6 rounded-md flex items-center justify-center',
            getIconBgClass(step.type),
          )}
        >
          {getStepIcon(step.type, step.status)}
        </div>
        <span className='text-[10px] font-medium tracking-wide flex-shrink-0 text-indigo-600 dark:text-indigo-400'>
          {getTypeLabel(step.type, t)}
        </span>
        <div className='flex flex-col min-w-0 flex-1'>
          <span className='text-sm font-medium text-gray-800 dark:text-gray-200 truncate'>{resourceName}</span>
          <span className='text-[11px] text-gray-400 dark:text-gray-500 truncate'>{parsed.skillName}</span>
        </div>
        <div className='flex-shrink-0'>
          {step.status === 'running' && <LoadingOutlined spin className='text-xs text-blue-500' />}
          {step.status === 'completed' && <CheckCircleOutlined className='text-xs text-emerald-500' />}
          {step.status === 'error' && <ExclamationCircleOutlined className='text-xs text-red-500' />}
        </div>
      </div>
    </div>
  );
});

SkillResourceCard.displayName = 'SkillResourceCard';

const ThoughtBubble: React.FC<{ text: string | Record<string, unknown> }> = memo(({ text }) => {
  const normalized = useMemo(() => {
    if (typeof text === 'string') return text;
    if (!text) return '';
    if (typeof text === 'object' && 'TODO' in text) {
      const todoValue = (text as Record<string, unknown>).TODO;
      if (typeof todoValue === 'string') return todoValue;
    }
    try {
      return JSON.stringify(text);
    } catch {
      return String(text);
    }
  }, [text]);
  const [intention, ...reasonLines] = normalized.split('\n');
  const reason = reasonLines.join('\n').trim();

  return (
    <div className='flex min-w-0 items-start gap-2 px-1 py-1'>
      <span className='mt-[5px] h-1.5 w-1.5 flex-shrink-0 rounded-full bg-slate-300 dark:bg-slate-600' />
      <div className='min-w-0 text-[12px] leading-relaxed text-slate-500 dark:text-slate-400'>
        <p className='m-0 break-words'>
          <StreamingText text={intention} />
        </p>
        {reason && <p className='m-0 mt-0.5 break-words text-slate-400 dark:text-slate-500'>{reason}</p>}
      </div>
    </div>
  );
});

ThoughtBubble.displayName = 'ThoughtBubble';

// Section Component
const SectionBlock: React.FC<{
  section: ThinkingSection;
  activeStepId?: string | null;
  onStepClick: (stepId: string) => void;
  defaultExpanded?: boolean;
  stepThoughts?: Record<string, string>;
}> = memo(({ section, activeStepId, onStepClick, defaultExpanded = true, stepThoughts }) => {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  const completedCount = section.steps.filter(s => s.status === 'completed').length;
  const totalCount = section.steps.length;
  const isAllCompleted = completedCount === totalCount && totalCount > 0;
  const hasRunningStep = section.steps.some(s => s.status === 'running');

  return (
    <div className='mb-4'>
      {/* Section Header */}
      <div className='flex items-center gap-2 mb-3 cursor-pointer group' onClick={() => setIsExpanded(!isExpanded)}>
        {/* Status indicator */}
        <div
          className={classNames('w-5 h-5 rounded-full flex items-center justify-center transition-all duration-300', {
            'bg-emerald-100 dark:bg-emerald-900/50 scale-110': isAllCompleted,
            'bg-blue-100 dark:bg-blue-900/50': hasRunningStep && !isAllCompleted,
            'bg-gray-100 dark:bg-gray-800': !isAllCompleted && !hasRunningStep,
          })}
        >
          {isAllCompleted ? (
            <CheckCircleFilled
              className={classNames('text-xs text-emerald-500 animate-bounce', {
                'animation-iteration-count-1': isAllCompleted,
              })}
            />
          ) : hasRunningStep ? (
            <LoadingOutlined spin className='text-xs text-blue-500' />
          ) : (
            <span className='w-2 h-2 rounded-full bg-gray-400 dark:bg-gray-500' />
          )}
        </div>

        {/* Section title */}
        <span className='text-sm font-medium text-gray-800 dark:text-gray-200 flex-1'>{section.title}</span>

        {/* Progress indicator */}
        {totalCount > 0 && (
          <span className='text-[10px] text-gray-400'>
            {completedCount}/{totalCount}
          </span>
        )}

        {/* Expand/collapse icon */}
        <span className='text-xs text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300 transition-colors'>
          {isExpanded ? <CaretDownOutlined /> : <CaretRightOutlined />}
        </span>
      </div>

      {/* Section Content */}
      {isExpanded && (
        <div className='ml-7 space-y-2 overflow-hidden'>
          {stepThoughts?.['initial'] && <ThoughtBubble text={stepThoughts['initial']} />}

          {section.steps.map(step => (
            <React.Fragment key={step.id}>
              {stepThoughts?.[step.id] && <ThoughtBubble text={stepThoughts[step.id]} />}
              {step.description?.includes('Action: get_skill_resource') ? (
                <SkillResourceCard
                  step={step}
                  isActive={step.id === activeStepId}
                  onClick={() => onStepClick(step.id)}
                />
              ) : (
                <StepCard step={step} isActive={step.id === activeStepId} onClick={() => onStepClick(step.id)} />
              )}
              {step.description?.includes('Observation:') && <ObservationFormatter observation={step.description} />}
            </React.Fragment>
          ))}
        </div>
      )}
    </div>
  );
});

SectionBlock.displayName = 'SectionBlock';

// Main Component
const ManusLeftPanel: React.FC<ManusLeftPanelProps> = ({
  sections,
  activeStepId,
  onStepClick,
  isWorking,
  userQuery,
  assistantText,
  modelName,
  stepThoughts,
  artifacts,
  onArtifactClick,
  onArtifactDownload,
  onViewAllFiles,
  onShare: _onShare,
  isCollapsed,
  onExpand,
  attachedFile,
  attachedKnowledge,
  attachedSkill,
  attachedDb,
  attachedConnectors,
  createdSkillName,
  onSkillCardClick,
  onSkillDownload,
  taskPlan,
}) => {
  const { t } = useTranslation();
  const handleStepClick = useCallback(
    (stepId: string, sectionId: string) => {
      onStepClick?.(stepId, sectionId);
    },
    [onStepClick],
  );

  // Collapsed mode: show compact summary of the round
  if (isCollapsed) {
    return (
      <div
        onClick={onExpand}
        className='group px-4 py-3 border-b border-gray-100 dark:border-gray-800 cursor-pointer hover:bg-gray-50/50 dark:hover:bg-[#1a1b1e]/50 transition-colors'
      >
        {/* User query bubble (compact) */}
        {userQuery && (
          <div className='flex justify-end mb-2'>
            <div className='max-w-[85%]'>
              <div className='rounded-2xl bg-gray-100 dark:bg-[#2a2b2f] px-3 py-2 text-sm text-gray-800 dark:text-gray-200 leading-relaxed line-clamp-2'>
                {userQuery}
              </div>
            </div>
          </div>
        )}
        {/* Truncated assistant response */}
        {assistantText && (
          <div className='text-sm text-gray-500 dark:text-gray-400 line-clamp-2 leading-relaxed'>
            {assistantText.slice(0, 150)}
            {assistantText.length > 150 ? '...' : ''}
          </div>
        )}
        {/* Completed indicator */}
        {!assistantText && sections.length > 0 && (
          <div className='flex items-center gap-1.5 text-xs text-gray-400'>
            <CheckCircleFilled className='text-emerald-500' />
            <span>{t('steps_completed_count', { count: sections.length })}</span>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className='flex flex-col'>
      <div className='px-4 py-4 space-y-4'>
        {userQuery && (
          <div className='flex justify-end'>
            <div className='max-w-[85%] space-y-2'>
              {attachedFile && (
                <div className='flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl border border-gray-200 dark:border-gray-700/60 bg-white dark:bg-[#1a1b1e] shadow-sm'>
                  <div className='w-8 h-8 rounded-lg bg-green-50 dark:bg-green-900/30 flex items-center justify-center flex-shrink-0'>
                    {getFileIconElement(attachedFile.name, attachedFile.type)}
                  </div>
                  <div className='min-w-0 flex-1'>
                    <div className='text-sm font-medium text-gray-800 dark:text-gray-200 truncate'>
                      {attachedFile.name}
                    </div>
                    <div className='text-[11px] text-gray-400 dark:text-gray-500'>
                      {getFileTypeLabel(attachedFile.name, t, attachedFile.type)} · {formatFileSize(attachedFile.size)}
                    </div>
                  </div>
                </div>
              )}
              {attachedKnowledge && (
                <div className='flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl border border-gray-200 dark:border-gray-700/60 bg-white dark:bg-[#1a1b1e] shadow-sm'>
                  <div className='w-8 h-8 rounded-lg bg-orange-50 dark:bg-orange-900/30 flex items-center justify-center flex-shrink-0'>
                    <BookOutlined className='text-orange-500 text-base' />
                  </div>
                  <div className='min-w-0 flex-1'>
                    <div className='text-sm font-medium text-gray-800 dark:text-gray-200 truncate'>
                      {attachedKnowledge.name}
                    </div>
                    <div className='text-[11px] text-gray-400 dark:text-gray-500'>
                      {attachedKnowledge.desc || attachedKnowledge.vector_type}
                    </div>
                  </div>
                </div>
              )}
              {attachedSkill && (
                <div className='flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl border border-gray-200 dark:border-gray-700/60 bg-white dark:bg-[#1a1b1e] shadow-sm'>
                  <div className='w-8 h-8 rounded-lg bg-indigo-50 dark:bg-indigo-900/30 flex items-center justify-center flex-shrink-0'>
                    <PlayCircleOutlined className='text-indigo-500 text-base' />
                  </div>
                  <div className='min-w-0 flex-1'>
                    <div className='text-sm font-medium text-gray-800 dark:text-gray-200 truncate'>
                      {attachedSkill.name}
                    </div>
                    <div className='text-[11px] text-gray-400 dark:text-gray-500'>{t('skill_label')}</div>
                  </div>
                </div>
              )}
              {attachedDb && (
                <div className='flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl border border-gray-200 dark:border-gray-700/60 bg-white dark:bg-[#1a1b1e] shadow-sm'>
                  <div className='w-8 h-8 rounded-lg bg-blue-50 dark:bg-blue-900/30 flex items-center justify-center flex-shrink-0'>
                    <DatabaseOutlined className='text-blue-500 text-base' />
                  </div>
                  <div className='min-w-0 flex-1'>
                    <div className='text-sm font-medium text-gray-800 dark:text-gray-200 truncate'>
                      {attachedDb.db_name}
                    </div>
                    <div className='text-[11px] text-gray-400 dark:text-gray-500'>
                      {attachedDb.db_type || t('database_label')}
                    </div>
                  </div>
                </div>
              )}
              {(attachedConnectors ?? []).map(c => (
                <div
                  key={c.id}
                  className='flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl border border-gray-200 dark:border-gray-700/60 bg-white dark:bg-[#1a1b1e] shadow-sm'
                >
                  <div className='w-8 h-8 rounded-lg bg-violet-50 dark:bg-violet-900/30 flex items-center justify-center flex-shrink-0'>
                    <ApiOutlined className='text-violet-500 text-base' />
                  </div>
                  <div className='min-w-0 flex-1'>
                    <div className='text-sm font-medium text-gray-800 dark:text-gray-200 truncate'>
                      {c.display_name}
                    </div>
                    <div className='text-[11px] text-gray-400 dark:text-gray-500'>{c.connector_type}</div>
                  </div>
                </div>
              ))}
              <div className='rounded-2xl bg-gray-100 dark:bg-[#2a2b2f] px-4 py-3 text-sm text-gray-800 dark:text-gray-200 leading-relaxed'>
                {userQuery}
              </div>
            </div>
          </div>
        )}

        {sections.length > 0 ? (
          <div className='pt-1'>
            {sections.map((section, index) => (
              <SectionBlock
                key={section.id}
                section={section}
                activeStepId={activeStepId}
                onStepClick={stepId => handleStepClick(stepId, section.id)}
                defaultExpanded={index === sections.length - 1}
                stepThoughts={stepThoughts}
              />
            ))}
          </div>
        ) : (
          <div className='px-4 py-6 text-gray-400 space-y-2'>
            {isWorking ? (
              <div className='flex items-center gap-2'>
                <LoadingOutlined spin className='text-blue-500' />
                <span className='text-sm text-blue-600 dark:text-blue-400'>{t('db_gpt_thinking')}</span>
              </div>
            ) : (
              <span className='text-sm'>{t('waiting_to_start')}</span>
            )}
            {isWorking && stepThoughts?.[activeStepId || 'initial'] && (
              <ThoughtBubble text={stepThoughts[activeStepId || 'initial']} />
            )}
          </div>
        )}

        {isWorking && sections.length > 0 && (
          <div className='px-4 py-3 mt-2 rounded-lg bg-blue-50/50 dark:bg-blue-900/20 border border-blue-100 dark:border-blue-800 space-y-2'>
            <div className='flex items-center gap-2'>
              <LoadingOutlined spin className='text-blue-500' />
              <span className='text-sm text-blue-600 dark:text-blue-400'>{t('db_gpt_thinking')}</span>
            </div>
            {stepThoughts?.[activeStepId || 'initial'] && (
              <ThoughtBubble text={stepThoughts[activeStepId || 'initial']} />
            )}
          </div>
        )}

        {taskPlan && taskPlan.length > 0 && (
          <div className='mt-3 px-1'>
            <TaskPlanCard tasks={taskPlan} defaultCollapsed={false} />
          </div>
        )}

        {assistantText && (
          <div className='mt-4 px-1'>
            <div className='prose prose-sm dark:prose-invert max-w-none text-gray-800 dark:text-gray-200 leading-relaxed'>
              <MarkdownContext>{assistantText}</MarkdownContext>
            </div>
          </div>
        )}

        {createdSkillName && (
          <div className='mt-5 px-1'>
            <SkillCompactCard
              skillName={createdSkillName}
              onClick={() => onSkillCardClick?.(createdSkillName)}
              onDownload={() => onSkillDownload?.(createdSkillName)}
            />
          </div>
        )}

        {artifacts && artifacts.length > 0 && (
          <div className='mt-5 px-1 pb-8'>
            <div className='flex flex-wrap gap-3'>
              {artifacts
                .filter(a => a.type === 'file' || a.type === 'html')
                .slice(0, 3)
                .map(artifact => (
                  <ArtifactCard
                    key={artifact.id}
                    artifact={artifact}
                    onClick={() => onArtifactClick?.(artifact)}
                    onDownload={() => onArtifactDownload?.(artifact)}
                  />
                ))}

              {onViewAllFiles && (
                <div
                  onClick={onViewAllFiles}
                  className='flex items-center gap-2 px-4 py-3 rounded-xl border border-gray-200 dark:border-gray-700/60 bg-white dark:bg-[#1a1b1e] cursor-pointer hover:border-gray-300 dark:hover:border-gray-600 hover:shadow-sm transition-all duration-200 min-w-[200px]'
                >
                  <div className='w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 bg-gray-50 dark:bg-gray-800'>
                    <FolderOpenOutlined className='text-gray-500 text-base' />
                  </div>
                  <span className='text-sm text-gray-600 dark:text-gray-300'>{t('view_all_task_files')}</span>
                </div>
              )}
            </div>

            <div className='flex items-center gap-1.5 mt-5'>
              <CheckOutlined className='text-xs text-emerald-500' />
              <span className='text-sm text-emerald-600 dark:text-emerald-400 font-medium'>{t('task_completed')}</span>
            </div>
          </div>
        )}
      </div>

      {modelName && (
        <div className='px-4 py-2 border-t border-gray-100 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-900/50'>
          <div className='flex items-center justify-between text-[10px] text-gray-400'>
            <span>{`Model: ${modelName}`}</span>
            <div className='flex items-center gap-2'>
              {isWorking && <span className='animate-pulse'>Processing...</span>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default memo(ManusLeftPanel);
