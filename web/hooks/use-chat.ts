import { ChatContext } from '@/app/chat-context';
import i18n from '@/app/i18n';
import { useQuestionSession } from '@/hooks/use-question-session';
import {
  createDashboardGenerationEventGate,
  type DashboardGenerationEvent,
} from '@/new-components/dashboard/dashboard-generation-state';
import { getUserId } from '@/utils';
import { HEADER_USER_ID_KEY } from '@/utils/constants/index';
import type { PendingQuestion } from '@/utils/question-session';
import { decodeFinalEvent } from '@/utils/react-agent-final';
import { EventStreamContentType, fetchEventSource } from '@microsoft/fetch-event-source';
import { message } from 'antd';
import { useCallback, useContext, useEffect, useRef, useState } from 'react';

export type PendingQuestionEvent = PendingQuestion;

type Props = {
  queryAgentURL?: string;
  app_code?: string;
};

type ChatParams = {
  chatId: string;
  ctrl?: AbortController;
  data?: any;
  query?: Record<string, string>;
  onMessage: (message: string) => void;
  onDashboardEvent?: (event: DashboardGenerationEvent) => void;
  onClose?: () => void;
  onDone?: () => void;
  onError?: (content: string, error?: Error) => void;
};

/** Context status pushed by the backend context-management layer. */
export interface ChatContextStatus {
  state: 'OK' | 'WARNING' | 'ERROR';
  used_tokens: number;
  max_tokens: number;
  usage_percent: number;
  layer?: string;
  message?: string;
}

/** Map backend TokenState enum values to frontend display states. */
function mapContextState(raw: string): 'OK' | 'WARNING' | 'ERROR' {
  switch (raw) {
    case 'warning':
      return 'WARNING';
    case 'error':
    case 'critical':
    case 'overflow':
      return 'ERROR';
    default:
      // 'normal' or unknown
      return 'OK';
  }
}

