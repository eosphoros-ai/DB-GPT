/**
 * OpenCode Agent Content Component
 *
 * Renders chat_agent messages in OpenCode style using OpenCodeSessionTurn.
 * This component handles both:
 * 1. Historical messages (parsing ReAct format from context string)
 * 2. Streaming messages (receiving real-time updates via props)
 */

import { ChatContext } from '@/app/chat-context';
import { parseReActText } from '@/hooks/use-react-agent';
import OpenCodeSessionTurn, { MessagePart } from '@/new-components/chat/content/OpenCodeSessionTurn';
import { IChatDialogueMessageSchema } from '@/types/chat';
import { AgentCitation, decodeHistoryAnswer } from '@/utils/react-agent-final';
import classNames from 'classnames';
import { memo, useContext, useMemo } from 'react';

interface Props {
  content: IChatDialogueMessageSchema;
  /** Optional streaming parts (for real-time updates) */
  streamingParts?: MessagePart[];
  /** Optional streaming final content */
  streamingFinalContent?: string;
  /** Optional structured citations for the streaming final answer. */
  streamingCitations?: AgentCitation[];
  /** Is currently working (streaming in progress) */
  isWorking?: boolean;
  /** Start time for duration tracking */
  startTime?: number;
  /** End time for duration tracking */
  endTime?: number;
  /** Current status text */
  currentStatus?: string;
  /** Additional className */
  className?: string;
}

/**
 * Parse ReAct format text from message context
 * This handles the historical messages stored in the database
 */
function parseContextToMessageParts(context: string): {
  parts: MessagePart[];
  finalContent: string;
  citations: AgentCitation[];
} {
  if (!context || typeof context !== 'string') {
    return { parts: [], finalContent: '', citations: [] };
  }

  const historyAnswer = decodeHistoryAnswer(context);
  const cleanContext = historyAnswer.content;

  // Check if this looks like ReAct format
  const hasReActFormat =
    cleanContext.includes('Thought:') ||
    cleanContext.includes('Action:') ||
    cleanContext.includes('Action Input:') ||
    cleanContext.includes('Observation:');

  if (!hasReActFormat) {
    // Not ReAct format, return as plain text
    return { parts: [], finalContent: cleanContext, citations: historyAnswer.citations };
  }

  // Use the parseReActText function from the hook
  const parsed = parseReActText(cleanContext);
  return {
    parts: parsed.parts,
    finalContent: parsed.finalContent,
    citations: historyAnswer.citations.length > 0 ? historyAnswer.citations : parsed.citations,
  };
}

/**
 * Extract user message and assistant response from message pair
 */
function extractMessages(
  content: IChatDialogueMessageSchema,
  allMessages?: IChatDialogueMessageSchema[],
): { userMessage: string; assistantMessage: string; parts: MessagePart[]; citations: AgentCitation[] } {
  const isView = content.role === 'view';
  const context = typeof content.context === 'string' ? content.context : JSON.stringify(content.context);

  if (isView) {
    // This is an assistant message (view role)
    const { parts, finalContent, citations } = parseContextToMessageParts(context);
    const historyAnswer = decodeHistoryAnswer(context);

    // Try to find the corresponding user message
    let userMessage = '';
    if (allMessages && content.order !== undefined) {
      const humanMsg = allMessages.find(m => m.role === 'human' && m.order === content.order);
      if (humanMsg) {
        userMessage = typeof humanMsg.context === 'string' ? humanMsg.context : JSON.stringify(humanMsg.context);
      }
    }

    return {
      userMessage,
      assistantMessage: finalContent || historyAnswer.content,
      parts,
      citations: content.citations ?? citations,
    };
  } else {
    // This is a user message (human role)
    return {
      userMessage: context,
      assistantMessage: '',
      parts: [],
      citations: [],
    };
  }
}

/**
 * OpenCode Agent Content Component
 *
 * Renders agent messages with OpenCode-style tool execution visualization.
 */
