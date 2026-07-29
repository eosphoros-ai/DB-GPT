// Pure parser for parallel sub-agent SSE events.
//
// The apply (setExecutionMap) stays in index.tsx's processEvent — this hook
// only exports a pure payload -> partial-state function so the parsing logic
// lives outside the 4000-line index.tsx (review I3: processEvent captures
// many setters as a closure, so the hook cannot own the state, only the
// parsing).

import type {
  SubAgentArtifactItem,
  SubAgentPartial,
  SubAgentState,
  SubAgentStatus,
  SubAgentStep,
} from '@/types/subagent';

const VALID_STATUS: SubAgentStatus[] = ['running', 'done', 'timeout', 'failed'];

function coerceStatus(raw: unknown, fallback: SubAgentStatus): SubAgentStatus {
  return VALID_STATUS.includes(raw as SubAgentStatus) ? (raw as SubAgentStatus) : fallback;
}

function coerceBatchId(payload: any): number {
  if (Number.isFinite(payload?.batch_id)) return Number(payload.batch_id);
  const match = String(payload?.agent_id || '').match(/^sub_d(\d+)_/);
  return match ? Number(match[1]) : 0;
}

// Map a raw tool name to a human-readable action label (zh). Falls back to the
// raw name so unknown tools still render something sensible.
const ACTION_LABELS: Record<string, string> = {
  sql_query: '查询数据库',
  code_interpreter: '运行代码',
  html_interpreter: '生成报告',
  knowledge_retrieve: '检索知识库',
  execute_skill_script_file: '执行技能脚本',
  shell_interpreter: '执行命令',
  load_skill: '加载技能',
  load_tools: '准备工具',
};

export function actionLabel(action: string): string {
  return ACTION_LABELS[action] || action;
}

function optionalString(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined;
  const trimmed = value.trim();
  return trimmed || undefined;
}

/**
 * Restore the bounded structured sub-agent snapshot persisted with a history
 * view message. Older messages do not have this field and intentionally
 * return an empty map so the existing result-summary fallback keeps working.
 */
export function restoreSubAgentStates(raw: unknown): Record<string, SubAgentState> {
  const items = Array.isArray(raw)
    ? raw
    : raw && typeof raw === 'object' && Array.isArray((raw as { items?: unknown }).items)
      ? ((raw as { items: unknown[] }).items ?? [])
      : [];
  const restored: Record<string, SubAgentState> = {};

  for (const value of items) {
    if (!value || typeof value !== 'object') continue;
    const item = value as Record<string, any>;
    const agentId = optionalString(item.agent_id ?? item.agentId);
    if (!agentId) continue;

    const rawSteps = Array.isArray(item.steps) ? item.steps : [];
    const steps: SubAgentStep[] = [];
    for (const rawStep of rawSteps) {
      if (!rawStep || typeof rawStep !== 'object') continue;
      const stepValue = rawStep as Record<string, any>;
      const action = optionalString(stepValue.action);
      if (!action) continue;

      const step: SubAgentStep = {
        action,
        label: optionalString(stepValue.label) || actionLabel(action),
      };
      const intention = optionalString(stepValue.intention);
      const sql = optionalString(stepValue.sql);
      if (intention) step.intention = intention;
      if (sql) step.sql = sql;
      if (Array.isArray(stepValue.chunks)) {
        const chunks = stepValue.chunks
          .filter(
            (chunk: unknown) =>
              Boolean(chunk) && typeof chunk === 'object' && Object.prototype.hasOwnProperty.call(chunk, 'content'),
          )
          .map((chunk: any) => {
            const restoredChunk = {
              output_type: String(chunk.output_type || 'text'),
              content: chunk.content,
              ...(optionalString(chunk.title) ? { title: optionalString(chunk.title) } : {}),
            };
            return restoredChunk;
          });
        if (chunks.length > 0) step.chunks = chunks;
      }
      steps.push(step);
    }

    const lane = Number(item.lane);
    const batchId = Number(item.batch_id ?? item.batchId);
    const artifactCount = Number(item.artifact_count ?? item.artifactCount);
    const elapsedMs = Number(item.elapsed_ms ?? item.elapsedMs);
    const status = coerceStatus(item.status, 'done');
    const artifacts = (Array.isArray(item.artifacts) ? item.artifacts : [])
      .filter(
        (artifact: unknown) =>
          Boolean(artifact) &&
          typeof artifact === 'object' &&
          Boolean(optionalString((artifact as Record<string, unknown>).url)),
      )
      .map((artifact: Record<string, unknown>) => ({
        type: optionalString(artifact.type) || 'file',
        url: optionalString(artifact.url)!,
        ...(optionalString(artifact.title) ? { title: optionalString(artifact.title) } : {}),
      }));
    const state: SubAgentState = {
      agentId,
      name: optionalString(item.name ?? item.agent_name ?? item.agentName) || agentId,
      status,
      lane: Number.isFinite(lane) ? lane : 0,
      batchId: Number.isFinite(batchId) ? batchId : coerceBatchId({ agent_id: agentId }),
      artifactCount: Number.isFinite(artifactCount) ? Math.max(0, artifactCount) : 0,
      ...(artifacts.length > 0 ? { artifacts } : {}),
      steps,
    };
    const goal = optionalString(item.goal);
    const result = optionalString(item.result);
    if (goal) state.goal = goal;
    if (result) state.result = result;
    if (Number.isFinite(elapsedMs)) state.elapsedMs = Math.max(0, elapsedMs);
    if (status === 'running' && steps.length > 0) {
      state.currentAction = steps[steps.length - 1].label;
    }
    restored[agentId] = state;
  }

  return restored;
}

