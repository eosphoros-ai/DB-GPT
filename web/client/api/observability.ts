import { GET } from './index';

// ---- DTOs (mirror dbgpt.observability.models) ----
export interface AgentSummary {
  agent_name: string;
  event_count: number;
  session_count: number;
  error_rate: number;
  first_seen?: string;
  last_seen?: string;
  drift_verdict?: string;
}
export interface HealthRow {
  agent_name: string;
  event_count: number;
  error_rate: number;
  drift_verdict?: string;
  drift_score?: number;
}
export interface TraceSummary {
  trace_id: string;
  root_operation_name?: string;
  agent_name?: string;
  start_time?: string;
  duration_ms?: number;
  status?: string;
  span_count: number;
  model_name?: string;
  total_tokens?: number;
  cost?: number;
  conversation_id?: string;
}
export interface SpanNode {
  span_id: string;
  parent_span_id?: string;
  operation_name?: string;
  span_type?: string;
  start_time?: string;
  end_time?: string;
  duration_ms?: number;
  status?: string;
  agent_name?: string;
  model_name?: string;
  tool_name?: string;
  total_tokens?: number;
  cost?: number;
  metadata?: Record<string, any>;
  error?: any;
  children?: SpanNode[];
}
export interface TraceTree {
  trace_id: string;
  root?: SpanNode;
  start_time?: string;
  end_time?: string;
  duration_ms?: number;
  span_count: number;
  status?: string;
  conversation_id?: string;
}
export interface TimeseriesPoint {
  timestamp: string;
  value: number;
}
export interface Timeseries {
  metric: string;
  points: TimeseriesPoint[];
}
export interface SessionSummary {
  session_id: string;
  agent_name?: string;
  event_count: number;
  start_time?: string;
  end_time?: string;
  duration_seconds?: number;
  error_count: number;
  new_event_types?: string[];
}

// ---- endpoints ----
const BASE = '/api/v1/observability';

export const getObservabilityCapabilities = () => GET<null, string[]>(`${BASE}/capabilities`);

export const getObservabilityAgents = (params?: { time_from?: string; time_to?: string }) =>
  GET<typeof params, AgentSummary[]>(`${BASE}/agents`, params);

export const getObservabilityHealth = (params?: { time_from?: string; time_to?: string }) =>
  GET<typeof params, HealthRow[]>(`${BASE}/health`, params);

export const getObservabilityAgentStats = (agentName: string) =>
  GET<null, Record<string, any>>(`${BASE}/agents/${encodeURIComponent(agentName)}/stats`);

export interface TraceQuery {
  trace_id?: string;
  agent_name?: string;
  model_name?: string;
  conversation_id?: string;
  operation_name?: string;
  status?: string;
  start_time?: string;
  end_time?: string;
  /** Drop pure-HTTP middleware traces (single-span). */
  min_span_count?: number;
  limit?: number;
  offset?: number;
}
export const searchObservabilityTraces = (params: TraceQuery) =>
  GET<typeof params, TraceSummary[]>(`${BASE}/traces`, params);

export const getObservabilityTrace = (traceId: string) =>
  GET<null, TraceTree>(`${BASE}/traces/${encodeURIComponent(traceId)}`);

export const getObservabilitySessions = (params?: { agent_name?: string; limit?: number }) =>
  GET<typeof params, SessionSummary[]>(`${BASE}/sessions`, params);

export interface MetricsQuery {
  metric: string;
  start: string;
  end: string;
  granularity?: string;
  agent_name?: string;
  model_name?: string;
  conversation_id?: string;
  status?: string;
}
export const getObservabilityMetrics = (params: MetricsQuery) =>
  GET<typeof params, Timeseries>(`${BASE}/metrics`, params);

export interface ModelUsageSummary {
  model_name: string;
  call_count: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cache_hit_tokens: number;
  cache_miss_tokens: number;
  avg_duration_ms?: number;
  error_count: number;
}
export const getObservabilityModelUsage = (params?: { time_from?: string; time_to?: string }) =>
  GET<typeof params, ModelUsageSummary[]>(`${BASE}/models/usage`, params);
