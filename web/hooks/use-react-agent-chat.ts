/**
 * useReActAgentChat Hook
 *
 * Integrates the ReAct Agent API with the chat flow.
 * Manages streaming state, history updates, and message formatting.
 */

import { MessagePart, ToolPart } from '@/new-components/chat/content/OpenCodeSessionTurn';
import { ChatHistoryResponse } from '@/types/chat';
import {
  ContextStatus,
  ReActSSEState,
  SSEQuestionAskedEvent,
  createReActSSEState,
  parseSSELine,
} from '@/utils/react-sse-parser';
import { useCallback, useEffect, useRef, useState } from 'react';

export interface ReActChatRequest {
  user_input: string;
  conv_uid: string;
  chat_mode?: string;
  model_name?: string;
  app_code?: string;
  temperature?: number;
  max_new_tokens?: number;
  select_param?: string;
  [key: string]: any;
}

export interface StreamingTurn {
  userMessage: string;
  parts: MessagePart[];
  finalContent: string;
  isWorking: boolean;
  startTime: number;
  endTime?: number;
  currentStatus: string;
  thinkingContent?: string;
  contextStatus?: ContextStatus | null;
}

export interface UseReActAgentChatOptions {
  baseUrl?: string;
  onHistoryUpdate?: (history: ChatHistoryResponse) => void;
  onError?: (error: string) => void;
  onComplete?: () => void;
}

export interface UseReActAgentChatReturn {
  streamingTurn: StreamingTurn | null;
  isStreaming: boolean;
  contextStatus: ContextStatus | null;
  pendingQuestion: SSEQuestionAskedEvent | null;
  sendMessage: (
    request: ReActChatRequest,
    currentHistory: ChatHistoryResponse,
    order: number,
  ) => Promise<ChatHistoryResponse>;
  cancel: () => void;
  replyQuestion: (requestId: string, answers: string[][]) => Promise<void>;
  rejectQuestion: (requestId: string) => Promise<void>;
}

