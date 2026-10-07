import { fireEvent, render, screen } from '@testing-library/react';
import { App } from 'antd';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  getDashboardPermissions: vi.fn(),
  listDashboardAudit: vi.fn(),
  listDashboardMembers: vi.fn(),
  removeDashboardMember: vi.fn(),
  upsertDashboardMember: vi.fn(),
}));

vi.mock('@/client/api', () => api);

import DashboardAccessPanel from './DashboardAccessPanel';

const response = (data: unknown) => Promise.resolve({ data: { data } });

describe('DashboardAccessPanel', () => {
  beforeEach(() => {
    api.getDashboardPermissions.mockReturnValue(
      response({
        dashboard_id: 'dashboard-1',
        actor_id: '001',
        role: 'owner',
        actions: ['view', 'edit', 'query', 'publish', 'manage_access', 'manage_schedule'],
      }),
    );
    api.listDashboardMembers.mockReturnValue(
      response([
        {
          dashboard_id: 'dashboard-1',
          principal_id: '001',
          role: 'owner',
          created_by: '001',
          created_at: '2026-08-13T08:00:00Z',
          updated_at: '2026-08-13T08:00:00Z',
        },
        {
          dashboard_id: 'dashboard-1',
          principal_id: 'analyst-01',
          role: 'viewer',
          created_by: '001',
          created_at: '2026-08-13T08:10:00Z',
          updated_at: '2026-08-13T08:10:00Z',
        },
      ]),
    );
    api.listDashboardAudit.mockReturnValue(
      response([
        {
          id: 1,
          dashboard_id: 'dashboard-1',
          actor_id: '001',
          action: 'dashboard.published',
          target_type: 'dashboard',
          details: {},
          created_at: '2026-08-13T09:00:00Z',
        },
      ]),
    );
    api.upsertDashboardMember.mockReturnValue(response({ principal_id: 'analyst-02', role: 'editor' }));
    api.removeDashboardMember.mockReturnValue(response(true));
  });

  it('shows access management controls, members and audit history', async () => {
    render(
      <App>
        <DashboardAccessPanel dashboardId='dashboard-1' open onClose={vi.fn()} />
      </App>,
    );

    expect(await screen.findByText('analyst-01')).toBeTruthy();
    expect(screen.getByText('当前账号')).toBeTruthy();
    expect(screen.getByText('发布与分享')).toBeTruthy();

    expect(screen.getByLabelText('成员账号')).toBeTruthy();
    expect(screen.getByRole('button', { name: /保存成员/ })).toBeTruthy();

    fireEvent.click(screen.getByText('操作记录 (1)'));
    expect(await screen.findByText('发布看板')).toBeTruthy();
    expect(api.listDashboardMembers).toHaveBeenCalledWith('dashboard-1');
    expect(api.listDashboardAudit).toHaveBeenCalledWith('dashboard-1');
  });
});
