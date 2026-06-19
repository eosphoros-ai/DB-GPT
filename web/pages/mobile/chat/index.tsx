import { ChatContext } from '@/app/chat-context';
import { apiInterceptors, getAppInfo, getChatHistory, getDialogueList, postChatModeParamsList } from '@/client/api';
import useUser from '@/hooks/use-user';
import { IApp } from '@/types/app';
import { ChatHistoryResponse } from '@/types/chat';
import { getUserId } from '@/utils';
import { HEADER_USER_ID_KEY } from '@/utils/constants/index';
import { EventStreamContentType, fetchEventSource } from '@microsoft/fetch-event-source';
import { useRequest } from 'ahooks';
import { Spin } from 'antd';
import dynamic from 'next/dynamic';
import { useSearchParams } from 'next/navigation';
import React, { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react';
import Header from './components/Header';
import InputContainer from './components/InputContainer';

const Content = dynamic(() => import('@/pages/mobile/chat/components/Content'), { ssr: false });

interface MobileChatProps {
  model: string;
  temperature: number;
  resource: any;
  setResource: React.Dispatch<React.SetStateAction<any>>;
  setTemperature: React.Dispatch<React.SetStateAction<number>>;
  setModel: React.Dispatch<React.SetStateAction<string>>;
  scene: string;
  history: ChatHistoryResponse; // Conversation content
  setHistory: React.Dispatch<React.SetStateAction<ChatHistoryResponse>>;
  scrollViewRef: React.RefObject<HTMLDivElement>; // Scrollable conversation area
  appInfo: IApp;
  conv_uid: string;
  resourceList?: Record<string, any>[];
  order: React.MutableRefObject<number>;
  handleChat: (_content?: string) => Promise<void>;
  canAbort: boolean;
  setCarAbort: React.Dispatch<React.SetStateAction<boolean>>;
  canNewChat: boolean;
  setCanNewChat: React.Dispatch<React.SetStateAction<boolean>>;
  ctrl: React.MutableRefObject<AbortController | undefined>;
  userInput: string;
  setUserInput: React.Dispatch<React.SetStateAction<string>>;
  getChatHistoryRun: () => void;
}

export const MobileChatContext = createContext<MobileChatProps>({
  model: '',
  temperature: 0.5,
  resource: null,
  setModel: () => {},
  setTemperature: () => {},
  setResource: () => {},
  scene: '',
  history: [],
  setHistory: () => {},
  scrollViewRef: { current: null },
  appInfo: {} as IApp,
  conv_uid: '',
  resourceList: [],
  order: { current: 1 },
  handleChat: () => Promise.resolve(),
  canAbort: false,
  setCarAbort: () => {},
  canNewChat: false,
  setCanNewChat: () => {},
  ctrl: { current: undefined },
  userInput: '',
  setUserInput: () => {},
  getChatHistoryRun: () => {},
});

const MobileChat: React.FC = () => {
  // Read basic params from the URL
  const searchParams = useSearchParams();
  const chatScene = searchParams?.get('chat_scene') ?? '';
  const appCode = searchParams?.get('app_code') ?? '';
  // Model list
  const { modelList } = useContext(ChatContext);

  const [history, setHistory] = useState<ChatHistoryResponse>([]);
  const [model, setModel] = useState<string>('');
  const [temperature, setTemperature] = useState<number>(0.5);
  const [resource, setResource] = useState<any>(null);
  const scrollViewRef = useRef<HTMLDivElement>(null);
  // User input
  const [userInput, setUserInput] = useState<string>('');
  // Whether the response can be aborted
  const [canAbort, setCarAbort] = useState<boolean>(false);
  // Whether a new question can be started (only after the previous reply ends or is paused)
  const [canNewChat, setCanNewChat] = useState<boolean>(true);

  const ctrl = useRef<AbortController>();
  const order = useRef<number>(1);

  // User info
  const userInfo = useUser();

  // Conversation ID
  const conv_uid = useMemo(() => `${userInfo?.user_no}_${appCode}`, [appCode, userInfo]);

  // Fetch conversation history
  const { run: getChatHistoryRun, loading: historyLoading } = useRequest(
    async () => await apiInterceptors(getChatHistory(`${userInfo?.user_no}_${appCode}`)),
    {
      manual: true,
      onSuccess: data => {
        const [, res] = data;
        const viewList = res?.filter(item => item.role === 'view');
        if (viewList && viewList.length > 0) {
          order.current = viewList[viewList.length - 1].order + 1;
        }
        setHistory(res || []);
      },
    },
  );

  // Fetch app info
  const {
    data: appInfo,
    run: getAppInfoRun,
    loading: appInfoLoading,
  } = useRequest(
    async (params: { chat_scene: string; app_code: string }) => {
      const [, res] = await apiInterceptors(getAppInfo(params));
      return res ?? ({} as IApp);
    },
    {
      manual: true,
    },
  );

  // Fetch selectable resource types
  const {
    run,
    data,
    loading: resourceLoading,
  } = useRequest(
    async () => {
      const [, res] = await apiInterceptors(postChatModeParamsList(chatScene));
      setResource(res?.[0]?.space_id || res?.[0]?.param);
      return res ?? [];
    },
    {
      manual: true,
    },
  );

  // Fetch conversation list
  const { run: getDialogueListRun, loading: dialogueListLoading } = useRequest(
    async () => {
      const [, res] = await apiInterceptors(getDialogueList());
      return res ?? [];
    },
    {
      manual: true,
      onSuccess: data => {
        const filterDialogue = data?.filter(item => item.conv_uid === conv_uid)?.[0];
        filterDialogue?.select_param && setResource(JSON.parse(filterDialogue?.select_param));
      },
    },
  );

  // Fetch app info
  useEffect(() => {
    if (chatScene && appCode && modelList.length) {
      getAppInfoRun({ chat_scene: chatScene, app_code: appCode });
    }
  }, [appCode, chatScene, getAppInfoRun, modelList]);

  // Load conversation history
  useEffect(() => {
    appCode && getChatHistoryRun();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [appCode]);

  // Set default model
  useEffect(() => {
    if (modelList.length > 0) {
      // Use model from app info
      const infoModel = appInfo?.param_need?.filter(item => item.type === 'model')?.[0]?.value;
      setModel(infoModel || modelList[0]);
    }
  }, [modelList, appInfo]);

  // Set default temperature
  useEffect(() => {
    // Use temperature from app info
    const infoTemperature = appInfo?.param_need?.filter(item => item.type === 'temperature')?.[0]?.value;
    setTemperature(infoTemperature || 0.5);
  }, [appInfo]);

  // Fetch selectable resource list
  useEffect(() => {
    if (chatScene && appInfo?.app_code) {
      const resourceVal = appInfo?.param_need?.filter(item => item.type === 'resource')?.[0]?.value;
      const bindResourceVal = appInfo?.param_need?.filter(item => item.type === 'resource')?.[0]?.bind_value;
      bindResourceVal && setResource(bindResourceVal);
      ['database', 'knowledge', 'plugin', 'awel_flow'].includes(resourceVal) && !bindResourceVal && run();
    }
  }, [appInfo, chatScene, run]);

  // Handle chat
  const handleChat = async (content?: string) => {
    setUserInput('');
    ctrl.current = new AbortController();
    const params = {
      chat_mode: chatScene,
      model_name: model,
      user_input: content || userInput,
      conv_uid,
      temperature,
      app_code: appInfo?.app_code,
      ...(resource && { select_param: resource }),
    };
    if (history && history.length > 0) {
      const viewList = history?.filter(item => item.role === 'view');
      order.current = viewList[viewList.length - 1].order + 1;
    }
    const tempHistory: ChatHistoryResponse = [
      {
        role: 'human',
        context: content || userInput,
        model_name: model,
        order: order.current,
        time_stamp: 0,
      },
      {
        role: 'view',
        context: '',
        model_name: model,
        order: order.current,
        time_stamp: 0,
        thinking: true,
      },
    ];
    const index = tempHistory.length - 1;
    setHistory([...history, ...tempHistory]);
    setCanNewChat(false);
    try {
      await fetchEventSource(`${process.env.API_BASE_URL ?? ''}/api/v1/chat/completions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          [HEADER_USER_ID_KEY]: getUserId() ?? '',
        },
        signal: ctrl.current.signal,
        body: JSON.stringify(params),
        openWhenHidden: true,
        async onopen(response) {
          if (response.ok && response.headers.get('content-type') === EventStreamContentType) {
            return;
          }
        },
        onclose() {
          ctrl.current?.abort();
          setCanNewChat(true);
          setCarAbort(false);
        },
        onerror(err) {
          throw new Error(err);
        },
        onmessage: event => {
          let message = event.data;
          try {
            message = JSON.parse(message).vis;
          } catch {
            message.replaceAll('\\n', '\n');
          }
          if (message === '[DONE]') {
            setCanNewChat(true);
            setCarAbort(false);
          } else if (message?.startsWith('[ERROR]')) {
            tempHistory[index].context = message?.replace('[ERROR]', '');
            tempHistory[index].thinking = false;
            setHistory([...history, ...tempHistory]);
            setCanNewChat(true);
            setCarAbort(false);
          } else {
            setCarAbort(true);
            tempHistory[index].context = message;
            tempHistory[index].thinking = false;
            setHistory([...history, ...tempHistory]);
          }
        },
      });
    } catch {
      ctrl.current?.abort();
      tempHistory[index].context = 'Sorry, we meet some error, please try again later.';
      tempHistory[index].thinking = false;
      setHistory([...tempHistory]);
      setCanNewChat(true);
      setCarAbort(false);
    }
  };

  // For native apps, fetch conversation list to get resource params
  useEffect(() => {
    if (chatScene && chatScene !== 'chat_agent') {
      getDialogueListRun();
    }
  }, [chatScene, getDialogueListRun]);

  return (
    <MobileChatContext.Provider
      value={{
        model,
        resource,
        setModel,
        setTemperature,
        setResource,
        temperature,
        appInfo: appInfo as IApp,
        conv_uid,
        scene: chatScene,
        history,
        scrollViewRef,
        setHistory,
        resourceList: data,
        order,
        handleChat,
        setCanNewChat,
        ctrl,
        canAbort,
        setCarAbort,
        canNewChat,
        userInput,
        setUserInput,
        getChatHistoryRun,
      }}
    >
      <Spin
        size='large'
        className='flex h-screen w-screen justify-center items-center max-h-screen'
        spinning={historyLoading || appInfoLoading || resourceLoading || dialogueListLoading}
      >
        <div className='flex flex-col h-screen bg-gradient-light dark:bg-gradient-dark p-4 pt-0'>
          <div ref={scrollViewRef} className='flex flex-col flex-1 overflow-y-auto mb-3'>
            <Header />
            <Content />
          </div>
          {appInfo?.app_code && <InputContainer />}
        </div>
      </Spin>
    </MobileChatContext.Provider>
  );
};

export default MobileChat;
