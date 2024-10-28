import { apiInterceptors, clearChatHistory } from '@/client/api';
import { ChatHistoryResponse } from '@/types/chat';
import { getUserId } from '@/utils';
import { HEADER_USER_ID_KEY } from '@/utils/constants/index';
import { ClearOutlined, LoadingOutlined, PauseCircleOutlined, RedoOutlined, SendOutlined } from '@ant-design/icons';
import { EventStreamContentType, fetchEventSource } from '@microsoft/fetch-event-source';
import { useRequest } from 'ahooks';
import { Button, Input, Popover, Spin, Tag } from 'antd';
import classnames from 'classnames';
import { useSearchParams } from 'next/navigation';
import React, { useContext, useEffect, useMemo, useState } from 'react';
import { MobileChatContext } from '../';
import ModelSelector from './ModelSelector';
import Resource from './Resource';
import Thermometer from './Thermometer';

const tagColors = ['magenta', 'orange', 'geekblue', 'purple', 'cyan', 'green'];

const InputContainer: React.FC = () => {
  // 从url上获取基本参数
  const searchParams = useSearchParams();
  const ques = searchParams?.get('ques') ?? '';
  const {
    history,
    model,
    scene,
    temperature,
    resource,
    conv_uid,
    appInfo,
    scrollViewRef,
    order,
    userInput,
    ctrl,
    canAbort,
    canNewChat,
    setHistory,
    setCanNewChat,
    setCarAbort,
    setUserInput,
  } = useContext(MobileChatContext);
  // 输入框聚焦
  const [isFocus, setIsFocus] = useState<boolean>(false);
  // 是否中文输入
  const [isZhInput, setIsZhInput] = useState<boolean>(false);

  // 处理会话
  const handleChat = async (content?: string) => {
    setUserInput('');
    ctrl.current = new AbortController();
    const params = {
      chat_mode: scene,
      model_name: model,
      user_input: content || userInput,
      conv_uid,
      temperature,
      app_code: appInfo?.app_code,
      ...(resource && { select_param: JSON.stringify(resource) }),
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

  // 会话提问
  const onSubmit = async () => {
    if (!userInput.trim() || !canNewChat) {
      return;
    }
    await handleChat();
  };

  useEffect(() => {
    scrollViewRef.current?.scrollTo({
      top: scrollViewRef.current?.scrollHeight,
      behavior: 'auto',
    });
  }, [history, scrollViewRef]);

  // 功能类型
  const paramType = useMemo(() => {
    if (!appInfo) {
      return [];
    }
    const { param_need = [] } = appInfo;
    return param_need?.map(item => item.type);
  }, [appInfo]);

  // 是否展示推荐问题
  const showRecommendQuestion = useMemo(() => {
    // 只在没有对话的时候展示
    return history.length === 0 && appInfo && !!appInfo?.recommend_questions?.length;
  }, [history, appInfo]);

  // 暂停回复
  const abort = () => {
    if (!canAbort) {
      return;
    }
    ctrl.current?.abort();
    setTimeout(() => {
      setCarAbort(false);
      setCanNewChat(true);
    }, 100);
  };

  // 再来一次
  const redo = () => {
    if (!canNewChat || history.length === 0) {
      return;
    }
    const lastHuman = history.filter(i => i.role === 'human')?.slice(-1)?.[0];
    handleChat(lastHuman?.context || '');
  };

  const { run: clearHistoryRun, loading } = useRequest(async () => await apiInterceptors(clearChatHistory(conv_uid)), {
    manual: true,
    onSuccess: () => {
      setHistory([]);
    },
  });

  // 清除历史会话
  const clearHistory = () => {
    if (!canNewChat) {
      return;
    }
    clearHistoryRun();
  };

  // 如果url携带ques问题，则直接提问
  useEffect(() => {
    if (ques && model && conv_uid && appInfo) {
      handleChat(ques);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [appInfo, conv_uid, model, ques]);

  return (
    <div className='flex flex-col'>
      {/* 推荐问题 */}
      {showRecommendQuestion && (
        <ul>
          {appInfo?.recommend_questions?.map((item, index) => (
            <li key={item.id} className='mb-3'>
              <Tag
                color={tagColors[index]}
                className='p-2 rounded-xl'
                onClick={async () => {
                  handleChat(item.question);
                }}
              >
                {item.question}
              </Tag>
            </li>
          ))}
        </ul>
      )}
      {/* 功能区域 */}
      <div className='flex items-center justify-between gap-1'>
        <div className='flex gap-2 mb-1 w-full overflow-x-auto'>
          {/* 模型选择 */}
          {paramType?.includes('model') && <ModelSelector />}
          {/* 额外资源 */}
          {paramType?.includes('resource') && <Resource />}
          {/* 温度调控 */}
          {paramType?.includes('temperature') && <Thermometer />}
        </div>
        <div className='flex items-center justify-between text-lg font-bold'>
          <Popover content='暂停回复' trigger={['hover']}>
            <PauseCircleOutlined
              className={classnames('p-2 cursor-pointer', {
                'text-[#0c75fc]': canAbort,
                'text-gray-400': !canAbort,
              })}
              onClick={abort}
            />
          </Popover>
          <Popover content='再来一次' trigger={['hover']}>
            <RedoOutlined
              className={classnames('p-2 cursor-pointer', {
                'text-gray-400': !history.length || !canNewChat,
              })}
              onClick={redo}
            />
          </Popover>
          {loading ? (
            <Spin spinning={loading} indicator={<LoadingOutlined style={{ fontSize: 18 }} spin />} className='p-2' />
          ) : (
            <Popover content='清除历史' trigger={['hover']}>
              <ClearOutlined
                className={classnames('p-2 cursor-pointer', {
                  'text-gray-400': !history.length || !canNewChat,
                })}
                onClick={clearHistory}
              />
            </Popover>
          )}
        </div>
      </div>
      {/* 输入框 */}
      <div
        className={classnames(
          'flex py-2 px-3 items-center justify-between bg-white dark:bg-[#242733] dark:border-[#6f7f95] rounded-xl border',
          {
            'border-[#0c75fc] dark:border-[rgba(12,117,252,0.8)]': isFocus,
          },
        )}
      >
        <Input.TextArea
          placeholder='可以问我任何问题'
          className='w-full resize-none border-0 p-0 focus:shadow-none'
          value={userInput}
          autoSize={{ minRows: 1 }}
          onKeyDown={e => {
            if (e.key === 'Enter') {
              if (e.shiftKey) {
                return;
              }
              if (isZhInput) {
                e.preventDefault();
                return;
              }
              if (!userInput.trim()) {
                return;
              }
              e.preventDefault();
              onSubmit();
            }
          }}
          onChange={e => {
            setUserInput(e.target.value);
          }}
          onFocus={() => {
            setIsFocus(true);
          }}
          onBlur={() => setIsFocus(false)}
          onCompositionStartCapture={() => {
            setIsZhInput(true);
          }}
          onCompositionEndCapture={() => {
            setTimeout(() => {
              setIsZhInput(false);
            }, 0);
          }}
        />

        <Button
          type='primary'
          className={classnames('flex items-center justify-center rounded-lg bg-button-gradient border-0 ml-2', {
            'opacity-40 cursor-not-allowed': !userInput.trim() || !canNewChat,
          })}
          onClick={onSubmit}
        >
          {canNewChat ? <SendOutlined /> : <Spin indicator={<LoadingOutlined className='text-white' />} />}
        </Button>
      </div>
    </div>
  );
};

export default InputContainer;
