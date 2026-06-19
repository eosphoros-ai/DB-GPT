/**
 * Scheduled task type definitions
 * Mirrors backend pydantic schema:
 *   packages/dbgpt-serve/src/dbgpt_serve/scheduled_task/api/schemas.py
 *
 * Reuse ResponseType<T> from web/client/api/index.ts for API response wrapping
 */

/** Frozen conversation snapshot used to replay a chat on scheduled execution. */
export type ChatReplayPayload = {
  version?: number;
  user_input: string;
  chat_mode?: string;
  model_name?: string | null;
  select_param?: string | null;
  temperature?: number | null;
  max_new_tokens?: number | null;
  ext_info?: Record<string, any> | null;
};

/** Create scheduled task request. */
export type CreateTaskRequest = {
  task_name: string;
  description?: string | null;
  cron_expression: string;
  payload: ChatReplayPayload;
  /** Creator display name (preferred over auth user_id) */
  creator_name?: string | null;
};

/** Update scheduled task request (partial fields optional). */
export type UpdateTaskRequest = {
  task_name?: string | null;
  description?: string | null;
  cron_expression?: string | null;
  /** Original question (payload.user_input; editable) */
  user_input?: string | null;
  /** Execution model (payload.model_name; editable) */
  model_name?: string | null;
};

/** Enable/pause task request. */
export type ToggleTaskRequest = {
  enabled: boolean;
};

/** Run status enum. */
export type ScheduledRunStatus = 'running' | 'success' | 'failed' | 'timeout';

/** Scheduled task response. */
export type TaskResponse = {
  task_id: string;
  task_name: string;
  description?: string | null;
  task_type: string;
  cron_expression: string;
  payload?: ChatReplayPayload | null;
  enabled: boolean;
  created_at?: string | null;
  updated_at?: string | null;
  user_name?: string | null;
  sys_code?: string | null;
  next_run_time?: string | null;
};

/** Single run history response. */
export type RunResponse = {
  run_id: string;
  task_id: string;
  started_at?: string | null;
  finished_at?: string | null;
  status: ScheduledRunStatus;
  result_summary?: string | null;
  error_message?: string | null;
  output_conv_uid?: string | null;
};