function OpenCodeAgentContent({
  content,
  streamingParts,
  streamingFinalContent,
  streamingCitations,
  isWorking = false,
  startTime,
  endTime,
  currentStatus: _currentStatus,
  className,
}: Props) {
  const { model } = useContext(ChatContext);
  const isView = content.role === 'view';

  // Parse the content to get message parts
  const { userMessage, assistantMessage, parts, citations } = useMemo(() => {
    return extractMessages(content);
  }, [content]);

  // Use streaming parts if provided, otherwise use parsed parts
  const displayParts = streamingParts || parts;
  const displayFinalContent = streamingFinalContent ?? assistantMessage;
  const displayCitations = streamingCitations ?? citations;

  // Only render view messages with OpenCodeSessionTurn
  // Human messages will be rendered as part of the next view message
  if (!isView) {
    // For human messages, we just show the message simply
    // The full OpenCode turn will be rendered when the view message comes
    return (
      <div className={classNames('w-full py-2', className)}>
        <OpenCodeSessionTurn
          userMessage={userMessage}
          assistantMessage=''
          parts={[]}
          isWorking={false}
          showSteps={false}
          modelName={model}
        />
      </div>
    );
  }

  return (
    <div className={classNames('w-full', className)}>
      <OpenCodeSessionTurn
        userMessage={userMessage}
        assistantMessage={displayFinalContent}
        citations={displayCitations}
        parts={displayParts}
        isWorking={isWorking}
        startTime={startTime}
        endTime={endTime}
        showSteps={displayParts.length > 0}
        defaultStepsExpanded={false}
        modelName={model}
        stepsPlacement='outside'
      />
    </div>
  );
}

export default memo(OpenCodeAgentContent);

/**
 * OpenCode Agent Message Pair Component
 *
 * Renders a pair of user + assistant messages together as one OpenCode turn.
 * This is useful when we have both messages available.
 */
interface MessagePairProps {
  humanMessage: IChatDialogueMessageSchema;
  viewMessage: IChatDialogueMessageSchema;
  streamingParts?: MessagePart[];
  streamingFinalContent?: string;
  streamingCitations?: AgentCitation[];
  isWorking?: boolean;
  startTime?: number;
  endTime?: number;
  className?: string;
}

export const OpenCodeAgentMessagePair = memo(function OpenCodeAgentMessagePair({
  humanMessage,
  viewMessage,
  streamingParts,
  streamingFinalContent,
  streamingCitations,
  isWorking = false,
  startTime,
  endTime,
  className,
}: MessagePairProps) {
  const { model } = useContext(ChatContext);

  // Get user message content
  const userMessage = useMemo(() => {
    const ctx = humanMessage.context;
    return typeof ctx === 'string' ? ctx : JSON.stringify(ctx);
  }, [humanMessage]);

  // Parse view message
  const { parts, finalContent, citations } = useMemo(() => {
    const ctx = viewMessage.context;
    const contextStr = typeof ctx === 'string' ? ctx : JSON.stringify(ctx);
    return parseContextToMessageParts(contextStr);
  }, [viewMessage]);

  // Use streaming data if provided
  const displayParts = streamingParts || parts;
  const displayFinalContent = streamingFinalContent ?? finalContent;
  const displayCitations = streamingCitations ?? viewMessage.citations ?? citations;

  return (
    <div className={classNames('w-full', className)}>
      <OpenCodeSessionTurn
        userMessage={userMessage}
        assistantMessage={displayFinalContent}
        citations={displayCitations}
        parts={displayParts}
        isWorking={isWorking}
        startTime={startTime}
        endTime={endTime}
        showSteps={displayParts.length > 0}
        defaultStepsExpanded={false}
        modelName={model}
        stepsPlacement='outside'
      />
    </div>
  );
});

/**
 * Hook to group messages into pairs for OpenCode rendering
 */
export function useGroupedMessages(
  messages: IChatDialogueMessageSchema[],
): Array<{ human?: IChatDialogueMessageSchema; view?: IChatDialogueMessageSchema }> {
  return useMemo(() => {
    const groups: Array<{ human?: IChatDialogueMessageSchema; view?: IChatDialogueMessageSchema }> = [];

    let currentGroup: { human?: IChatDialogueMessageSchema; view?: IChatDialogueMessageSchema } = {};

    for (const msg of messages) {
      if (msg.role === 'human') {
        // Start a new group with human message
        if (currentGroup.human || currentGroup.view) {
          groups.push(currentGroup);
        }
        currentGroup = { human: msg };
      } else if (msg.role === 'view') {
        // Add view to current group
        currentGroup.view = msg;
        groups.push(currentGroup);
        currentGroup = {};
      }
    }

    // Don't forget the last group if it has content
    if (currentGroup.human || currentGroup.view) {
      groups.push(currentGroup);
    }

    return groups;
  }, [messages]);
}
