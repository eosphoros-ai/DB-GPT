import i18n from '@/app/i18n';
import { getUserId } from '@/utils';
import { HEADER_USER_ID_KEY } from '@/utils/constants/index';
import { EventStreamContentType, fetchEventSource } from '@microsoft/fetch-event-source';
import { message } from 'antd';
import { useCallback, useEffect, useMemo, useState } from 'react';

type Props = {
  queryAgentURL?: string;
  app_code?: string;
};

type ChatParams = {
  chatId: string;
  ctrl: AbortController;
  data?: Record<string, any>;
  query?: Record<string, string>;
  onMessage: (message: string) => void;
  onClose?: () => void;
  onDone?: () => void;
  onError?: (content: string, error?: Error) => void;
};

const useChat = ({ queryAgentURL = '/api/v1/chat/completions', app_code = '' }: Props) => {
  const [ctrl, setCtrl] = useState<AbortController>({} as AbortController);
  const chat = useCallback(
    async ({ data, chatId, onMessage, onClose, onDone, onError, ctrl }: ChatParams) => {
      setCtrl(ctrl);
      if (!data?.user_input && !data?.doc_id) {
        message.warning(i18n.t('no_context_tip'));
        return;
      }

      const params = {
        ...data,
        conv_uid: chatId,
        app_code,
      };

      if (!params.conv_uid) {
        message.error('conv_uid 不存在，请刷新后重试');
        return;
      }

      try {
        await fetchEventSource(`${process.env.API_BASE_URL ?? ''}${queryAgentURL}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            [HEADER_USER_ID_KEY]: getUserId() ?? '',
          },
          body: JSON.stringify(params),
          signal: ctrl.signal,
          openWhenHidden: true,
          async onopen(response) {
            if (response.ok && response.headers.get('content-type') === EventStreamContentType) {
              return;
            }
          },
          onclose() {
            ctrl.abort();
            onClose?.();
          },
          onerror(err) {
            throw new Error(err);
          },
          onmessage: (event) => {
            let message = event.data;
            try {
              message = JSON.parse(message).vis;
            } catch (e) {
              message.replaceAll('\\n', '\n');
            }
            if (message === '[DONE]') {
              onDone?.();
            } else if (message?.startsWith('[ERROR]')) {
              onError?.(message?.replace('[ERROR]', ''));
            } else {
              onMessage?.(message);
            }
          },
        });
      } catch (err) {
        ctrl.abort();
        onError?.('Sorry, We meet some error, please try agin later.', err as Error);
      }
    },
    [queryAgentURL],
  );

  return { chat, ctrl };
};

export default useChat;
