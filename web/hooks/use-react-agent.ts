/**
 * useReActAgent Hook
 *
 * Custom React hook for interacting with the DB-GPT ReAct Agent API.
 * Handles SSE streaming and converts events to OpenCode MessagePart format.
 */

import { MessagePart, ReasoningPart, ToolPart } from '@/new-components/chat/content/OpenCodeSessionTurn';
import { ReActSSEState, SSEQuestionAskedEvent, createReActSSEState, parseSSELine } from '@/utils/react-sse-parser';
import { useCallback, useEffect, useRef, useState } from 'react';

export interface ReActAgentRequest {
  user_input: string;
  conv_uid?: string;
  chat_mode?: string;
  model_name?: string;
  select_param?: string;
  temperature?: number;
  ext_info?: Record<string, any>;
}

export interface ReActAgentState {
  isWorking: boolean;
  parts: MessagePart[];
  finalContent: string;
  error: string | null;
  startTime: number | null;
  endTime: number | null;
  currentStatus: string;
}

export interface UseReActAgentOptions {
  baseUrl?: string;
  onPartUpdate?: (parts: MessagePart[]) => void;
  onFinalContent?: (content: string) => void;
  onError?: (error: string) => void;
  onComplete?: () => void;
}

export interface UseReActAgentReturn {
  state: ReActAgentState;
  pendingQuestion: SSEQuestionAskedEvent | null;
  sendMessage: (request: ReActAgentRequest) => Promise<void>;
  cancel: () => void;
  reset: () => void;
  replyQuestion: (requestId: string, answers: string[][]) => Promise<void>;
  rejectQuestion: (requestId: string) => Promise<void>;
}

const initialState: ReActAgentState = {
  isWorking: false,
  parts: [],
  finalContent: '',
  error: null,
  startTime: null,
  endTime: null,
  currentStatus: '',
};

