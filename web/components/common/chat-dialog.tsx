import useChat from '@/hooks/use-chat';
import CompletionInput from './completion-input';
import { useCallback, useState } from 'react';
import { IChatDialogueMessageSchema, IChatDialogueSchema } from '@/types/chat';
import AgentContent from '../chat/agent-content';
import { renderModelIcon } from '../chat/header/model-selector';
import MyEmpty from './MyEmpty';
import { CaretLeftOutlined } from '@ant-design/icons';
import classNames from 'classnames';
import { useRequest } from 'ahooks';
import { apiInterceptors, newDialogue } from '@/client/api';
import ChatContent from '../chat/chat-content';

interface Props {
  title?: string;
  completionApi?: string;
  chatMode: IChatDialogueSchema['chat_mode'];
  chatParams?: {
    select_param?: string;
  } & Record<string, string>;
  model?: string;
}

function ChatDialog({ title, chatMode, completionApi, chatParams, model = '' }: Props) {
  const chat = useChat({ queryAgentURL: completionApi });

  const [loading, setLoading] = useState(false);
  const [list, setList] = useState<IChatDialogueMessageSchema[]>([]);
  const [open, setOpen] = useState(false);

  const { data } = useRequest(
    async () => {
      const [, res] = await apiInterceptors(newDialogue({ chat_mode: chatMode }));
      return res;
    },
    {
      ready: !!chatMode,
    },
  );

  const handleChat = useCallback(
    (content: string) => {
      if (!data) return;
      return new Promise<void>((resolve) => {
        const tempList: IChatDialogueMessageSchema[] = [
          ...list,
          { role: 'human', context: content, model_name: model, order: 0, time_stamp: 0 },
          { role: 'view', context: '', model_name: model, order: 0, time_stamp: 0 },
        ];
        const index = tempList.length - 1;
        setList([...tempList]);
        setLoading(true);
        chat({
          chatId: data?.conv_uid,
          data: { ...chatParams, chat_mode: chatMode, model_name: model, user_input: content },
          onMessage: (message) => {
            tempList[index].context = message;
            setList([...tempList]);
          },
          onDone: () => {
            resolve();
          },
          onClose: () => {
            resolve();
          },
          onError: (message) => {
            tempList[index].context = message;
            setList([...tempList]);
            resolve();
          },
        }).finally(() => {
          setLoading(false);
        });
      });
    },
    [chat, list, data?.conv_uid],
  );

  return (
    <div
      className={classNames(
        'fixed top-0 right-0 w-[30rem] h-screen flex flex-col bg-white dark:bg-theme-dark-container shadow-[-5px_0_40px_-4px_rgba(100,100,100,.1)] transition-transform duration-300',
        {
          'translate-x-0': open,
          'translate-x-full': !open,
        },
      )}
    >
      {title && <div className="p-4 border-b border-solid border-gray-100">{title}</div>}
      <div className="flex-1 overflow-y-auto px-2">
        {list.map((item, index) => (
          <>{chatParams?.chat_mode === 'chat_agent' ? <AgentContent key={index} content={item} /> : <ChatContent key={index} content={item} />}</>
        ))}
        {!list.length && <MyEmpty description="" />}
      </div>
      <div className="flex w-full p-4 border-t border-solid border-gray-100 items-center">
        {model && <div className="mr-2 flex">{renderModelIcon(model)}</div>}
        <CompletionInput loading={loading} onSubmit={handleChat} />
      </div>
      <div
        className="flex items-center justify-center rounded-tl rounded-bl cursor-pointer w-5 h-11 absolute top-[50%] -left-5 -translate-y-[50%] bg-white"
        onClick={() => {
          setOpen(!open);
        }}
      >
        <CaretLeftOutlined />
      </div>
    </div>
  );
}

export default ChatDialog;
