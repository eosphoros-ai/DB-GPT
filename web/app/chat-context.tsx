import { createContext, useEffect, useMemo, useState } from 'react';
import { apiInterceptors, getDialogueList, getUsableModels } from '@/client/api';
import { useRequest } from 'ahooks';
import { ChatHistoryResponse, DialogueListResponse, IChatDialogueSchema } from '@/types/chat';
import { useSearchParams } from 'next/navigation';

interface IChatContext {
  isContract?: boolean;
  isMenuExpand?: boolean;
  scene: IChatDialogueSchema['chat_mode'] | (string & {});
  chatId: string;
  model: string;
  dbParam?: string;
  modelList: Array<string>;
  agentList: string[];
  dialogueList?: DialogueListResponse;
  setAgentList?: (val: string[]) => void;
  setModel: (val: string) => void;
  setIsContract: (val: boolean) => void;
  setIsMenuExpand: (val: boolean) => void;
  setDbParam: (val: string) => void;
  queryDialogueList: () => void;
  refreshDialogList: () => void;
  currentDialogue?: DialogueListResponse[0];
  history: ChatHistoryResponse;
  setHistory: (val: ChatHistoryResponse) => void;
  docId?: number;
  setDocId: (docId: number) => void;
}

const ChatContext = createContext<IChatContext>({
  scene: '',
  chatId: '',
  modelList: [],
  model: '',
  dbParam: undefined,
  dialogueList: [],
  agentList: [],
  setAgentList: () => {},
  setModel: () => {},
  setIsContract: () => {},
  setIsMenuExpand: () => {},
  setDbParam: () => void 0,
  queryDialogueList: () => {},
  refreshDialogList: () => {},
  history: [],
  setHistory: () => {},
  docId: undefined,
  setDocId: () => {},
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
  const [agentList, setAgentList] = useState<string[]>([]);
  const [history, setHistory] = useState<ChatHistoryResponse>([]);
  const [docId, setDocId] = useState<number>();

  const {
    run: queryDialogueList,
    data: dialogueList = [],
    refresh: refreshDialogList,
  } = useRequest(
    async () => {
      const [, res] = await apiInterceptors(getDialogueList());
      return res ?? [];
    },
    {
      manual: true,
    },
  );

  const { data: modelList = [] } = useRequest(async () => {
    const [, res] = await apiInterceptors(getUsableModels());
    return res ?? [];
  });
  useEffect(() => {
    setModel(modelList[0]);
  }, [modelList, modelList?.length]);

  const currentDialogue = useMemo(() => dialogueList.find((item: any) => item.conv_uid === chatId), [chatId, dialogueList]);
  const contextValue = {
    isContract,
    isMenuExpand,
    scene,
    chatId,
    modelList,
    model,
    dbParam: dbParam || db_param,
    dialogueList,
    agentList,
    setAgentList,
    setModel,
    setIsContract,
    setIsMenuExpand,
    setDbParam,
    queryDialogueList,
    refreshDialogList,
    currentDialogue,
    history,
    setHistory,
    docId,
    setDocId,
  };
  return <ChatContext.Provider value={contextValue}>{children}</ChatContext.Provider>;
};

export { ChatContext, ChatContextProvider };
