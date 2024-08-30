import { ChatContext } from '@/app/chat-context';
import { apiInterceptors, getAppInfo, getChatHistory, getDialogueList } from '@/client/api';
import useChat from '@/hooks/use-chat';
import ChatContentContainer from '@/new-components/chat/ChatContentContainer';
import ChatDefault from '@/new-components/chat/content/ChatDefault';
import ChatInputPanel from '@/new-components/chat/input/ChatInputPanel';
import ChatSider from '@/new-components/chat/sider/ChatSider';
import { IApp } from '@/types/app';
import { ChartData, ChatHistoryResponse, IChatDialogueSchema } from '@/types/chat';
import { getInitMessage } from '@/utils';
import { useAsyncEffect, useRequest } from 'ahooks';
import { Flex, Layout, Spin } from 'antd';
import dynamic from 'next/dynamic';
import { useSearchParams } from 'next/navigation';
import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';

const DbEditor = dynamic(() => import('@/components/chat/db-editor'), {
  ssr: false,
});
const ChatContainer = dynamic(() => import('@/components/chat/chat-container'), { ssr: false });

const { Content } = Layout;

interface ChatContentProps {
  history: ChatHistoryResponse; // 会话记录列表
  replyLoading: boolean; // 对话回复loading
  scrollRef: React.RefObject<HTMLDivElement>; // 会话内容可滚动dom
  canAbort: boolean; // 是否能中断回复
  chartsData: ChartData[];
  agent: string;
  currentDialogue: IChatDialogueSchema; // 当前选择的会话
  appInfo: IApp;
  temperatureValue: any;
  resourceValue: any;
  modelValue: string;
  setModelValue: React.Dispatch<React.SetStateAction<string>>;
  setTemperatureValue: React.Dispatch<React.SetStateAction<any>>;
  setResourceValue: React.Dispatch<React.SetStateAction<any>>;
  setAppInfo: React.Dispatch<React.SetStateAction<IApp>>;
  setAgent: React.Dispatch<React.SetStateAction<string>>;
  setCanAbort: React.Dispatch<React.SetStateAction<boolean>>;
  setReplyLoading: React.Dispatch<React.SetStateAction<boolean>>;
  handleChat: (content: string, data?: Record<string, any>) => Promise<void>; // 处理会话请求逻辑函数
  refreshDialogList: () => void;
  refreshHistory: () => void;
  refreshAppInfo: () => void;
  setHistory: React.Dispatch<React.SetStateAction<ChatHistoryResponse>>;
}
export const ChatContentContext = createContext<ChatContentProps>({
  history: [],
  replyLoading: false,
  scrollRef: { current: null },
  canAbort: false,
  chartsData: [],
  agent: '',
  currentDialogue: {} as any,
  appInfo: {} as any,
  temperatureValue: 0.5,
  resourceValue: {},
  modelValue: '',
  setModelValue: () => {},
  setResourceValue: () => {},
  setTemperatureValue: () => {},
  setAppInfo: () => {},
  setAgent: () => {},
  setCanAbort: () => {},
  setReplyLoading: () => {},
  refreshDialogList: () => {},
  refreshHistory: () => {},
  refreshAppInfo: () => {},
  setHistory: () => {},
  handleChat: () => Promise.resolve(),
});

