/**
 * 定时任务相关类型定义
 * 镜像后端 pydantic schema:
 *   packages/dbgpt-serve/src/dbgpt_serve/scheduled_task/api/schemas.py
 *
 * API 响应包装请复用 web/client/api/index.ts 中的 ResponseType<T>
 */

/** 冻结的对话快照,定时执行时用于回放对话。 */
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

/** 创建定时任务请求。 */
export type CreateTaskRequest = {
  task_name: string;
  description?: string | null;
  cron_expression: string;
  payload: ChatReplayPayload;
  /** 创建人显示名称(优先于鉴权 user_id) */
  creator_name?: string | null;
};

/** 更新定时任务请求(部分字段可选)。 */
export type UpdateTaskRequest = {
  task_name?: string | null;
  description?: string | null;
  cron_expression?: string | null;
  /** 原始问题（payload.user_input，编辑时可改） */
  user_input?: string | null;
  /** 执行模型（payload.model_name，编辑时可改） */
  model_name?: string | null;
};

/** 启用/暂停任务请求。 */
export type ToggleTaskRequest = {
  enabled: boolean;
};

/** 执行状态枚举。 */
export type ScheduledRunStatus = 'running' | 'success' | 'failed' | 'timeout';

/** 定时任务响应。 */
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

/** 单次执行历史响应。 */
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
