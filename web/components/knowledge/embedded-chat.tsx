import { apiInterceptors, getKnowledgeSpaceStats, getSpaceList, getUsableModels, newDialogue } from '@/client/api';
import useReActAgent from '@/hooks/use-react-agent';
import OpenCodeSessionTurn, { MessagePart, ToolPart } from '@/new-components/chat/content/OpenCodeSessionTurn';
import {
  ClearOutlined,
  CopyOutlined,
  FileTextOutlined,
  FileSearchOutlined,
  LoadingOutlined,
  NodeIndexOutlined,
  PauseCircleOutlined,
  RedoOutlined,
  RightOutlined,
  ShareAltOutlined,
} from '@ant-design/icons';
import { Button, Empty, Input, Select, Spin, Tooltip, message } from 'antd';
import Image from 'next/image';
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

interface StreamingTurn {
  userMessage: string;
  parts: MessagePart[];
  finalContent: string;
  isWorking: boolean;
  startTime: number;
  endTime?: number;
}

interface HistoryTurn {
  id: string;
  userMessage: string;
  assistantMessage: string;
  parts: MessagePart[];
  references: FileReference[];
  startTime: number | null;
  endTime: number | null;
}

interface EmbeddedChatProps {
  spaceName: string;
}

/** A file reference discovered during the conversation */
interface FileReference {
  id: string;
  path: string;
  name: string;
  content: string;
  status: 'running' | 'completed' | 'error';
  source: 'kb_cat' | 'kb_grep' | 'kb_ls' | 'kb_glob' | 'semantic_search';
}

let turnIdCounter = 0;

/** Extract file references from tool parts */
function extractReferences(parts: MessagePart[]): FileReference[] {
  const refs: FileReference[] = [];
  for (const p of parts) {
    if (p.type !== 'tool') continue;
    const tp = p as ToolPart;
    const action = (tp.state.metadata?.action as string) || tp.tool || '';
    const input = tp.state.input as Record<string, unknown> | undefined;
    const output = tp.state.output || '';
    if (!output) continue;

    const path = (input?.path as string) || (input?.query as string) || (input?.pattern as string) || '';

    if (action === 'kb_cat' && path) {
      refs.push({
        id: tp.id, path,
        name: path.split('/').pop() || path,
        content: output,
        status: tp.state.status === 'running' ? 'running' : tp.state.status === 'error' ? 'error' : 'completed',
        source: 'kb_cat',
      });
    } else if (action === 'kb_grep' && path) {
      refs.push({
        id: tp.id, path,
        name: path.split('/').pop() || path,
        content: output,
        status: tp.state.status === 'running' ? 'running' : tp.state.status === 'error' ? 'error' : 'completed',
        source: 'kb_grep',
      });
    } else if (action === 'kb_ls' && output) {
      refs.push({
        id: tp.id,
        path: (input?.path as string) || '/',
        name: `📂 ${(input?.path as string) || '/'}`,
        content: output,
        status: tp.state.status === 'running' ? 'running' : tp.state.status === 'error' ? 'error' : 'completed',
        source: 'kb_ls',
      });
    } else if (action === 'kb_glob' && output) {
      refs.push({
        id: tp.id,
        path: (input?.query as string) || (input?.pattern as string) || '*',
        name: `🔍 ${(input?.query as string) || (input?.pattern as string) || '*'}`,
        content: output,
        status: tp.state.status === 'running' ? 'running' : tp.state.status === 'error' ? 'error' : 'completed',
        source: 'kb_glob',
      });
    } else if (action === 'semantic_search' && output) {
      refs.push({
        id: tp.id,
        path: 'Semantic Search',
        name: `🔍 ${(input?.query as string)?.slice(0, 40) || 'Semantic Search'}`,
        content: output,
        status: tp.state.status === 'running' ? 'running' : tp.state.status === 'error' ? 'error' : 'completed',
        source: 'semantic_search',
      });
    }
  }
  return refs;
}

