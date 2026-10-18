/**
 * Conversation-side observability trace panel.
 *
 * Mounted as one of the right-panel tabs. Reads the spans linked to the current
 * conversation and renders them as a **message-style timeline** (user question →
 * system prompt → thought → tool call → observation → reply), mirroring how the
 * messages actually looked to the model — rather than a flat span tree.
 *
 * Data mapping (from span metadata):
 *   user          agent.generate_reply.received_message.content
 *   system        Agent.llm_client.no_streaming_call.messages[role==system]
 *   thought       agent.act.run.action_out.thoughts / action_intention / action_reason
 *   tool call     agent.act.run.action_out.action + action_input
 *   observation   agent.act.run.action_out.observations
 *   reply         agent.generate_reply.reply_message (terminate.action_input.result)
 */
import type { SpanNode, TraceSummary, TraceTree } from '@/client/api';
import { apiInterceptors, getObservabilityTrace, searchObservabilityTraces } from '@/client/api';
import { Empty, Spin, Tag } from 'antd';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

interface ConversationTracePanelProps {
  conversationId: string;
}

/** Parse a value that may be a JSON string, a Python dict repr, or already structured. */
function parseMaybe(v: unknown): any {
  if (v == null) return v;
  if (typeof v !== 'string') return v;
  const s = v.trim();
  if (!s) return v;
  // Standard JSON object/array.
  if (s.startsWith('{') || s.startsWith('[')) {
    try {
      return JSON.parse(s);
    } catch {
      /* fall through to literal */
    }
  }
  // Python dict repr uses single quotes — parse via JSON after a quick sanitize.
  if (s.startsWith("{'")) {
    try {
      return JSON.parse(s.replace(/'/g, '"'));
    } catch {
      /* keep as string */
    }
  }
  return v;
}

type MessageKind = 'user' | 'system' | 'thought' | 'tool_call' | 'reply';

interface TraceMessage {
  id: string;
  kind: MessageKind;
  content: string;
  actionName?: string;
  /** Tool call input (the JSON args). */
  actionInput?: string;
  /** Tool call output (observation / returned result). */
  output?: string;
  intention?: string;
  reason?: string;
  modelName?: string;
  durationMs?: number;
  success?: boolean;
}

function msToSeconds(ms?: number | null): string {
  if (ms == null) return '-';
  return `${(ms / 1000).toFixed(2)}s`;
}

/** Flatten a span tree into an ordered list (sorted by start_time). */
function flattenSpans(node: SpanNode, acc: SpanNode[] = []): SpanNode[] {
  acc.push(node);
  (node.children || []).forEach(c => flattenSpans(c, acc));
  return acc;
}

/** Extract a structured message timeline from a flattened span list. */
function extractMessages(spans: SpanNode[]): TraceMessage[] {
  const sorted = [...spans].sort((a, b) => {
    const at = a.start_time ? new Date(a.start_time).getTime() : 0;
    const bt = b.start_time ? new Date(b.start_time).getTime() : 0;
    return at - bt;
  });

  const messages: TraceMessage[] = [];
  let systemEmitted = false;
  let userEmitted = false;

  // Collect terminate action inputs to find the clean final reply.
  let finalReply: string | null = null;
  const actRuns: SpanNode[] = [];

  for (const span of sorted) {
    const op = span.operation_name || '';
    if (op === 'Agent.llm_client.no_streaming_call') {
      // System prompt from the model's message list (only once).
      const messagesArr = span.metadata?.messages;
      if (!systemEmitted && Array.isArray(messagesArr)) {
        const sys = messagesArr.find((m: any) => m?.role === 'system');
        if (sys?.content) {
          messages.push({
            id: span.span_id + '-sys',
            kind: 'system',
            content: String(sys.content),
            modelName: span.metadata?.model_name || span.model_name,
          });
          systemEmitted = true;
        }
      }
    } else if (op === 'agent.generate_reply') {
      // User question from the first received_message.
      if (!userEmitted) {
        const received = parseMaybe(span.metadata?.received_message);
        const content = received?.content;
        if (content) {
          messages.push({ id: span.span_id + '-user', kind: 'user', content: String(content) });
          userEmitted = true;
        }
      }
    } else if (op === 'agent.act.run') {
      actRuns.push(span);
      const ao = parseMaybe(span.metadata?.action_out) || {};
      if (ao.action === 'terminate') {
        const input = parseMaybe(ao.action_input);
        if (input?.result) finalReply = String(input.result);
      }
    }
  }

  // Tool calls + thoughts + observations (one group per act.run, in order).
  for (const span of actRuns) {
    const ao = parseMaybe(span.metadata?.action_out) || {};
    const thoughts = ao.thoughts ? String(ao.thoughts) : '';
    const intention = ao.action_intention ? String(ao.action_intention) : '';
    const reason = ao.action_reason ? String(ao.action_reason) : '';
    const actionName = ao.action ? String(ao.action) : '';
    const actionInput = ao.action_input != null ? formatInput(parseMaybe(ao.action_input)) : '';
    const observation = ao.observations ? String(ao.observations) : '';

    if (thoughts) {
      messages.push({
        id: span.span_id + '-thought',
        kind: 'thought',
        content: thoughts,
        intention: intention || undefined,
        reason: reason || undefined,
      });
    }
    if (actionName) {
      messages.push({
        id: span.span_id + '-tool',
        kind: 'tool_call',
        content: actionName,
        actionName,
        actionInput: actionInput || undefined,
        output: observation || undefined,
        durationMs: span.duration_ms,
        success: ao.is_exe_success,
      });
    }
  }

  // Final reply.
  if (finalReply) {
    messages.push({ id: 'reply', kind: 'reply', content: finalReply });
  }

  return messages;
}

function formatInput(v: any): string {
  if (v == null) return '';
  if (typeof v === 'string') return v;
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
}

const KIND_META: Record<MessageKind, { color: string; bg: string }> = {
  user: { color: '#1677ff', bg: 'bg-blue-50 dark:bg-blue-900/20' },
  system: { color: '#8c8c8c', bg: 'bg-gray-50 dark:bg-gray-800/60' },
  thought: { color: '#722ed1', bg: 'bg-purple-50 dark:bg-purple-900/20' },
  tool_call: { color: '#fa8c16', bg: 'bg-orange-50 dark:bg-orange-900/20' },
  reply: { color: '#1677ff', bg: 'bg-blue-50 dark:bg-blue-900/20' },
};

function MessageBubble({ msg }: { msg: TraceMessage }) {
  const { t } = useTranslation();
  const meta = KIND_META[msg.kind];
  const isSystem = msg.kind === 'system';
  const isTool = msg.kind === 'tool_call';
  return (
    <div className={`rounded-lg ${meta.bg} px-3 py-2.5`}>
      <div className='flex items-center gap-2 mb-1'>
        <span className='text-[11px] font-semibold' style={{ color: meta.color }}>
          {t(`observability_kind_${msg.kind}`)}
        </span>
        {msg.kind === 'tool_call' && msg.success != null && (
          <Tag color={msg.success ? 'green' : 'red'} style={{ marginInlineEnd: 0, fontSize: 10, lineHeight: '16px' }}>
            {t(msg.success ? 'observability_success' : 'observability_failure')}
          </Tag>
        )}
        {msg.durationMs != null && msg.kind === 'tool_call' && (
          <span className='text-[10px] text-gray-400'>{msToSeconds(msg.durationMs)}</span>
        )}
      </div>

      {msg.intention && (
        <div className='text-[11px] text-gray-500 mb-0.5'>
          {t('observability_intention')}：{msg.intention}
        </div>
      )}
      {msg.reason && (
        <div className='text-[11px] text-gray-500 mb-0.5'>
          {t('observability_reason')}：{msg.reason}
        </div>
      )}

      {isTool ? (
        <div className='space-y-1.5'>
          <div className='font-mono text-xs text-gray-800 dark:text-gray-200'>
            <span className='text-orange-600 dark:text-orange-400 font-semibold'>{msg.content}</span>
          </div>
          {msg.actionInput && (
            <div>
              <div className='text-[10px] text-gray-400 mb-0.5'>{t('observability_input')}</div>
              <pre className='text-[11px] font-mono text-gray-600 dark:text-gray-300 bg-white/60 dark:bg-black/20 rounded p-2 overflow-x-auto whitespace-pre-wrap break-all'>
                {msg.actionInput}
              </pre>
            </div>
          )}
          {msg.output && (
            <div>
              <div className='text-[10px] text-gray-400 mb-0.5'>{t('observability_output')}</div>
              <pre className='text-[11px] font-mono text-gray-600 dark:text-gray-300 bg-white/60 dark:bg-black/20 rounded p-2 overflow-x-auto whitespace-pre-wrap break-all'>
                {msg.output}
              </pre>
            </div>
          )}
        </div>
      ) : (
        <div
          className={`text-xs text-gray-800 dark:text-gray-200 whitespace-pre-wrap break-words ${
            isSystem ? 'max-h-40 overflow-y-auto' : ''
          }`}
        >
          {msg.content}
        </div>
      )}
    </div>
  );
}

const ConversationTracePanel: React.FC<ConversationTracePanelProps> = ({ conversationId }) => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [activeTraceId, setActiveTraceId] = useState<string | null>(null);
  const [tree, setTree] = useState<TraceTree | null>(null);
  const [treeLoading, setTreeLoading] = useState(false);

  // Load the list of traces linked to this conversation.
  // NOTE: use functional setActiveTraceId to avoid depending on `activeTraceId`
  // here — depending on it would re-create loadTraces on every selection change,
  // which re-runs this effect (it resets activeTraceId), causing an infinite
  // request loop.
  const loadTraces = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [, data] = await apiInterceptors(searchObservabilityTraces({ conversation_id: conversationId, limit: 50 }));
      const list = data || [];
      setTraces(list);
      setActiveTraceId(prev => prev ?? list[0]?.trace_id ?? null);
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setLoading(false);
    }
  }, [conversationId]);

  useEffect(() => {
    if (!conversationId) return;
    setActiveTraceId(null);
    setTraces([]);
    setTree(null);
    void loadTraces();
  }, [conversationId, loadTraces]);

  // Load the span tree for the selected trace.
  useEffect(() => {
    if (!activeTraceId) {
      setTree(null);
      return;
    }
    let cancelled = false;
    setTreeLoading(true);
    apiInterceptors(getObservabilityTrace(activeTraceId))
      .then(([, data]) => {
        if (!cancelled) setTree(data || null);
      })
      .catch(() => {
        if (!cancelled) setTree(null);
      })
      .finally(() => {
        if (!cancelled) setTreeLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [activeTraceId]);

  const messages = useMemo(() => {
    if (!tree?.root) return [];
    return extractMessages(flattenSpans(tree.root));
  }, [tree]);

  if (loading) {
    return (
      <div className='flex h-full items-center justify-center'>
        <Spin />
      </div>
    );
  }
  if (treeLoading && !tree) {
    return (
      <div className='flex h-full items-center justify-center'>
        <Spin />
      </div>
    );
  }
  if (error) {
    return (
      <div className='p-5'>
        <Empty description={error} />
      </div>
    );
  }

  return (
    <div className='flex h-full flex-col overflow-y-auto p-4 space-y-3'>
      {/* Trace selector */}
      {traces.length > 1 && (
        <div className='flex items-center gap-2 text-xs'>
          <span className='text-gray-400'>{t('observability_trace') || 'Trace'}:</span>
          <select
            value={activeTraceId || ''}
            onChange={e => setActiveTraceId(e.target.value)}
            className='rounded border border-gray-200 dark:border-gray-700 bg-transparent px-2 py-1 text-xs'
          >
            {traces.map(t0 => (
              <option key={t0.trace_id} value={t0.trace_id}>
                {t0.root_operation_name || t0.trace_id.slice(0, 12)} · {t0.span_count} spans
              </option>
            ))}
          </select>
        </div>
      )}

      {messages.length === 0 ? (
        <div className='flex h-full items-center justify-center p-5'>
          <Empty description={t('observability_no_trace') || 'No trace yet'} />
        </div>
      ) : (
        <div className='space-y-2'>
          {messages.map(msg => (
            <MessageBubble key={msg.id} msg={msg} />
          ))}
        </div>
      )}
    </div>
  );
};

export default ConversationTracePanel;
