import { ChatContext } from '@/app/chat-context';
import { apiInterceptors, getAppInfo } from '@/client/api';
import MonacoEditor from '@/components/chat/monaco-editor';
import ChatContent from '@/new-components/chat/content/ChatContent';
import { ChatContentContext } from '@/pages/chat';
import { IApp } from '@/types/app';
import { IChatDialogueMessageSchema } from '@/types/chat';
import { STORAGE_INIT_MESSAGE_KET, getInitMessage } from '@/utils';
import { useAsyncEffect } from 'ahooks';
import { Modal } from 'antd';
import { cloneDeep } from 'lodash';
import { useSearchParams } from 'next/navigation';
import React, { useContext, useEffect, useMemo, useRef, useState } from 'react';
import { v4 as uuid } from 'uuid';

const ChatCompletion: React.FC = () => {
  const scrollableRef = useRef<HTMLDivElement>(null);
  const searchParams = useSearchParams();
  const chatId = searchParams?.get('id') ?? '';

  const { currentDialogInfo, model } = useContext(ChatContext);
  const { history, handleChat, refreshDialogList, setAppInfo, setModelValue, setTemperatureValue, setResourceValue } =
    useContext(ChatContentContext);

  const [jsonModalOpen, setJsonModalOpen] = useState(false);
  const [jsonValue, setJsonValue] = useState<string>('');

  const showMessages = useMemo(() => {
    const tempMessage: IChatDialogueMessageSchema[] = cloneDeep(history);
    return tempMessage
      .filter(item => ['view', 'human'].includes(item.role))
      .map(item => {
        return {
          ...item,
          key: uuid(),
        };
      });
  }, [history]);

  useAsyncEffect(async () => {
    const initMessage = getInitMessage();
    if (initMessage && initMessage.id === chatId) {
      const [, res] = await apiInterceptors(
        getAppInfo({
          ...currentDialogInfo,
        }),
      );
      if (res) {
        const paramKey: string[] = res?.param_need?.map(i => i.type) || [];
        const resModel = res?.param_need?.filter(item => item.type === 'model')[0]?.value || model;
        const temperature = res?.param_need?.filter(item => item.type === 'temperature')[0]?.value || 0.5;
        const resource = res?.param_need?.filter(item => item.type === 'resource')[0]?.bind_value;
        setAppInfo(res || ({} as IApp));
        setTemperatureValue(temperature || 0.5);
        setModelValue(resModel);
        setResourceValue(resource);
        await handleChat(initMessage.message, {
          app_code: res?.app_code,
          model_name: resModel,
          ...(paramKey?.includes('temperature') && { temperature }),
          ...(paramKey.includes('resource') && {
            select_param: typeof resource === 'string' ? resource : JSON.stringify(resource),
          }),
        });
        await refreshDialogList();
        localStorage.removeItem(STORAGE_INIT_MESSAGE_KET);
      }
    }
  }, [chatId, currentDialogInfo]);

  useEffect(() => {
    setTimeout(() => {
      scrollableRef.current?.scrollTo(0, scrollableRef.current?.scrollHeight);
    }, 50);
  }, [history, history[history.length - 1].context]);

  return (
    <div className='flex flex-col w-5/6 mx-auto' ref={scrollableRef}>
      {!!showMessages.length &&
        showMessages.map((content, index) => {
          return (
            <ChatContent
              key={index}
              content={content}
              onLinkClick={() => {
                setJsonModalOpen(true);
                setJsonValue(JSON.stringify(content?.context, null, 2));
              }}
            />
          );
        })}
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
    </div>
  );
};

export default ChatCompletion;
