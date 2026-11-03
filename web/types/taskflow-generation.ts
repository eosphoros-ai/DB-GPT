import type { ITaskflowDSL, ITaskflowNode } from './taskflow';

export interface EditingSnapshot {
  dsl: ITaskflowDSL;
  meta: { uid?: string; name?: string; label: string; description?: string; state?: string };
}

export interface GenerationCandidate {
  candidate_id: string;
  status: 'pending' | 'applied' | 'discarded' | 'stale';
  summary: string;
  candidate_dsl: ITaskflowDSL;
  flow_meta: { label?: string; description?: string };
  assumptions: string[];
  change_summary: Array<{
    node_id?: string;
    label: string;
    type: string;
    fields: string[];
    before?: ITaskflowNode | null;
    after?: ITaskflowNode | null;
  }>;
  missing_configuration: Array<{ node_id: string; field: string; message: string }>;
}

export interface GenerationRequest {
  request_id: string;
  status: 'running' | 'succeeded' | 'failed' | 'cancelled';
  phase?: string;
  error?: string;
}

export interface GenerationSession {
  session_id: string;
  draft_revision: number;
  context_revision: number;
  snapshot: EditingSnapshot;
  messages: Array<{ role: 'user' | 'assistant'; text: string }>;
  questions: Array<{ question_id: string; text: string; options: string[] }>;
  candidate: GenerationCandidate | null;
  requests: Record<string, GenerationRequest>;
  undo: { applied_revision: number } | null;
  run: { status: 'running' | 'success' | 'failed'; draft_revision: number } | null;
  dirty: boolean;
}
