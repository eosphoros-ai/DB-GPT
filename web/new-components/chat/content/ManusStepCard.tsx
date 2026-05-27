import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  CodeOutlined,
  ConsoleSqlOutlined,
  EditOutlined,
  ExclamationCircleOutlined,
  FileSearchOutlined,
  FileTextOutlined,
  LoadingOutlined,
  PlayCircleOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import { Spin, Tooltip } from 'antd';
import classNames from 'classnames';
import React, { memo, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import i18n from '@/app/i18n';

export type StepStatus = 'pending' | 'running' | 'completed' | 'error';

export interface StepCardProps {
  id: string;
  type: 'read' | 'edit' | 'write' | 'bash' | 'grep' | 'glob' | 'task' | 'skill' | 'python' | 'html' | 'other';
  title: string;
  subtitle?: string;
  description?: string;
  status: StepStatus;
  isActive?: boolean;
  onClick?: () => void;
  stats?: {
    additions?: number;
    deletions?: number;
    files?: number;
  };
}

const getStepIcon = (type: StepCardProps['type'], status: StepStatus) => {
  const iconClass = 'text-base';

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
    default:
      return <FileTextOutlined className={classNames(iconClass, 'text-gray-500')} />;
  }
};

const getStatusIndicator = (status: StepStatus) => {
  switch (status) {
    case 'pending':
      return (
        <div className='w-5 h-5 rounded-full border-2 border-gray-300 dark:border-gray-600 flex items-center justify-center'>
          <ClockCircleOutlined className='text-[10px] text-gray-400' />
        </div>
      );
    case 'running':
      return (
        <div className='w-5 h-5 rounded-full bg-blue-100 dark:bg-blue-900/50 flex items-center justify-center'>
          <Spin size='small' indicator={<LoadingOutlined spin className='text-blue-500 text-xs' />} />
        </div>
      );
    case 'completed':
      return (
        <div className='w-5 h-5 rounded-full bg-emerald-100 dark:bg-emerald-900/50 flex items-center justify-center'>
          <CheckCircleOutlined className='text-xs text-emerald-500' />
        </div>
      );
    case 'error':
      return (
        <div className='w-5 h-5 rounded-full bg-red-100 dark:bg-red-900/50 flex items-center justify-center'>
          <ExclamationCircleOutlined className='text-xs text-red-500' />
        </div>
      );
  }
};

const getTypeLabel = (type: StepCardProps['type'], t: (key: string) => string): string => {
  const labels: Record<StepCardProps['type'], string> = {
    read: i18n.t('step_type_read'),
    edit: i18n.t('step_type_edit'),
    write: i18n.t('step_type_write'),
    bash: i18n.t('step_type_bash'),
    grep: i18n.t('step_type_grep'),
    glob: i18n.t('step_type_glob'),
    task: i18n.t('step_type_task'),
    skill: i18n.t('step_type_skill'),
    python: i18n.t('step_type_python'),
    html: i18n.t('step_type_html'),
    other: i18n.t('step_type_other'),
  };
  return labels[type] || t('step_type_other');
};

