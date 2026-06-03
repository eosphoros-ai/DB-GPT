/**
 * OpenCode Chat Completion Component
 *
 * Renders chat messages in OpenCode style for all scenes.
 * Uses OpenCodeSessionTurn for each conversation turn.
 * Integrates ReAct Agent API for agent mode with real-time streaming.
 */

import { useAsyncEffect } from 'ahooks';
import { Modal } from 'antd';
import { cloneDeep } from 'lodash';
import { usePageQuery } from '@/utils/use-page-query';
import React, { useCallback, useContext, useMemo, useState } from 'react';
import { v4 as uuid } from 'uuid';

import { ChatContext } from '@/app/chat-context';
import { apiInterceptors, getAppInfo } from '@/client/api';
import MonacoEditor from '@/components/chat/monaco-editor';
import { ChatContentContext } from '@/pages/chat';
import { IApp } from '@/types/app';
import { IChatDialogueMessageSchema } from '@/types/chat';
import { STORAGE_INIT_MESSAGE_KET, getInitMessage } from '@/utils';

import { parseReActText } from '@/hooks/use-react-agent';
import ContextUsageBar from './ContextUsageBar';
import OpenCodeSessionTurn, { MessagePart } from './OpenCodeSessionTurn';

interface GroupedTurn {
  human?: IChatDialogueMessageSchema;
  view?: IChatDialogueMessageSchema;
  key: string;
}

