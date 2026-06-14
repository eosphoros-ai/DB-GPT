/**
 * OpenCode Agent Chat Container
 *
 * A dedicated chat container for agent mode that uses the ReAct Agent API
 * with OpenCode-style UI rendering. This component replaces the default
 * chat flow when scene === 'chat_agent'.
 */

import { ChatContext } from '@/app/chat-context';
import { apiInterceptors, getChatHistory } from '@/client/api';
import { IChatDialogueMessageSchema } from '@/types/chat';
import { STORAGE_INIT_MESSAGE_KET, getInitMessage } from '@/utils';
import { useAsyncEffect } from 'ahooks';
import { message } from 'antd';
import classNames from 'classnames';
import React, { useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import useReActAgent, { ReActAgentRequest, parseReActText } from '@/hooks/use-react-agent';
import OpenCodeSessionTurn, { MessagePart } from '@/new-components/chat/content/OpenCodeSessionTurn';
import QuestionDock from '@/new-components/chat/content/QuestionDock';
import MyEmpty from '../common/MyEmpty';
import CompletionInput from '../common/completion-input';
import MuiLoading from '../common/loading';
import Header from './header';
import { renderModelIcon } from './header/model-selector';

interface StreamingTurn {
  userMessage: string;
  parts: MessagePart[];
  finalContent: string;
  isWorking: boolean;
  startTime: number;
  endTime?: number;
}

interface HistoryTurn {
  human?: IChatDialogueMessageSchema;
  view?: IChatDialogueMessageSchema;
}

const OpenCodeAgentChatContainer: React.FC = () => {
  const { t } = useTranslation();
  const { scene, chatId, model, agent, setModel, history, setHistory } = useContext(ChatContext);

  const [loading, setLoading] = useState(false);
  const [streamingTurn, setStreamingTurn] = useState<StreamingTurn | null>(null);
  const scrollableRef = useRef<HTMLDivElement>(null);

  const {
    state: agentState,
    pendingQuestion,
    sendMessage,
    cancel,
    reset: _reset,
    replyQuestion,
    rejectQuestion,
  } = useReActAgent({
    baseUrl: '/api/v1/chat/react-agent',
    onPartUpdate: parts => {
      setStreamingTurn(prev => (prev ? { ...prev, parts } : null));
    },
    onFinalContent: content => {
      setStreamingTurn(prev => (prev ? { ...prev, finalContent: content } : null));
    },
    onComplete: () => {
      setStreamingTurn(prev => {
        if (!prev) return null;

        const endTime = Date.now();
        const newHistoryItem: IChatDialogueMessageSchema = {
          role: 'view',
          context: prev.finalContent || buildReActContext(prev.parts),
          model_name: model,
          order: history.length,
          time_stamp: endTime,
        };

        setHistory(h => [...h, newHistoryItem]);

        return { ...prev, isWorking: false, endTime };
      });

      setTimeout(() => setStreamingTurn(null), 100);
    },
    onError: error => {
      message.error(error);
      setStreamingTurn(prev => (prev ? { ...prev, isWorking: false } : null));
    },
  });

  const getHistory = useCallback(async () => {
    setLoading(true);
    const [, res] = await apiInterceptors(getChatHistory(chatId));
    setHistory(res ?? []);
    setLoading(false);
  }, [chatId, setHistory]);

  useAsyncEffect(async () => {
    const initMessage = getInitMessage();
    if (initMessage && initMessage.id === chatId) return;
    await getHistory();
  }, [chatId]);

  useEffect(() => {
    if (!history.length) return;
    const lastView = history.filter(i => i.role === 'view')?.slice(-1)?.[0];
    lastView?.model_name && setModel(lastView.model_name);
  }, [history.length, setModel]);

  useEffect(() => {
    return () => {
      setHistory([]);
      cancel();
    };
  }, [setHistory, cancel]);

  const handleChat = useCallback(
    async (content: string, data?: Record<string, any>) => {
      if (!content.trim()) return;
      if (!agent) {
        message.warning(t('choice_agent_tip'));
        return;
      }

      const humanMessage: IChatDialogueMessageSchema = {
        role: 'human',
        context: content,
        model_name: model,
        order: history.length,
        time_stamp: Date.now(),
      };
      setHistory(h => [...h, humanMessage]);

      setStreamingTurn({
        userMessage: content,
        parts: [],
        finalContent: '',
        isWorking: true,
        startTime: Date.now(),
      });

      const request: ReActAgentRequest = {
        user_input: content,
        conv_uid: chatId,
        chat_mode: scene || 'chat_agent',
        model_name: model,
        select_param: agent,
        temperature: 0.2,
        ...data,
      };

      await sendMessage(request);
    },
    [agent, model, chatId, scene, history.length, setHistory, sendMessage, t],
  );

  useAsyncEffect(async () => {
    const initMessage = getInitMessage();
    if (initMessage && initMessage.id === chatId) {
      await handleChat(initMessage.message);
      localStorage.removeItem(STORAGE_INIT_MESSAGE_KET);
    }
  }, [chatId]);

  const groupedHistory = useMemo(() => {
    const groups: HistoryTurn[] = [];
    let currentGroup: HistoryTurn = {};

    for (const msg of history) {
      if (msg.role === 'human') {
        if (currentGroup.human || currentGroup.view) {
          groups.push(currentGroup);
        }
        currentGroup = { human: msg };
      } else if (msg.role === 'view') {
        currentGroup.view = msg;
        groups.push(currentGroup);
        currentGroup = {};
      }
    }

    if (currentGroup.human || currentGroup.view) {
      groups.push(currentGroup);
    }

    return groups;
  }, [history]);

  useEffect(() => {
    if (scrollableRef.current) {
      scrollableRef.current.scrollTo({
        top: scrollableRef.current.scrollHeight,
        behavior: 'smooth',
      });
    }
  }, [groupedHistory.length, streamingTurn?.parts.length, streamingTurn?.finalContent]);

  const renderHistoryTurn = (turn: HistoryTurn, index: number) => {
    const userMessage = turn.human?.context
      ? typeof turn.human.context === 'string'
        ? turn.human.context
        : JSON.stringify(turn.human.context)
      : '';

    let assistantMessage = '';
    let parts: MessagePart[] = [];

    if (turn.view?.context) {
      const contextStr = typeof turn.view.context === 'string' ? turn.view.context : JSON.stringify(turn.view.context);

      const parsed = parseReActText(contextStr);
      parts = parsed.parts;
      assistantMessage = parsed.finalContent || contextStr;
    }

    return (
      <OpenCodeSessionTurn
        key={`turn-${index}`}
        userMessage={userMessage}
        assistantMessage={assistantMessage}
        parts={parts}
        isWorking={false}
        showSteps={parts.length > 0}
        defaultStepsExpanded={false}
        modelName={turn.view?.model_name || model}
        className='w-full'
      />
    );
  };

  const isWorking = streamingTurn?.isWorking || agentState.isWorking;

  return (
    <div className='flex flex-col h-screen w-full overflow-hidden'>
      <MuiLoading visible={loading} />

      <div className='flex-none'>
        <Header refreshHistory={getHistory} modelChange={(newModel: string) => setModel(newModel)} />
      </div>

      <div className='flex-1 flex flex-col overflow-hidden px-4 lg:px-8'>
        <div ref={scrollableRef} className='flex-1 overflow-y-auto'>
          <div className='max-w-4xl mx-auto py-4 space-y-6'>
            {groupedHistory.length === 0 && !streamingTurn ? (
              <MyEmpty description={t('Start a conversation')} />
            ) : (
              <>
                {groupedHistory.map((turn, index) => renderHistoryTurn(turn, index))}

                {streamingTurn && (
                  <OpenCodeSessionTurn
                    userMessage={streamingTurn.userMessage}
                    assistantMessage={streamingTurn.finalContent}
                    parts={streamingTurn.parts}
                    isWorking={streamingTurn.isWorking}
                    startTime={streamingTurn.startTime}
                    endTime={streamingTurn.endTime}
                    showSteps={true}
                    defaultStepsExpanded={true}
                    modelName={model}
                    className='w-full'
                  />
                )}
              </>
            )}
          </div>
        </div>

        <div
          className={classNames(
            'flex-none sticky bottom-0 bg-theme-light dark:bg-theme-dark',
            'after:absolute after:-top-8 after:h-8 after:w-full',
            'after:bg-gradient-to-t after:from-theme-light after:to-transparent',
            'dark:after:from-theme-dark',
          )}
        >
          <div className='max-w-4xl mx-auto'>
            {pendingQuestion && (
              <div className='px-4 pt-2'>
                <QuestionDock
                  request={{
                    request_id: pendingQuestion.request_id,
                    conv_id: pendingQuestion.conv_id,
                    questions: pendingQuestion.questions,
                  }}
                  onReply={replyQuestion}
                  onReject={rejectQuestion}
                />
              </div>
            )}
            <div className='flex flex-wrap w-full py-2 sm:pt-6 sm:pb-10 items-center'>
              {model && <div className='mr-2 flex'>{renderModelIcon(model)}</div>}
              <CompletionInput loading={isWorking} onSubmit={handleChat} handleFinish={() => {}} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

function buildReActContext(parts: MessagePart[]): string {
  const lines: string[] = [];

  for (const part of parts) {
    if (part.type === 'reasoning') {
      lines.push(`Thought: ${part.text}`);
    } else if (part.type === 'tool') {
      const toolPart = part as MessagePart & { tool: string; state: any };
      const action = toolPart.state?.metadata?.action || toolPart.tool;
      lines.push(`Action: ${action}`);
      if (toolPart.state?.input) {
        lines.push(`Action Input: ${JSON.stringify(toolPart.state.input)}`);
      }
      if (toolPart.state?.output) {
        lines.push(`Observation: ${toolPart.state.output}`);
      }
    }
  }

  return lines.join('\n');
}

export default OpenCodeAgentChatContainer;