export function useReActAgent(options: UseReActAgentOptions = {}): UseReActAgentReturn {
  const { baseUrl = '/api/v1/chat/react-agent', onPartUpdate, onFinalContent, onError, onComplete } = options;

  const [state, setState] = useState<ReActAgentState>(initialState);
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
    setState(prev => ({
      ...prev,
      isWorking: false,
      endTime: Date.now(),
    }));
  }, []);

  const reset = useCallback(() => {
    cancel();
    setState(initialState);
    sseStateRef.current = null;
  }, [cancel]);

  const processSSELine = useCallback(
    (line: string) => {
      if (!sseStateRef.current) return;

      const event = parseSSELine(line);
      if (!event) return;

      sseStateRef.current.processEvent(event);

      // Update pending question state
      const latestQuestion = sseStateRef.current.getPendingQuestion();
      setPendingQuestion(latestQuestion);

      // Update React state
      const parts = sseStateRef.current.toMessageParts();
      const finalContent = sseStateRef.current.getFinalContent();
      const isWorking = sseStateRef.current.isWorking();
      const currentStatus = sseStateRef.current.getCurrentStatus();

      setState(prev => ({
        ...prev,
        parts,
        finalContent,
        isWorking,
        currentStatus,
        endTime: sseStateRef.current?.isComplete() ? (sseStateRef.current.getEndTime() ?? null) : null,
      }));

      // Trigger callbacks
      if (onPartUpdate) {
        onPartUpdate(parts);
      }

      if (event.type === 'final' && onFinalContent) {
        onFinalContent(finalContent);
      }

      if (event.type === 'done' && onComplete) {
        onComplete();
      }
    },
    [onPartUpdate, onFinalContent, onComplete],
  );

  const sendMessage = useCallback(
    async (request: ReActAgentRequest) => {
      // Cancel any existing request
      cancel();

      // Initialize state
      sseStateRef.current = createReActSSEState();
      abortControllerRef.current = new AbortController();

      setState({
        isWorking: true,
        parts: [],
        finalContent: '',
        error: null,
        startTime: Date.now(),
        endTime: null,
        currentStatus: 'Starting...',
      });

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

        // Mark as complete
        setState(prev => ({
          ...prev,
          isWorking: false,
          endTime: Date.now(),
        }));
      } catch (error: any) {
        if (error.name === 'AbortError') {
          // Request was cancelled, don't treat as error
          return;
        }

        const errorMessage = error.message || 'Unknown error occurred';

        setState(prev => ({
          ...prev,
          isWorking: false,
          error: errorMessage,
          endTime: Date.now(),
        }));

        if (onError) {
          onError(errorMessage);
        }
      }
    },
    [baseUrl, cancel, processSSELine, onError],
  );

  const replyQuestion = useCallback(async (requestId: string, answers: string[][]) => {
    const res = await fetch(`/api/v1/chat/question/${requestId}/reply`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answers }),
    });
    if (res.ok) {
      setPendingQuestion(null);
    }
  }, []);

  const rejectQuestion = useCallback(async (requestId: string) => {
    const res = await fetch(`/api/v1/chat/question/${requestId}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    if (res.ok) {
      setPendingQuestion(null);
    }
  }, []);

  return {
    state,
    pendingQuestion,
    sendMessage,
    cancel,
    reset,
    replyQuestion,
    rejectQuestion,
  };
}

/**
 * Parse existing ReAct format text (non-streaming)
 * Useful for rendering historical messages that contain ReAct format
 */
export function parseReActText(text: string): { parts: MessagePart[]; finalContent: string } {
  const parts: MessagePart[] = [];
  let finalContent = '';

  // Pattern to match ReAct format
  const thoughtPattern = /Thought:\s*(.*?)(?=Action:|Observation:|$)/gs;
  const actionPattern = /Action:\s*(.*?)(?=Action Input:|Observation:|$)/gs;
  const actionInputPattern = /Action Input:\s*(.*?)(?=Observation:|Thought:|$)/gs;
  const observationPattern = /Observation:\s*(.*?)(?=Thought:|$)/gs;

  let stepNum = 0;
  let currentThought = '';
  let currentAction = '';
  let currentActionInput: any = null;

  // Split by "Thought:" to get individual steps
  const sections = text.split(/(?=Thought:)/);

  for (const section of sections) {
    if (!section.trim()) continue;

    // Extract thought
    const thoughtMatch = section.match(/Thought:\s*(.*?)(?=Action:|Observation:|$)/s);
    if (thoughtMatch) {
      currentThought = thoughtMatch[1].trim();
    }

    // Extract action
    const actionMatch = section.match(/Action:\s*(.*?)(?=Action Input:|Observation:|$)/s);
    if (actionMatch) {
      currentAction = actionMatch[1].trim();
    }

    // Extract action input
    const inputMatch = section.match(/Action Input:\s*(.*?)(?=Observation:|Thought:|$)/s);
    if (inputMatch) {
      const inputText = inputMatch[1].trim();
      try {
        currentActionInput = JSON.parse(inputText);
      } catch {
        currentActionInput = { value: inputText };
      }
    }

    // Extract observation
    const obsMatch = section.match(/Observation:\s*(.*?)(?=Thought:|$)/s);
    const observation = obsMatch ? obsMatch[1].trim() : '';

    // Check if this is a terminate action
    if (currentAction.toLowerCase() === 'terminate') {
      if (currentActionInput && currentActionInput.output) {
        finalContent = currentActionInput.output;
      }
      currentThought = '';
      currentAction = '';
      currentActionInput = null;
      continue;
    }

    // Only add if we have something meaningful
    if (currentThought || currentAction) {
      stepNum++;
      const stepId = `react-step-${stepNum}`;

      // Add reasoning part if we have a thought
      if (currentThought) {
        parts.push({
          id: `${stepId}-reasoning`,
          type: 'reasoning',
          text: currentThought,
        } as ReasoningPart);
      }

      // Add tool part
      const toolPart: ToolPart = {
        id: stepId,
        type: 'tool',
        tool: mapActionToTool(currentAction),
        state: {
          status: 'completed',
          input: currentActionInput,
          output: observation || undefined,
          metadata: { action: currentAction },
        },
      };
      parts.push(toolPart);
    }

    // Reset for next iteration
    currentThought = '';
    currentAction = '';
    currentActionInput = null;
  }

  return { parts, finalContent };
}

/**
 * Map action name to OpenCode tool type
 */
function mapActionToTool(action: string): string {
  const lowerAction = action.toLowerCase();

  const actionMap: Record<string, string> = {
    load_skills: 'list',
    select_skill: 'question',
    load_skill: 'skill',
    load_file: 'read',
    execute_analysis: 'bash',
    load_tools: 'list',
    execute_tool: 'bash',
    terminate: 'task',
    read: 'read',
    write: 'write',
    edit: 'edit',
    search: 'grep',
    grep: 'grep',
    glob: 'glob',
    bash: 'bash',
    webfetch: 'webfetch',
  };

  return actionMap[lowerAction] || 'task';
}

export default useReActAgent;
