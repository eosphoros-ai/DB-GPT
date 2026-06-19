import {
  BulbOutlined,
  CheckOutlined,
  CopyOutlined,
  EyeOutlined,
  ThunderboltOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import { Tooltip, message } from 'antd';
import classNames from 'classnames';
import React, { useMemo } from 'react';

export interface ReActSection {
  type: 'thought' | 'action' | 'action_input' | 'observation' | 'error' | 'text';
  content: string;
  actionName?: string;
}

export interface ReActThinkingProps {
  content: string;
  round?: number;
  showCopy?: boolean;
  className?: string;
  compact?: boolean;
}

export function parseReActContent(content: string): ReActSection[] {
  if (!content || typeof content !== 'string') return [];

  const sections: ReActSection[] = [];

  const normalizedContent = content.replace(/\r\n/g, '\n').replace(/\r/g, '\n');

  const sectionPatterns = [
    { type: 'thought' as const, pattern: /(?:^|\n)(?:Thought|\u601d\u8003|💭)\s*[:：]\s*/gi },
    { type: 'action' as const, pattern: /(?:^|\n)(?:Action|\u52a8\u4f5c|⚡)\s*[:：]\s*/gi },
    {
      type: 'action_input' as const,
      pattern: /(?:^|\n)(?:Action Input|Action_Input|ActionInput|\u52a8\u4f5c\u8f93\u5165|\u8f93\u5165)\s*[:：]\s*/gi,
    },
    { type: 'observation' as const, pattern: /(?:^|\n)(?:Observation|\u89c2\u5bdf|\u89c2\u5bdf\u7ed3\u679c|👁)\s*[:：]\s*/gi },
  ];

  const matches: { type: ReActSection['type']; index: number; length: number }[] = [];

  for (const { type, pattern } of sectionPatterns) {
    let match;
    const regex = new RegExp(pattern.source, pattern.flags);
    while ((match = regex.exec(normalizedContent)) !== null) {
      matches.push({
        type,
        index: match.index,
        length: match[0].length,
      });
    }
  }

  matches.sort((a, b) => a.index - b.index);

  if (matches.length === 0) {
    const errorPatterns = [/error/i, /failed/i, /exception/i, /traceback/i];

    const isError = errorPatterns.some(p => p.test(normalizedContent));

    return [
      {
        type: isError ? 'error' : 'text',
        content: normalizedContent.trim(),
      },
    ];
  }

  if (matches[0].index > 0) {
    const leadingText = normalizedContent.substring(0, matches[0].index).trim();
    if (leadingText) {
      sections.push({ type: 'text', content: leadingText });
    }
  }

  for (let i = 0; i < matches.length; i++) {
    const current = matches[i];
    const next = matches[i + 1];

    const startIndex = current.index + current.length;
    const endIndex = next ? next.index : normalizedContent.length;

    let sectionContent = normalizedContent.substring(startIndex, endIndex).trim();

    let actionName: string | undefined;
    if (current.type === 'action') {
      const pipeIndex = sectionContent.indexOf('|');
      if (pipeIndex > 0) {
        actionName = sectionContent.substring(0, pipeIndex).trim();
        sectionContent = sectionContent.substring(pipeIndex + 1).trim();
      } else {
        const firstLineEnd = sectionContent.indexOf('\n');
        if (firstLineEnd > 0) {
          actionName = sectionContent.substring(0, firstLineEnd).trim();
          sectionContent = sectionContent.substring(firstLineEnd + 1).trim();
        } else {
          actionName = sectionContent;
          sectionContent = '';
        }
      }
    }

    if (sectionContent || actionName) {
      sections.push({
        type: current.type,
        content: sectionContent,
        actionName,
      });
    }
  }

  return sections;
}

function getSectionIcon(type: ReActSection['type']) {
  switch (type) {
    case 'thought':
      return <BulbOutlined className='text-amber-500' />;
    case 'action':
      return <ThunderboltOutlined className='text-blue-500' />;
    case 'action_input':
      return <ThunderboltOutlined className='text-slate-500' />;
    case 'observation':
      return <EyeOutlined className='text-emerald-500' />;
    case 'error':
      return <WarningOutlined className='text-red-500' />;
    default:
      return null;
  }
}

function getSectionTitle(type: ReActSection['type'], actionName?: string): string {
  switch (type) {
    case 'thought':
      return 'Thought';
    case 'action':
      return actionName ? `Action: ${actionName}` : 'Action';
    case 'action_input':
      return 'Action Input';
    case 'observation':
      return 'Observation';
    case 'error':
      return 'Error';
    default:
      return '';
  }
}

function getSectionStyles(type: ReActSection['type']) {
  switch (type) {
    case 'thought':
      return {
        container: 'bg-amber-50 dark:bg-amber-900/20 border-l-4 border-amber-400 dark:border-amber-500',
        header: 'text-amber-700 dark:text-amber-400',
        content: 'text-amber-900 dark:text-amber-200',
      };
    case 'action':
      return {
        container: 'bg-blue-50 dark:bg-blue-900/20 border-l-4 border-blue-400 dark:border-blue-500',
        header: 'text-blue-700 dark:text-blue-400',
        content: 'text-blue-900 dark:text-blue-200',
      };
    case 'action_input':
      return {
        container: 'bg-slate-100 dark:bg-slate-800/50 border-l-4 border-slate-400 dark:border-slate-500',
        header: 'text-slate-600 dark:text-slate-400',
        content: 'text-slate-800 dark:text-slate-200',
      };
    case 'observation':
      return {
        container: 'bg-emerald-50 dark:bg-emerald-900/20 border-l-4 border-emerald-400 dark:border-emerald-500',
        header: 'text-emerald-700 dark:text-emerald-400',
        content: 'text-emerald-900 dark:text-emerald-200',
      };
    case 'error':
      return {
        container: 'bg-red-50 dark:bg-red-900/20 border-l-4 border-red-400 dark:border-red-500',
        header: 'text-red-700 dark:text-red-400',
        content: 'text-red-800 dark:text-red-300',
      };
    default:
      return {
        container: 'bg-gray-50 dark:bg-gray-800/50 border-l-4 border-gray-300 dark:border-gray-600',
        header: 'text-gray-600 dark:text-gray-400',
        content: 'text-gray-800 dark:text-gray-200',
      };
  }
}

function isJsonContent(content: string): boolean {
  const trimmed = content.trim();
  return (trimmed.startsWith('{') && trimmed.endsWith('}')) || (trimmed.startsWith('[') && trimmed.endsWith(']'));
}

function formatAndHighlightJson(content: string): React.ReactNode {
  try {
    const parsed = JSON.parse(content);
    const formatted = JSON.stringify(parsed, null, 2);
    return highlightJson(formatted);
  } catch {
    return highlightJson(content);
  }
}

function highlightJson(jsonString: string): React.ReactNode {
  const lines = jsonString.split('\n');

  return (
    <div className='font-mono text-xs leading-relaxed'>
      {lines.map((line, lineIndex) => {
        const tokens: React.ReactNode[] = [];
        let remaining = line;
        let keyIndex = 0;

        const addToken = (text: string, className: string) => {
          if (text) {
            tokens.push(
              <span key={`${lineIndex}-${keyIndex++}`} className={className}>
                {text}
              </span>,
            );
          }
        };

        const indentMatch = remaining.match(/^(\s*)/);
        if (indentMatch && indentMatch[1]) {
          addToken(indentMatch[1], '');
          remaining = remaining.substring(indentMatch[1].length);
        }

        while (remaining.length > 0) {
          const keyMatch = remaining.match(/^"([^"\\]|\\.)*"\s*:/);
          if (keyMatch) {
            const colonIndex = keyMatch[0].lastIndexOf(':');
            const keyPart = keyMatch[0].substring(0, colonIndex);
            addToken(keyPart, 'text-purple-600 dark:text-purple-400');
            addToken(':', 'text-gray-500 dark:text-gray-400');
            remaining = remaining.substring(keyMatch[0].length);
            continue;
          }

          const stringMatch = remaining.match(/^"([^"\\]|\\.)*"/);
          if (stringMatch) {
            addToken(stringMatch[0], 'text-green-600 dark:text-green-400');
            remaining = remaining.substring(stringMatch[0].length);
            continue;
          }

          const numberMatch = remaining.match(/^-?\d+\.?\d*([eE][+-]?\d+)?/);
          if (numberMatch) {
            addToken(numberMatch[0], 'text-blue-600 dark:text-blue-400');
            remaining = remaining.substring(numberMatch[0].length);
            continue;
          }

          const boolNullMatch = remaining.match(/^(true|false|null)/);
          if (boolNullMatch) {
            addToken(boolNullMatch[0], 'text-orange-600 dark:text-orange-400');
            remaining = remaining.substring(boolNullMatch[0].length);
            continue;
          }

          const bracketMatch = remaining.match(/^[{}\[\]]/);
          if (bracketMatch) {
            addToken(bracketMatch[0], 'text-gray-700 dark:text-gray-300 font-semibold');
            remaining = remaining.substring(1);
            continue;
          }

          const punctMatch = remaining.match(/^[,:\s]+/);
          if (punctMatch) {
            addToken(punctMatch[0], 'text-gray-500 dark:text-gray-400');
            remaining = remaining.substring(punctMatch[0].length);
            continue;
          }

          addToken(remaining[0], 'text-gray-700 dark:text-gray-300');
          remaining = remaining.substring(1);
        }

        return (
          <div key={lineIndex} className='min-h-[1.25em]'>
            {tokens.length > 0 ? tokens : '\u00A0'}
          </div>
        );
      })}
    </div>
  );
}

