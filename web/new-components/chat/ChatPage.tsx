import classNames from 'classnames';
import React, { memo, useCallback, useMemo, useRef } from 'react';
import ChatHeader from './ChatHeader';
import ChatMessageList, { ChatTurn } from './ChatMessageList';
import ChatWelcome from './ChatWelcome';
import QuestionDock, { QuestionRequest } from './content/QuestionDock';
import { SlashCommand } from './input/CommandPopover';
import { ContentPart } from './input/EnhancedChatInput';
import StandaloneChatInput, { StandaloneChatInputRef } from './input/StandaloneChatInput';

export interface ChatPageProps {
  turns: ChatTurn[];
  isLoading?: boolean;
  modelName?: string;
  title?: string;

  onSendMessage?: (text: string, parts: ContentPart[]) => void;
  onNewChat?: () => void;
  onOpenSettings?: () => void;
  onStopGeneration?: () => void;

  agents?: Array<{ name: string; description?: string }>;
  commands?: SlashCommand[];
  onFileSearch?: (query: string) => Promise<string[]>;
  onCommandSelect?: (command: SlashCommand) => void;

  disabled?: boolean;
  inputPlaceholder?: string;
  showSteps?: boolean;

  pendingQuestion?: QuestionRequest | null;
  onReplyQuestion?: (requestId: string, answers: string[][]) => void;
  onRejectQuestion?: (requestId: string) => void;

  headerExtra?: React.ReactNode;
  welcomeExtra?: React.ReactNode;
  inputExtra?: React.ReactNode;

  className?: string;
}

const ChatPage: React.FC<ChatPageProps> = ({
  turns,
  isLoading = false,
  modelName,
  title,

  onSendMessage,
  onNewChat,
  onOpenSettings,
  onStopGeneration,

  agents = [],
  commands = [],
  onFileSearch,
  onCommandSelect,

  disabled = false,
  inputPlaceholder,
  showSteps = true,

  pendingQuestion,
  onReplyQuestion,
  onRejectQuestion,

  headerExtra,
  welcomeExtra,
  inputExtra,

  className,
}) => {
  const inputRef = useRef<StandaloneChatInputRef>(null);

  const isEmpty = turns.length === 0;

  const isStreaming = useMemo(() => {
    if (turns.length === 0) return false;
    return turns[turns.length - 1]?.isWorking ?? false;
  }, [turns]);

  const handleSubmit = useCallback(
    (text: string, parts: ContentPart[]) => {
      if (!text.trim() && parts.filter(p => p.type === 'image').length === 0) return;
      onSendMessage?.(text, parts);
    },
    [onSendMessage],
  );

  const handleStop = useCallback(() => {
    onStopGeneration?.();
  }, [onStopGeneration]);

  const handleCopy = useCallback((text: string) => {
    navigator.clipboard.writeText(text);
  }, []);

  const handleSuggestionClick = useCallback((suggestion: { title: string }) => {
    if (inputRef.current) {
      inputRef.current.focus();
    }
  }, []);

  return (
    <div className={classNames('flex flex-col h-full', 'bg-[var(--oc-background-base)]', className)}>
      <ChatHeader
        title={title}
        modelName={modelName}
        onNewChat={onNewChat}
        onOpenSettings={onOpenSettings}
        extra={headerExtra}
      />

      <main className='flex-1 flex flex-col min-h-0 overflow-hidden'>
        {isEmpty ? (
          <ChatWelcome onSuggestionClick={handleSuggestionClick} className='flex-1'>
            {welcomeExtra}
          </ChatWelcome>
        ) : (
          <ChatMessageList
            turns={turns}
            isLoading={isLoading}
            onCopy={handleCopy}
            showSteps={showSteps}
            className='flex-1'
          />
        )}

        <div className='flex-shrink-0'>
          {pendingQuestion && onReplyQuestion && onRejectQuestion && (
            <div className='mx-auto max-w-3xl px-4 pt-2'>
              <QuestionDock
                request={pendingQuestion}
                onReply={onReplyQuestion}
                onReject={onRejectQuestion}
              />
            </div>
          )}
          <StandaloneChatInput
            ref={inputRef}
            onSubmit={handleSubmit}
            onStop={handleStop}
            disabled={disabled}
            loading={isStreaming}
            placeholder={inputPlaceholder}
            agents={agents}
            commands={commands}
            onFileSearch={onFileSearch}
            onCommandSelect={onCommandSelect}
            className='border-t border-[var(--oc-border-weak)]'
          >
            {inputExtra}
          </StandaloneChatInput>
        </div>
      </main>
    </div>
  );
};

export default memo(ChatPage);
