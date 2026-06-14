import { ChatContext } from '@/app/chat-context';
import i18n from '@/app/i18n';
import { getUserId } from '@/utils';
import { HEADER_USER_ID_KEY } from '@/utils/constants/index';
import { EventStreamContentType, fetchEventSource } from '@microsoft/fetch-event-source';
import { message } from 'antd';
import { useCallback, useContext, useRef, useState } from 'react';

export interface PendingQuestionEvent {
  request_id: string;
  conv_id: string;
  questions: Array<{
    question: string;
    header: string;
    options: Array<{ label: string; description: string }>;
    multiple?: boolean;
    custom?: boolean;
  }>;
}

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

const useChat = ({ queryAgentURL = '/api/v1/chat/completions', app_code }: Props) => {
  const [ctrl, setCtrl] = useState<AbortController>({} as AbortController);
  const lastMessageRef = useRef<string>('');
  const { scene } = useContext(ChatContext);
  const [contextStatus, setContextStatus] = useState<ChatContextStatus | null>(null);
  const [pendingQuestion, setPendingQuestion] = useState<PendingQuestionEvent | null>(null);
  const chat = useCallback(
    async ({ data, chatId, onMessage, onClose, onDone, onError, ctrl }: ChatParams) => {
      ctrl && setCtrl(ctrl);
      lastMessageRef.current = '';
      setContextStatus(null);
      if (!data?.user_input && !data?.doc_id) {
        message.warning(i18n.t('no_context_tip'));
        return;
      }

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
        await fetchEventSource(`${process.env.API_BASE_URL ?? ''}${queryAgentURL}`, {
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
                onMessage?.(data);
                onDone?.();
                ctrl && ctrl.abort();
              });
            }
          },
          onclose() {
            ctrl && ctrl.abort();
            lastMessageRef.current = '';
            onClose?.();
          },
          onerror(err) {
            throw new Error(err);
          },
          onmessage: event => {
            let message = event.data;
            let needReplaceNewline = false;
            let parsedData;

            try {
              parsedData = JSON.parse(message);

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
              if (parsedData.type === 'question.asked') {
                setPendingQuestion(parsedData);
                return;
              }
              if (parsedData.type === 'question.replied' || parsedData.type === 'question.rejected') {
                setPendingQuestion(null);
                return;
              }

              if (scene === 'chat_agent') {
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
                lastMessageRef.current = '';
                onDone?.();
              } else if (message?.startsWith('[ERROR]')) {
                onError?.(message?.replace('[ERROR]', ''));
              } else {
                if (scene === 'chat_react_agent') {
                  const previous = lastMessageRef.current;
                  const delta = message.startsWith(previous) ? message.slice(previous.length) : message;
                  lastMessageRef.current = message;
                  if (delta) {
                    onMessage?.(delta);
                  }
                } else {
                  onMessage?.(message);
                }
              }
            } else {
              onMessage?.(message);
              onDone?.();
            }
          },
        });
      } catch (err) {
        ctrl && ctrl.abort();
        onError?.('Sorry, We meet some error, please try agin later.', err as Error);
      }
    },
    [queryAgentURL, app_code, scene],
  );

  const replyQuestion = useCallback(async (requestId: string, answers: string[][]) => {
    const res = await fetch(`${process.env.API_BASE_URL ?? ''}/api/v1/chat/question/${requestId}/reply`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        [HEADER_USER_ID_KEY]: getUserId() ?? '',
      },
      body: JSON.stringify({ answers }),
    });
    if (res.ok) {
      setPendingQuestion(null);
    }
  }, []);

  const rejectQuestion = useCallback(async (requestId: string) => {
    const res = await fetch(`${process.env.API_BASE_URL ?? ''}/api/v1/chat/question/${requestId}/reject`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        [HEADER_USER_ID_KEY]: getUserId() ?? '',
      },
    });
    if (res.ok) {
      setPendingQuestion(null);
    }
  }, []);

  return { chat, ctrl, contextStatus, pendingQuestion, replyQuestion, rejectQuestion };
};

export default useChat;
