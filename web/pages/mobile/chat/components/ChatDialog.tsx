import ModelIcon from '@/new-components/chat/content/ModelIcon';
import MarkdownContext from '@/new-components/common/MarkdownContext';
import { IChatDialogueMessageSchema } from '@/types/chat';
import { Divider } from 'antd';
import cls from 'classnames';
import React, { memo, useContext, useMemo, useRef } from 'react';
import { MobileChatContext } from '../';
import Feedback from './Feedback';

type DBGPTView = {
  name: string;
  status: 'todo' | 'runing' | 'failed' | 'completed' | (string & {});
  result?: string;
  err_msg?: string;
};

// 对话气泡
const ChatDialog: React.FC<{
  message: IChatDialogueMessageSchema;
  index: number;
}> = ({ message, index }) => {
  const { scene } = useContext(MobileChatContext);
  const { context, model_name, role, thinking } = message;
  // GPT回复
  const isRobot = useMemo(() => role === 'view', [role]);

  const chatDialogRef = useRef<HTMLDivElement>(null);

  const { value } = useMemo<{
    relations: string[];
    value: string;
    cachePluginContext: DBGPTView[];
  }>(() => {
    if (typeof context !== 'string') {
      return {
        relations: [],
        value: '',
        cachePluginContext: [],
      };
    }
    const [value, relation] = context.split('\trelations:');
    const relations = relation ? relation.split(',') : [];
    const cachePluginContext: DBGPTView[] = [];

    let cacheIndex = 0;
    const result = value.replace(/<dbgpt-view[^>]*>[^<]*<\/dbgpt-view>/gi, matchVal => {
      try {
        const pluginVal = matchVal.replaceAll('\n', '\\n').replace(/<[^>]*>|<\/[^>]*>/gm, '');
        const pluginContext = JSON.parse(pluginVal) as DBGPTView;
        const replacement = `<custom-view>${cacheIndex}</custom-view>`;

        cachePluginContext.push({
          ...pluginContext,
          result: formatMarkdownVal(pluginContext.result ?? ''),
        });
        cacheIndex++;

        return replacement;
      } catch (e) {
        console.log((e as any).message, e);
        return matchVal;
      }
    });
    return {
      relations,
      cachePluginContext,
      value: result,
    };
  }, [context]);

  const formatMarkdownVal = (val: string) => {
    return val
      .replaceAll('\\n', '\n')
      .replace(/<table(\w*=[^>]+)>/gi, '<table $1>')
      .replace(/<tr(\w*=[^>]+)>/gi, '<tr $1>');
  };

  const formatMarkdownValForAgent = (val: string) => {
    return val?.replace(/<table(\w*=[^>]+)>/gi, '<table $1>').replace(/<tr(\w*=[^>]+)>/gi, '<tr $1>');
  };

  return (
    <div
      className={cls('flex w-full', {
        'justify-end': !isRobot,
      })}
      ref={chatDialogRef}
    >
      {/* 用户提问 */}
      {!isRobot && <div className='flex bg-[#0C75FC]  text-white p-3 rounded-xl rounded-br-none'>{context}</div>}
      {isRobot && (
        <div className='flex max-w-full flex-col flex-wrap bg-white dark:bg-[rgba(255,255,255,0.16)] p-3 rounded-xl rounded-bl-none'>
          {typeof context === 'string' && scene === 'chat_agent' && (
            <MarkdownContext>{formatMarkdownValForAgent(value)}</MarkdownContext>
          )}
          {typeof context === 'string' && scene !== 'chat_agent' && (
            <MarkdownContext>{formatMarkdownVal(value)}</MarkdownContext>
          )}
          {/* 正在思考 */}
          {thinking && !context && (
            <div className='flex items-center gap-2'>
              <span className='flex text-sm text-[#1c2533] dark:text-white'>思考中</span>
              <div className='flex'>
                <div className='w-1 h-1 rounded-full mx-1 animate-pulse1'></div>
                <div className='w-1 h-1 rounded-full mx-1 animate-pulse2'></div>
                <div className='w-1 h-1 rounded-full mx-1 animate-pulse3'></div>
              </div>
            </div>
          )}
          {!thinking && <Divider className='my-2' />}
          <div
            className={cls('opacity-0 h-0 w-0', {
              'opacity-100 flex items-center justify-between gap-6 w-auto h-auto': !thinking,
            })}
          >
            {/* 用户反馈 */}
            <Feedback content={message} index={index} chatDialogRef={chatDialogRef} />
            {scene !== 'chat_agent' && (
              <div className='flex gap-1 items-center'>
                <ModelIcon width={14} height={14} model={model_name} />
                <span className='text-xs text-gray-500'>{model_name}</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default memo(ChatDialog);
