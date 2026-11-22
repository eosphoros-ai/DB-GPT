import { interfaceThemeTokens, interfaceThemeVariables } from '@/lib/interface-tokens';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { App } from 'antd';
import { describe, expect, it, vi } from 'vitest';
import DashboardPublishDialog from './DashboardPublishDialog';

vi.mock('@/client/api/dashboard', () => ({
  getDashboardLiveShare: vi.fn().mockResolvedValue({ data: { success: true, data: { active: false } } }),
  revokeDashboardLiveShare: vi.fn(),
}));

describe('DashboardPublishDialog mode selection', () => {
  it('selects a whole card without publishing, then submits the chosen mode', async () => {
    const onPublish = vi.fn().mockResolvedValue(undefined);
    render(
      <App>
        <DashboardPublishDialog
          dashboardId='test'
          themeStyle={interfaceThemeVariables(interfaceThemeTokens('clarity', 'light'))}
          busy={false}
          onClose={vi.fn()}
          onPublish={onPublish}
        />
      </App>,
    );
    const live = screen.getByRole('radio', { name: '跟随数据源更新' }) as HTMLInputElement;
    const snapshot = screen.getByRole('radio', { name: '固定发布时的数据' }) as HTMLInputElement;
    expect(screen.getByRole('dialog').style.getPropertyValue('--app-accent')).toBe('#5865F2');
    expect(snapshot.checked).toBe(true);
    expect(live.checked).toBe(false);
    fireEvent.click(screen.getByText('适合日常看板。数据变化自动呈现，无需重复发布。'));
    expect(live.checked).toBe(true);
    expect(snapshot.checked).toBe(false);
    expect(onPublish).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '发布并跟随更新' }));
    await waitFor(() => expect(onPublish).toHaveBeenCalledExactlyOnceWith('live'));
  });

  it('keeps the selected mode while publication is in progress', async () => {
    const onPublish = vi.fn();
    render(
      <App>
        <DashboardPublishDialog dashboardId='test' busy onClose={vi.fn()} onPublish={onPublish} />
      </App>,
    );
    const live = screen.getByRole('radio', { name: '跟随数据源更新' }) as HTMLInputElement;
    const snapshot = screen.getByRole('radio', { name: '固定发布时的数据' }) as HTMLInputElement;
    await waitFor(() => expect(live.disabled).toBe(true));
    expect(snapshot.disabled).toBe(true);
    fireEvent.click(screen.getByText('适合日常看板。数据变化自动呈现，无需重复发布。'));
    expect(snapshot.checked).toBe(true);
    expect(onPublish).not.toHaveBeenCalled();
  });
});
