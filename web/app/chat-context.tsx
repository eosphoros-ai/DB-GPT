import { apiInterceptors, getDialogueList, getUsableModels, queryAdminList } from '@/client/api';
import { ChatHistoryResponse, DialogueListResponse, IChatDialogueSchema } from '@/types/chat';
import { UserInfoResponse } from '@/types/userinfo';
import { getUserId } from '@/utils';
import { STORAGE_THEME_KEY } from '@/utils/constants/index';
import { useRequest } from 'ahooks';
import { useSearchParams } from 'next/navigation';
import { createContext, useEffect, useMemo, useState } from 'react';

type ThemeMode = 'dark' | 'light';

interface IChatContext {
  mode: ThemeMode;
  isContract?: boolean;
  isMenuExpand?: boolean;
  scene: IChatDialogueSchema['chat_mode'] | (string & {});
  chatId: string;
  model: string;
  modelList: string[];
  dbParam?: string;
  agent: string;
  dialogueList?: DialogueListResponse;
  setAgent?: (val: string) => void;
  setMode: (mode: ThemeMode) => void;
  setModel: (val: string) => void;
  setIsContract: (val: boolean) => void;
  setIsMenuExpand: (val: boolean) => void;
  setDbParam: (val: string) => void;
  currentDialogue?: DialogueListResponse[0];
  history: ChatHistoryResponse;
  setHistory: (val: ChatHistoryResponse) => void;
  docId?: number;
  setDocId: (docId: number) => void;
  // 当前对话信息
  currentDialogInfo: {
    chat_scene: string;
    app_code: string;
  };
  setCurrentDialogInfo: (val: { chat_scene: string; app_code: string }) => void;
  adminList: UserInfoResponse[];
  refreshDialogList?: any;
}

function getDefaultTheme(): ThemeMode {
  const theme = localStorage.getItem(STORAGE_THEME_KEY) as ThemeMode;
  if (theme) return theme;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

const ChatContext = createContext<IChatContext>({
  mode: 'light',
  scene: '',
  chatId: '',
  model: '',
  modelList: [],
  dbParam: undefined,
  dialogueList: [],
  agent: '',
  setAgent: () => {},
  setModel: () => {},
  setIsContract: () => {},
  setIsMenuExpand: () => {},
  setDbParam: () => void 0,
  setMode: () => void 0,
  history: [],
  setHistory: () => {},
  docId: undefined,
  setDocId: () => {},
  currentDialogInfo: {
    chat_scene: '',
    app_code: '',
  },
  setCurrentDialogInfo: () => {},
  adminList: [],
  refreshDialogList: () => {},
});

const ChatContextProvider = ({ children }: { children: React.ReactElement }) => {
  const searchParams = useSearchParams();
  const chatId = searchParams?.get('id') ?? '';
  const scene = searchParams?.get('scene') ?? '';
  const db_param = searchParams?.get('db_param') ?? '';
  const [isContract, setIsContract] = useState(false);
  const [model, setModel] = useState<string>('');
  const [isMenuExpand, setIsMenuExpand] = useState<boolean>(scene !== 'chat_dashboard');
  const [dbParam, setDbParam] = useState<string>(db_param);
  const [agent, setAgent] = useState<string>('');
  const [history, setHistory] = useState<ChatHistoryResponse>([]);
  const [docId, setDocId] = useState<number>();
  const [mode, setMode] = useState<ThemeMode>('light');
  // 管理员列表
  const [adminList, setAdminList] = useState<UserInfoResponse[]>([]);

  const [currentDialogInfo, setCurrentDialogInfo] = useState({
    chat_scene: '',
    app_code: '',
  });

  // 获取model
  const { data: modelList = [] } = useRequest(async () => {
    const [, res] = await apiInterceptors(getUsableModels());
    return res ?? [];
  });

  // 获取管理员列表
  const { run: queryAdminListRun } = useRequest(
    async () => {
      const [, res] = await apiInterceptors(queryAdminList({ role: 'admin' }));
      return res ?? [];
    },
    {
      onSuccess: (data) => {
        setAdminList(data);
      },
      manual: true,
    },
  );

  useEffect(() => {
    if (getUserId()) {
      queryAdminListRun();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queryAdminListRun, getUserId()]);

  useEffect(() => {
    setMode(getDefaultTheme());
    try {
      const dialogInfo = JSON.parse(localStorage.getItem('cur_dialog_info') || '');
      setCurrentDialogInfo(dialogInfo);
    } catch (error) {
      setCurrentDialogInfo({
        chat_scene: '',
        app_code: '',
      });
    }
  }, []);

  useEffect(() => {
    setModel(modelList[0]);
  }, [modelList, modelList?.length]);

  const contextValue = {
    isContract,
    isMenuExpand,
    scene,
    chatId,
    model,
    modelList,
    dbParam: dbParam || db_param,
    agent,
    setAgent,
    mode,
    setMode,
    setModel,
    setIsContract,
    setIsMenuExpand,
    setDbParam,
    history,
    setHistory,
    docId,
    setDocId,
    currentDialogInfo,
    setCurrentDialogInfo,
    adminList,
  };
  return <ChatContext.Provider value={contextValue}>{children}</ChatContext.Provider>;
};

export { ChatContext, ChatContextProvider };
