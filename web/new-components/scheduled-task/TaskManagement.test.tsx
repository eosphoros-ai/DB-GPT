import type { TaskResponse } from '@/types/scheduled-task';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { App } from 'antd';
import { describe, expect, it, vi } from 'vitest';
import EditScheduledTaskDrawer from './EditScheduledTaskDrawer';
import TaskRunsTable from './TaskRunsTable';
const mocks = vi.hoisted(() => ({ listRuns: vi.fn(), updateTask: vi.fn(), push: vi.fn(), t: (key: string) => key }));
vi.mock('next/router', () => ({ useRouter: () => ({ push: mocks.push }) }));
vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: mocks.t }) }));
vi.mock('@/hooks/use-scheduled-task', () => ({
  useScheduledTask: () => ({ listRuns: mocks.listRuns, updateTask: mocks.updateTask }),
}));
vi.mock('@/app/chat-context', async () => {
  const { createContext } = await import('react');
  return { ChatContext: createContext({ modelList: [] }) };
});
vi.mock('@/components/chat/header/model-selector', () => ({ renderModelIcon: () => null }));

describe('dashboard task management', () => {
  it('opens the dashboard from a partial execution even without a published output URL', async () => {
    mocks.listRuns.mockResolvedValue([
      {
        run_id: 'run-1',
        task_id: 'task-1',
        status: 'partial_success',
        output_resource_id: null,
        result: { dashboard_id: 'board-1' },
        result_summary: '1 of 2 charts refreshed',
      },
    ]);
    render(<TaskRunsTable taskId='task-1' dashboardId='board-1' />);
    await screen.findByText('scheduled.runs.statusPartialSuccess');
    fireEvent.click(screen.getByText('scheduled.runs.view'));
    expect(mocks.push).toHaveBeenCalledWith('/dashboards/board-1/');
  });
  it('refreshes an initially empty history after the first scheduled execution', async () => {
    mocks.listRuns
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([{ run_id: 'run-1', task_id: 'task-1', status: 'success' }]);
    render(<TaskRunsTable taskId='task-1' />);
    await screen.findByText('scheduled.runs.empty');
    fireEvent.click(screen.getByText('scheduled.runs.refresh'));
    await screen.findByText('scheduled.runs.statusSuccess');
  });
  it('edits dashboard metadata without requiring a chat prompt or rewriting the existing cron', async () => {
    const task: TaskResponse = {
      task_id: 'task-1',
      task_type: 'dashboard_refresh',
      task_name: 'Sales',
      enabled: true,
      cron_expression: '* * * * *',
      payload: { dashboard_id: 'board-1', filters: { year: 2026 } },
    };
    const onSaved = vi.fn();
    mocks.updateTask.mockResolvedValue(task);
    render(<EditScheduledTaskDrawer open onClose={vi.fn()} task={task} onSaved={onSaved} />, { wrapper: App });
    await waitFor(() => expect((screen.getByLabelText('Cron 表达式') as HTMLInputElement).value).toBe('* * * * *'));
    expect(screen.queryByText('scheduled.edit.rawQuestionLabel')).toBeNull();
    fireEvent.change(screen.getByRole('textbox', { name: 'scheduled.save.nameLabel' }), {
      target: { value: 'Renamed' },
    });
    fireEvent.click(screen.getByText('scheduled.edit.save'));
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    expect(mocks.updateTask).toHaveBeenCalledWith('task-1', { task_name: 'Renamed', description: null });
  });
});
