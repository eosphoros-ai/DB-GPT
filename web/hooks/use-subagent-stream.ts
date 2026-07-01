// Pure parser for parallel sub-agent SSE events.
//
// The apply (setExecutionMap) stays in index.tsx's processEvent — this hook
// only exports a pure payload -> partial-state function so the parsing logic
// lives outside the 4000-line index.tsx (review I3: processEvent captures
// many setters as a closure, so the hook cannot own the state, only the
// parsing).

import type { SubAgentPartial, SubAgentState, SubAgentStatus, SubAgentStep } from '@/types/subagent';

const VALID_STATUS: SubAgentStatus[] = ['running', 'done', 'timeout', 'failed'];

function coerceStatus(raw: unknown, fallback: SubAgentStatus): SubAgentStatus {
  return VALID_STATUS.includes(raw as SubAgentStatus) ? (raw as SubAgentStatus) : fallback;
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
        artifactCount: 0,
        steps: [],
      };
      return { upsert };
    }
    case 'subagent.artifacts': {
      const items = Array.isArray(payload.items) ? payload.items : [];
      return { totalArtifacts: items.length };
    }
    default:
      return null;
  }
}
