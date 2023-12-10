import { ChatContext } from '@/app/chat-context';
import { ChatHistoryResponse } from '@/types/chat';
import { useCallback, useContext } from 'react';
import useChat from './use-chat';
import { apiInterceptors, getChatHistory } from '@/client/api';

const useSummary = () => {
  const { history, setHistory, chatId, model, docId } = useContext(ChatContext);
  const chat = useChat({ queryAgentURL: '/knowledge/document/summary' });

  const summary = useCallback(
    async (curDocId?: number) => {
      const [, res] = await apiInterceptors(getChatHistory(chatId));
      const tempHistory: ChatHistoryResponse = [
        ...res!,
        { role: 'human', context: '', model_name: model, order: 0, time_stamp: 0 },
        { role: 'view', context: '', model_name: model, order: 0, time_stamp: 0, retry: true },
      ];
      const index = tempHistory.length - 1;
      setHistory([...tempHistory]);
      await chat({
        data: {
          doc_id: curDocId || docId,
          model_name: model,
        },
        chatId,
        onMessage: (message) => {
          tempHistory[index].context = message;
          setHistory([...tempHistory]);
        },
      });
    },
    [history, model, docId, chatId],
  );
  return summary;
};

export default useSummary;
