import { renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useScheduledTask } from './use-scheduled-task';
const api = vi.hoisted(() => ({ post: vi.fn(), get: vi.fn(), put: vi.fn(), delete: vi.fn() }));
vi.mock('@/utils/ctx-axios', () => ({ default: api }));
vi.mock('@/utils', () => ({ getUserId: () => 'signed-in-user' }));

describe('unified scheduled task API', () => {
  it('creates dashboard tasks through the dashboard permission and audit endpoint', async () => {
    api.post.mockResolvedValue({ success: true, data: { task_id: 'task-1' } });
    const { result } = renderHook(useScheduledTask);
    await result.current.createTask({
      task_type: 'dashboard_refresh',
      task_name: 'Sales',
      cron_expression: '* * * * *',
      payload: { dashboard_id: 'board-1', version: 1, filters: { region: 'east' }, publish_after_refresh: false },
    });
    expect(api.post).toHaveBeenCalledWith(
      '/api/v1/dashboards/board-1/schedules',
      {
        task_name: 'Sales',
        cron_expression: '* * * * *',
        filters: { region: 'east' },
        publish_after_refresh: false,
      },
      { headers: { 'user-id': 'signed-in-user' } },
    );
  });
  it('keeps the official chat creation endpoint', async () => {
    api.post.mockResolvedValue({ success: true, data: { task_id: 'chat-1' } });
    const { result } = renderHook(useScheduledTask);
    const body = { task_name: 'Chat', cron_expression: '0 9 * * *', payload: { user_input: 'Daily summary' } };
    await result.current.createTask(body);
    expect(api.post).toHaveBeenCalledWith('/api/v2/serve/scheduled-tasks/', body, {
      headers: { 'user-id': 'signed-in-user' },
    });
  });
  it('does not report a failed 200-envelope operation as success', async () => {
    api.post.mockResolvedValue({ success: false, err_msg: 'Scheduler unavailable', data: null });
    api.delete.mockResolvedValue({ success: false, err_msg: 'Access denied', data: null });
    const { result } = renderHook(useScheduledTask);
    await expect(
      result.current.createTask({ task_name: 'Chat', cron_expression: '0 9 * * *', payload: { user_input: 'Hi' } }),
    ).rejects.toThrow('Scheduler unavailable');
    await expect(result.current.deleteTask('task-1')).rejects.toThrow('Access denied');
  });
  it('uses the current account for listing, editing and reading run history', async () => {
    api.get.mockResolvedValue({ success: true, data: [] });
    api.put.mockResolvedValue({ success: true, data: {} });
    const { result } = renderHook(useScheduledTask);
    await result.current.listTasks();
    await result.current.updateTask('task-1', { task_name: 'Rename' });
    await result.current.listRuns('task-1');
    expect(api.get).toHaveBeenCalledWith('/api/v2/serve/scheduled-tasks/', {
      params: { enabled_only: false },
      headers: { 'user-id': 'signed-in-user' },
    });
    expect(api.put).toHaveBeenCalledWith(
      '/api/v2/serve/scheduled-tasks/task-1',
      { task_name: 'Rename' },
      { headers: { 'user-id': 'signed-in-user' } },
    );
    expect(api.get).toHaveBeenCalledWith('/api/v2/serve/scheduled-tasks/task-1/runs', {
      params: { limit: 50, offset: 0 },
      headers: { 'user-id': 'signed-in-user' },
    });
  });
});
