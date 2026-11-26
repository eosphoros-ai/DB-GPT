import type { GenerationSession } from '@/types/taskflow-generation';
import { GET, POST, PUT } from './index';

const base = '/api/v2/serve/awel/taskflow/generation-sessions';

/** Keep normal API authentication/headers and surface actionable HTTP errors. */
export async function generationApi<T = GenerationSession>(
  path: string,
  data?: unknown,
  method: 'GET' | 'POST' | 'PUT' = 'POST',
): Promise<T> {
  try {
    const response =
      method === 'GET'
        ? await GET<unknown, T>(`${base}${path}`)
        : method === 'PUT'
          ? await PUT<unknown, T>(`${base}${path}`, data)
          : await POST<unknown, T>(`${base}${path}`, data);
    if (!response.data.success) throw new Error(response.data.err_msg || '请求失败');
    return response.data.data;
  } catch (error: any) {
    const body = error.response?.data;
    const detail = body?.detail ?? body?.err_msg;
    throw new Error(typeof detail === 'string' ? detail : detail ? JSON.stringify(detail) : error.message);
  }
}
