import { ChatContentContext } from '@/pages/chat';
import { LoadingOutlined } from '@ant-design/icons';
import { Button, Input, Spin } from 'antd';
import classNames from 'classnames';
import { usePageQuery } from '@/utils/use-page-query';
import React, { forwardRef, useContext, useImperativeHandle, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { UserChatContent } from '@/types/chat';
import { parseResourceValue } from '@/utils';
import { SlashCommand } from './CommandPopover';
import EnhancedChatInput, { ContentPart, EnhancedChatInputRef } from './EnhancedChatInput';
import ToolsBar from './ToolsBar';

const USE_ENHANCED_INPUT = false;

const defaultCommands: SlashCommand[] = [
  { id: 'clear', trigger: 'clear', title: 'Clear chat history', type: 'builtin' },
  { id: 'help', trigger: 'help', title: 'Show available commands', type: 'builtin' },
  { id: 'model', trigger: 'model', title: 'Switch AI model', type: 'builtin' },
];

const ChatInputPanel: React.ForwardRefRenderFunction<any, { ctrl: AbortController }> = ({ ctrl }, ref) => {
  const { t } = useTranslation();
  const {
    replyLoading,
    handleChat,
    appInfo,
    currentDialogue,
    temperatureValue,
    maxNewTokensValue,
    resourceValue,
    knowledgeValue,
    setResourceValue,
    refreshDialogList,
  } = useContext(ChatContentContext);

  const searchParams = usePageQuery();
  const scene = searchParams.get('scene') ?? '';
  const select_param = searchParams.get('select_param') ?? '';

  const [userInput, setUserInput] = useState<string>('');
  const [isFocus, setIsFocus] = useState<boolean>(false);
  const [isZhInput, setIsZhInput] = useState<boolean>(false);

  const enhancedInputRef = useRef<EnhancedChatInputRef>(null);
  const submitCountRef = useRef(0);

  const paramKey: string[] = useMemo(() => {
    return appInfo.param_need?.map(i => i.type) || [];
  }, [appInfo.param_need]);

  const buildChatParams = () => ({
    app_code: appInfo.app_code || '',
    ...(paramKey.includes('temperature') && { temperature: temperatureValue }),
    ...(paramKey.includes('max_new_tokens') && { max_new_tokens: maxNewTokensValue }),
    select_param,
    ...(paramKey.includes('resource') && {
      select_param:
        typeof resourceValue === 'string'
          ? resourceValue
          : JSON.stringify(resourceValue) || currentDialogue.select_param,
    }),
    // Include knowledge space in ext_info for RAG
    ...(knowledgeValue && {
      ext_info: { knowledge_space: knowledgeValue },
    }),
  });

  const handleEnhancedSubmit = async (text: string, parts: ContentPart[]) => {
    submitCountRef.current++;

    const resources = parseResourceValue(resourceValue);
    let newUserInput: UserChatContent;

    const imageParts = parts.filter(p => p.type === 'image');
    const hasImages = imageParts.length > 0;
    const hasResources = resources.length > 0;

    if (hasResources || hasImages) {
      if (scene !== 'chat_excel') {
        setResourceValue(null);
      }

      const messages = [...resources];

      imageParts.forEach(img => {
        if (img.dataUrl) {
          messages.push({
            type: 'image_url',
            image_url: {
              url: img.dataUrl,
              fileName: img.filename || 'image',
            },
          });
        }
      });

      messages.push({
        type: 'text',
        text: text,
      });

      newUserInput = {
        role: 'user',
        content: messages,
      };
    } else {
      newUserInput = text;
    }

    const params = buildChatParams();
    await handleChat(newUserInput, params);

    if (submitCountRef.current === 1) {
      await refreshDialogList();
    }
  };

  const onLegacySubmit = async () => {
    submitCountRef.current++;
    setUserInput('');
    const resources = parseResourceValue(resourceValue);
    let newUserInput: UserChatContent;
    if (resources.length > 0) {
      if (scene !== 'chat_excel') {
        setResourceValue(null);
      }
      const messages = [...resources];
      messages.push({
        type: 'text',
        text: userInput,
      });
      newUserInput = {
        role: 'user',
        content: messages,
      };
    } else {
      newUserInput = userInput;
    }

    const params = buildChatParams();
    await handleChat(newUserInput, params);

    if (submitCountRef.current === 1) {
      await refreshDialogList();
    }
  };

  const handleCommandSelect = (command: SlashCommand) => {
    console.log('Command selected:', command);
  };

  useImperativeHandle(ref, () => ({
    setUserInput: (value: string) => {
      if (USE_ENHANCED_INPUT) {
        enhancedInputRef.current?.setValue(value);
      } else {
        setUserInput(value);
      }
    },
  }));

  if (USE_ENHANCED_INPUT) {
    return (
      <div className='flex flex-col w-5/6 mx-auto pt-4 pb-6 bg-transparent'>
        <div className='flex flex-col bg-white dark:bg-[rgba(255,255,255,0.16)] px-5 py-4 pt-2 rounded-xl relative'>
          <ToolsBar ctrl={ctrl} />
          <EnhancedChatInput
            ref={enhancedInputRef}
            onSubmit={handleEnhancedSubmit}
            disabled={replyLoading}
            loading={replyLoading}
            placeholder={t('input_tips')}
            commands={defaultCommands}
            onCommandSelect={handleCommandSelect}
            className='border-0 bg-transparent'
            maxHeight={150}
          />
        </div>
      </div>
    );
  }

  return (
    <div className='flex flex-col w-5/6 mx-auto pt-4 pb-6 bg-transparent'>
      <div
        className={`flex flex-1 flex-col bg-white dark:bg-[rgba(255,255,255,0.16)] px-5 py-4 pt-2 rounded-xl relative border-t border-b border-l border-r dark:border-[rgba(255,255,255,0.6)] ${
          isFocus ? 'border-[#0c75fc]' : ''
        }`}
        id='input-panel'
      >
        <ToolsBar ctrl={ctrl} />
        <Input.TextArea
          placeholder={t('input_tips')}
          className='w-full h-20 resize-none border-0 p-0 focus:shadow-none dark:bg-transparent'
          value={userInput}
          onKeyDown={e => {
            if (e.key === 'Enter') {
              if (e.shiftKey) {
                return;
              }
              if (isZhInput) {
                return;
              }
              e.preventDefault();
              if (!userInput.trim() || replyLoading) {
                return;
              }
              onLegacySubmit();
            }
          }}
          onChange={e => {
            setUserInput(e.target.value);
          }}
          onFocus={() => {
            setIsFocus(true);
          }}
          onBlur={() => setIsFocus(false)}
          onCompositionStart={() => setIsZhInput(true)}
          onCompositionEnd={() => setIsZhInput(false)}
        />
        <Button
          type='primary'
          className={classNames(
            'flex items-center justify-center w-14 h-8 rounded-lg text-sm absolute right-4 bottom-3 bg-button-gradient border-0',
            {
              'cursor-not-allowed': !userInput.trim(),
            },
          )}
          onClick={() => {
            if (replyLoading || !userInput.trim()) {
              return;
            }
            onLegacySubmit();
          }}
        >
          {replyLoading ? (
            <Spin spinning={replyLoading} indicator={<LoadingOutlined className='text-white' />} />
          ) : (
            t('sent')
          )}
        </Button>
      </div>
    </div>
  );
};

export default forwardRef(ChatInputPanel);
