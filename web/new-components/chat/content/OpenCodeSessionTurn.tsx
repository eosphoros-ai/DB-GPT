import markdownComponents, { markdownPlugins, preprocessLaTeX } from '@/components/chat/chat-content/config';
import { STORAGE_USERINFO_KEY } from '@/utils/constants/index';
import { CheckOutlined, CopyOutlined, LoadingOutlined } from '@ant-design/icons';
import { GPTVis } from '@antv/gpt-vis';
import { Spin, Tooltip, message } from 'antd';
import classNames from 'classnames';
import Image from 'next/image';
import React, { memo, useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ToolIcon, getStatusText, getToolIconName } from '../icons/ToolIcon';
import { BasicTool } from '../tools/BasicTool';
import { ErrorDisplay, ReActThinking } from './ReActThinking';
import RobotIcon from './RobotIcon';

import { FileExcelOutlined, FileImageOutlined, FilePptOutlined, FileTextOutlined } from '@ant-design/icons';

export type ToolStatus = 'pending' | 'running' | 'completed' | 'error';

export interface ToolPart {
  id: string;
  type: 'tool';
  tool: string;
  callID?: string;
  state: {
    status: ToolStatus;
    input?: Record<string, unknown>;
    output?: string;
    error?: string;
    metadata?: Record<string, unknown>;
  };
}

export interface TextPart {
  id: string;
  type: 'text';
  text: string;
  synthetic?: boolean;
}

export interface ReasoningPart {
  id: string;
  type: 'reasoning';
  text: string;
}

export type MessagePart = ToolPart | TextPart | ReasoningPart;

export interface FileAttachment {
  name: string;
  size: number;
  type: string;
}

