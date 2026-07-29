import markdownComponents, { markdownPlugins, preprocessLaTeX } from '@/components/chat/chat-content/config';
import { STORAGE_USERINFO_KEY } from '@/utils/constants/index';
import {
  ApartmentOutlined,
  CheckOutlined,
  ClockCircleOutlined,
  CloseOutlined,
  CodeOutlined,
  CopyOutlined,
  DownOutlined,
  EditOutlined,
  FileOutlined,
  LoadingOutlined,
  PlayCircleOutlined,
  SearchOutlined,
  UpOutlined,
} from '@ant-design/icons';
import { GPTVis } from '@antv/gpt-vis';
import { Spin, Tooltip, message } from 'antd';
import classNames from 'classnames';
import Image from 'next/image';
import React, { memo, useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import RobotIcon from './RobotIcon';

export type StepStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface ExecutionStep {
  id: string;
  name: string;
  status: StepStatus;
  startTime?: number;
  endTime?: number;
  result?: string;
  error?: string;
  tool?: string;
}

export interface SessionTurnProps {
  userMessage: string;
  assistantMessage?: string;
  steps?: ExecutionStep[];
  isWorking?: boolean;
  startTime?: number;
  endTime?: number;
  onCopy?: (text: string) => void;
  showSteps?: boolean;
  defaultStepsExpanded?: boolean;
  modelName?: string;
  thinkingContent?: string;
}

const stepStatusConfig: Record<StepStatus, { icon: React.ReactNode; className: string; bgClassName: string }> = {
  pending: {
    icon: <ClockCircleOutlined />,
    className: 'text-gray-400',
    bgClassName: 'bg-gray-100 dark:bg-gray-800',
  },
  running: {
    icon: <LoadingOutlined spin />,
    className: 'text-blue-500',
    bgClassName: 'bg-blue-50 dark:bg-blue-900/20',
  },
  completed: {
    icon: <CheckOutlined />,
    className: 'text-green-500',
    bgClassName: 'bg-green-50 dark:bg-green-900/20',
  },
  failed: {
    icon: <CloseOutlined />,
    className: 'text-red-500',
    bgClassName: 'bg-red-50 dark:bg-red-900/20',
  },
};

const getToolIcon = (tool?: string): React.ReactNode => {
  switch (tool) {
    case 'read':
    case 'file':
      return <FileOutlined />;
    case 'search':
    case 'grep':
    case 'glob':
      return <SearchOutlined />;
    case 'edit':
    case 'write':
      return <EditOutlined />;
    case 'bash':
    case 'command':
      return <PlayCircleOutlined />;
    case 'code':
      return <CodeOutlined />;
    case 'kb_codegraph_explore':
    case 'kb_codegraph_call_chain':
    case 'kb_codegraph_class_hierarchy':
      return <ApartmentOutlined />;
    default:
      return <CodeOutlined />;
  }
};

const STATUS_TEXT_MAP: Record<string, string> = {
  read: 'Gathering context...',
  search: 'Searching codebase...',
  grep: 'Searching codebase...',
  glob: 'Searching codebase...',
  edit: 'Making edits...',
  write: 'Making edits...',
  bash: 'Running commands...',
  task: 'Delegating task...',
};

const computeStatusText = (step: ExecutionStep): string => {
  if (step.tool && STATUS_TEXT_MAP[step.tool]) {
    return STATUS_TEXT_MAP[step.tool];
  }
  return step.name;
};

const formatDuration = (ms: number): string => {
  if (ms < 1000) return `${ms}ms`;
  const seconds = Math.floor(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${minutes}m ${remainingSeconds}s`;
};

const UserIcon: React.FC = () => {
  const userStr = typeof window !== 'undefined' ? localStorage.getItem(STORAGE_USERINFO_KEY) : null;
  const user = userStr ? JSON.parse(userStr) : {};

  if (!user.avatar_url) {
    return (
      <div className='flex items-center justify-center w-8 h-8 rounded-full bg-gradient-to-tr from-[#31afff] to-[#1677ff] text-xs text-white'>
        {user?.nick_name?.charAt(0) || 'U'}
      </div>
    );
  }
  return (
    <Image
      className='rounded-full border border-gray-200 object-contain bg-white inline-block'
      width={32}
      height={32}
      src={user?.avatar_url}
      alt={user?.nick_name || 'User'}
    />
  );
};

const StepItem: React.FC<{ step: ExecutionStep; isLast: boolean }> = ({ step, isLast }) => {
  const config = stepStatusConfig[step.status];
  const duration = step.startTime && step.endTime ? step.endTime - step.startTime : undefined;

  return (
    <div className={classNames('flex items-start gap-3 py-2 px-3 rounded-lg', config.bgClassName)}>
      <div className={classNames('flex-shrink-0 mt-0.5', config.className)}>{getToolIcon(step.tool)}</div>
      <div className='flex-1 min-w-0'>
        <div className='flex items-center justify-between'>
          <span className='text-sm font-medium text-gray-700 dark:text-gray-300 truncate'>
            {computeStatusText(step)}
          </span>
          <div className='flex items-center gap-2 flex-shrink-0'>
            {duration !== undefined && <span className='text-xs text-gray-400'>{formatDuration(duration)}</span>}
            <span className={config.className}>{config.icon}</span>
          </div>
        </div>
        {step.error && <div className='mt-1 text-xs text-red-500 truncate'>{step.error}</div>}
      </div>
    </div>
  );
};

const SessionTurn: React.FC<SessionTurnProps> = ({
  userMessage,
  assistantMessage,
  steps = [],
  isWorking = false,
  startTime,
  endTime,
  onCopy,
  showSteps = true,
  defaultStepsExpanded = false,
  modelName,
  thinkingContent,
}) => {
  const { t } = useTranslation();
  const [stepsExpanded, setStepsExpanded] = useState(defaultStepsExpanded);
  const [elapsedTime, setElapsedTime] = useState(0);

  useEffect(() => {
    if (!isWorking || !startTime) return;

    const updateElapsed = () => {
      const now = Date.now();
      setElapsedTime(now - startTime);
    };

    updateElapsed();
    const timer = setInterval(updateElapsed, 1000);
    return () => clearInterval(timer);
  }, [isWorking, startTime]);

  const duration = useMemo(() => {
    if (endTime && startTime) {
      return formatDuration(endTime - startTime);
    }
    if (isWorking && startTime) {
      return formatDuration(elapsedTime);
    }
    return null;
  }, [startTime, endTime, isWorking, elapsedTime]);

  const currentStatus = useMemo(() => {
    if (!isWorking) return null;

    const runningStep = steps.find(s => s.status === 'running');
    if (runningStep) {
      return computeStatusText(runningStep);
    }

    return 'Considering next steps...';
  }, [isWorking, steps]);

  const hasSteps = steps.length > 0;

  const handleCopy = useCallback(
    (text: string) => {
      if (onCopy) {
        onCopy(text);
      } else {
        navigator.clipboard
          .writeText(text)
          .then(() => {
            message.success(t('copy_to_clipboard_success'));
          })
          .catch(() => {
            message.error(t('copy_to_clipboard_failed'));
          });
      }
    },
    [onCopy, t],
  );

  const formatMarkdownVal = (val: string) => {
    return val.replace(/<table(\w*=[^>]+)>/gi, '<table $1>').replace(/<tr(\w*=[^>]+)>/gi, '<tr $1>');
  };

  const getStepsButtonText = () => {
    if (isWorking) return currentStatus;
    if (stepsExpanded) return 'Hide steps';
    return 'Show steps';
  };

  return (
    <div className='flex flex-col gap-4 py-4' data-component='session-turn'>
      <div className='flex gap-3'>
        <div className='flex-shrink-0'>
          <UserIcon />
        </div>
        <div className='flex-1 min-w-0'>
          <div className='flex items-start justify-between group'>
            <div className='text-sm text-gray-800 dark:text-gray-200 whitespace-pre-wrap break-words'>
              {userMessage}
            </div>
            <Tooltip title={t('copy_to_clipboard')}>
              <button
                className='flex-shrink-0 ml-2 p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 opacity-0 group-hover:opacity-100 transition-opacity'
                onClick={() => handleCopy(userMessage)}
              >
                <CopyOutlined />
              </button>
            </Tooltip>
          </div>
        </div>
      </div>

      {(isWorking || assistantMessage || hasSteps) && (
        <div className='flex gap-3'>
          <div className='flex-shrink-0'>
            <RobotIcon model={modelName || ''} />
          </div>
          <div className='flex-1 min-w-0 flex flex-col gap-2'>
            {showSteps && (isWorking || hasSteps) && (
              <div className='flex flex-col'>
                <button
                  className={classNames(
                    'flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors',
                    'bg-gray-50 hover:bg-gray-100 dark:bg-gray-800 dark:hover:bg-gray-700',
                    'text-gray-600 dark:text-gray-400',
                  )}
                  onClick={() => setStepsExpanded(!stepsExpanded)}
                >
                  {isWorking && <Spin size='small' indicator={<LoadingOutlined />} />}
                  <span className='flex-1 text-left truncate'>{getStepsButtonText()}</span>
                  {duration && (
                    <>
                      <span className='text-gray-400'>·</span>
                      <span className='text-gray-400'>{duration}</span>
                    </>
                  )}
                  {hasSteps &&
                    (stepsExpanded ? <UpOutlined className='text-xs' /> : <DownOutlined className='text-xs' />)}
                </button>

                {stepsExpanded && hasSteps && (
                  <div className='mt-2 flex flex-col gap-1.5 pl-2 border-l-2 border-gray-200 dark:border-gray-700'>
                    {steps.map((step, index) => (
                      <StepItem key={step.id} step={step} isLast={index === steps.length - 1} />
                    ))}
                  </div>
                )}
              </div>
            )}

            {thinkingContent && (
              <div className='px-3 py-2 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800'>
                <div className='flex items-center gap-2 text-amber-600 dark:text-amber-400 text-xs mb-1'>
                  <LoadingOutlined spin />
                  <span>{t('thinking')}</span>
                </div>
                <div className='text-sm text-amber-800 dark:text-amber-200 whitespace-pre-wrap'>{thinkingContent}</div>
              </div>
            )}

            {assistantMessage && (
              <div className='bg-white dark:bg-[rgba(255,255,255,0.08)] p-4 rounded-2xl rounded-tl-none'>
                <GPTVis components={markdownComponents as any} {...(markdownPlugins as any)}>
                  {preprocessLaTeX(formatMarkdownVal(assistantMessage))}
                </GPTVis>
              </div>
            )}

            {isWorking && !assistantMessage && !thinkingContent && (
              <div className='bg-white dark:bg-[rgba(255,255,255,0.08)] p-4 rounded-2xl rounded-tl-none'>
                <div className='flex items-center gap-2'>
                  <span className='text-sm text-gray-600 dark:text-gray-400'>{t('thinking')}</span>
                  <div className='flex gap-1'>
                    <div
                      className='w-1.5 h-1.5 rounded-full bg-blue-500 animate-bounce'
                      style={{ animationDelay: '0ms' }}
                    />
                    <div
                      className='w-1.5 h-1.5 rounded-full bg-blue-500 animate-bounce'
                      style={{ animationDelay: '150ms' }}
                    />
                    <div
                      className='w-1.5 h-1.5 rounded-full bg-blue-500 animate-bounce'
                      style={{ animationDelay: '300ms' }}
                    />
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default memo(SessionTurn);