const Chat: React.FC = () => {
  const { model, currentDialogInfo } = useContext(ChatContext);
  const { isContract, setIsContract, setIsMenuExpand } = useContext(ChatContext);
  const { chat, ctrl } = useChat({
    app_code: currentDialogInfo.app_code || '',
  });

  const searchParams = useSearchParams();
  const chatId = searchParams?.get('id') ?? '';
  const scene = searchParams?.get('scene') ?? '';
  const knowledgeId = searchParams?.get('knowledge_id') ?? '';
  const dbName = searchParams?.get('db_name') ?? '';

  const scrollRef = useRef<HTMLDivElement>(null);
  const order = useRef<number>(1);

  const [history, setHistory] = useState<ChatHistoryResponse>([]);
  const [chartsData] = useState<Array<ChartData>>();
  const [replyLoading, setReplyLoading] = useState<boolean>(false);
  const [canAbort, setCanAbort] = useState<boolean>(false);
  const [agent, setAgent] = useState<string>('');
  const [appInfo, setAppInfo] = useState<IApp>({} as IApp);
  const [temperatureValue, setTemperatureValue] = useState();
  const [resourceValue, setResourceValue] = useState<any>();
  const [modelValue, setModelValue] = useState<string>('');

  useEffect(() => {
    setTemperatureValue(appInfo?.param_need?.filter(item => item.type === 'temperature')[0]?.value || 0.5);
    setModelValue(appInfo?.param_need?.filter(item => item.type === 'model')[0]?.value || model);
    setResourceValue(
      knowledgeId || dbName || appInfo?.param_need?.filter(item => item.type === 'resource')[0]?.bind_value,
    );
  }, [appInfo, dbName, knowledgeId, model]);

  useEffect(() => {
    // 仅初始化执行，防止dashboard页面无法切换状态
    setIsMenuExpand(scene !== 'chat_dashboard');
    // 路由变了要取消Editor模式，再进来是默认的Preview模式
    if (chatId && scene) {
      setIsContract(false);
    }
  }, [chatId, scene]);

  // 是否是默认小助手
  const isChatDefault = useMemo(() => {
    return !chatId && !scene;
  }, [chatId, scene]);

  // 获取会话列表
  const {
    data: dialogueList = [],
    refresh: refreshDialogList,
    loading: listLoading,
  } = useRequest(async () => {
    return await apiInterceptors(getDialogueList());
  });

  // 获取应用详情
  const { run: queryAppInfo, refresh: refreshAppInfo } = useRequest(
    async () =>
      await apiInterceptors(
        getAppInfo({
          ...currentDialogInfo,
        }),
      ),
    {
      manual: true,
      onSuccess: data => {
        const [, res] = data;
        setAppInfo(res || ({} as IApp));
      },
    },
  );

  // 列表当前活跃对话
  const currentDialogue = useMemo(() => {
    const [, list] = dialogueList;
    return list?.find(item => item.conv_uid === chatId) || ({} as IChatDialogueSchema);
  }, [chatId, dialogueList]);

  useEffect(() => {
    const initMessage = getInitMessage();
    if (currentDialogInfo.chat_scene === scene && !isChatDefault && !(initMessage && initMessage.message)) {
      queryAppInfo();
    }
  }, [chatId, currentDialogInfo, isChatDefault, queryAppInfo, scene]);

  // 获取会话历史记录
  const {
    run: getHistory,
    loading: historyLoading,
    refresh: refreshHistory,
  } = useRequest(async () => await apiInterceptors(getChatHistory(chatId)), {
    manual: true,
    onSuccess: data => {
      const [, res] = data;
      const viewList = res?.filter(item => item.role === 'view');
      if (viewList && viewList.length > 0) {
        order.current = viewList[viewList.length - 1].order + 1;
      }
      setHistory(res || []);
    },
  });

  // 会话提问
  const handleChat = useCallback(
    (content: string, data?: Record<string, any>) => {
      return new Promise<void>(resolve => {
        const initMessage = getInitMessage();
        const ctrl = new AbortController();
        setReplyLoading(true);
        if (history && history.length > 0) {
          const viewList = history?.filter(item => item.role === 'view');
          const humanList = history?.filter(item => item.role === 'human');
          order.current = (viewList[viewList.length - 1]?.order || humanList[humanList.length - 1]?.order) + 1;
        }
        const tempHistory: ChatHistoryResponse = [
          ...(initMessage && initMessage.id === chatId ? [] : history),
          {
            role: 'human',
            context: content,
            model_name: data?.model_name || modelValue,
            order: order.current,
            time_stamp: 0,
          },
          {
            role: 'view',
            context: '',
            model_name: data?.model_name || modelValue,
            order: order.current,
            time_stamp: 0,
            thinking: true,
          },
        ];
        const index = tempHistory.length - 1;
        setHistory([...tempHistory]);
        chat({
          data: {
            chat_mode: scene,
            model_name: modelValue,
            user_input: content,
            ...data,
          },
          ctrl,
          chatId,
          onMessage: message => {
            setCanAbort(true);
            if (data?.incremental) {
              tempHistory[index].context += message;
              tempHistory[index].thinking = false;
            } else {
              tempHistory[index].context = message;
              tempHistory[index].thinking = false;
            }
            setHistory([...tempHistory]);
          },
          onDone: () => {
            setReplyLoading(false);
            setCanAbort(false);
            resolve();
          },
          onClose: () => {
            setReplyLoading(false);
            setCanAbort(false);
            resolve();
          },
          onError: message => {
            setReplyLoading(false);
            setCanAbort(false);
            tempHistory[index].context = message;
            tempHistory[index].thinking = false;
            setHistory([...tempHistory]);
            resolve();
          },
        });
      });
    },
    [chatId, history, modelValue, chat, scene],
  );

  useAsyncEffect(async () => {
    // 如果是默认小助手，不获取历史记录
    if (isChatDefault) {
      return;
    }
    const initMessage = getInitMessage();
    if (initMessage && initMessage.id === chatId) {
      return;
    }
    await getHistory();
  }, [chatId, scene, getHistory]);

  useEffect(() => {
    if (isChatDefault) {
      order.current = 1;
      setHistory([]);
    }
  }, [isChatDefault]);

  const contentRender = () => {
    if (scene === 'chat_dashboard') {
      return isContract ? <DbEditor /> : <ChatContainer />;
    } else {
      return isChatDefault ? (
        <Content>
          <ChatDefault />
        </Content>
      ) : (
        <Spin spinning={historyLoading} className='w-full h-full m-auto'>
          <Content className='flex flex-col h-screen'>
            <ChatContentContainer ref={scrollRef} />
            <ChatInputPanel ctrl={ctrl} />
          </Content>
        </Spin>
      );
    }
  };

  return (
    <ChatContentContext.Provider
      value={{
        history,
        replyLoading,
        scrollRef,
        canAbort,
        chartsData: chartsData || [],
        agent,
        currentDialogue,
        appInfo,
        temperatureValue,
        resourceValue,
        modelValue,
        setModelValue,
        setResourceValue,
        setTemperatureValue,
        setAppInfo,
        setAgent,
        setCanAbort,
        setReplyLoading,
        handleChat,
        refreshDialogList,
        refreshHistory,
        refreshAppInfo,
        setHistory,
      }}
    >
      <Flex flex={1}>
        <Layout className='bg-gradient-light bg-cover bg-center dark:bg-gradient-dark'>
          <ChatSider
            refresh={refreshDialogList}
            dialogueList={dialogueList}
            listLoading={listLoading}
            historyLoading={historyLoading}
            order={order}
          />
          <Layout className='bg-transparent'>{contentRender()}</Layout>
        </Layout>
      </Flex>
    </ChatContentContext.Provider>
  );
};

export default Chat;
