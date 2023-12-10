import React, { useCallback, useContext, useEffect, useState } from 'react';
import { useAsyncEffect } from 'ahooks';
import useChat from '@/hooks/use-chat';
import Completion from './completion';
import { ChartData, ChatHistoryResponse } from '@/types/chat';
import { apiInterceptors, getChatHistory } from '@/client/api';
import { ChatContext } from '@/app/chat-context';
import Header from './header';
import Chart from '../chart';
import classNames from 'classnames';
import MuiLoading from '../common/loading';
import { Empty } from 'antd';
import { useSearchParams } from 'next/navigation';
import { getInitMessage } from '@/utils';

const ChatContainer = () => {
  const searchParams = useSearchParams();
  const { scene, chatId, model, setModel, history, setHistory } = useContext(ChatContext);
  const chat = useChat({});
  const initMessage = (searchParams && searchParams.get('initMessage')) ?? '';

  const [loading, setLoading] = useState<boolean>(false);
  const [chartsData, setChartsData] = useState<Array<ChartData>>();

  const getHistory = async () => {
    setLoading(true);
    const [, res] = await apiInterceptors(getChatHistory(chatId));
    setHistory(res ?? []);
    setLoading(false);
  };

  const getChartsData = (list: ChatHistoryResponse) => {
    const contextTemp = list[list.length - 1]?.context;
    if (contextTemp) {
      try {
        const contextObj = JSON.parse(contextTemp);
        setChartsData(contextObj?.template_name === 'report' ? contextObj?.charts : undefined);
      } catch (e) {
        setChartsData(undefined);
      }
    }
  };

  useAsyncEffect(async () => {
    const initMessage = getInitMessage();
    if (initMessage && initMessage.id === chatId) return;
    await getHistory();
  }, [initMessage, chatId]);

  useEffect(() => {
    if (!history.length) return;
    /** use last view model_name as default model name */
    const lastView = history.filter((i) => i.role === 'view')?.slice(-1)?.[0];
    lastView?.model_name && setModel(lastView.model_name);

    getChartsData(history);
  }, [history.length]);

  useEffect(() => {
    return () => {
      setHistory([]);
    };
  }, []);

  const handleChat = useCallback(
    (content: string, data?: Record<string, any>) => {
      return new Promise<void>((resolve) => {
        const tempHistory: ChatHistoryResponse = [
          ...history,
          { role: 'human', context: content, model_name: model, order: 0, time_stamp: 0 },
          { role: 'view', context: '', model_name: model, order: 0, time_stamp: 0 },
        ];
        const index = tempHistory.length - 1;
        setHistory([...tempHistory]);
        chat({
          data: { ...data, chat_mode: scene || 'chat_normal', model_name: model, user_input: content },
          chatId,
          onMessage: (message) => {
            tempHistory[index].context = message;
            setHistory([...tempHistory]);
          },
          onDone: () => {
            getChartsData(tempHistory);
            resolve();
          },
          onClose: () => {
            getChartsData(tempHistory);
            resolve();
          },
          onError: (message) => {
            tempHistory[index].context = message;
            setHistory([...tempHistory]);
            resolve();
          },
        });
      });
    },
    [history, chat, model],
  );

  return (
    <>
      <MuiLoading visible={loading} />
      <Header
        refreshHistory={getHistory}
        modelChange={(newModel: string) => {
          setModel(newModel);
        }}
      />
      <div className="px-4 flex flex-1 flex-wrap overflow-hidden relative">
        {!!chartsData?.length && (
          <div className="w-full xl:w-3/4 h-3/5 xl:pr-4 xl:h-full overflow-y-auto">
            <Chart chartsData={chartsData} />
          </div>
        )}
        {!chartsData?.length && scene === 'chat_dashboard' && (
          <Empty
            image="/empty.png"
            imageStyle={{ width: 320, height: 320, margin: '0 auto', maxWidth: '100%', maxHeight: '100%' }}
            className="w-full xl:w-3/4 h-3/5 xl:h-full pt-0 md:pt-10"
          />
        )}
        {/** chat panel */}
        <div
          className={classNames('flex flex-1 flex-col overflow-hidden', {
            'px-0 xl:pl-4 h-2/5 xl:h-full border-t xl:border-t-0 xl:border-l': scene === 'chat_dashboard',
            'h-full lg:px-8': scene !== 'chat_dashboard',
          })}
        >
          <Completion messages={history} onSubmit={handleChat} />
        </div>
      </div>
    </>
  );
};

export default ChatContainer;
