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
}

/** A single confirmed tool action inside a sub-agent (drill-down row). */
export interface SubAgentStep {
  /** Raw tool name from the backend, e.g. "sql_query". */
  action: string;
  /** Human-readable label, e.g. "查询数据库". */
  label: string;
  /** Optional one-line intention from the model. */
  intention?: string;
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
  /** Number of artifacts (images/html) this sub-agent produced. */
  artifactCount: number;
  /** Human-readable current action while running, e.g. "正在查询数据库". */
  currentAction?: string;
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
   * When set (subagent.artifacts), the total number of artifacts produced
   * across the batch. The backend event carries a flat item list without
   * per-agent attribution, so the card shows an aggregate count only.
   */
  totalArtifacts?: number;
}
