import { ArrowDownOutlined } from '@ant-design/icons';
import classNames from 'classnames';
import React, { memo, useCallback, useEffect, useRef, useState } from 'react';
import SessionTurn, { ExecutionStep } from './content/SessionTurn';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp?: number;
  steps?: ExecutionStep[];
  isStreaming?: boolean;
  modelName?: string;
  thinkingContent?: string;
}

export interface ChatTurn {
  id: string;
  userMessage: string;
  assistantMessage?: string;
  steps?: ExecutionStep[];
  isWorking?: boolean;
  startTime?: number;
  endTime?: number;
  modelName?: string;
  thinkingContent?: string;
}

interface ChatMessageListProps {
  turns: ChatTurn[];
  isLoading?: boolean;
  onCopy?: (text: string) => void;
  showSteps?: boolean;
  className?: string;
  emptyState?: React.ReactNode;
}

const ChatMessageList: React.FC<ChatMessageListProps> = ({
  turns,
  isLoading = false,
  onCopy,
  showSteps = true,
  className,
  emptyState,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const [showScrollButton, setShowScrollButton] = useState(false);
  const userScrolledRef = useRef(false);

  const scrollToBottom = useCallback((behavior: ScrollBehavior = 'smooth') => {
    if (bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior, block: 'end' });
    }
  }, []);

  const handleScroll = useCallback(() => {
    if (!containerRef.current) return;

    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
    const threshold = 100;

    const atBottom = distanceFromBottom < threshold;
    setIsAtBottom(atBottom);
    setShowScrollButton(!atBottom && scrollHeight > clientHeight);

    if (!atBottom) {
      userScrolledRef.current = true;
    }
  }, []);

  useEffect(() => {
    if (turns.length === 0) return;

    const lastTurn = turns[turns.length - 1];
    const isStreaming = lastTurn?.isWorking;

    if (isStreaming && !userScrolledRef.current) {
      scrollToBottom('auto');
    } else if (!isStreaming && isAtBottom) {
      scrollToBottom('smooth');
      userScrolledRef.current = false;
    }
  }, [turns, isAtBottom, scrollToBottom]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    container.addEventListener('scroll', handleScroll, { passive: true });
    return () => container.removeEventListener('scroll', handleScroll);
  }, [handleScroll]);

  if (turns.length === 0 && emptyState) {
    return <>{emptyState}</>;
  }

  return (
    <div className='relative flex-1 min-h-0'>
      <div ref={containerRef} className={classNames('h-full overflow-y-auto px-4 py-6', 'oc-scrollbar', className)}>
        <div className='max-w-3xl mx-auto'>
          {turns.map(turn => (
            <div key={turn.id} className='oc-animate-fade-in border-b border-[var(--oc-border-weak)] last:border-b-0'>
              <SessionTurn
                userMessage={turn.userMessage}
                assistantMessage={turn.assistantMessage}
                steps={turn.steps}
                isWorking={turn.isWorking}
                startTime={turn.startTime}
                endTime={turn.endTime}
                onCopy={onCopy}
                showSteps={showSteps}
                modelName={turn.modelName}
                thinkingContent={turn.thinkingContent}
              />
            </div>
          ))}
          <div ref={bottomRef} className='h-px' />
        </div>
      </div>

      {showScrollButton && (
        <button
          className={classNames(
            'absolute bottom-4 right-4 flex items-center justify-center',
            'w-10 h-10 rounded-full shadow-lg',
            'bg-[var(--oc-surface-raised)] border border-[var(--oc-border-base)]',
            'text-[var(--oc-icon-base)] hover:text-[var(--oc-icon-strong)]',
            'hover:shadow-xl transition-all duration-200',
            'oc-animate-scale-in',
          )}
          onClick={() => {
            userScrolledRef.current = false;
            scrollToBottom('smooth');
          }}
        >
          <ArrowDownOutlined />
        </button>
      )}
    </div>
  );
};

export default memo(ChatMessageList);
