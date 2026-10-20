export type ReportBlockType = 'metric' | 'table' | 'chart' | 'insight' | 'text';
export type ArtifactType = 'sql' | 'python' | 'chart' | 'reference';
export type ClaimVerificationStatus =
  | 'verified'
  | 'partially_supported'
  | 'unsupported'
  | 'insufficient_evidence'
  | 'contradicted'
  | 'unverifiable'
  | 'error';
export type ClaimVerificationMethod =
  | 'exact_match'
  | 'recompute'
  | 'comparison_rule'
  | 'trend_rule'
  | 'business_rule'
  | 'time_series_rule'
  | 'ranking_rule'
  | 'nli'
  | 'minicheck'
  | 'llm_judge';

export interface ClaimVerificationResult {
  status: ClaimVerificationStatus;
  verification_method?: ClaimVerificationMethod;
  support_score?: number;
  evidence_artifact_ids?: string[];
  details?: Record<string, unknown>;
}

export type InferenceConfidenceLevel = 'high' | 'medium' | 'low';

/** Evidence-grounded interpretation strength; never an LLM self-assessment. */
export interface ClaimInferenceConfidence {
  score: number;
  level: InferenceConfidenceLevel;
  method: 'evidence_grounded_heuristic_v1';
  reason_codes: string[];
  evidence_artifact_ids: string[];
}

export interface ReportClaim {
  claim_id: string;
  claim_type?: string;
  text: string;
  normalized?: Record<string, unknown>;
  verification?: ClaimVerificationResult;
  inference_confidence?: ClaimInferenceConfidence;
}

export type ReportTextSegment =
  { type: 'text'; text: string } | { type: 'claim'; segment_id: string; claim_id: string; text: string };

export interface ArtifactContent {
  inline?: unknown;
  uri?: string;
  media_type?: string;
  sha256?: string;
  size?: number;
}

export type TimingMeasurementState = 'captured' | 'not_measured' | 'included_in_source_execution' | 'not_applicable';

export interface ArtifactTiming {
  server_execution_ms?: number;
  derivative_processing_ms?: number;
  browser_render_ms?: number;
  derivative_processing_state: TimingMeasurementState;
  browser_render_state: TimingMeasurementState;
}

export interface ReportArtifact {
  type: ArtifactType;
  artifact_id: string;
  name?: string;
  status?: 'succeeded' | 'failed' | 'cancelled' | 'timed_out';
  duration_ms?: number;
  timing?: ArtifactTiming;
  error?: string;
  input_artifact_ids: string[];
  metadata: Record<string, unknown>;
  execution: {
    conv_uid: string;
    step_id: string;
    message_id?: string;
    task_id?: string;
    run_id?: string;
    action?: string;
  };
  result?: ArtifactContent;
  output?: ArtifactContent;
  columns?: string[];
  row_count?: number;
  sql?: string;
  database?: string;
  code?: string;
  language?: string;
  stdout?: string;
  stderr?: string;
  chart_type?: string;
  spec?: Record<string, unknown>;
  reference_type?: 'knowledge' | 'memory' | 'web' | 'model' | 'file';
  source_id?: string;
  source_name?: string;
  uri?: string;
  locator?: Record<string, unknown>;
  excerpt?: string;
}

export interface ArtifactLineage {
  source_id?: string;
  source_name?: string;
  tables?: string[];
}

export interface EvidenceReference {
  artifact_id: string;
  role: 'source' | 'calculation' | 'support';
  selector: Record<string, unknown>;
  target_selector: Record<string, unknown>;
}

export interface ReportBlock {
  type: ReportBlockType;
  block_id: string;
  title?: string;
  evidence: EvidenceReference[];
  metadata: Record<string, unknown>;
  value?: unknown;
  display_value?: string;
  unit?: string;
  content?: string;
  data_artifact_id?: string;
  chart_artifact_id?: string;
  description?: string;
  claims?: ReportClaim[];
  segments?: ReportTextSegment[];
}

export interface ReportDocument {
  schema_version: 3;
  report_id: string;
  title: string;
  conv_uid: string;
  created_at: string;
  sections: Array<{
    section_id: string;
    title: string;
    blocks: ReportBlock[];
  }>;
  artifacts: ReportArtifact[];
  metadata: Record<string, unknown>;
}

export interface ReportRunSummary {
  run_id: string;
  report_id: string;
  revision: number;
  schema_version: 3;
  trigger_type: string;
  parent_run_id?: string;
  status: string;
  created_at: string;
}

export interface ReportRun extends ReportRunSummary {
  document: ReportDocument;
}

export interface ReportEvidenceDetail {
  section_id: string;
  block_id: string;
  ordinal: number;
  evidence: EvidenceReference;
  artifact: ReportArtifact;
}

export interface BrowserRenderObservation {
  observation_id: string;
  artifact_id: string;
  renderer: 'echarts' | 'g2' | 'image' | 'table';
  state: 'rendered' | 'failed' | 'not_rendered';
  duration_ms?: number;
  options?: Record<string, unknown>;
  options_content?: ArtifactContent;
  error?: string;
  source?: 'browser';
  received_at?: string;
}
