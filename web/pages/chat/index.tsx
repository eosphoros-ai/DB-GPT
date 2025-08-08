import { ChatContext } from '@/app/chat-context';
import { apiInterceptors, getAppInfo, getChatHistory, getDialogueList } from '@/client/api';
import PromptBot from '@/components/common/prompt-bot';
import useChat from '@/hooks/use-chat';
import ChatContentContainer from '@/new-components/chat/ChatContentContainer';
import ChatDefault from '@/new-components/chat/content/ChatDefault';
import ChatInputPanel from '@/new-components/chat/input/ChatInputPanel';
import ChatSider from '@/new-components/chat/sider/ChatSider';
import { IApp } from '@/types/app';
import { ChartData, ChatHistoryResponse, IChatDialogueSchema, UserChatContent } from '@/types/chat';
import { getInitMessage, transformFileUrl } from '@/utils';
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
  maxNewTokensValue: any;
  resourceValue: any;
  modelValue: string;
  setModelValue: React.Dispatch<React.SetStateAction<string>>;
  setTemperatureValue: React.Dispatch<React.SetStateAction<any>>;
  setMaxNewTokensValue: React.Dispatch<React.SetStateAction<any>>;
  setResourceValue: React.Dispatch<React.SetStateAction<any>>;
  setAppInfo: React.Dispatch<React.SetStateAction<IApp>>;
  setAgent: React.Dispatch<React.SetStateAction<string>>;
  setCanAbort: React.Dispatch<React.SetStateAction<boolean>>;
  setReplyLoading: React.Dispatch<React.SetStateAction<boolean>>;
  handleChat: (content: UserChatContent, data?: Record<string, any>) => Promise<void>; // 处理会话请求逻辑函数
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
  maxNewTokensValue: 1024,
  resourceValue: {},
  modelValue: '',
  setModelValue: () => {},
  setResourceValue: () => {},
  setTemperatureValue: () => {},
  setMaxNewTokensValue: () => {},
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

  // Create ref for ChatInputPanel to control input value externally
  const chatInputRef = useRef<any>(null);

  // Use ref to store the selected prompt_code
  const selectedPromptCodeRef = useRef<string | undefined>(undefined);

  const [history, setHistory] = useState<ChatHistoryResponse>([]);
  const [chartsData] = useState<Array<ChartData>>();
  const [replyLoading, setReplyLoading] = useState<boolean>(false);
  const [canAbort, setCanAbort] = useState<boolean>(false);
  const [agent, setAgent] = useState<string>('');
  const [appInfo, setAppInfo] = useState<IApp>({} as IApp);
  const [temperatureValue, setTemperatureValue] = useState();
  const [maxNewTokensValue, setMaxNewTokensValue] = useState();
  const [resourceValue, setResourceValue] = useState<any>();
  const [modelValue, setModelValue] = useState<string>('');

  useEffect(() => {
    setTemperatureValue(appInfo?.param_need?.filter(item => item.type === 'temperature')[0]?.value || 0.6);
    setMaxNewTokensValue(appInfo?.param_need?.filter(item => item.type === 'max_new_tokens')[0]?.value || 4000);
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
  }, [chatId, scene, setIsContract, setIsMenuExpand]);

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
      // Normalize history: parse JSON-like contexts for agent/flow to avoid showing raw JSON after refresh
      const normalized = (res || []).map(item => {
        if (item?.role !== 'view' || typeof item?.context !== 'string') return item;
        try {
          const parsed = JSON.parse(item.context);
          let content: any;
          if (scene === 'chat_agent') {
            content = parsed?.vis ?? parsed?.choices?.[0]?.message?.content ??
              (typeof parsed === 'string' ? parsed : JSON.stringify(parsed, null, 2));
          } else if (scene === 'chat_flow') {
            content = parsed?.choices?.[0]?.message?.content ?? parsed?.vis ??
              (typeof parsed === 'string' ? parsed : JSON.stringify(parsed, null, 2));
          }
          if (typeof content === 'string') {
            return { ...item, context: content.replaceAll('\\n', '\n') };
          }
          return item;
        } catch {
          return item;
        }
      });
      const viewList = normalized?.filter(item => item.role === 'view');
      if (viewList && viewList.length > 0) {
        order.current = viewList[viewList.length - 1].order + 1;
      }
      setHistory(normalized || []);
    },
  });

  // 会话提问
  const handleChat = useCallback(
    (content: UserChatContent, data?: Record<string, any>) => {
      return new Promise<void>(resolve => {
        const initMessage = getInitMessage();
        const ctrl = new AbortController();
        setReplyLoading(true);
        if (history && history.length > 0) {
          const viewList = history?.filter(item => item.role === 'view');
          const humanList = history?.filter(item => item.role === 'human');
          order.current = (viewList[viewList.length - 1]?.order || humanList[humanList.length - 1]?.order) + 1;
        }
        // Process the content based on its type
        let formattedDisplayContent: string = '';

        if (typeof content === 'string') {
          formattedDisplayContent = content;
        } else {
          // Extract content items for display formatting
          const contentItems = content.content || [];
          const textItems = contentItems.filter(item => item.type === 'text');
          const mediaItems = contentItems.filter(item => item.type !== 'text');

          // Format for display in the UI - extract text for main message
          if (textItems.length > 0) {
            // Use the text content for the main message display
            formattedDisplayContent = textItems.map(item => item.text).join(' ');
          }

          // Format media items for display (using markdown)
          const mediaMarkdown = mediaItems
            .map(item => {
              if (item.type === 'image_url') {
                const originalUrl = item.image_url?.url || '';
                // Transform the URL to a service URL that can be displayed
                const displayUrl = transformFileUrl(originalUrl);
                const fileName = item.image_url?.fileName || 'image';
                return `\n![${fileName}](${displayUrl})`;
              } else if (item.type === 'video') {
                const originalUrl = item.video || '';
                const displayUrl = transformFileUrl(originalUrl);
                return `\n[Video](${displayUrl})`;
              } else {
                return `\n[${item.type} attachment]`;
              }
            })
            .join('\n');

          // Combine text and media markup
          if (mediaMarkdown) {
            formattedDisplayContent = formattedDisplayContent + '\n' + mediaMarkdown;
          }
        }

        const tempHistory: ChatHistoryResponse = [
          ...(initMessage && initMessage.id === chatId ? [] : history),
          {
            role: 'human',
            context: formattedDisplayContent,
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
        // Create data object with all fields
        const apiData: Record<string, any> = {
          chat_mode: scene,
          model_name: modelValue,
          user_input: content,
        };

        // Force chat_flow for AWEL flow chats to prevent server from forking new conv ids
        const urlSelectParam = searchParams?.get('select_param') ?? '';
        if (urlSelectParam && scene !== 'chat_flow') {
          apiData.chat_mode = 'chat_flow';
          apiData.select_param = urlSelectParam;
        }

        // Add other data fields
        if (data) {
          Object.assign(apiData, data);
        }

        // For non-dashboard scenes, try to get prompt_code from ref or localStorage
        if (scene !== 'chat_dashboard') {
          const finalPromptCode = selectedPromptCodeRef.current || localStorage.getItem(`dbgpt_prompt_code_${chatId}`);
          if (finalPromptCode) {
            apiData.prompt_code = finalPromptCode;
            localStorage.removeItem(`dbgpt_prompt_code_${chatId}`);
          }
        }

        chat({
          data: apiData,
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
    [chatId, history, modelValue, chat, scene, searchParams],
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
            <ChatContentContainer ref={scrollRef} className='flex-1' />
            {/* Pass ref to ChatInputPanel for external control */}
            <ChatInputPanel ref={chatInputRef} ctrl={ctrl} />
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
        maxNewTokensValue,
        resourceValue,
        modelValue,
        setModelValue,
        setResourceValue,
        setTemperatureValue,
        setMaxNewTokensValue,
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
          <Layout className='bg-transparent'>
            {contentRender()}
            {/* Render PromptBot at the bottom right */}
            <PromptBot
              submit={prompt => {
                // For chat_dashboard, only store prompt_code in localStorage
                // The input filling will be handled by the CompletionInput's PromptBot
                if (scene === 'chat_dashboard') {
                  localStorage.setItem(`dbgpt_prompt_code_${chatId}`, prompt.prompt_code);
                } else {
                  // For other scenes, fill input and store prompt_code
                  chatInputRef.current?.setUserInput?.(prompt.content);
                  selectedPromptCodeRef.current = prompt.prompt_code;
                  localStorage.setItem(`dbgpt_prompt_code_${chatId}`, prompt.prompt_code);
                }
              }}
              chat_scene={scene}
            />
          </Layout>
        </Layout>
      </Flex>
    </ChatContentContext.Provider>
  );
};

export default Chat;
