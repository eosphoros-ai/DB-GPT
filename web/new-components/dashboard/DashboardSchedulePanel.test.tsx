import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { App } from 'antd';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  createDashboardSchedule: vi.fn(),
  deleteDashboardSchedule: vi.fn(),
  getDashboardSchedulerStatus: vi.fn(),
  listDashboardScheduleRuns: vi.fn(),
  listDashboardSchedules: vi.fn(),
  runDashboardSchedule: vi.fn(),
  toggleDashboardSchedule: vi.fn(),
  updateDashboardSchedule: vi.fn(),
}));

vi.mock('@/client/api', () => api);
vi.mock('./DashboardRefreshFrequencyInput', () => ({
  default: ({ value }: { value: string }) => <div>frequency:{value}</div>,
  describeDashboardScheduleCron: (value: string) => `频率 ${value}`,
}));

import DashboardSchedulePanel from './DashboardSchedulePanel';

const response = (data: unknown) => Promise.resolve({ data: { data, success: true } });

const schedule = {
  task_id: 'schedule-1',
  task_name: '每天刷新',
  description: '',
  task_type: 'dashboard_refresh' as const,
  cron_expression: '0 6 * * *',
  enabled: true,
  payload: {
    version: 1,
    dashboard_id: 'dashboard-1',
    filters: { region: 'east' },
    publish_after_refresh: false,
    timeout_seconds: 180,
    max_attempts: 2,
  },
};

const renderPanel = (children?: ReactNode) =>
  render(
    <App>
      <DashboardSchedulePanel
        dashboardId='dashboard-1'
        filters={{ region: 'east' }}
        filterDefinitions={[]}
        open
        onClose={vi.fn()}
      />
      {children}
    </App>,
  );

describe('DashboardSchedulePanel', () => {
  it('loads scoped schedules and exposes partial-success history', async () => {
    api.getDashboardSchedulerStatus.mockReturnValue(response({ running: true, message: '后台调度正在运行' }));
    api.listDashboardSchedules.mockReturnValue(response([schedule]));
    api.runDashboardSchedule.mockReturnValue(
      response({
        run_id: 'run-1',
        task_id: 'schedule-1',
        status: 'partial_success',
        attempt_count: 1,
        result_summary: '1 of 2 widgets failed',
      }),
    );
    api.listDashboardScheduleRuns.mockReturnValue(
      response([
        {
          run_id: 'run-1',
          task_id: 'schedule-1',
          status: 'partial_success',
          attempt_count: 1,
          result_summary: '1 of 2 widgets failed',
        },
      ]),
    );

    renderPanel();

    expect(await screen.findByText('每天刷新')).toBeTruthy();
    expect(api.listDashboardSchedules).toHaveBeenCalledWith('dashboard-1');

    fireEvent.click(screen.getByRole('button', { name: /立即运行/ }));
    await waitFor(() => expect(api.runDashboardSchedule).toHaveBeenCalledWith('dashboard-1', 'schedule-1'));

    fireEvent.click(screen.getByRole('button', { name: /运行记录/ }));
    expect((await screen.findAllByText('部分成功')).length).toBeGreaterThan(0);
    expect(screen.getByText('1 of 2 widgets failed')).toBeTruthy();
    expect(api.listDashboardScheduleRuns).toHaveBeenCalledWith('dashboard-1', 'schedule-1');
  });
  it('shows a saved enabled plan as waiting when the scheduler is stopped', async () => {
    api.getDashboardSchedulerStatus.mockReturnValue(response({ running: false, message: '后台调度尚未运行' }));
    api.listDashboardSchedules.mockReturnValue(response([schedule]));
    api.listDashboardScheduleRuns.mockReturnValue(response([]));
    renderPanel();
    expect(await screen.findByText('等待后台启动')).toBeTruthy();
    expect(screen.getByText('后台未运行')).toBeTruthy();
    expect(screen.queryByText('运行中')).toBeNull();
  });
});
