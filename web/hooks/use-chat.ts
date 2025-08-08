import { ChatContext } from '@/app/chat-context';
import i18n from '@/app/i18n';
import { getUserId } from '@/utils';
import { HEADER_USER_ID_KEY } from '@/utils/constants/index';
import { EventStreamContentType, fetchEventSource } from '@microsoft/fetch-event-source';
import { message } from 'antd';
import { useCallback, useContext, useState } from 'react';

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

const useChat = ({ queryAgentURL = '/api/v1/chat/completions', app_code }: Props) => {
  const [ctrl, setCtrl] = useState<AbortController>({} as AbortController);
  const { scene } = useContext(ChatContext);
  const chat = useCallback(
    async ({ data, chatId, onMessage, onClose, onDone, onError, ctrl }: ChatParams) => {
      ctrl && setCtrl(ctrl);
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

      // AWEL fallback: if select_param exists but chat_mode is not specified or is 'chat_agent',
      // force chat_mode to 'chat_flow' to avoid creating new conversations and raw JSON responses
      if (data?.select_param && (!params.chat_mode || params.chat_mode === 'chat_agent')) {
        params.chat_mode = 'chat_flow';
      }

      // Decide scene used for parsing response
      const sceneForParse = (params.chat_mode as string) || scene;

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
                try {
                  let payload: any = data;
                  if (sceneForParse === 'chat_agent') {
                    // Prefer vis, then OpenAI-style choices content, then fallback stringify
                    payload =
                      data?.vis ??
                      (data?.choices?.[0]?.message?.content ?? undefined) ??
                      JSON.stringify(data, null, 2);
                  } else if (sceneForParse === 'chat_flow') {
                    if (data?.choices?.[0]?.message?.content) {
                      payload = data.choices[0].message.content;
                    } else if (data?.vis) {
                      payload = data.vis;
                    } else if (typeof data === 'string') {
                      payload = data;
                    } else {
                      payload = JSON.stringify(data, null, 2);
                    }
                  } else {
                    payload = data?.choices?.[0]?.message?.content ?? data;
                  }
                  if (typeof payload === 'string') {
                    payload = payload.replaceAll('\\n', '\n');
                  }
                  onMessage?.(payload);
                } finally {
                  onDone?.();
                  ctrl && ctrl.abort();
                }
              });
            }
          },
          onclose() {
            ctrl && ctrl.abort();
            onClose?.();
          },
          onerror(err) {
            throw new Error(err);
          },
          onmessage: event => {
            let message = event.data;
            // Normalize SSE frames that include the 'data:' prefix from backend
            if (typeof message === 'string' && message.startsWith('data:')) {
              message = message.replace(/^data:\s*/, '');
            }
            try {
              if (sceneForParse === 'chat_agent') {
                const parsed = JSON.parse(message);
                message = parsed?.vis ?? parsed?.choices?.[0]?.message?.content ?? JSON.stringify(parsed, null, 2);
              } else if (sceneForParse === 'chat_flow') {
                // Handle AWEL workflow responses - check if it's JSON and extract content appropriately
                try {
                  const parsed = JSON.parse(message);
                  // If it's a structured response with choices, extract the content
                  if (parsed.choices?.[0]?.message?.content) {
                    message = parsed.choices[0].message.content;
                  } else if (parsed.vis) {
                    // If it has vis field like agent responses
                    message = parsed.vis;
                  } else if (typeof parsed === 'string') {
                    message = parsed;
                  } else {
                    // For other structured responses, stringify for display
                    message = JSON.stringify(parsed, null, 2);
                  }
                } catch {
                  // If not JSON, use as-is but replace newlines
                  message = message.replaceAll('\\n', '\n');
                }
              } else {
                data = JSON.parse(event.data);
                message = data.choices?.[0]?.message?.content;
              }
            } catch {
              // ensure message is a string before replaceAll; avoid silent failure
              if (typeof message === 'string') {
                message = message.replaceAll('\\n', '\n');
              }
            }
            if (typeof message === 'string') {
              // Normalize escaped newlines after successful parsing too
              message = message.replaceAll('\\n', '\n');
              if (message === '[DONE]') {
                onDone?.();
              } else if (message?.startsWith('[ERROR]')) {
                onError?.(message?.replace('[ERROR]', ''));
              } else {
                onMessage?.(message);
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

  return { chat, ctrl };
};

export default useChat;
