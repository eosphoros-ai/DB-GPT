import { ChatContext } from '@/app/chat-context';
import MarkdownContext from '@/new-components/common/MarkdownContext';
import type { ITaskflowAgentStep, ITaskflowNode, ITaskflowStepMarker } from '@/types/taskflow';
import { parseTaskflowStream, stripVisBlocks, type ITaskflowSection } from '@/utils/taskflow';
import { Button, Drawer, Input, Select, Spin } from 'antd';
import React, { useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

interface DebugStep {
  id: string;
  label: string;
  status: 'running' | 'success' | 'pending';
  duration_ms?: number;
}

/** One compact tool-call / thinking row (aligned with the agent trace UI). */
const AgentStepRow: React.FC<{ step: ITaskflowAgentStep }> = ({ step }) => {
  const detail = (step.detail ?? '').replace(/\s+/g, ' ').trim();
  if (step.kind === 'thinking') {
    return (
      <div className='text-[12px] text-gray-400 leading-snug truncate' title={detail}>
        💭 {detail}
      </div>
    );
  }
  if (step.kind === 'observation') {
    return (
      <div className='text-[11.5px] text-gray-400 leading-snug pl-5 truncate' title={detail}>
        └ {detail}
      </div>
    );
  }
  // action: compact one-liner like ">_ kb_ls · {params}"
  return (
    <div className='flex items-center gap-1.5 text-[12px] leading-snug'>
      <span className='font-mono text-[11px] text-gray-400 flex-none'>&gt;_</span>
      <span className='font-semibold text-gray-700 dark:text-gray-200 flex-none'>{step.title}</span>
      {detail && (
        <span className='font-mono text-[11px] text-gray-400 truncate' title={detail}>
          · {detail}
        </span>
      )}
    </div>
  );
};

/**
 * Debug-run drawer: sends one question through the unsaved flow (server-side
 * /flow/debug) and renders the streamed answer plus the TaskFlow step trace.
 */
const DebugDrawer: React.FC<{
  open: boolean;
  onClose: () => void;
  buildPayload: () => Record<string, any> | null;
  dslNodes: ITaskflowNode[];
}> = ({ open, onClose, buildPayload, dslNodes }) => {
  const { t } = useTranslation();
  const { model, modelList } = useContext(ChatContext);
  // Debug-local model selection: defaults to the globally selected model but
  // can be overridden per debug run without changing the global choice.
  const [debugModel, setDebugModel] = useState<string>(model);
  useEffect(() => {
    if (model && model !== debugModel) setDebugModel(model);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [model]);
  const modelOptions = useMemo(() => (modelList ?? []).map(item => ({ label: item, value: item })), [modelList]);
  const [question, setQuestion] = useState('');
  const [running, setRunning] = useState(false);
  const [answer, setAnswer] = useState('');
  const [sections, setSections] = useState<ITaskflowSection[]>([]);
  const [markers, setMarkers] = useState<ITaskflowStepMarker[]>([]);
  const [error, setError] = useState<string | null>(null);
  const controllerRef = useRef<AbortController | null>(null);

  const steps = useMemo<DebugStep[]>(() => {
    const markerMap = new Map(markers.map(m => [m.step_id, m]));
    let pendingSeen = false;
    return dslNodes.map(node => {
      const marker = markerMap.get(node.id);
      if (marker) {
        return {
          id: node.id,
          label: marker.label,
          status: 'success',
          duration_ms: marker.duration_ms,
        };
      }
      const status = running && !pendingSeen ? 'running' : 'pending';
      if (status === 'running') pendingSeen = true;
      return { id: node.id, label: node.label ?? node.kind, status };
    });
  }, [dslNodes, markers, running]);

  const handleRun = async () => {
    const payload = buildPayload();
    if (!payload || !question.trim()) return;
    setRunning(true);
    setAnswer('');
    setSections([]);
    setMarkers([]);
    setError(null);
    const controller = new AbortController();
    controllerRef.current = controller;
    try {
      const response = await fetch(`${process.env.API_BASE_URL ?? ''}/api/v2/serve/awel/flow/debug`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          flow: payload,
          request: {
            model: debugModel,
            messages: question,
            stream: false,
            conv_uid: `taskflow-debug-${Date.now()}`,
          },
        }),
        signal: controller.signal,
      });
      if (!response.ok || !response.body) {
        throw new Error(`HTTP ${response.status}`);
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';
      let accumulated = '';
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';
        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith('data:')) continue;
          let chunk = trimmed.slice(5);
          if (chunk.startsWith('[SERVER_ERROR]')) {
            setError(chunk);
            continue;
          }
          // Negative lookbehind: keep escaped backslashes inside marker
          // JSON (e.g. code like print('\n')) from being corrupted.
          chunk = chunk.replace(/(?<!\\)\\n/g, '\n');
          accumulated += chunk;
          const parsed = parseTaskflowStream(accumulated);
          setMarkers(parsed.markers);
          setSections(parsed.sections);
          setAnswer(parsed.cleanText);
        }
      }
    } catch (e: any) {
      if (e?.name !== 'AbortError') setError(e?.message ?? String(e));
    } finally {
      setRunning(false);
      controllerRef.current = null;
    }
  };

  return (
    <Drawer
      title={t('taskflow_debug')}
      width={560}
      open={open}
      onClose={() => {
        controllerRef.current?.abort();
        onClose();
      }}
    >
      <div className='flex flex-col gap-4 h-full'>
        <div className='flex gap-2'>
          <Select
            className='!w-44 flex-none'
            value={debugModel}
            options={modelOptions}
            onChange={val => setDebugModel(val)}
            showSearch
          />
          <Input
            value={question}
            placeholder={t('taskflow_debug_placeholder') as string}
            onChange={e => setQuestion(e.target.value)}
            onPressEnter={() => !running && handleRun()}
          />
          <Button type='primary' loading={running} onClick={handleRun} disabled={!question.trim()}>
            {t('taskflow_run')}
          </Button>
        </div>

        {(running || markers.length > 0 || answer) && (
          <div className='border border-gray-100 dark:border-white/10 rounded-xl p-3'>
            <div className='text-[11px] font-semibold text-gray-400 mb-2'>
              {running ? t('taskflow_flow_running') : t('taskflow_flow_completed')}
            </div>
            <div className='flex flex-col gap-1.5'>
              {steps.map((step, idx) => (
                <div key={step.id} className='flex items-center gap-2 text-[12px]'>
                  {step.status === 'success' ? (
                    <span className='w-4 h-4 rounded-full bg-green-50 text-green-600 flex items-center justify-center text-[10px]'>
                      ✓
                    </span>
                  ) : step.status === 'running' ? (
                    <Spin size='small' />
                  ) : (
                    <span className='w-4 h-4 rounded-full bg-gray-100 text-gray-400 flex items-center justify-center text-[9px]'>
                      {idx + 1}
                    </span>
                  )}
                  <span className={step.status === 'pending' ? 'text-gray-400' : 'text-gray-700'}>{step.label}</span>
                  {step.duration_ms != null && (
                    <span className='text-[10px] text-gray-300 font-mono ml-auto'>
                      {(step.duration_ms / 1000).toFixed(1)}s
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {error && (
          <div className='text-[12px] text-red-600 bg-red-50 dark:bg-red-500/10 rounded-lg px-3 py-2 whitespace-pre-wrap'>
            {error}
          </div>
        )}

        {answer && (
          <div className='flex-1 overflow-y-auto flex flex-col gap-2'>
            {sections.length > 0 ? (
              // Per-node attribution: each node/agent gets its own labeled
              // block so multi-agent runs stay readable.
              sections.map(sec => {
                const kindIcon =
                  sec.marker.kind === 'agent'
                    ? '🤖'
                    : sec.marker.kind === 'db_query'
                      ? '🗄'
                      : sec.marker.kind === 'file_data'
                        ? '📄'
                        : sec.marker.kind === 'visualize'
                          ? '📊'
                          : '🧮';
                return (
                  <div
                    key={sec.marker.step_id}
                    className='border border-gray-100 dark:border-white/10 rounded-xl overflow-hidden'
                  >
                    <div className='flex items-center gap-2 px-3 py-2 bg-gray-50 dark:bg-white/5 border-b border-gray-100 dark:border-white/10'>
                      <span className='text-[13px]'>{kindIcon}</span>
                      <span className='text-[12.5px] font-semibold text-gray-800 dark:text-gray-100'>
                        {sec.marker.label}
                      </span>
                      <span className='text-[10.5px] text-gray-400 ml-auto'>{sec.marker.kind}</span>
                    </div>
                    <div className='p-3 text-[13px]'>
                      {/* Structured ReAct trace (live): compact tool rows in
                          place of a raw text wall. */}
                      {sec.marker.steps && sec.marker.steps.length > 0 && (
                        <div className='flex flex-col gap-1 mb-2 pb-2 border-b border-dashed border-gray-100 dark:border-white/10'>
                          {sec.marker.steps.map((st, i) => (
                            <AgentStepRow key={i} step={st} />
                          ))}
                          {sec.marker.status === 'running' && (
                            <div className='flex items-center gap-1.5 text-[11.5px] text-blue-600 mt-0.5'>
                              <Spin size='small' />
                              {t('taskflow_agent_round', {
                                n: (sec.marker.steps[sec.marker.steps.length - 1]?.round ?? 0) + 1,
                              })}
                            </div>
                          )}
                        </div>
                      )}
                      {/* While running, the trace text body duplicates the
                          structured rows (hide it); after completion the body
                          is the clean answer — show rows AND answer. */}
                      {(sec.marker.status !== 'running' ||
                        !(sec.marker.steps && sec.marker.steps.length > 0)) && (
                        <MarkdownContext>{stripVisBlocks(sec.content) || ' '}</MarkdownContext>
                      )}
                    </div>
                  </div>
                );
              })
            ) : (
              <div className='border border-gray-100 dark:border-white/10 rounded-xl p-3'>
                <MarkdownContext>{answer}</MarkdownContext>
              </div>
            )}
          </div>
        )}
      </div>
    </Drawer>
  );
};

export default DebugDrawer;
