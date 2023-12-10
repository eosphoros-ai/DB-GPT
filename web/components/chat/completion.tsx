import { useState, useRef, useEffect, useMemo, useContext } from 'react';
import { useSearchParams } from 'next/navigation';
import MonacoEditor from './monaco-editor';
import ChatContent from './chat-content';
import ChatFeedback from './chat-feedback';
import { ChatContext } from '@/app/chat-context';
import { FeedBack, IChatDialogueMessageSchema } from '@/types/chat';
import classNames from 'classnames';
import { Empty, Modal, message, Tooltip } from 'antd';
import { renderModelIcon } from './header/model-selector';
import { cloneDeep } from 'lodash';
import copy from 'copy-to-clipboard';
import { useTranslation } from 'react-i18next';
import CompletionInput from '../common/completion-input';
import { useAsyncEffect } from 'ahooks';
import { STORAGE_INIT_MESSAGE_KET } from '@/utils';
import { Button, IconButton } from '@mui/joy';
import { CopyOutlined, RedoOutlined } from '@ant-design/icons';
import { getInitMessage } from '@/utils';
import { apiInterceptors, getChatFeedBackSelect } from '@/client/api';
import useSummary from '@/hooks/use-summary';

type Props = {
  messages: IChatDialogueMessageSchema[];
  onSubmit: (message: string, otherQueryBody?: Record<string, any>) => Promise<void>;
};