function formatContent(content: string, isCode: boolean): string {
  if (!content) return '';

  if (isCode) {
    return content.trim();
  }

  const lines = content.split('\n');

  const nonEmptyLines = lines.filter(l => l.trim().length > 0);
  if (nonEmptyLines.length === 0) return '';

  const avgLineLength = nonEmptyLines.reduce((sum, line) => sum + line.trim().length, 0) / nonEmptyLines.length;
  const shortLineRatio = nonEmptyLines.filter(l => l.trim().length < 10).length / nonEmptyLines.length;

  const looksLikeWordSplit =
    avgLineLength < 8 && shortLineRatio > 0.7 && !content.includes('{') && !content.includes('[');

  if (looksLikeWordSplit) {
    return content
      .replace(/\n\n+/g, '{{PARAGRAPH}}')
      .replace(/\n/g, ' ')
      .replace(/\s+/g, ' ')
      .replace(/{{PARAGRAPH}}/g, '\n\n')
      .trim();
  }

  return content.trim();
}

const CopyButton: React.FC<{ text: string }> = ({ text }) => {
  const [copied, setCopied] = React.useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      message.success('Copied!');
      setTimeout(() => setCopied(false), 2000);
    } catch {
      message.error('Failed to copy');
    }
  };

  return (
    <Tooltip title={copied ? 'Copied!' : 'Copy'}>
      <button
        onClick={handleCopy}
        className='p-1.5 rounded-md hover:bg-black/5 dark:hover:bg-white/10 transition-colors'
      >
        {copied ? (
          <CheckOutlined className='text-green-500 text-xs' />
        ) : (
          <CopyOutlined className='text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-xs' />
        )}
      </button>
    </Tooltip>
  );
};