const useChat = ({ queryAgentURL, app_code }: Props) => {
  const [ctrl, setCtrl] = useState<AbortController>({} as AbortController);
  const activeRequest = useRef<AbortController | null>(null);
  const { scene } = useContext(ChatContext);
  const [contextStatus, setContextStatus] = useState<ChatContextStatus | null>(null);
  const { pendingQuestion, handleQuestionEvent, clearQuestions, replyQuestion, rejectQuestion } = useQuestionSession();
  useEffect(() => () => activeRequest.current?.abort(), []);
  const chat = useCallback(
    async ({
      data,
      chatId,
      onMessage,
      onDashboardEvent,
      onClose,
      onDone,
      onError,
      ctrl = new AbortController(),
    }: ChatParams) => {
      if (!data?.user_input && !data?.doc_id) {
        message.warning(i18n.t('no_context_tip'));
        return;
      }
      activeRequest.current?.abort();
      activeRequest.current = ctrl;
      setCtrl(ctrl);
      clearQuestions();
      setContextStatus(null);
      let lastMessage = '';
      let terminal = false;
      const isCurrent = () => activeRequest.current === ctrl && !ctrl.signal.aborted;
      const finish = () => {
        if (!isCurrent() || terminal) return;
        terminal = true;
        onDone?.();
      };
      const acceptGenerationEvent = createDashboardGenerationEventGate();
      const requestScene = data.chat_mode || scene;
      const endpoint =
        queryAgentURL ||
        (requestScene === 'chat_react_agent' ? '/api/v1/chat/react-agent' : '/api/v1/chat/completions');

      // Ensure prompt_code is preserved and not overwritten
      const params: Record<string, any> = {
        conv_uid: chatId,
        app_code,
      };

      // Add data fields, ensuring prompt_code is set correctly
      if (data) {
        Object.keys(data).forEach(key => {
          params[key] = data[key];
        });
      }

      try {
        await fetchEventSource(`${process.env.API_BASE_URL ?? ''}${endpoint}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            [HEADER_USER_ID_KEY]: getUserId() ?? '',
          },
          body: JSON.stringify(params),
          signal: ctrl ? ctrl.signal : null,
          openWhenHidden: true,
          async onopen(response) {
            if (response.ok && response.headers.get('content-type') === EventStreamContentType) {
              return;
            }
            if (response.headers.get('content-type') === 'application/json') {
              response.json().then(data => {
                if (!isCurrent() || terminal) return;
                onMessage?.(data);
                finish();
                ctrl && ctrl.abort();
              });
            }
          },
          onclose() {
            if (!isCurrent()) return;
            if (!terminal) onClose?.();
            terminal = true;
            ctrl && ctrl.abort();
          },
          onerror(err) {
            throw new Error(err);
          },
          onmessage: event => {
            // Each callback belongs to one transport. A late terminal/question
            // from the previous request cannot touch the next turn's state.
            if (!isCurrent() || terminal) return;
            let message = event.data;
            let needReplaceNewline = false;
            let parsedData;

            try {
              parsedData = JSON.parse(message);

              if (typeof parsedData?.type === 'string' && parsedData.type.startsWith('dashboard.')) {
                if (!acceptGenerationEvent(parsedData)) return;
                onDashboardEvent?.(parsedData);
                if (parsedData.type === 'dashboard.generation.failed') {
                  clearQuestions();
                  finish();
                }
                return;
              }
              if (parsedData?.type === 'final') {
                onMessage(decodeFinalEvent(parsedData).content);
                return;
              }
              if (parsedData?.type === 'done') {
                finish();
                return;
              }
              if (parsedData?.type === 'error') {
                terminal = true;
                clearQuestions();
                onError?.(parsedData.message || parsedData.content || '聊天执行失败，请重新发起本次操作。');
                return;
              }

              // Handle context status events from context management layer
              // Completions format: {"context_status": {"used": ..., "budget": ..., ...}}
              // React-agent format: {"type": "context.status", "used": ..., "budget": ..., ...}
              const cs = parsedData.context_status ?? (parsedData.type === 'context.status' ? parsedData : null);
              if (cs) {
                const budget = Number(cs.budget ?? 0);
                if (!Number.isFinite(budget) || budget <= 0) {
                  setContextStatus(null);
                  return;
                }
                // Only show banner when Layer 3 (LLM compression) is active
                if (cs.compact_layer === 'layer3') {
                  setContextStatus({
                    state: mapContextState(cs.state || 'normal'),
                    used_tokens: cs.used ?? 0,
                    max_tokens: budget,
                    usage_percent: (cs.ratio ?? 0) * 100,
                    layer: cs.compact_layer,
                    message: cs.message,
                  });
                } else {
                  setContextStatus(null);
                }
                return; // Don't process as a chat message
              }

              // Handle human-in-the-loop question events
              if (handleQuestionEvent(parsedData, chatId)) return;

              // Agent progress/tool events are not completion message text.
              if (typeof parsedData.type === 'string') return;

              if (requestScene === 'chat_agent') {
                if (parsedData.vis) {
                  message = parsedData.vis;
                } else {
                  needReplaceNewline = true;
                  message = parsedData.choices?.[0]?.message?.content;
                }
              } else {
                message = parsedData.choices?.[0]?.message?.content;
              }
            } catch {
              if (typeof message === 'string') {
                message = message.replaceAll('\\n', '\n');
              }
            }
            if (typeof message === 'string') {
              if (needReplaceNewline) {
                message = message.replaceAll('\\n', '\n');
              }
              if (message === '[DONE]') {
                finish();
              } else if (message?.startsWith('[ERROR]')) {
                terminal = true;
                onError?.(message?.replace('[ERROR]', ''));
              } else {
                if (requestScene === 'chat_react_agent') {
                  const previous = lastMessage;
                  const delta = message.startsWith(previous) ? message.slice(previous.length) : message;
                  lastMessage = message;
                  if (delta) {
                    onMessage?.(delta);
                  }
                } else {
                  onMessage?.(message);
                }
              }
            }
          },
        });
      } catch (err) {
        if (!isCurrent() || terminal) return;
        terminal = true;
        ctrl && ctrl.abort();
        onError?.('Sorry, We meet some error, please try agin later.', err as Error);
      }
    },
    [queryAgentURL, app_code, scene, handleQuestionEvent, clearQuestions],
  );

  return { chat, ctrl, contextStatus, pendingQuestion, replyQuestion, rejectQuestion };
};

export default useChat;