/**
 * Shape of a sub-agent artifact as the frontend stores it. Structurally
 * compatible with the ``Artifact`` interface in ``pages/index.tsx`` — kept
 * local here so the hook does not import from a page module (which would be
 * a layering violation and a circular import risk). ``type`` is narrowed to
 * the literal union (not ``string``) so records assign cleanly to ``Artifact``
 * whose ``type`` is itself a literal union.
 */
export interface SubAgentArtifactRecord {
  id: string;
  type: 'image' | 'html' | 'file';
  name: string;
  content: any;
  createdAt: number;
  messageId: string;
  stepId: string;
  sourceAgent: string;
  downloadable: boolean;
}

/**
 * Convert ``subagent.artifacts`` items (as emitted by the backend) into
 * artifact records the global ``artifacts`` state can merge. Each record
 * carries its source sub-agent so the files tab can label "by <agent>".
 *
 * Dedup is left to the caller (the caller knows the existing artifact ids);
 * this function only shapes the data.
 */
export function buildSubAgentArtifacts(
  items: SubAgentArtifactItem[],
  messageId: string,
  now: number = Date.now(),
): SubAgentArtifactRecord[] {
  return items.map((item, idx) => {
    const url = item.url || (typeof item.content === 'string' ? item.content : '') || '';
    const fallbackName = url.split('/').pop() || `subagent-artifact-${idx}`;
    const name = item.title || fallbackName;
    const type = item.type === 'image' ? 'image' : item.type === 'html' ? 'html' : 'file';
    return {
      id: `${messageId}-subagent-${item.agent_id}-${idx}`,
      type,
      name,
      content: url,
      createdAt: now,
      messageId,
      stepId: item.agent_id,
      sourceAgent: item.agent_name,
      downloadable: true,
    };
  });
}

/**
 * Parse a sub-agent SSE payload into a partial state update.
 *
 * Handles:
 *  - agent.start         -> upsert a running sub-agent row
 *  - agent.step          -> append a confirmed tool action + set currentAction
 *  - agent.done          -> upsert the same row with its final status
 *  - subagent.artifacts  -> report the aggregate artifact count
 *
 * Returns null for any unrelated event so the caller can skip it.
 */
export function parseSubAgentEvent(payload: any): SubAgentPartial | null {
  if (!payload || typeof payload !== 'object') return null;

  switch (payload.type) {
    case 'agent.start': {
      if (!payload.agent_id) return null;
      const upsert: SubAgentState = {
        agentId: String(payload.agent_id),
        name: String(payload.agent_name || payload.agent_id),
        goal: payload.goal ? String(payload.goal) : undefined,
        status: 'running',
        lane: Number.isFinite(payload.lane) ? Number(payload.lane) : 0,
        batchId: coerceBatchId(payload),
        artifactCount: 0,
        steps: [],
      };
      return { upsert };
    }
    case 'agent.step': {
      if (!payload.agent_id || !payload.action) return null;
      const step: SubAgentStep = {
        action: String(payload.action),
        label: actionLabel(String(payload.action)),
        intention: payload.intention ? String(payload.intention) : undefined,
        sql: typeof payload.sql === 'string' && payload.sql.trim() ? payload.sql.trim() : undefined,
        // Backend already parsed the tool result into structured chunks.
        chunks: Array.isArray(payload.chunks) ? payload.chunks : undefined,
      };
      return { stepUpdate: { agentId: String(payload.agent_id), step } };
    }
    case 'agent.done': {
      if (!payload.agent_id) return null;
      // Only the status is known here; the caller merges onto the existing
      // row (name/goal/lane/steps preserved).
      const upsert: SubAgentState = {
        agentId: String(payload.agent_id),
        name: String(payload.agent_id),
        status: coerceStatus(payload.status, 'done'),
        lane: 0,
        batchId: coerceBatchId(payload),
        artifactCount: 0,
        result: typeof payload.result === 'string' ? payload.result : undefined,
        elapsedMs: Number.isFinite(payload.elapsed_ms) ? Number(payload.elapsed_ms) : undefined,
        steps: [],
      };
      return { upsert };
    }
    case 'subagent.artifacts': {
      const rawItems = Array.isArray(payload.items) ? payload.items : [];
      // Keep only items with a usable agent_id; skip malformed ones rather
      // than crashing the whole event apply.
      const items: SubAgentArtifactItem[] = rawItems
        .filter((it: any) => it && typeof it.agent_id === 'string')
        .map((it: any) => ({
          type: String(it.type || 'file'),
          url: it.url,
          content: it.content,
          title: it.title,
          agent_id: it.agent_id,
          agent_name: String(it.agent_name || it.agent_id),
        }));
      return { artifactItems: items, totalArtifacts: items.length };
    }
    default:
      return null;
  }
}
