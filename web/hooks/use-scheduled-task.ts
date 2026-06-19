import { useCallback } from 'react';
import axios from '@/utils/ctx-axios';
import type {
  CreateTaskRequest,
  UpdateTaskRequest,
  TaskResponse,
  RunResponse,
} from '@/types/scheduled-task';

const BASE = '/api/v2/serve/scheduled-tasks';

/**
 * The ctx-axios response interceptor already unwraps the axios response to
 * response.data (the API envelope {success, err_code, err_msg, data}).
 * This helper takes .data again to get the business payload.
 */
function unwrap<T>(payload: any): T {
  return (payload?.data ?? payload) as T;
}

/**
 * Scheduled task API hooks.
 *
 * Wraps 8 REST endpoints and returns Promises so callers handle loading/error.
 * All functions are stable references (useCallback with empty deps).
 */
export function useScheduledTask() {
  /** POST /api/v2/serve/scheduled-tasks/ — create scheduled task */
  const createTask = useCallback(async (body: CreateTaskRequest): Promise<TaskResponse> => {
    const res = await axios.post(`${BASE}/`, body);
    return unwrap<TaskResponse>(res);
  }, []);

  /** GET /api/v2/serve/scheduled-tasks/?enabled_only=false — task list */
  const listTasks = useCallback(async (enabledOnly = false): Promise<TaskResponse[]> => {
    const res = await axios.get(`${BASE}/`, {
      params: { enabled_only: enabledOnly },
    });
    return unwrap<TaskResponse[]>(res) ?? [];
  }, []);

  /** GET /api/v2/serve/scheduled-tasks/{task_id} — task detail */
  const getTask = useCallback(async (taskId: string): Promise<TaskResponse> => {
    const res = await axios.get(`${BASE}/${taskId}`);
    return unwrap<TaskResponse>(res);
  }, []);

  /** PUT /api/v2/serve/scheduled-tasks/{task_id} — update task */
  const updateTask = useCallback(
    async (taskId: string, body: UpdateTaskRequest): Promise<TaskResponse> => {
      const res = await axios.put(`${BASE}/${taskId}`, body);
      return unwrap<TaskResponse>(res);
    },
    [],
  );

  /** POST /api/v2/serve/scheduled-tasks/{task_id}/toggle — enable/disable task */
  const toggleTask = useCallback(
    async (taskId: string, enabled: boolean): Promise<TaskResponse> => {
      const res = await axios.post(`${BASE}/${taskId}/toggle`, { enabled });
      return unwrap<TaskResponse>(res);
    },
    [],
  );

  /** DELETE /api/v2/serve/scheduled-tasks/{task_id} — delete task */
  const deleteTask = useCallback(async (taskId: string): Promise<void> => {
    await axios.delete(`${BASE}/${taskId}`);
  }, []);

  /** GET /api/v2/serve/scheduled-tasks/{task_id}/runs?limit=&offset= — run history list */
  const listRuns = useCallback(
    async (taskId: string, limit = 50, offset = 0): Promise<RunResponse[]> => {
      const res = await axios.get(`${BASE}/${taskId}/runs`, {
        params: { limit, offset },
      });
      return unwrap<RunResponse[]>(res) ?? [];
    },
    [],
  );

  /** GET /api/v2/serve/scheduled-tasks/{task_id}/runs/{run_id} — single run detail */
  const getRun = useCallback(
    async (taskId: string, runId: string): Promise<RunResponse> => {
      const res = await axios.get(`${BASE}/${taskId}/runs/${runId}`);
      return unwrap<RunResponse>(res);
    },
    [],
  );

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
