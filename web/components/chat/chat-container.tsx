import { ChatContext } from '@/app/chat-context';
import { apiInterceptors, getChatHistory } from '@/client/api';
import useChat from '@/hooks/use-chat';
import { ChartData, ChatHistoryResponse } from '@/types/chat';
import { getInitMessage } from '@/utils';
import { useAsyncEffect } from 'ahooks';
import classNames from 'classnames';
import { useSearchParams } from 'next/navigation';
import { useCallback, useContext, useEffect, useState } from 'react';
import Chart from '../chart';
import MyEmpty from '../common/MyEmpty';
import MuiLoading from '../common/loading';
import Completion from './completion';
import Header from './header';

const ChatContainer = () => {
  const searchParams = useSearchParams();
  const { scene, chatId, model, agent, setModel, history, setHistory } = useContext(ChatContext);
  const { chat } = useChat({});
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
        const contextObj = typeof contextTemp === 'string' ? JSON.parse(contextTemp) : contextTemp;
        setChartsData(contextObj?.template_name === 'report' ? contextObj?.charts : undefined);
      } catch (e) {
        console.log(e);
        setChartsData([]);
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
    const lastView = history.filter(i => i.role === 'view')?.slice(-1)?.[0];
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
      return new Promise<void>(resolve => {
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
          onMessage: message => {
            if (data?.incremental) {
              tempHistory[index].context += message;
            } else {
              tempHistory[index].context = message;
            }
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
          onError: message => {
            tempHistory[index].context = message;
            setHistory([...tempHistory]);
            resolve();
          },
        });
      });
    },
    [history, chat, chatId, model, agent, scene],
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
      <div className='px-4 flex flex-1 flex-wrap overflow-hidden relative'>
        {!!chartsData?.length && (
          <div className='w-full pb-4 xl:w-3/4 h-1/2 xl:pr-4 xl:h-full overflow-y-auto'>
            <Chart chartsData={chartsData} />
          </div>
        )}
        {!chartsData?.length && scene === 'chat_dashboard' && <MyEmpty className='w-full xl:w-3/4 h-1/2 xl:h-full' />}
        {/** chat panel */}
        <div
          className={classNames('flex flex-1 flex-col overflow-hidden', {
            'px-0 xl:pl-4 h-1/2 w-full xl:w-auto xl:h-full border-t xl:border-t-0 xl:border-l dark:border-gray-800':
              scene === 'chat_dashboard',
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