const Completion = ({ messages, onSubmit }: Props) => {
  const { dbParam, currentDialogue, scene, model, refreshDialogList, chatId, agentList, docId } = useContext(ChatContext);
  const { t } = useTranslation();
  const searchParams = useSearchParams();

  const spaceNameOriginal = (searchParams && searchParams.get('spaceNameOriginal')) ?? '';

  const [isLoading, setIsLoading] = useState(false);
  const [jsonModalOpen, setJsonModalOpen] = useState(false);
  const [showMessages, setShowMessages] = useState(messages);
  const [jsonValue, setJsonValue] = useState<string>('');
  const [select_param, setSelectParam] = useState<FeedBack>();

  const scrollableRef = useRef<HTMLDivElement>(null);

  const isChartChat = useMemo(() => scene === 'chat_dashboard', [scene]);

  const summary = useSummary();

  const selectParam = useMemo(() => {
    switch (scene) {
      case 'chat_agent':
        return agentList.join(',');
      case 'chat_excel':
        return currentDialogue?.select_param;
      default:
        return spaceNameOriginal || dbParam;
    }
  }, [scene, agentList, currentDialogue, dbParam, spaceNameOriginal]);

  const handleChat = async (message: string) => {
    if (isLoading || !message.trim()) return;
    try {
      setIsLoading(true);
      await onSubmit(message, {
        select_param: selectParam ?? '',
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleJson2Obj = (jsonStr: string) => {
    try {
      return JSON.parse(jsonStr);
    } catch (e) {
      return jsonStr;
    }
  };

  const [messageApi, contextHolder] = message.useMessage();

  const onCopyContext = async (context: any) => {
    const pureStr = context?.replace(/\trelations:.*/g, '');
    const result = copy(pureStr);
    if (result) {
      if (pureStr) {
        messageApi.open({ type: 'success', content: t('Copy_success') });
      } else {
        messageApi.open({ type: 'warning', content: t('Copy_nothing') });
      }
    } else {
      messageApi.open({ type: 'error', content: t('Copry_error') });
    }
  };

  const handleRetry = async () => {
    if (isLoading || !docId) {
      return;
    }
    setIsLoading(true);
    await summary(docId);
    setIsLoading(false);
  };

  useAsyncEffect(async () => {
    const initMessage = getInitMessage();
    if (initMessage && initMessage.id === chatId) {
      await handleChat(initMessage.message);
      refreshDialogList();
      localStorage.removeItem(STORAGE_INIT_MESSAGE_KET);
    }
  }, [chatId]);

  useEffect(() => {
    let tempMessage: IChatDialogueMessageSchema[] = messages;
    if (isChartChat) {
      tempMessage = cloneDeep(messages).map((item) => {
        if (item?.role === 'view' && typeof item?.context === 'string') {
          item.context = handleJson2Obj(item?.context);
        }
        return item;
      });
    }
    setShowMessages(tempMessage.filter((item) => ['view', 'human'].includes(item.role)));
  }, [isChartChat, messages]);

  useEffect(() => {
    apiInterceptors(getChatFeedBackSelect())
      .then((res) => {
        setSelectParam(res[1] ?? {});
      })
      .catch((err) => {
        console.log(err);
      });
  }, []);

  useEffect(() => {
    setTimeout(() => {
      scrollableRef.current?.scrollTo(0, scrollableRef.current.scrollHeight);
    }, 50);
  }, [messages]);

  return (
    <>
      {contextHolder}
      <div ref={scrollableRef} className="flex flex-1 overflow-y-auto pb-8 w-full flex-col">
        <div className="flex items-center flex-1 flex-col text-sm leading-6 text-slate-900 dark:text-slate-300 sm:text-base sm:leading-7">
          {showMessages.length ? (
            showMessages.map((content, index) => {
              return (
                <ChatContent
                  key={index}
                  content={content}
                  isChartChat={isChartChat}
                  onLinkClick={() => {
                    setJsonModalOpen(true);
                    setJsonValue(JSON.stringify(content?.context, null, 2));
                  }}
                >
                  {content.role === 'view' && (
                    <div className="flex w-full pt-2 md:pt-4 border-t border-gray-200 mt-2 md:mt-4 pl-2">
                      {scene === 'chat_knowledge' && content.retry ? (
                        <Button onClick={handleRetry} slots={{ root: IconButton }} slotProps={{ root: { variant: 'plain', color: 'primary' } }}>
                          <RedoOutlined />
                          &nbsp;<span className="text-sm">{t('Retry')}</span>
                        </Button>
                      ) : null}
                      <div className="flex w-full flex-row-reverse">
                        <ChatFeedback
                          select_param={select_param}
                          conv_index={Math.ceil((index + 1) / 2)}
                          question={showMessages?.filter((e) => e?.role === 'human' && e?.order === content.order)[0]?.context}
                          knowledge_space={spaceNameOriginal || dbParam || ''}
                        />
                        <Tooltip title={t('Copy')}>
                          <Button
                            onClick={() => onCopyContext(content?.context)}
                            slots={{ root: IconButton }}
                            slotProps={{ root: { variant: 'plain', color: 'primary' } }}
                            sx={{ borderRadius: 40 }}
                          >
                            <CopyOutlined />
                          </Button>
                        </Tooltip>
                      </div>
                    </div>
                  )}
                </ChatContent>
              );
            })
          ) : (
            <Empty
              image="/empty.png"
              imageStyle={{ width: 320, height: 320, margin: '0 auto', maxWidth: '100%', maxHeight: '100%' }}
              className="flex items-center justify-center flex-col h-full w-full"
              description="Start a conversation"
            />
          )}
        </div>
      </div>
      <div
        className={classNames(
          'relative after:absolute after:-top-8 after:h-8 after:w-full after:bg-gradient-to-t after:from-white after:to-transparent dark:after:from-[#212121]',
          {
            'cursor-not-allowed': scene === 'chat_excel' && !currentDialogue?.select_param,
          },
        )}
      >
        <div className="flex flex-wrap w-full py-2 sm:pt-6 sm:pb-10 items-center">
          {model && <div className="mr-2 flex">{renderModelIcon(model)}</div>}
          <CompletionInput loading={isLoading} onSubmit={handleChat} handleFinish={setIsLoading} />
        </div>
      </div>
      <Modal
        title="JSON Editor"
        open={jsonModalOpen}
        width="60%"
        cancelButtonProps={{
          hidden: true,
        }}
        onOk={() => {
          setJsonModalOpen(false);
        }}
        onCancel={() => {
          setJsonModalOpen(false);
        }}
      >
        <MonacoEditor className="w-full h-[500px]" language="json" value={jsonValue} />
      </Modal>
    </>
  );
};

export default Completion;