export function useReActAgentChat(options: UseReActAgentChatOptions = {}): UseReActAgentChatReturn {
  const { baseUrl = '/api/v1/chat/react-agent', onHistoryUpdate, onError, onComplete } = options;

  const [streamingTurn, setStreamingTurn] = useState<StreamingTurn | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [contextStatus, setContextStatus] = useState<ContextStatus | null>(null);
  const [pendingQuestion, setPendingQuestion] = useState<SSEQuestionAskedEvent | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const sseStateRef = useRef<ReActSSEState | null>(null);
  const readerRef = useRef<ReadableStreamDefaultReader<Uint8Array> | null>(null);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cancel();
    };
  }, []);

  const cancel = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    if (readerRef.current) {
      readerRef.current.cancel();
      readerRef.current = null;
    }
    setIsStreaming(false);
    setStreamingTurn(prev => {
      if (prev) {
        return { ...prev, isWorking: false, endTime: Date.now() };
      }
      return null;
    });
  }, []);

  const processSSELine = useCallback((line: string) => {
    if (!sseStateRef.current) return;

    const event = parseSSELine(line);
    if (!event) return;

    sseStateRef.current.processEvent(event);

    // Update streaming turn state
    const parts = sseStateRef.current.toMessageParts();
    const finalContent = sseStateRef.current.getFinalContent();
    const isWorking = sseStateRef.current.isWorking();
    const currentStatus = sseStateRef.current.getCurrentStatus();

    // Extract thinking content from reasoning parts
    const reasoningParts = parts.filter(p => p.type === 'reasoning');
    const thinkingContent = reasoningParts.length > 0 ? reasoningParts.map(p => (p as any).text).join('\n') : undefined;

    // Get context budget status and promote to independent state
    const latestContextStatus = sseStateRef.current.getContextStatus();
    if (latestContextStatus) {
      setContextStatus(latestContextStatus);
    }

    // Update pending question state
    const latestQuestion = sseStateRef.current.getPendingQuestion();
    setPendingQuestion(latestQuestion);

    setStreamingTurn(prev => {
      if (!prev) return null;
      return {
        ...prev,
        parts,
        finalContent,
        isWorking,
        currentStatus,
        thinkingContent,
        contextStatus: latestContextStatus,
        endTime: sseStateRef.current?.isComplete() ? sseStateRef.current.getEndTime() : undefined,
      };
    });
  }, []);

  const sendMessage = useCallback(
    async (
      request: ReActChatRequest,
      currentHistory: ChatHistoryResponse,
      order: number,
    ): Promise<ChatHistoryResponse> => {
      // Cancel any existing request
      cancel();

      // Initialize state
      sseStateRef.current = createReActSSEState();
      abortControllerRef.current = new AbortController();
      setIsStreaming(true);
      setContextStatus(null);

      const userMessage =
        typeof request.user_input === 'string' ? request.user_input : JSON.stringify(request.user_input);

      // Initialize streaming turn
      const startTime = Date.now();
      setStreamingTurn({
        userMessage,
        parts: [],
        finalContent: '',
        isWorking: true,
        startTime,
        currentStatus: 'Starting...',
      });

      // Add human message to history immediately
      const tempHistory: ChatHistoryResponse = [
        ...currentHistory,
        {
          role: 'human',
          context: userMessage,
          model_name: request.model_name || '',
          order: order,
          time_stamp: startTime,
        },
        {
          role: 'view',
          context: '',
          model_name: request.model_name || '',
          order: order,
          time_stamp: startTime,
          thinking: true,
        },
      ];

      if (onHistoryUpdate) {
        onHistoryUpdate(tempHistory);
      }

      try {
        const response = await fetch(baseUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'text/event-stream',
          },
          body: JSON.stringify(request),
          signal: abortControllerRef.current.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        if (!response.body) {
          throw new Error('Response body is null');
        }

        const reader = response.body.getReader();
        readerRef.current = reader;
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();

          if (done) {
            // Process any remaining buffer
            if (buffer.trim()) {
              const lines = buffer.split('\n');
              for (const line of lines) {
                if (line.trim()) {
                  processSSELine(line.trim());
                }
              }
            }
            break;
          }

          // Decode chunk and add to buffer
          buffer += decoder.decode(value, { stream: true });

          // Process complete lines
          const lines = buffer.split('\n');
          buffer = lines.pop() || ''; // Keep incomplete line in buffer

          for (const line of lines) {
            const trimmedLine = line.trim();
            if (trimmedLine) {
              processSSELine(trimmedLine);
            }
          }
        }

        // Get final state
        const finalParts = sseStateRef.current?.toMessageParts() || [];
        const finalContent = sseStateRef.current?.getFinalContent() || '';

        // Format final response for history
        // Combine tool parts and final content into a structured response
        const formattedResponse = formatReActResponse(finalParts, finalContent);

        // Update final history
        const finalHistory: ChatHistoryResponse = [
          ...currentHistory,
          {
            role: 'human',
            context: userMessage,
            model_name: request.model_name || '',
            order: order,
            time_stamp: startTime,
          },
          {
            role: 'view',
            context: formattedResponse,
            model_name: request.model_name || '',
            order: order,
            time_stamp: Date.now(),
            thinking: false,
          },
        ];

        // Clear streaming turn after a brief delay
        setTimeout(() => {
          setStreamingTurn(null);
          setIsStreaming(false);
        }, 300);

        if (onHistoryUpdate) {
          onHistoryUpdate(finalHistory);
        }

        if (onComplete) {
          onComplete();
        }

        return finalHistory;
      } catch (error: any) {
        if (error.name === 'AbortError') {
          // Request was cancelled
          return tempHistory;
        }

        const errorMessage = error.message || 'Unknown error occurred';

        setStreamingTurn(prev => {
          if (prev) {
            return { ...prev, isWorking: false, endTime: Date.now() };
          }
          return null;
        });
        setIsStreaming(false);

        // Update history with error
        const errorHistory: ChatHistoryResponse = [
          ...currentHistory,
          {
            role: 'human',
            context: userMessage,
            model_name: request.model_name || '',
            order: order,
            time_stamp: startTime,
          },
          {
            role: 'view',
            context: `Error: ${errorMessage}`,
            model_name: request.model_name || '',
            order: order,
            time_stamp: Date.now(),
            thinking: false,
          },
        ];

        if (onHistoryUpdate) {
          onHistoryUpdate(errorHistory);
        }

        if (onError) {
          onError(errorMessage);
        }

        return errorHistory;
      }
    },
    [baseUrl, cancel, processSSELine, onHistoryUpdate, onError, onComplete],
  );

  const replyQuestion = useCallback(async (requestId: string, answers: string[][]) => {
    try {
      const res = await fetch(`/api/v1/chat/question/${requestId}/reply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answers }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setPendingQuestion(null);
    } catch (e) {
      console.error('replyQuestion failed:', e);
    }
  }, []);

  const rejectQuestion = useCallback(async (requestId: string) => {
    try {
      const res = await fetch(`/api/v1/chat/question/${requestId}/reject`, {
        method: 'POST',
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setPendingQuestion(null);
    } catch (e) {
      console.error('rejectQuestion failed:', e);
    }
  }, []);

  return {
    streamingTurn,
    isStreaming,
    contextStatus,
    pendingQuestion,
    sendMessage,
    cancel,
    replyQuestion,
    rejectQuestion,
  };
}

/**
 * Format ReAct response parts into a storable string format
 * This preserves tool execution info in a parseable format
 */
function formatReActResponse(parts: MessagePart[], finalContent: string): string {
  const toolParts = parts.filter(p => p.type === 'tool') as ToolPart[];

  if (toolParts.length === 0) {
    return finalContent;
  }

  // Format as ReAct-style text that can be parsed later
  let formatted = '';
  let stepNum = 0;

  for (const part of parts) {
    if (part.type === 'reasoning') {
      formatted += `Thought: ${(part as any).text}\n`;
    } else if (part.type === 'tool') {
      const tool = part as ToolPart;
      stepNum++;
      const action = tool.state.metadata?.action || tool.tool;
      formatted += `Action: ${action}\n`;
      if (tool.state.input) {
        formatted += `Action Input: ${JSON.stringify(tool.state.input)}\n`;
      }
      if (tool.state.output) {
        formatted += `Observation: ${tool.state.output}\n`;
      }
      if (tool.state.error) {
        formatted += `Error: ${tool.state.error}\n`;
      }
    }
  }

  if (finalContent) {
    formatted += `\nFinal Answer: ${finalContent}`;
  }

  return formatted || finalContent;
}

export default useReActAgentChat;
