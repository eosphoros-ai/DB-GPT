import type { CreateTaskRequest, RunResponse, TaskResponse, UpdateTaskRequest } from '@/types/scheduled-task';
import axios from '@/utils/ctx-axios';
import { useCallback } from 'react';

const BASE = '/api/v2/serve/scheduled-tasks';

/**
 * ctx-axios 的 response interceptor 已经把 axios response 解包为
 * response.data（即 API envelope {success, err_code, err_msg, data}）。
 * 这里再取 .data 得到业务数据。
 */
function unwrap<T>(payload: any): T {
  return (payload?.data ?? payload) as T;
}

/**
 * 定时任务 API hooks。
 *
 * 封装 8 个 REST 端点，返回 Promise 以便调用方自行处理 loading/error。
 * 所有函数均为稳定引用（useCallback + 空依赖）。
 */
export function useScheduledTask() {
  /** POST /api/v2/serve/scheduled-tasks/ — 创建定时任务 */
  const createTask = useCallback(async (body: CreateTaskRequest): Promise<TaskResponse> => {
    const res = await axios.post(`${BASE}/`, body);
    return unwrap<TaskResponse>(res);
  }, []);

  /** GET /api/v2/serve/scheduled-tasks/?enabled_only=false — 任务列表 */
  const listTasks = useCallback(async (enabledOnly = false): Promise<TaskResponse[]> => {
    const res = await axios.get(`${BASE}/`, {
      params: { enabled_only: enabledOnly },
    });
    return unwrap<TaskResponse[]>(res) ?? [];
  }, []);

  /** GET /api/v2/serve/scheduled-tasks/{task_id} — 任务详情 */
  const getTask = useCallback(async (taskId: string): Promise<TaskResponse> => {
    const res = await axios.get(`${BASE}/${taskId}`);
    return unwrap<TaskResponse>(res);
  }, []);

  /** PUT /api/v2/serve/scheduled-tasks/{task_id} — 更新任务 */
  const updateTask = useCallback(async (taskId: string, body: UpdateTaskRequest): Promise<TaskResponse> => {
    const res = await axios.put(`${BASE}/${taskId}`, body);
    return unwrap<TaskResponse>(res);
  }, []);

  /** POST /api/v2/serve/scheduled-tasks/{task_id}/toggle — 启停任务 */
  const toggleTask = useCallback(async (taskId: string, enabled: boolean): Promise<TaskResponse> => {
    const res = await axios.post(`${BASE}/${taskId}/toggle`, { enabled });
    return unwrap<TaskResponse>(res);
  }, []);

  /** DELETE /api/v2/serve/scheduled-tasks/{task_id} — 删除任务 */
  const deleteTask = useCallback(async (taskId: string): Promise<void> => {
    await axios.delete(`${BASE}/${taskId}`);
  }, []);

  /** GET /api/v2/serve/scheduled-tasks/{task_id}/runs?limit=&offset= — 执行历史列表 */
  const listRuns = useCallback(async (taskId: string, limit = 50, offset = 0): Promise<RunResponse[]> => {
    const res = await axios.get(`${BASE}/${taskId}/runs`, {
      params: { limit, offset },
    });
    return unwrap<RunResponse[]>(res) ?? [];
  }, []);

  /** GET /api/v2/serve/scheduled-tasks/{task_id}/runs/{run_id} — 单次执行详情 */
  const getRun = useCallback(async (taskId: string, runId: string): Promise<RunResponse> => {
    const res = await axios.get(`${BASE}/${taskId}/runs/${runId}`);
    return unwrap<RunResponse>(res);
  }, []);

  return {
    createTask,
    listTasks,
    getTask,
    updateTask,
    toggleTask,
    deleteTask,
    listRuns,
    getRun,
  };
}
