import { fireEvent, render, screen } from '@testing-library/react';
import { App } from 'antd';
import { describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  getDashboardEditVersion: vi.fn(),
  listDashboardEditVersions: vi.fn(),
  listDashboardPublications: vi.fn(),
  listDashboardRevisions: vi.fn(),
  restoreDashboardEditVersion: vi.fn(),
  restoreDashboardRevision: vi.fn(),
  revokeDashboardPublication: vi.fn(),
  rotateDashboardPublication: vi.fn(),
}));

vi.mock('@/client/api', () => api);
vi.mock('@/client/api/dashboard', () => ({
  getDashboardLiveShare: vi.fn().mockResolvedValue({ data: { success: true, data: { active: false } } }),
  createDashboardLiveShare: vi.fn(),
  revokeDashboardLiveShare: vi.fn(),
}));

import DashboardLifecyclePanel from './DashboardLifecyclePanel';

const response = (data: unknown) => Promise.resolve({ data: { data } });

describe('DashboardLifecyclePanel', () => {
  it('loads immutable revisions and active share lifecycle records', async () => {
    api.listDashboardEditVersions.mockReturnValue(
      response([
        {
          dashboard_id: 'dashboard-1',
          revision: 4,
          source: 'ai_annotation',
          actor_id: 'alice',
          created_at: '2026-08-12T11:00:00Z',
        },
      ]),
    );
    api.getDashboardEditVersion.mockReturnValue(
      response({
        dashboard_id: 'dashboard-1',
        revision: 4,
        source: 'ai_annotation',
        actor_id: 'alice',
        created_at: '2026-08-12T11:00:00Z',
        schema: {
          dashboard: { title: '经营健康看板' },
          filters: [{ id: 'date' }],
          widgets: [{ id: 'revenue', title: '营业收入', type: 'kpi' }],
          layouts: { desktop: [{ widget_id: 'revenue', x: 0, y: 0, w: 4, h: 3 }] },
        },
      }),
    );
    api.listDashboardRevisions.mockReturnValue(
      response([
        {
          dashboard_id: 'dashboard-1',
          published_revision: 3,
          published_at: '2026-08-12T10:00:00Z',
          validation: { valid: true, issues: [], widget_status: {} },
        },
      ]),
    );
    api.listDashboardPublications.mockReturnValue(
      response([
        {
          dashboard_id: 'dashboard-1',
          published_revision: 3,
          active: true,
          created_at: '2026-08-12T10:00:00Z',
          expires_at: '2026-08-19T10:00:00Z',
        },
      ]),
    );

    render(
      <App>
        <DashboardLifecyclePanel
          dashboardId='dashboard-1'
          currentRevision={4}
          open
          onClose={vi.fn()}
          onOpenPublish={vi.fn()}
          onRecordChange={vi.fn()}
        />
      </App>,
    );

    expect(await screen.findAllByText('发布版本 3')).toHaveLength(2);
    expect(screen.getByText('编辑修订 4')).toBeTruthy();
    expect(screen.getByText('AI 提案应用')).toBeTruthy();
    expect(screen.getByText('有效')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /查看/ }));
    const preview = await screen.findByTestId('dashboard-version-preview');
    expect(preview.textContent).toContain('经营健康看板');
    expect(preview.textContent).toContain('营业收入');
    expect(api.listDashboardRevisions).toHaveBeenCalledWith('dashboard-1');
    expect(api.listDashboardEditVersions).toHaveBeenCalledWith('dashboard-1');
    expect(api.getDashboardEditVersion).toHaveBeenCalledWith('dashboard-1', 4);
    expect(api.listDashboardPublications).toHaveBeenCalledWith('dashboard-1');
  });
});