const ManusStepCard: React.FC<StepCardProps> = ({
  id,
  type,
  title,
  subtitle,
  description,
  status,
  isActive = false,
  onClick,
  stats,
}) => {
  const { t } = useTranslation();

  const typeLabel = useMemo(() => getTypeLabel(type, t), [type, t]);

  return (
    <div
      data-step-id={id}
      onClick={onClick}
      className={classNames(
        'group relative flex items-start gap-3 p-3 rounded-xl cursor-pointer transition-all duration-200',
        'border bg-white dark:bg-[#1f2024]',
        {
          'border-blue-300 dark:border-blue-700 shadow-md ring-2 ring-blue-200/50 dark:ring-blue-800/50': isActive,
          'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600 hover:shadow-sm':
            !isActive,
          'border-l-4 border-l-blue-500': status === 'running',
          'border-l-4 border-l-emerald-500': status === 'completed' && isActive,
          'border-l-4 border-l-red-500': status === 'error',
        },
      )}
    >
      {/* Left Icon */}
      <div
        className={classNames('flex-shrink-0 w-9 h-9 rounded-lg flex items-center justify-center', {
          'bg-emerald-50 dark:bg-emerald-900/30': type === 'read',
          'bg-amber-50 dark:bg-amber-900/30': type === 'edit' || type === 'write',
          'bg-purple-50 dark:bg-purple-900/30': type === 'bash',
          'bg-cyan-50 dark:bg-cyan-900/30': type === 'grep' || type === 'glob',
          'bg-blue-50 dark:bg-blue-900/30': type === 'python',
          'bg-orange-50 dark:bg-orange-900/30': type === 'html',
          'bg-indigo-50 dark:bg-indigo-900/30': type === 'task' || type === 'skill',
          'bg-gray-50 dark:bg-gray-800': type === 'other',
        })}
      >
        {getStepIcon(type, status)}
      </div>

      {/* Content */}
      <div className='flex-1 min-w-0'>
        <div className='flex items-center gap-2 mb-0.5'>
          <span
            className={classNames('text-[10px] font-medium uppercase tracking-wider', {
              'text-emerald-600 dark:text-emerald-400': type === 'read',
              'text-amber-600 dark:text-amber-400': type === 'edit' || type === 'write',
              'text-purple-600 dark:text-purple-400': type === 'bash',
              'text-cyan-600 dark:text-cyan-400': type === 'grep' || type === 'glob',
              'text-blue-600 dark:text-blue-400': type === 'python',
              'text-orange-600 dark:text-orange-400': type === 'html',
              'text-indigo-600 dark:text-indigo-400': type === 'task' || type === 'skill',
              'text-gray-500': type === 'other',
            })}
          >
            {typeLabel}
          </span>
          {status === 'running' && <span className='text-[10px] text-blue-500 animate-pulse'>{t('running')}</span>}
        </div>

        <div className='text-sm font-medium text-gray-800 dark:text-gray-200 truncate'>{title}</div>

        {subtitle && (
          <div className='text-xs text-gray-500 dark:text-gray-400 truncate mt-0.5 font-mono'>{subtitle}</div>
        )}

        {description && <div className='text-xs text-gray-400 dark:text-gray-500 mt-1 line-clamp-2'>{description}</div>}

        {/* Stats for edit operations */}
        {stats && (type === 'edit' || type === 'write') && (
          <div className='flex items-center gap-3 mt-2 text-[11px]'>
            {stats.additions !== undefined && stats.additions > 0 && (
              <span className='text-emerald-600 dark:text-emerald-400'>+{stats.additions}</span>
            )}
            {stats.deletions !== undefined && stats.deletions > 0 && (
              <span className='text-red-500 dark:text-red-400'>-{stats.deletions}</span>
            )}
            {stats.files !== undefined && <span className='text-gray-400'>{t('files_count', { count: stats.files })}</span>}
          </div>
        )}
      </div>

      {/* Right Status */}
      <div className='flex-shrink-0'>{getStatusIndicator(status)}</div>

      {/* Hover Play Button */}
      {status === 'pending' && (
        <Tooltip title={t('click_to_execute')}>
          <div className='absolute right-3 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity'>
            <PlayCircleOutlined className='text-lg text-blue-500 hover:text-blue-600' />
          </div>
        </Tooltip>
      )}
    </div>
  );
};

export default memo(ManusStepCard);

export interface ThinkingSectionProps {
  title: string;
  content: string | Record<string, unknown>;
  isExpanded?: boolean;
  onToggle?: () => void;
  children?: React.ReactNode;
}

const normalizeText = (value: unknown): string => {
  if (typeof value === 'string') return value;
  if (value && typeof value === 'object') {
    const todoValue = (value as Record<string, unknown>).TODO;
    if (typeof todoValue === 'string') return todoValue;
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return value == null ? '' : String(value);
};

export const ThinkingSection: React.FC<ThinkingSectionProps> = memo(
  ({ title, content, isExpanded = true, onToggle, children }) => {
    return (
      <div className='mb-4'>
        <div className='flex items-center gap-2 mb-2 cursor-pointer group' onClick={onToggle}>
          <div className='w-5 h-5 rounded-full bg-emerald-100 dark:bg-emerald-900/50 flex items-center justify-center'>
            <CheckCircleOutlined className='text-xs text-emerald-500' />
          </div>
          <span className='text-sm font-medium text-gray-800 dark:text-gray-200'>{title}</span>
          <span className='text-xs text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300'>
            {isExpanded ? '▼' : '▶'}
          </span>
        </div>

        {isExpanded && (
          <div className='ml-7 space-y-3'>
            <p className='text-sm text-gray-600 dark:text-gray-400 leading-relaxed'>{normalizeText(content)}</p>
            {children}
          </div>
        )}
      </div>
    );
  },
);

ThinkingSection.displayName = 'ThinkingSection';