/** Get icon for file type based on extension */
function getFileIcon(fileName: string): React.ReactNode {
  const ext = fileName.split('.').pop()?.toLowerCase();
  const iconMap: Record<string, React.ReactNode> = {
    md: <FileTextOutlined className='text-blue-500' />,
    py: <FileTextOutlined className='text-green-500' />,
    js: <FileTextOutlined className='text-yellow-500' />,
    ts: <FileTextOutlined className='text-blue-400' />,
    sql: <FileTextOutlined className='text-purple-500' />,
    json: <FileTextOutlined className='text-orange-500' />,
    yaml: <FileTextOutlined className='text-red-400' />,
    yml: <FileTextOutlined className='text-red-400' />,
    txt: <FileTextOutlined className='text-gray-500' />,
    csv: <FileTextOutlined className='text-green-400' />,
    html: <FileTextOutlined className='text-orange-400' />,
    css: <FileTextOutlined className='text-blue-300' />,
  };
  return iconMap[ext || ''] || <FileTextOutlined className='text-gray-400' />;
}

/** Get language label for file type */
function getFileLang(fileName: string): string {
  const ext = fileName.split('.').pop()?.toLowerCase();
  const langMap: Record<string, string> = {
    md: 'markdown', py: 'python', js: 'javascript', ts: 'typescript',
    sql: 'sql', json: 'json', yaml: 'yaml', yml: 'yaml',
    txt: 'text', csv: 'csv', html: 'html', css: 'css',
  };
  return langMap[ext || ''] || ext || '';
}

/**
 * Embedded chat for knowledge base detail page.
 * Left: chat messages. Right: References panel showing files consulted.
 */