const OpenCodeChatCompletion: React.FC = () => {
  const searchParams = usePageQuery();
  const chatId = searchParams.get('id') ?? '';
  const scene = searchParams.get('scene') ?? '';

  const { currentDialogInfo, model } = useContext(ChatContext);
  const {
    history,
    handleChat: originalHandleChat,
    refreshDialogList,
    setAppInfo,
    setModelValue,
    setTemperatureValue,
    setMaxNewTokensValue,
    setResourceValue,
    replyLoading,
    modelValue,
    setHistory,
    setReplyLoading,
    // Context management status from use-chat hook
    contextStatus,
  } = useContext(ChatContentContext);

  const [jsonModalOpen, setJsonModalOpen] = useState(false);
  const [jsonValue, setJsonValue] = useState<string>('');

  // ReAct streaming turn is not used when routing through completions API
  const streamingTurn: any = null;
  const isStreaming = false;

  // Track if we should use ReAct API for agent scene
  const useReActAPI = scene === 'chat_agent';

  // Group messages into turns
  const groupedTurns = useMemo<GroupedTurn[]>(() => {
    const tempMessages = cloneDeep(history).filter(item => ['view', 'human'].includes(item.role));
    const groups: GroupedTurn[] = [];
    let currentGroup: Partial<GroupedTurn> = {};

    for (const msg of tempMessages) {
      if (msg.role === 'human') {
        if (currentGroup.human || currentGroup.view) {
          groups.push({ ...currentGroup, key: uuid() } as GroupedTurn);
        }
        currentGroup = { human: msg };
      } else if (msg.role === 'view') {
        currentGroup.view = msg;
        groups.push({ ...currentGroup, key: uuid() } as GroupedTurn);
        currentGroup = {};
      }
    }

    if (currentGroup.human || currentGroup.view) {
      groups.push({ ...currentGroup, key: uuid() } as GroupedTurn);
    }

    return groups;
  }, [history]);

  // Handle initial message from storage
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
        const temperature = res?.param_need?.filter(item => item.type === 'temperature')[0]?.value || 0.6;
        const maxNewTokens = res?.param_need?.filter(item => item.type === 'max_new_tokens')[0]?.value || 4000;
        const resource = res?.param_need?.filter(item => item.type === 'resource')[0]?.bind_value;
        setAppInfo(res || ({} as IApp));
        setTemperatureValue(temperature || 0.6);
        setMaxNewTokensValue(maxNewTokens || 4000);
        setModelValue(resModel);
        setResourceValue(resource);
        await originalHandleChat(initMessage.message, {
          app_code: res?.app_code,
          model_name: resModel,
          ...(paramKey?.includes('temperature') && { temperature }),
          ...(paramKey?.includes('max_new_tokens') && { max_new_tokens: maxNewTokens }),
          ...(paramKey.includes('resource') && {
            select_param: typeof resource === 'string' ? resource : JSON.stringify(resource),
          }),
        });
        await refreshDialogList();
        localStorage.removeItem(STORAGE_INIT_MESSAGE_KET);
      }
    }
  }, [chatId, currentDialogInfo]);

  // Render a single turn from history
  const renderTurn = useCallback(
    (turn: GroupedTurn, index: number, isLast: boolean) => {
      const userMessage = turn.human?.context
        ? typeof turn.human.context === 'string'
          ? turn.human.context
          : JSON.stringify(turn.human.context)
        : '';

      let assistantMessage = '';
      let parts: MessagePart[] = [];
      const isThinking = turn.view?.thinking && !turn.view?.context;

      if (turn.view?.context) {
        const contextStr =
          typeof turn.view.context === 'string' ? turn.view.context : JSON.stringify(turn.view.context);

        // Parse ReAct format for agent mode, plain text for others
        if (useReActAPI || contextStr.includes('Thought:') || contextStr.includes('Action:')) {
          const parsed = parseReActText(contextStr);
          parts = parsed.parts;
          // Use final content if available, otherwise use the original context
          assistantMessage = parsed.finalContent || extractFinalAnswer(contextStr) || contextStr;
        } else {
          assistantMessage = contextStr;
        }
      }

      // Show loading only if this is the last turn and we're in loading state but not streaming
      const showLoading = isLast && replyLoading && !isStreaming && !streamingTurn;
      const isWorking = showLoading || isThinking;

      return (
        <OpenCodeSessionTurn
          key={turn.key}
          userMessage={userMessage}
          assistantMessage={assistantMessage}
          parts={parts}
          isWorking={isWorking}
          showSteps={parts.length > 0}
          defaultStepsExpanded={isLast}
          modelName={turn.view?.model_name || modelValue || model}
          startTime={turn.human?.time_stamp ? Number(turn.human.time_stamp) : undefined}
          endTime={turn.view?.time_stamp ? Number(turn.view.time_stamp) : undefined}
          className='w-full'
        />
      );
    },
    [useReActAPI, replyLoading, isStreaming, streamingTurn, modelValue, model],
  );

  // Render the streaming turn (real-time updates)
  const renderStreamingTurn = () => {
    if (!streamingTurn) return null;

    return (
      <OpenCodeSessionTurn
        key='streaming-turn'
        userMessage={streamingTurn.userMessage}
        assistantMessage={streamingTurn.finalContent}
        parts={streamingTurn.parts}
        isWorking={streamingTurn.isWorking}
        startTime={streamingTurn.startTime}
        endTime={streamingTurn.endTime}
        showSteps={true}
        defaultStepsExpanded={true}
        modelName={modelValue || model}
        thinkingContent={streamingTurn.thinkingContent}
        currentStatus={streamingTurn.currentStatus}
        className='w-full'
      />
    );
  };

  return (
    <div className='flex flex-col w-5/6 mx-auto space-y-2 py-4'>
      {/* Context usage floating bar — persists after streaming ends */}
      {contextStatus && (
        <div className='sticky top-0 z-10 flex justify-center py-1'>
          <ContextUsageBar
            used={contextStatus.used_tokens}
            budget={contextStatus.max_tokens}
            ratio={contextStatus.usage_percent / 100}
            state={contextStatus.state}
            compactLayer={contextStatus.layer ?? null}
          />
        </div>
      )}

      {groupedTurns.map((turn, index) => renderTurn(turn, index, index === groupedTurns.length - 1 && !streamingTurn))}

      {renderStreamingTurn()}

      <Modal
        title='JSON Editor'
        open={jsonModalOpen}
        width='60%'
        cancelButtonProps={{ hidden: true }}
        onOk={() => setJsonModalOpen(false)}
        onCancel={() => setJsonModalOpen(false)}
      >
        <MonacoEditor className='w-full h-[500px]' language='json' value={jsonValue} />
      </Modal>
    </div>
  );
};

/**
 * Extract final answer from ReAct format text
 */
function extractFinalAnswer(text: string): string | null {
  // Look for "Final Answer:" pattern
  const finalAnswerMatch = text.match(/Final Answer:\s*([\s\S]*?)$/i);
  if (finalAnswerMatch) {
    return finalAnswerMatch[1].trim();
  }

  // Look for terminate action with output
  const terminateMatch = text.match(/Action:\s*terminate[\s\S]*?Action Input:\s*\{[\s\S]*?"output":\s*"([^"]+)"/i);
  if (terminateMatch) {
    return terminateMatch[1];
  }

  return null;
}

export default OpenCodeChatCompletion;