export interface OpenCodeSessionTurnProps {
  userMessage: string;
  assistantMessage?: string;
  parts?: MessagePart[];
  isWorking?: boolean;
  startTime?: number;
  endTime?: number;
  onCopy?: (text: string) => void;
  showSteps?: boolean;
  defaultStepsExpanded?: boolean;
  modelName?: string;
  thinkingContent?: string;
  currentStatus?: string;
  stepsPlacement?: 'inside' | 'outside';
  className?: string;
  attachedFile?: FileAttachment;
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  const seconds = Math.floor(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${minutes}m ${remainingSeconds}s`;
}

function formatTimestamp(timestamp: number): string {
  const date = new Date(timestamp);
  const hours = date.getHours().toString().padStart(2, '0');
  const minutes = date.getMinutes().toString().padStart(2, '0');
  return `${hours}:${minutes}`;
}

function getFilename(path: string | undefined): string {
  if (!path) return '';
  const parts = path.split('/');
  return parts[parts.length - 1] || path;
}

function getToolTitle(tool: string): string {
  const titleMap: Record<string, string> = {
    read: 'Read File',
    list: 'List Directory',
    glob: 'Find Files',
    grep: 'Search Content',
    bash: 'Run Command',
    edit: 'Edit File',
    write: 'Write File',
    task: 'Delegate Task',
    todowrite: 'Update Todo',
    todoread: 'Read Todo',
    webfetch: 'Fetch Web',
    question: 'Ask Question',
    apply_patch: 'Apply Patch',
    skill: 'Load Skill',
  };
  return titleMap[tool] || tool;
}

function getToolSubtitle(tool: string, input?: Record<string, unknown>): string | undefined {
  if (!input) return undefined;

  switch (tool) {
    case 'read':
    case 'edit':
    case 'write':
      return input.filePath ? getFilename(input.filePath as string) : undefined;
    case 'glob':
      return input.pattern as string | undefined;
    case 'grep':
      return input.pattern as string | undefined;
    case 'bash':
      return input.description as string | undefined;
    case 'task':
      return input.description as string | undefined;
    case 'webfetch':
      return input.url as string | undefined;
    case 'list':
      return input.path ? getFilename(input.path as string) : undefined;
    default:
      // Try common input keys
      return (input.value || input.name || input.query) as string | undefined;
  }
}

// Copy button with success state
const CopyButton: React.FC<{ text: string; className?: string }> = ({ text, className }) => {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(
    async (e: React.MouseEvent) => {
      e.stopPropagation();
      try {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        message.success(t('copy_to_clipboard_success'));
        setTimeout(() => setCopied(false), 2000);
      } catch {
        message.error(t('copy_to_clipboard_failed'));
      }
    },
    [text, t],
  );

  return (
    <Tooltip title={copied ? t('copy_success') : t('copy_to_clipboard')}>
      <button
        className={classNames(
          'flex-shrink-0 p-1.5 rounded-md transition-all duration-200',
          'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300',
          'hover:bg-gray-100 dark:hover:bg-gray-700',
          copied && 'text-green-500 hover:text-green-500',
          className,
        )}
        onClick={handleCopy}
      >
        {copied ? <CheckOutlined className='text-sm' /> : <CopyOutlined className='text-sm' />}
      </button>
    </Tooltip>
  );
};

const UserIcon: React.FC = () => {
  const userStr = typeof window !== 'undefined' ? localStorage.getItem(STORAGE_USERINFO_KEY) : null;
  const user = userStr ? JSON.parse(userStr) : {};

  if (!user.avatar_url) {
    return (
      <div className='flex items-center justify-center w-7 h-7 rounded-full bg-gradient-to-tr from-[#31afff] to-[#1677ff] text-xs text-white font-medium shadow-sm'>
        {user?.nick_name?.charAt(0) || 'U'}
      </div>
    );
  }
  return (
    <Image
      className='rounded-full border border-gray-200 object-contain bg-white inline-block shadow-sm'
      width={28}
      height={28}
      src={user?.avatar_url}
      alt={user?.nick_name || 'User'}
    />
  );
};

interface ToolPartDisplayProps {
  part: ToolPart;
  defaultOpen?: boolean;
}

const ToolPartDisplay: React.FC<ToolPartDisplayProps> = ({ part, defaultOpen = false }) => {
  const iconName = getToolIconName(part.tool);
  const title = getToolTitle(part.tool);
  const subtitle = getToolSubtitle(part.tool, part.state.input);
  const isRunning = part.state.status === 'running';
  const hasError = part.state.status === 'error';
  const hasOutput = !!part.state.output;

  // Check if output contains ReAct format (Thought/Action/Observation)
  const isReActOutput = useMemo(() => {
    if (!part.state.output) return false;
    const output = part.state.output;
    return /(?:Thought|Action|Observation|思考|动作|观察)\s*[:：]/i.test(output);
  }, [part.state.output]);

  // Extract round number from title if present (e.g., "Delegate Task ReAct Round 1")
  const roundNumber = useMemo(() => {
    const match = title.match(/Round\s*(\d+)/i);
    return match ? parseInt(match[1], 10) : undefined;
  }, [title]);

  // Parse skill output into name and description for card display
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

  const skillInfo = useMemo(() => {
    if (part.tool !== 'skill' || !part.state.output) return null;
    const output = normalizeText(part.state.output);
    // Try "Skill: <name> - <description>" format on first line
    const firstLine = output.split('\n')[0];
    const match = firstLine.match(/^Skill:\s*(.+?)\s+-\s+(.+)$/);
    if (match) {
      return { name: match[1].trim(), description: match[2].trim() };
    }
    // Try frontmatter format
    const fmMatch = output.match(/^---\n([\s\S]*?)\n---/);
    if (fmMatch) {
      const nameMatch = fmMatch[1].match(/^name:\s*(.+)$/m);
      const descMatch = fmMatch[1].match(/^description:\s*(.+)$/m);
      if (nameMatch) {
        return {
          name: nameMatch[1].trim(),
          description: descMatch ? descMatch[1].trim() : '',
        };
      }
    }
    // Fallback: first heading + first paragraph
    const headingMatch = output.match(/^#\s+(.+)$/m);
    const paraMatch = output.match(/^(?!#|---|\s*$)(.+)/m);
    if (headingMatch) {
      return {
        name: headingMatch[1].trim(),
        description: paraMatch ? paraMatch[1].trim() : '',
      };
    }
    return null;
  }, [part.tool, part.state.output]);

  return (
    <BasicTool
      icon={iconName}
      trigger={{
        title,
        subtitle,
        action: isRunning ? (
          <Spin size='small' indicator={<LoadingOutlined spin />} />
        ) : hasError ? (
          <span className='text-xs text-red-500'>Error</span>
        ) : null,
      }}
      defaultOpen={defaultOpen}
      className={classNames({
        'border-l-2 border-l-blue-500': isRunning,
        'border-l-2 border-l-red-500': hasError,
      })}
    >
      {(hasOutput || hasError) && (
        <div className='py-2'>
          {hasError && part.state.error && <ErrorDisplay error={part.state.error} toolName={title} className='mb-2' />}
          {hasOutput && (
            <div className='relative'>
              {skillInfo ? (
                <div className='rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden bg-white dark:bg-[#1a1b1e]'>
                  <div className='px-5 py-4'>
                    <div className='flex items-center gap-2.5 mb-2'>
                      <div className='flex-shrink-0 w-9 h-9 rounded-lg bg-indigo-50 dark:bg-indigo-900/30 flex items-center justify-center'>
                        <ToolIcon name='brain' size='medium' className='text-indigo-500' />
                      </div>
                      <div className='min-w-0 flex-1'>
                        <div className='text-sm font-semibold text-gray-800 dark:text-gray-200 truncate'>
                          {skillInfo.name}
                        </div>
                        <div className='text-[11px] text-gray-400 dark:text-gray-500'>Skill</div>
                      </div>
                    </div>
                    {skillInfo.description && (
                      <p className='text-sm text-gray-600 dark:text-gray-400 leading-relaxed mt-2'>
                        {skillInfo.description}
                      </p>
                    )}
                  </div>
                </div>
              ) : isReActOutput ? (
                <ReActThinking content={normalizeText(part.state.output)} round={roundNumber} compact={true} />
              ) : (
                <div className='group'>
                  <pre className='text-xs text-gray-600 dark:text-gray-400 whitespace-pre-wrap break-words max-h-60 overflow-auto bg-gray-50 dark:bg-gray-800 p-2 rounded'>
                    {normalizeText(part.state.output)}
                  </pre>
                  <div className='absolute top-1 right-1 opacity-0 group-hover:opacity-100 transition-opacity'>
                    <CopyButton text={normalizeText(part.state.output)} />
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </BasicTool>
  );
};

// Animated spinner with pulsing effect
const Spinner: React.FC<{ className?: string }> = ({ className }) => (
  <div className={classNames('oc-spinner inline-flex items-center justify-center', className)}>
    <svg className='animate-spin' viewBox='0 0 20 20' fill='none' width='16' height='16'>
      <circle
        cx='10'
        cy='10'
        r='8'
        stroke='currentColor'
        strokeWidth='2'
        strokeLinecap='round'
        strokeDasharray='50.265'
        strokeDashoffset='25'
        className='opacity-25'
      />
      <circle
        cx='10'
        cy='10'
        r='8'
        stroke='currentColor'
        strokeWidth='2'
        strokeLinecap='round'
        strokeDasharray='50.265'
        strokeDashoffset='37.5'
        className='opacity-75'
      />
    </svg>
  </div>
);

// Thinking dots animation
const ThinkingDots: React.FC = () => (
  <div className='flex gap-1 items-center'>
    <div
      className='w-2 h-2 rounded-full bg-blue-500 animate-bounce'
      style={{ animationDelay: '0ms', animationDuration: '1s' }}
    />
    <div
      className='w-2 h-2 rounded-full bg-blue-500 animate-bounce'
      style={{ animationDelay: '150ms', animationDuration: '1s' }}
    />
    <div
      className='w-2 h-2 rounded-full bg-blue-500 animate-bounce'
      style={{ animationDelay: '300ms', animationDuration: '1s' }}
    />
  </div>
);

// Pulse animation for working state
const PulseIndicator: React.FC = () => (
  <span className='relative flex h-2 w-2'>
    <span className='animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75'></span>
    <span className='relative inline-flex rounded-full h-2 w-2 bg-blue-500'></span>
  </span>
);

const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
};

const getFileTypeLabel = (fileName: string, mimeType?: string): string => {
  const ext = fileName.toLowerCase().split('.').pop() || '';
  if (['xlsx', 'xls'].includes(ext) || mimeType?.includes('spreadsheet') || mimeType?.includes('excel')) {
    return t('file_type_spreadsheet');
  }
  if (ext === 'csv' || mimeType?.includes('csv')) {
    return t('file_type_spreadsheet');
  }
  if (ext === 'pdf' || mimeType?.includes('pdf')) return 'PDF';
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(ext) || mimeType?.includes('image')) return t('artifact_type_image');
  if (['doc', 'docx'].includes(ext) || mimeType?.includes('word')) return t('file_type_word');
  if (['txt', 'md'].includes(ext) || mimeType?.includes('text')) return t('file_type_text');
  if (['json'].includes(ext)) return 'JSON';
  return t('artifact_type_file');
};

const FileIconComponent: React.FC<{ fileName: string; mimeType?: string }> = ({ fileName, mimeType }) => {
  const ext = fileName.toLowerCase().split('.').pop() || '';
  if (
    ['xlsx', 'xls', 'csv'].includes(ext) ||
    mimeType?.includes('spreadsheet') ||
    mimeType?.includes('excel') ||
    mimeType?.includes('csv')
  ) {
    return <FileExcelOutlined className='text-green-600 text-lg' />;
  }
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(ext) || mimeType?.includes('image')) {
    return <FileImageOutlined className='text-pink-500 text-lg' />;
  }
  if (['ppt', 'pptx'].includes(ext)) {
    return <FilePptOutlined className='text-orange-500 text-lg' />;
  }
  return <FileTextOutlined className='text-blue-500 text-lg' />;
};

const FileAttachmentCard: React.FC<{ file: FileAttachment }> = ({ file }) => {
  const fileTypeLabel = getFileTypeLabel(file.name, file.type);
  const formattedSize = formatFileSize(file.size);

  return (
    <div className='inline-flex items-center gap-3 px-3 py-2 bg-white dark:bg-[#1f2024] border border-gray-200 dark:border-gray-700 rounded-xl mb-2 max-w-sm shadow-sm'>
      <div className='w-9 h-9 bg-green-50 dark:bg-green-900/30 rounded-lg flex items-center justify-center flex-shrink-0'>
        <FileIconComponent fileName={file.name} mimeType={file.type} />
      </div>
      <div className='min-w-0 flex-1'>
        <div className='font-medium text-sm text-gray-800 dark:text-gray-200 truncate'>{file.name}</div>
        <div className='text-xs text-gray-500 dark:text-gray-400'>
          {fileTypeLabel} · {formattedSize}
        </div>
      </div>
    </div>
  );
};

const OpenCodeSessionTurn: React.FC<OpenCodeSessionTurnProps> = ({
  userMessage,
  assistantMessage,
  parts = [],
  isWorking = false,
  startTime,
  endTime,
  onCopy,
  showSteps = true,
  defaultStepsExpanded = false,
  modelName,
  thinkingContent,
  currentStatus,
  stepsPlacement = 'inside',
  className,
  attachedFile,
}) => {
  const { t } = useTranslation();
  const [stepsExpanded, setStepsExpanded] = useState(defaultStepsExpanded);
  const [elapsedTime, setElapsedTime] = useState(0);

  useEffect(() => {
    if (!isWorking || !startTime) return;

    const updateElapsed = () => {
      setElapsedTime(Date.now() - startTime);
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

  const toolParts = useMemo(() => {
    return parts.filter((p): p is ToolPart => {
      if (p.type !== 'tool') return false;
      const title = getToolTitle(p.tool);
      if (title.match(/^ReAct Round \d+$/i)) return false;
      const action = (p.state.metadata?.action as string) ?? '';
      if (action.toLowerCase() === 'terminate') return false;
      return true;
    });
  }, [parts]);

  const hasSteps = toolParts.length > 0;

  const displayStatus = useMemo(() => {
    if (currentStatus) return currentStatus;
    if (!isWorking) return null;

    const runningPart = toolParts.find(p => p.state.status === 'running');
    if (runningPart) {
      return getStatusText(runningPart.tool);
    }

    return t('thinking') || 'Thinking...';
  }, [isWorking, toolParts, currentStatus, t]);

  const formatMarkdownVal = (val: string) => {
    return val.replace(/<table(\w*=[^>]+)>/gi, '<table $1>').replace(/<tr(\w*=[^>]+)>/gi, '<tr $1>');
  };

  const getStepsButtonText = () => {
    if (isWorking) {
      return (
        <span className='flex items-center gap-2'>
          <PulseIndicator />
          <span>{displayStatus}</span>
        </span>
      );
    }
    if (stepsExpanded) return `Hide ${toolParts.length} step${toolParts.length > 1 ? 's' : ''}`;
    return `Show ${toolParts.length} step${toolParts.length > 1 ? 's' : ''}`;
  };

  const stepsAndThinking = (showSteps && (isWorking || hasSteps)) || thinkingContent;

  const stepsBlock = stepsAndThinking ? (
    <div data-slot='steps-section' className='flex flex-col'>
      {thinkingContent && (
        <div
          data-slot='thinking-content'
          className='mb-3 px-4 py-3 rounded-xl bg-gradient-to-r from-amber-50 to-orange-50 dark:from-amber-900/20 dark:to-orange-900/20 border border-amber-200/50 dark:border-amber-800/50'
        >
          <div className='flex items-center gap-2 text-amber-600 dark:text-amber-400 text-xs font-medium mb-2'>
            <Spinner className='text-amber-500' />
            <span>{t('thinking')}</span>
          </div>
          <div className='text-sm text-amber-800 dark:text-amber-200 whitespace-pre-wrap leading-relaxed'>
            {thinkingContent}
          </div>
        </div>
      )}

      {showSteps && (isWorking || hasSteps) && (
        <div className='flex flex-col'>
          <button
            data-slot='steps-trigger'
            className={classNames(
              'oc-steps-trigger',
              'flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-all duration-200',
              'bg-gray-50 hover:bg-gray-100 dark:bg-gray-800/60 dark:hover:bg-gray-700/60',
              'text-gray-600 dark:text-gray-400',
              'text-left w-auto inline-flex',
              'border border-transparent',
              isWorking && 'border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-900/20',
            )}
            onClick={() => setStepsExpanded(!stepsExpanded)}
          >
            {isWorking && <Spinner className='text-blue-500' />}
            <span className='flex-1 text-left truncate max-w-md'>{getStepsButtonText()}</span>
            {duration && (
              <>
                <span className='text-gray-400'>·</span>
                <span className='text-gray-400 tabular-nums'>{duration}</span>
              </>
            )}
            {hasSteps && !isWorking && (
              <ToolIcon
                name={stepsExpanded ? 'chevron-down' : 'chevron-right'}
                size='small'
                className='text-gray-400 transition-transform duration-200'
              />
            )}
          </button>

          {stepsExpanded && hasSteps && (
            <div
              data-slot='steps-content'
              className='mt-2 flex flex-col gap-1.5 pl-3 border-l-2 border-gray-200 dark:border-gray-700 animate-fadeIn'
            >
              {toolParts.map((part, index) => (
                <ToolPartDisplay
                  key={part.id}
                  part={part}
                  defaultOpen={
                    part.state.status === 'error' || (index === toolParts.length - 1 && part.state.status === 'running')
                  }
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  ) : null;

  return (
    <div data-component='opencode-session-turn' className={classNames('oc-session-turn', className)}>
      <div data-slot='session-turn-content' className='flex flex-col gap-4 py-4'>
        <div data-slot='user-message' className='flex gap-3 group'>
          <div className='flex-shrink-0 mt-0.5'>
            <UserIcon />
          </div>
          <div className='flex-1 min-w-0'>
            <div className='flex items-start justify-between'>
              <div className='flex-1 min-w-0'>
                {attachedFile && <FileAttachmentCard file={attachedFile} />}
                <div className='text-sm text-gray-800 dark:text-gray-200 whitespace-pre-wrap break-words leading-relaxed'>
                  {userMessage}
                </div>
                {startTime && <div className='mt-1 text-xs text-gray-400'>{formatTimestamp(startTime)}</div>}
              </div>
              <CopyButton text={userMessage} className='opacity-0 group-hover:opacity-100 ml-2' />
            </div>
          </div>
        </div>

        {(isWorking || assistantMessage || hasSteps || thinkingContent) && (
          <>
            <div data-slot='assistant-section' className='flex gap-3'>
              <div className='flex-shrink-0 mt-0.5'>
                <RobotIcon model={modelName || ''} />
              </div>
              <div className='flex-1 min-w-0 flex flex-col gap-2'>
                {stepsPlacement === 'inside' && stepsBlock}

                {assistantMessage && (
                  <div
                    data-slot='assistant-response'
                    className='group relative bg-white dark:bg-[rgba(255,255,255,0.08)] p-4 rounded-2xl rounded-tl-none shadow-sm border border-gray-100 dark:border-gray-800'
                  >
                    <div className='prose prose-sm dark:prose-invert max-w-none'>
                      <GPTVis components={markdownComponents as any} {...(markdownPlugins as any)}>
                        {preprocessLaTeX(formatMarkdownVal(assistantMessage))}
                      </GPTVis>
                    </div>
                    {endTime && (
                      <div className='mt-2 pt-2 border-t border-gray-100 dark:border-gray-700 flex items-center justify-between'>
                        <span className='text-xs text-gray-400'>
                          {formatTimestamp(endTime)}
                          {duration && <span className='ml-2'>· {duration}</span>}
                        </span>
                        <CopyButton text={assistantMessage} className='opacity-0 group-hover:opacity-100' />
                      </div>
                    )}
                    {!endTime && (
                      <div className='absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity'>
                        <CopyButton text={assistantMessage} />
                      </div>
                    )}
                  </div>
                )}

                {isWorking && !assistantMessage && !thinkingContent && (
                  <div
                    data-slot='loading-placeholder'
                    className='bg-white dark:bg-[rgba(255,255,255,0.08)] p-4 rounded-2xl rounded-tl-none border border-gray-100 dark:border-gray-800'
                  >
                    <div className='flex items-center gap-3'>
                      <ThinkingDots />
                      <span className='text-sm text-gray-500 dark:text-gray-400'>{displayStatus || t('thinking')}</span>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {stepsPlacement === 'outside' && stepsBlock && (
              <div data-slot='assistant-steps-outside' className='flex gap-3'>
                <div className='flex-shrink-0 mt-0.5 w-7' />
                <div className='flex-1 min-w-0'>{stepsBlock}</div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default memo(OpenCodeSessionTurn);
