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

      // Debug: Log the params object to verify prompt_code is included
      console.log('DEBUG - API request params:', params);
      console.log('DEBUG - prompt_code in params:', params.prompt_code);
      console.log('DEBUG - data object received:', data);

      try {
        // Debug: Log the actual request body that will be sent
        const requestBody = JSON.stringify(params);
        console.log('DEBUG - API request body:', requestBody);

        await fetchEventSource(`${process.env.API_BASE_URL ?? ''}${queryAgentURL}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            [HEADER_USER_ID_KEY]: getUserId() ?? '',
          },
          body: requestBody,
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
            onClose?.();
          },
          onerror(err) {
            throw new Error(err);
          },
          onmessage: event => {
            let message = event.data;
            try {
              if (scene === 'chat_agent') {
                message = JSON.parse(message).vis;
              } else {
                message = JSON.parse(message);
              }
            } catch {
              message.replaceAll('\\n', '\n');
            }
            if (typeof message === 'string') {
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
