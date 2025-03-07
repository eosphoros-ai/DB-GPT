import { ChatContext } from '@/app/chat-context';
import { apiInterceptors, getChatFeedBackSelect } from '@/client/api';
import useSummary from '@/hooks/use-summary';
import { FeedBack, IChatDialogueMessageSchema } from '@/types/chat';
import { STORAGE_INIT_MESSAGE_KET, getInitMessage } from '@/utils';
import { CopyOutlined, RedoOutlined } from '@ant-design/icons';
import { Button, IconButton } from '@mui/joy';
import { useAsyncEffect } from 'ahooks';
import { Modal, Tooltip, message } from 'antd';
import classNames from 'classnames';
import copy from 'copy-to-clipboard';
import { cloneDeep } from 'lodash';
import { useSearchParams } from 'next/navigation';
import { useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import MyEmpty from '../common/MyEmpty';
import CompletionInput from '../common/completion-input';
import AgentContent from './agent-content';
import ChatContent from './chat-content';
import ChatFeedback from './chat-feedback';
import { renderModelIcon } from './header/model-selector';
import MonacoEditor from './monaco-editor';

type Props = {
  messages: IChatDialogueMessageSchema[];
  onSubmit: (message: string, otherQueryBody?: Record<string, any>) => Promise<void>;
  onFormatContent?: (content: any) => any; // Callback for extracting thinking part
};

const Completion = ({ messages, onSubmit, onFormatContent }: Props) => {
  const { dbParam, currentDialogue, scene, model, refreshDialogList, chatId, agent, docId } = useContext(ChatContext);
  const { t } = useTranslation();
  const searchParams = useSearchParams();

  const flowSelectParam = (searchParams && searchParams.get('select_param')) ?? '';
  const spaceNameOriginal = (searchParams && searchParams.get('spaceNameOriginal')) ?? '';

  const [isLoading, setIsLoading] = useState(false);
  const [jsonModalOpen, setJsonModalOpen] = useState(false);
  const [showMessages, setShowMessages] = useState(messages);
  const [jsonValue, setJsonValue] = useState<string>('');
  const [select_param, setSelectParam] = useState<FeedBack>();

  const scrollableRef = useRef<HTMLDivElement>(null);

  // const incremental = useMemo(() => scene === 'chat_flow', [scene]);
  const isChartChat = useMemo(() => scene === 'chat_dashboard', [scene]);

  const summary = useSummary();

  const selectParam = useMemo(() => {
    switch (scene) {
      case 'chat_agent':
        return agent;
      case 'chat_excel':
        return currentDialogue?.select_param;
      case 'chat_flow':
        return flowSelectParam;
      default:
        return spaceNameOriginal || dbParam;
    }
  }, [scene, agent, currentDialogue, dbParam, spaceNameOriginal, flowSelectParam]);

  const handleChat = async (content: string) => {
    if (isLoading || !content.trim()) return;
    if (scene === 'chat_agent' && !agent) {
      message.warning(t('choice_agent_tip'));
      return;
    }
    try {
      setIsLoading(true);
      await onSubmit(content, {
        select_param: selectParam ?? '',
        // incremental,
      });
    } finally {
      setIsLoading(false);
    }
  };

  // Process message content - if onFormatContent is provided and this is a dashboard chat,
  // we'll extract the thinking part from vis-thinking code blocks
  const processMessageContent = (content: any) => {
    if (isChartChat && onFormatContent && typeof content === 'string') {
      return onFormatContent(content);
    }
    return content;
  };

  const [messageApi, contextHolder] = message.useMessage();

  const onCopyContext = async (context: any) => {
    // If we have a formatting function and this is a string, apply it before copying
    const contentToCopy =
      isChartChat && onFormatContent && typeof context === 'string' ? onFormatContent(context) : context;

    const pureStr = contentToCopy?.replace(/\trelations:.*/g, '');
    const result = copy(pureStr);
    if (result) {
      if (pureStr) {
        messageApi.open({ type: 'success', content: t('copy_success') });
      } else {
        messageApi.open({ type: 'warning', content: t('copy_nothing') });
      }
    } else {
      messageApi.open({ type: 'error', content: t('copy_failed') });
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
      tempMessage = cloneDeep(messages).map(item => {
        if (item?.role === 'view') {
          if (typeof item?.context === 'string') {
            // Try to parse JSON first
            try {
              item.context = JSON.parse(item.context);
            } catch {
              // If JSON parsing fails and we have a formatting function,
              // it might be a vis-thinking block, so process it
              if (onFormatContent) {
                item.context = processMessageContent(item.context);
              }
            }
          }
        }
        return item;
      });
    }
    setShowMessages(tempMessage.filter(item => ['view', 'human'].includes(item.role)));
  }, [isChartChat, messages, onFormatContent]);

  useEffect(() => {
    apiInterceptors(getChatFeedBackSelect())
      .then(res => {
        setSelectParam(res[1] ?? {});
      })
      .catch(err => {
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
      <div ref={scrollableRef} className='flex flex-1 overflow-y-auto h-full w-full flex-col'>
        <div className='flex items-center flex-1 flex-col text-sm leading-6 text-slate-900 dark:text-slate-300 sm:text-base sm:leading-7'>
          {showMessages.length ? (
            showMessages.map((content, index) => {
              if (scene === 'chat_agent') {
                return <AgentContent key={index} content={content} />;
              }
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
                    <div className='flex w-full border-t border-gray-200 dark:border-theme-dark'>
                      {scene === 'chat_knowledge' && content.retry ? (
                        <Button
                          onClick={handleRetry}
                          slots={{ root: IconButton }}
                          slotProps={{ root: { variant: 'plain', color: 'primary' } }}
                        >
                          <RedoOutlined />
                          &nbsp;<span className='text-sm'>{t('Retry')}</span>
                        </Button>
                      ) : null}
                      <div className='flex w-full flex-row-reverse'>
                        <ChatFeedback
                          select_param={select_param}
                          conv_index={Math.ceil((index + 1) / 2)}
                          question={
                            showMessages?.filter(e => e?.role === 'human' && e?.order === content.order)[0]?.context
                          }
                          knowledge_space={spaceNameOriginal || dbParam || ''}
                        />
                        <Tooltip title={t('Copy_Btn')}>
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
            <MyEmpty description='Start a conversation' />
          )}
        </div>
      </div>
      <div
        className={classNames(
          'relative sticky bottom-0 bg-theme-light dark:bg-theme-dark after:absolute after:-top-8 after:h-8 after:w-full after:bg-gradient-to-t after:from-theme-light after:to-transparent dark:after:from-theme-dark',
          {
            'cursor-not-allowed': scene === 'chat_excel' && !currentDialogue?.select_param,
          },
        )}
      >
        <div className='flex flex-wrap w-full py-2 sm:pt-6 sm:pb-10 items-center'>
          {model && <div className='mr-2 flex'>{renderModelIcon(model)}</div>}
          <CompletionInput loading={isLoading} onSubmit={handleChat} handleFinish={setIsLoading} />
        </div>
      </div>
      <Modal
        title='JSON Editor'
        open={jsonModalOpen}
        width='60%'
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
        <MonacoEditor className='w-full h-[500px]' language='json' value={jsonValue} />
      </Modal>
    </>
  );
};

export default Completion;
