// Types for the parallel sub-agent aggregate card.
//
// Sub-agents surface in the main timeline (web/pages/index.tsx) as a grouped
// card — one row per sub-agent with a live "current action" line and a
// drill-down step list. Driven by the backend SSE events
// agent.start / agent.step / agent.done / subagent.artifacts (design spec §4.7
// "关键进展行 + 可下钻" — aligned with Claude Code / Devin / Manus).

export type SubAgentStatus = 'running' | 'done' | 'timeout' | 'failed';

/** A structured output chunk of a sub-agent step (markdown table / code / …). */
export interface SubAgentOutputChunk {
  output_type: string;
  content: any;
  title?: string;
}

export interface SubAgentArtifactRef {
  type: string;
  url: string;
  title?: string;
}

/** A single confirmed tool action inside a sub-agent (drill-down row). */
export interface SubAgentStep {
  /** Raw tool name from the backend, e.g. "sql_query". */
  action: string;
  /** Human-readable label, e.g. "查询数据库". */
  label: string;
  /** Optional one-line intention from the model. */
  intention?: string;
  /** Sanitized SQL executed by a confirmed sql_query action. */
  sql?: string;
  /** Structured output chunks (already parsed by the backend) for the
   * right-panel process view — markdown tables / code / json render properly. */
  chunks?: SubAgentOutputChunk[];
}

export interface SubAgentState {
  /** Stable id from the backend, e.g. "sub_0". */
  agentId: string;
  /** Display title (the sub-task title). */
  name: string;
  /** The delegated goal (optional, shown on hover / detail). */
  goal?: string;
  /** Current lifecycle status. */
  status: SubAgentStatus;
  /** Parallel lane index (ordering). */
  lane: number;
  /** One-based dispatch batch number within the lead-agent run. */
  batchId: number;
  /** Number of artifacts (images/html) this sub-agent produced. */
  artifactCount: number;
  /** Bounded artifact path references persisted for history restoration. */
  artifacts?: SubAgentArtifactRef[];
  /** Human-readable current action while running, e.g. "正在查询数据库". */
  currentAction?: string;
  /** Clean final answer extracted from the terminate action (never raw CoT). */
  result?: string;
  /** Wall-clock execution time reported by the backend. */
  elapsedMs?: number;
  /** Confirmed tool actions so far (drill-down list). */
  steps: SubAgentStep[];
}

/** A partial update produced by parseSubAgentEvent, applied to executionMap. */
export interface SubAgentPartial {
  /** When set, upsert this single sub-agent (agent.start / agent.done). */
  upsert?: SubAgentState;
  /** When set (agent.step), append a step to this sub-agent + set currentAction. */
  stepUpdate?: { agentId: string; step: SubAgentStep };
  /**
   * When set (subagent.artifacts), the per-agent items produced this batch.
   * Each item carries its source ``agent_id`` / ``agent_name`` (stamped by the
   * backend) so the frontend can count per row and label "by <agent>" in the
   * files tab. ``totalArtifacts`` is kept as a fallback aggregate count.
   */
  artifactItems?: SubAgentArtifactItem[];
  totalArtifacts?: number;
}

/** One artifact produced by a sub-agent, as carried by subagent.artifacts. */
export interface SubAgentArtifactItem {
  type: string; // 'image' | 'html' | 'file' | ...
  url?: string;
  content?: string;
  title?: string;
  /** Source sub-agent id, e.g. "sub_d1_0". */
  agent_id: string;
  /** Source sub-agent display name (the sub-task title). */
  agent_name: string;
}
