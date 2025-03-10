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

// Function to extract JSON from vis-thinking code blocks
const parseVisThinking = (content: any) => {
  // Check if content is a string
  if (typeof content !== 'string') {
    return content;
  }

  // Check if this is a vis-thinking code block
  if (content.startsWith('```vis-thinking') || content.includes('```vis-thinking')) {
    // Find where the JSON part begins
    // We're looking for the first occurrence of '{"' after the vis-thinking header
    const jsonStartIndex = content.indexOf('{"');

    if (jsonStartIndex !== -1) {
      // Extract everything from the JSON start to the end
      const jsonContent = content.substring(jsonStartIndex);

      // Attempt to parse the JSON
      try {
        return JSON.parse(jsonContent);
      } catch {
        // If there's a parsing error, try to clean up the JSON string
        // This might happen if there are backticks at the end
        const cleanedContent = jsonContent.replace(/```$/g, '').trim();
        try {
          return JSON.parse(cleanedContent);
        } catch (e2) {
          console.error('Error parsing cleaned JSON:', e2);
          return null;
        }
      }
    }
  }

  // If it's not a vis-thinking block, try to parse it directly as JSON
  try {
    return typeof content === 'string' ? JSON.parse(content) : content;
  } catch {
    // If it's not valid JSON, return the original content
    console.log('Not JSON format or vis-thinking format, returning original content');
    return content;
  }
};

// Function to extract the thinking part from vis-thinking code blocks while preserving tags
const formatToVisThinking = (content: any) => {
  // Only process strings
  if (typeof content !== 'string') {
    return content;
  }

  // Check if this is a vis-thinking code block
  if (content.startsWith('```vis-thinking') || content.includes('```vis-thinking')) {
    // Find the start of the vis-thinking block
    const blockStartIndex = content.indexOf('```vis-thinking');
    const thinkingStartIndex = blockStartIndex + '```vis-thinking'.length;

    // Find the end of the vis-thinking block
    const thinkingEndIndex = content.indexOf('```', thinkingStartIndex);

    if (thinkingEndIndex !== -1) {
      // Extract the thinking content with the tags
      return content.substring(blockStartIndex, thinkingEndIndex + 3);
    }
  }

  // If it's not a vis-thinking block or can't extract thinking part, return the original content
  return content;
};

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
        // First, parse the context to handle vis-thinking code blocks
        const parsedContext = parseVisThinking(contextTemp);

        // Then, handle the normal JSON processing
        const contextObj =
          typeof parsedContext === 'object'
            ? parsedContext
            : typeof contextTemp === 'string'
              ? JSON.parse(contextTemp)
              : contextTemp;

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
    <div className='flex flex-col h-screen w-full overflow-hidden'>
      <MuiLoading visible={loading} />

      <div className='flex-none'>
        <Header
          refreshHistory={getHistory}
          modelChange={(newModel: string) => {
            setModel(newModel);
          }}
        />
      </div>

      {/* Use flex-auto to ensure the remaining height is filled */}
      <div className='flex-auto flex overflow-hidden'>
        {/* Left chart area */}
        {!!chartsData?.length && (
          <div
            className={classNames('overflow-auto', {
              'w-full h-1/2 md:h-full md:w-3/4 pb-4 md:pr-4': scene === 'chat_dashboard',
            })}
          >
            <Chart chartsData={chartsData} />
          </div>
        )}
        {!chartsData?.length && scene === 'chat_dashboard' && (
          <div
            className={classNames('flex items-center justify-center', {
              'w-full h-1/2 md:h-full md:w-3/4': scene === 'chat_dashboard',
            })}
          >
            <MyEmpty />
          </div>
        )}

        <div
          className={classNames('flex flex-col overflow-hidden', {
            'w-full h-1/2 md:h-full md:w-1/4 border-t md:border-t-0 md:border-l dark:border-gray-800':
              scene === 'chat_dashboard',
            'w-full h-full px-4 lg:px-8': scene !== 'chat_dashboard',
          })}
        >
          {/* Wrap the Completion component in a container with a specific height */}
          <div className='h-full overflow-hidden'>
            <Completion messages={history} onSubmit={handleChat} onFormatContent={formatToVisThinking} />
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChatContainer;