const EmbeddedChat: React.FC<EmbeddedChatProps> = ({ spaceName }) => {
  const { t } = useTranslation();
  const [history, setHistory] = useState<HistoryTurn[]>([]);
  const [userInput, setUserInput] = useState('');
  const [isZhInput, setIsZhInput] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const [convUid, setConvUid] = useState<string | null>(null);
  const [initLoading, setInitLoading] = useState(true);

  const [modelList, setModelList] = useState<string[]>([]);
  const [modelValue, setModelValue] = useState<string>('');

  const [knowledgeSpaces, setKnowledgeSpaces] = useState<{ name: string; desc: string; id?: any }[]>([]);
  const [knowledgeValue, setKnowledgeValue] = useState<string>(spaceName);

  // Graph stats for the selected knowledge space
  const [graphStats, setGraphStats] = useState<{ vertexCount: number | null; edgeCount: number | null }>({
    vertexCount: null, edgeCount: null,
  });

  const [streamingTurn, setStreamingTurn] = useState<StreamingTurn | null>(null);

  // Right panel state
  const [rightPanelCollapsed, setRightPanelCollapsed] = useState(false);
  const [selectedRefId, setSelectedRefId] = useState<string | null>(null);

  const onPartUpdateRef = useRef<(parts: MessagePart[]) => void>(() => {});
  const onFinalContentRef = useRef<(content: string) => void>(() => {});
  const onCompleteRef = useRef<() => void>(() => {});
  const onErrorRef = useRef<(error: string) => void>(() => {});

  onPartUpdateRef.current = parts => {
    setStreamingTurn(prev => (prev ? { ...prev, parts } : null));
  };
  onFinalContentRef.current = content => {
    setStreamingTurn(prev => (prev ? { ...prev, finalContent: content } : null));
  };
  onCompleteRef.current = () => {
    setStreamingTurn(prev => {
      if (!prev) return null;
      const endTime = Date.now();
      const savedRefs = extractReferences(prev.parts);
      turnIdCounter += 1;
      setHistory(h => [...h, {
        id: `turn-${turnIdCounter}`,
        userMessage: prev.userMessage,
        assistantMessage: prev.finalContent || buildReActContext(prev.parts),
        parts: prev.parts,
        references: savedRefs,
        startTime: prev.startTime,
        endTime,
      }]);
      return { ...prev, isWorking: false, endTime };
    });
  };
  onErrorRef.current = () => {
    setStreamingTurn(prev => (prev ? { ...prev, isWorking: false } : null));
  };

  const { state: agentState, sendMessage, cancel } = useReActAgent({
    baseUrl: `${process.env.API_BASE_URL ?? ''}/api/v1/chat/react-agent`,
    onPartUpdate: (parts: MessagePart[]) => onPartUpdateRef.current(parts),
    onFinalContent: (content: string) => onFinalContentRef.current(content),
    onComplete: () => onCompleteRef.current(),
    onError: (error: string) => onErrorRef.current(error),
  });

  useEffect(() => {
    (async () => {
      const [, dialogueData] = await apiInterceptors(newDialogue({ chat_mode: 'chat_react_agent' }));
      if (dialogueData?.conv_uid) setConvUid(dialogueData.conv_uid);
      const [, models] = await apiInterceptors(getUsableModels());
      if (models?.length) { setModelList(models); setModelValue(models[0]); }
      const [, spaces] = await apiInterceptors(getSpaceList());
      if (spaces) setKnowledgeSpaces(spaces);
      setInitLoading(false);
    })();
  }, []);

  // Fetch graph stats for the selected knowledge space
  useEffect(() => {
    if (!knowledgeValue) return;
    (async () => {
      const [, stats] = await apiInterceptors(getKnowledgeSpaceStats(knowledgeValue));
      if (stats) {
        setGraphStats({
          vertexCount: stats.graph_vertex_count ?? null,
          edgeCount: stats.graph_edge_count ?? null,
        });
      }
    })();
  }, [knowledgeValue]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
    }
  }, [history.length, streamingTurn?.parts.length, streamingTurn?.finalContent]);

  // References: from streaming turn (live) or latest history turn (after complete)
  const references = useMemo(() => {
    if (streamingTurn?.isWorking) return extractReferences(streamingTurn.parts);
    const lastTurn = history[history.length - 1];
    if (lastTurn?.references?.length) return lastTurn.references;
    if (streamingTurn?.parts?.length) return extractReferences(streamingTurn.parts);
    return [] as FileReference[];
  }, [streamingTurn, history]);

  // Auto-select latest reference (only during streaming)
  useEffect(() => {
    if (!streamingTurn || references.length === 0) return;
    const last = references[references.length - 1];
    setSelectedRefId(last.id);
    if (rightPanelCollapsed) setRightPanelCollapsed(false);
  }, [references.length, streamingTurn]);

  // When history changes (new turn added), select first reference
  useEffect(() => {
    if (streamingTurn) return;
    const lastTurn = history[history.length - 1];
    if (lastTurn?.references?.length) {
      setSelectedRefId(lastTurn.references[0].id);
    }
  }, [history.length, streamingTurn]);

  const handleSend = useCallback(async () => {
    const text = userInput.trim();
    if (!text || !convUid || agentState.isWorking) return;
    const selectedSpace = knowledgeSpaces.find(s => s.name === knowledgeValue);
    const selectedSpaceId = selectedSpace?.id;
    setUserInput('');
    setSelectedRefId(null);
    setStreamingTurn({ userMessage: text, parts: [], finalContent: '', isWorking: true, startTime: Date.now() });
    await sendMessage({
      user_input: `[Knowledge: ${knowledgeValue}] ${text}`,
      conv_uid: convUid,
      chat_mode: 'chat_react_agent',
      model_name: modelValue,
      temperature: 0.6,
      select_param: '',
      ext_info: { knowledge_space_name: knowledgeValue, ...(selectedSpaceId !== undefined && { knowledge_space_id: selectedSpaceId }) },
    });
  }, [userInput, convUid, agentState.isWorking, sendMessage, modelValue, knowledgeValue, knowledgeSpaces]);

  const handleStop = useCallback(() => cancel(), [cancel]);
  const handleRetry = useCallback(() => {
    const lastTurn = history[history.length - 1];
    if (!lastTurn || agentState.isWorking) return;
    setHistory(prev => prev.slice(0, -1));
    setUserInput(lastTurn.userMessage);
  }, [history, agentState.isWorking]);
  const handleClear = useCallback(() => { setHistory([]); setSelectedRefId(null); }, []);

  const knowledgeOptions = useMemo(() => knowledgeSpaces.map(s => ({ label: s.name, value: s.name })), [knowledgeSpaces]);
  const isWorking = streamingTurn?.isWorking || agentState.isWorking;

  if (initLoading) return <div className='flex items-center justify-center h-full'><Spin size='large' /></div>;
  if (!convUid) return <div className='flex items-center justify-center h-full'><Empty description={t('No_Results')} /></div>;

  return (
    <div className='h-full flex bg-white dark:bg-[#232734]'>
      {/* Left: Chat area */}
      <div className='flex-1 min-w-0 flex flex-col'>
        <div ref={scrollRef} className='flex-1 overflow-auto'>
          <div className='max-w-4xl mx-auto py-4 space-y-6 px-4'>
            {history.length === 0 && !streamingTurn ? (
              <div className='flex flex-col items-center justify-center h-full text-gray-400 gap-3 py-12'>
                <Image src='/icons/kb_icon.png' alt='KB' width={48} height={48} className='opacity-30' />
                <p className='text-sm'>{t('input_tips')}</p>
              </div>
            ) : (
              <>
                {history.map(turn => (
                  <OpenCodeSessionTurn key={turn.id} userMessage={turn.userMessage}
                    assistantMessage={turn.assistantMessage} parts={turn.parts}
                    isWorking={false} showSteps={turn.parts.length > 0}
                    defaultStepsExpanded={false} modelName={modelValue} className='w-full' />
                ))}
                {streamingTurn && streamingTurn.isWorking && (
                  <OpenCodeSessionTurn userMessage={streamingTurn.userMessage}
                    assistantMessage={streamingTurn.finalContent} parts={streamingTurn.parts}
                    isWorking={streamingTurn.isWorking} startTime={streamingTurn.startTime}
                    endTime={streamingTurn.endTime} showSteps={true}
                    defaultStepsExpanded={true} modelName={modelValue} className='w-full' />
                )}
              </>
            )}
          </div>
        </div>

        {/* Input area */}
        <div className='flex-shrink-0 px-4 pb-4 pt-2'>
          <div className='max-w-4xl mx-auto'>
            <div className='flex flex-col bg-white dark:bg-[rgba(255,255,255,0.16)] px-5 py-4 pt-2 rounded-xl border dark:border-[rgba(255,255,255,0.6)] relative'>
              <div className='flex items-center justify-between mb-2'>
                <div className='flex gap-3 text-lg items-center'>
                  <Select value={modelValue} placeholder={t('choose_model')} className='h-8 rounded-3xl' size='small'
                    onChange={val => setModelValue(val)} popupMatchSelectWidth={300}
                    options={modelList.map(m => ({ label: m, value: m }))} />
                  <Select value={knowledgeValue} onChange={val => setKnowledgeValue(val)}
                    placeholder={<span className='flex items-center gap-1'><Image src='/icons/kb_icon.png' alt='KB' width={14} height={14} />{t('knowledge')}</span>}
                    className='w-40 h-8' size='small' options={knowledgeOptions} />
                </div>
                <div className='flex gap-1'>
                  <Tooltip title={t('stop_replying')}><div
                    className={`flex w-8 h-8 items-center justify-center rounded-md text-lg ${isWorking ? 'cursor-pointer' : 'opacity-30 cursor-not-allowed'}`}
                    onClick={isWorking ? handleStop : undefined}><PauseCircleOutlined className={isWorking ? 'text-[#0c75fc]' : ''} /></div></Tooltip>
                  <Tooltip title={t('answer_again')}><div
                    className={`flex w-8 h-8 items-center justify-center rounded-md text-lg ${!isWorking && history.length > 0 ? 'cursor-pointer hover:bg-[rgb(221,221,221,0.6)]' : 'opacity-30 cursor-not-allowed'}`}
                    onClick={!isWorking && history.length > 0 ? handleRetry : undefined}><RedoOutlined /></div></Tooltip>
                  <Tooltip title={t('erase_memory')}><div
                    className={`flex w-8 h-8 items-center justify-center rounded-md text-lg ${history.length > 0 ? 'cursor-pointer hover:bg-[rgb(221,221,221,0.6)]' : 'opacity-30 cursor-not-allowed'}`}
                    onClick={history.length > 0 ? handleClear : undefined}><ClearOutlined /></div></Tooltip>
                </div>
              </div>
              <Input.TextArea placeholder={t('input_tips')}
                className='w-full h-20 resize-none border-0 p-0 focus:shadow-none dark:bg-transparent'
                value={userInput}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !isZhInput) { e.preventDefault(); if (userInput.trim() && !isWorking) handleSend(); } }}
                onChange={e => setUserInput(e.target.value)}
                onCompositionStart={() => setIsZhInput(true)} onCompositionEnd={() => setIsZhInput(false)} />
              <Button type='primary'
                className='flex items-center justify-center w-14 h-8 rounded-lg text-sm absolute right-8 bottom-5 bg-button-gradient border-0'
                disabled={!userInput.trim() && !isWorking} onClick={isWorking ? handleStop : handleSend}>
                {isWorking ? <Spin spinning indicator={<LoadingOutlined className='text-white' />} /> : t('sent')}
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Right: References Panel */}
      {references.length > 0 && !rightPanelCollapsed && (
        <div className='w-[360px] min-w-[360px] border-l dark:border-gray-700 flex flex-col bg-gray-50 dark:bg-[#1e2130] overflow-hidden'>
          {/* Header */}
          <div className='flex items-center justify-between px-3 py-2.5 border-b dark:border-gray-700 bg-white dark:bg-[#232734]'>
            <div className='flex items-center gap-2 min-w-0'>
              <Image src='/icons/kb_icon.png' alt='KB' width={16} height={16} className='flex-shrink-0' />
              <span className='text-xs font-semibold text-gray-700 dark:text-gray-200 truncate'>
                {knowledgeValue}
              </span>
              <span className='text-[11px] px-1.5 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400 font-medium flex-shrink-0'>
                {references.length}
              </span>
              {/* Graph stats */}
              {graphStats.vertexCount != null && (
                <span className='text-[10px] text-gray-400 dark:text-gray-500 flex items-center gap-0.5 flex-shrink-0'>
                  <NodeIndexOutlined className='text-violet-400' style={{ fontSize: 10 }} />
                  {graphStats.vertexCount}
                </span>
              )}
              {graphStats.edgeCount != null && (
                <span className='text-[10px] text-gray-400 dark:text-gray-500 flex items-center gap-0.5 flex-shrink-0'>
                  <ShareAltOutlined className='text-violet-400' style={{ fontSize: 10 }} />
                  {graphStats.edgeCount}
                </span>
              )}
            </div>
            <Button type='text' size='small' icon={<RightOutlined />}
              onClick={() => setRightPanelCollapsed(true)} className='text-gray-400 hover:text-gray-600' />
          </div>

          {/* Reference file list */}
          <div className='flex-1 overflow-auto'>
            {references.map(ref => {
              const isActive = selectedRefId === ref.id;
              const isRunning = ref.status === 'running';
              const contentPreview = ref.content.slice(0, 200);
              const isFile = ref.source === 'kb_cat' || ref.source === 'kb_grep';
              return (
                <div key={ref.id}>
                  {/* File row — clickable */}
                  <button
                    onClick={() => setSelectedRefId(isActive ? null : ref.id)}
                    className={`w-full text-left px-3 py-2.5 border-b dark:border-gray-700/50 transition-colors ${
                      isActive
                        ? 'bg-blue-50 dark:bg-blue-900/20 border-l-2 border-l-blue-500'
                        : 'hover:bg-gray-100 dark:hover:bg-gray-800/50 border-l-2 border-l-transparent'
                    }`}
                  >
                    <div className='flex items-center gap-2'>
                      {isRunning ? (
                        <LoadingOutlined className='text-blue-500 text-xs flex-shrink-0' />
                      ) : ref.source === 'semantic_search' ? (
                        <FileSearchOutlined className='text-green-500 text-xs flex-shrink-0' />
                      ) : (
                        getFileIcon(ref.name)
                      )}
                      <div className='min-w-0 flex-1'>
                        <div className='text-xs font-medium text-gray-800 dark:text-gray-200 truncate'>
                          {ref.name}
                        </div>
                        {isFile && (
                          <div className='text-[10px] text-gray-400 dark:text-gray-500 truncate mt-0.5 font-mono'>
                            {ref.path}
                          </div>
                        )}
                      </div>
                      {!isRunning && isFile && (
                        <span className='text-[10px] px-1.5 py-0.5 rounded flex-shrink-0 bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400'>
                          {getFileLang(ref.name)}
                        </span>
                      )}
                    </div>
                    {/* Preview snippet when collapsed */}
                    {!isActive && contentPreview && (
                      <div className='mt-1.5 text-[11px] text-gray-400 dark:text-gray-500 leading-relaxed line-clamp-2 pl-5'>
                        {contentPreview}
                      </div>
                    )}
                  </button>

                  {/* Expanded content */}
                  {isActive && (
                    <div className='border-b dark:border-gray-700/50 bg-white dark:bg-[#1a1d2e]'>
                      <div className='flex items-center justify-between px-3 py-1.5 bg-gray-50 dark:bg-gray-800/50 border-b dark:border-gray-700/50'>
                        <span className='text-[10px] text-gray-400 font-mono truncate flex-1'>{ref.path}</span>
                        <Tooltip title={t('Copy_Btn') || 'Copy'}>
                          <button onClick={() => {
                            navigator.clipboard?.writeText(ref.content || '');
                            message.success(t('copy_to_clipboard_success'));
                          }}
                          className='text-gray-400 hover:text-teal-500 transition-colors ml-2'>
                            <CopyOutlined style={{ fontSize: 11 }} />
                          </button>
                        </Tooltip>
                      </div>
                      <div className='p-3'>
                        <pre className='text-xs text-gray-700 dark:text-gray-300 whitespace-pre-wrap font-mono leading-relaxed m-0 max-h-[400px] overflow-auto'>
                          {ref.content || t('No_Results')}
                        </pre>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {references.length > 0 && rightPanelCollapsed && (
        <div className='border-l dark:border-gray-700 bg-gray-50 dark:bg-[#1e2130] flex items-center'>
          <Button type='text' size='small' icon={<RightOutlined style={{ transform: 'rotate(180deg)' }} />}
            onClick={() => setRightPanelCollapsed(false)}
            className='text-gray-400 hover:text-gray-600 h-full px-1' />
        </div>
      )}
    </div>
  );
};

function buildReActContext(parts: MessagePart[]): string {
  const lines: string[] = [];
  for (const part of parts) {
    if (part.type === 'reasoning') {
      lines.push(`Thought: ${part.text}`);
    } else if (part.type === 'tool') {
      const toolPart = part as any;
      const action = toolPart.state?.metadata?.action || toolPart.tool;
      lines.push(`Action: ${action}`);
      if (toolPart.state?.input) lines.push(`Action Input: ${JSON.stringify(toolPart.state.input)}`);
      if (toolPart.state?.output) lines.push(`Observation: ${toolPart.state.output}`);
    }
  }
  return lines.join('\n');
}

export default EmbeddedChat;