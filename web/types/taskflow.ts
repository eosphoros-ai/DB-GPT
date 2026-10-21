/**
 * TaskFlow (taskflow/1) — the product-layer flow definition.
 *
 * The DSL is what the TaskFlow editor edits; the server compiles it into an
 * AWEL FlowData on save. See docs/design/taskflow-redesign-plan.md.
 */

export type TaskflowNodeKind =
  | 'start'
  | 'db_query'
  | 'file_data'
  | 'ai_analysis'
  | 'agent'
  | 'visualize'
  | 'human_confirm'
  | 'report'
  | 'output'
  | (string & {});

export type TaskflowGroup = 'boundary' | 'source' | 'analysis' | 'control' | 'output';

export interface ITaskflowNode {
  id: string;
  kind: TaskflowNodeKind;
  label?: string;
  config: Record<string, any>;
}

export type TaskflowEdge = [string, string];

/** GET /taskflow/agent-options — drives the agent node's property panel. */
export interface ITaskflowAgentProfile {
  id: string;
  label: string;
  label_en: string;
  desc?: string;
  desc_en?: string;
  default_tools?: string[];
}

export interface ITaskflowAgentToolOption {
  id: string;
  label: string;
  label_en: string;
  desc?: string;
  desc_en?: string;
}

export interface ITaskflowAgentSkillOption {
  name: string;
  label: string;
  desc?: string;
}

export interface ITaskflowAgentOptions {
  profiles: ITaskflowAgentProfile[];
  tools: ITaskflowAgentToolOption[];
  skills: ITaskflowAgentSkillOption[];
}

export interface ITaskflowDSL {
  format: string;
  nodes: ITaskflowNode[];
  edges: TaskflowEdge[];
  viewport?: Record<string, any>;
}

export interface ITaskflowConfigField {
  name: string;
  type:
    | 'text'
    | 'textarea'
    | 'number'
    | 'switch'
    | 'select'
    | 'datasource'
    | 'model'
    | 'file'
    | 'multiselect'
    | 'checkbox_group'
    | 'agent_profile';
  label: string;
  label_en: string;
  required: boolean;
  default?: any;
  options?: Array<{ label: string; value: string }> | null;
  placeholder?: string | null;
  desc?: string | null;
  desc_en?: string | null;
}

export interface ITaskflowNodeKind {
  kind: TaskflowNodeKind;
  label: string;
  label_en: string;
  desc: string;
  desc_en: string;
  group: TaskflowGroup;
  group_label: string;
  group_label_en: string;
  icon: string;
  config_fields: ITaskflowConfigField[];
  inputs_desc: string;
  inputs_desc_en: string;
  outputs_desc: string;
  outputs_desc_en: string;
  unique_in_flow: boolean;
}

/** Payload of a `vis-flow-step` marker emitted by TaskFlow operators. */
export interface ITaskflowAgentStep {
  kind: 'thinking' | 'action' | 'observation' | 'answer' | (string & {});
  title: string;
  detail?: string;
  round?: number;
}

export interface ITaskflowStepMarker {
  step_id: string;
  label: string;
  kind: string;
  status: 'running' | 'success' | 'failed' | 'waiting_confirm';
  duration_ms?: number;
  summary?: string;
  /** Transient structured ReAct trace (live events only; not persisted). */
  steps?: ITaskflowAgentStep[];
}

/** First-class artifact of a flow node (metadata only — the payload lives
 *  on disk and is served via the scoped artifact-file endpoint). */
export interface ITaskflowArtifact {
  name: string;
  type: string; // html | image | query | ...
  path: string;
  size?: number;
  /** Inline SQL result payload for ``type === 'query'`` artifacts. */
  query?: {
    sql: string;
    columns: string[];
    rows: any[][];
    row_count?: number;
    truncated?: boolean;
    db_name?: string;
  };
  row_count?: number;
}

/** A flow (or template) offered in the chat "+" menu. */
export interface ITaskflowRef {
  uid?: string;
  name: string;
  label: string;
  description?: string;
  isTemplate: boolean;
  nodeCount: number;
  taskflow_source?: ITaskflowDSL;
}