const ReActSectionDisplay: React.FC<{
  section: ReActSection;
  compact?: boolean;
  showCopy?: boolean;
}> = ({ section, compact, showCopy = true }) => {
  const styles = getSectionStyles(section.type);
  const title = getSectionTitle(section.type, section.actionName);
  const icon = getSectionIcon(section.type);

  const isCode = section.type === 'action_input' && isJsonContent(section.content);
  const formattedContent = useMemo(() => formatContent(section.content, isCode), [section.content, isCode]);

  if (section.type === 'text') {
    return <div className='text-sm text-gray-700 dark:text-gray-300 leading-relaxed'>{formattedContent}</div>;
  }

  if (section.type === 'thought') {
    return (
      <div className='text-sm text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-wrap'>
        {formattedContent}
      </div>
    );
  }

  return (
    <div className={classNames('rounded-lg overflow-hidden transition-all', styles.container, compact ? 'p-2' : 'p-3')}>
      <div className='flex items-center justify-between gap-2 mb-2'>
        <div
          className={classNames('flex items-center gap-2 font-semibold text-xs uppercase tracking-wide', styles.header)}
        >
          {icon}
          <span>{title}</span>
        </div>
        {showCopy && formattedContent && <CopyButton text={section.content} />}
      </div>

      {formattedContent && (
        <div className={classNames('rounded-md', isCode ? 'bg-white/50 dark:bg-black/20 p-3 overflow-x-auto' : '')}>
          {isCode ? (
            formatAndHighlightJson(section.content)
          ) : (
            <div
              className={classNames(
                'leading-relaxed whitespace-pre-wrap',
                styles.content,
                compact ? 'text-xs' : 'text-sm',
              )}
            >
              {formattedContent}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export const ReActThinking: React.FC<ReActThinkingProps> = ({
  content,
  round,
  showCopy = true,
  className,
  compact = false,
}) => {
  const sections = useMemo(() => parseReActContent(content), [content]);

  const thoughtSections = sections.filter(s => s.type === 'thought');

  if (!thoughtSections.length) {
    return null;
  }

  return (
    <div className={classNames('react-thinking', className)}>
      {round !== undefined && (
        <div className='flex items-center gap-2 mb-3'>
          <div className='h-px flex-1 bg-gradient-to-r from-transparent via-gray-300 dark:via-gray-600 to-transparent' />
          <span className='text-xs font-medium text-gray-500 dark:text-gray-400 px-2'>Round {round}</span>
          <div className='h-px flex-1 bg-gradient-to-l from-transparent via-gray-300 dark:via-gray-600 to-transparent' />
        </div>
      )}

      <div className={classNames('space-y-3', compact && 'space-y-2')}>
        {thoughtSections.map((section, index) => (
          <ReActSectionDisplay
            key={`${section.type}-${index}`}
            section={section}
            compact={compact}
            showCopy={showCopy}
          />
        ))}
      </div>
    </div>
  );
};

export interface ErrorDisplayProps {
  error: string;
  toolName?: string;
  className?: string;
  showRetry?: boolean;
  onRetry?: () => void;
}

export const ErrorDisplay: React.FC<ErrorDisplayProps> = ({ error, toolName, className, showRetry, onRetry }) => {
  const parsedError = useMemo(() => {
    const patterns = [/(?:Error|Exception):\s*(.+)/i, /Tool \[([^\]]+)\] execute failed!\s*(.+)/i, /failed[:\s]+(.+)/i];

    for (const pattern of patterns) {
      const match = error.match(pattern);
      if (match) {
        return {
          summary: match[1] || match[2] || error,
          details: error,
        };
      }
    }

    return {
      summary: error.length > 100 ? error.substring(0, 100) + '...' : error,
      details: error,
    };
  }, [error]);

  const [showDetails, setShowDetails] = React.useState(false);

  return (
    <div
      className={classNames(
        'rounded-lg border-l-4 border-red-400 dark:border-red-500',
        'bg-red-50 dark:bg-red-900/20',
        'overflow-hidden',
        className,
      )}
    >
      <div className='px-3 py-2 flex items-start gap-2'>
        <WarningOutlined className='text-red-500 mt-0.5 flex-shrink-0' />
        <div className='flex-1 min-w-0'>
          <div className='flex items-center gap-2'>
            <span className='text-sm font-medium text-red-700 dark:text-red-400'>
              {toolName ? `${toolName} Failed` : 'Error'}
            </span>
          </div>
          <p className='text-sm text-red-600 dark:text-red-300 mt-0.5'>{parsedError.summary}</p>

          {parsedError.details !== parsedError.summary && (
            <button
              onClick={() => setShowDetails(!showDetails)}
              className='text-xs text-red-500 hover:text-red-600 dark:text-red-400 dark:hover:text-red-300 mt-1 underline'
            >
              {showDetails ? 'Hide details' : 'Show details'}
            </button>
          )}
        </div>

        <div className='flex items-center gap-1 flex-shrink-0'>
          <CopyButton text={error} />
          {showRetry && onRetry && (
            <Tooltip title='Retry'>
              <button
                onClick={onRetry}
                className='p-1 rounded hover:bg-red-100 dark:hover:bg-red-800/50 transition-colors text-red-500'
              >
                <svg className='w-4 h-4' fill='none' viewBox='0 0 24 24' stroke='currentColor'>
                  <path
                    strokeLinecap='round'
                    strokeLinejoin='round'
                    strokeWidth={2}
                    d='M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15'
                  />
                </svg>
              </button>
            </Tooltip>
          )}
        </div>
      </div>

      {showDetails && (
        <div className='px-3 py-2 bg-red-100/50 dark:bg-red-900/30 border-t border-red-200 dark:border-red-800/50'>
          <pre className='text-xs text-red-700 dark:text-red-300 whitespace-pre-wrap break-words font-mono'>
            {parsedError.details}
          </pre>
        </div>
      )}
    </div>
  );
};

export default ReActThinking;
