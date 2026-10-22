import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import ApprovalSettingsPage from './approval-settings';

vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key: string) => key }) }));

const policyView = {
  mode: 'tiered',
  ttl_seconds: 300,
  intent_analysis: true,
  fail_safe: 'confirm',
  tool_overrides: [],
  rules: [],
  version: 1,
};

function mockFetch() {
  const calls: { url: string; body?: any }[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: any) => {
      const body = init?.body ? JSON.parse(init.body) : undefined;
      calls.push({ url, body });
      if (String(url).includes('/approval/policy/save')) {
        return { json: async () => ({ success: true, data: { version: 2, diff: {} } }) };
      }
      if (String(url).includes('/approval/policy')) {
        return { json: async () => ({ success: true, data: policyView }) };
      }
      if (String(url).includes('/approval/whitelist')) {
        return { json: async () => ({ success: true, data: [] }) };
      }
      return { json: async () => ({ success: true, data: {} }) };
    }),
  );
  return calls;
}

describe('approval setting page', () => {
  it('disables Add rule until a pattern is entered, then drafts and saves it', async () => {
    const calls = mockFetch();
    render(<ApprovalSettingsPage />);
    await waitFor(() => expect(screen.getByText('setting_mode')).toBeTruthy());

    const addBtn = screen.getByRole('button', { name: 'setting_add_rule' });
    expect((addBtn as HTMLButtonElement).disabled).toBe(true);
    // hint explains why
    expect(screen.getAllByText('setting_pattern_required').length).toBeGreaterThan(0);

    const pattern = screen.getByPlaceholderText('setting_pattern_ph');
    fireEvent.change(pattern, { target: { value: 'rm\\s+-rf\\s+/tmp/x' } });
    expect((addBtn as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(addBtn);

    // draft row + dirty save bar appear
    await waitFor(() => expect(screen.getByText('rm\\s+-rf\\s+/tmp/x')).toBeTruthy());
    expect(screen.getByText('setting_row_new')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'setting_save' })).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'setting_save' }));
    await waitFor(() => {
      const save = calls.find(c => String(c.url).includes('/approval/policy/save'));
      expect(save).toBeTruthy();
      expect(save!.body.add_rules).toEqual([
        { tool: 'bash', arg_pattern: 'rm\\s+-rf\\s+/tmp/x', tier: 'confirm' },
      ]);
    });
  });

  it('supports Enter in the pattern input', async () => {
    mockFetch();
    render(<ApprovalSettingsPage />);
    await waitFor(() => expect(screen.getByText('setting_mode')).toBeTruthy());
    const pattern = screen.getByPlaceholderText('setting_pattern_ph');
    fireEvent.change(pattern, { target: { value: 'sudo\\s+' } });
    fireEvent.keyDown(pattern, { key: 'Enter' });
    await waitFor(() => expect(screen.getByText('sudo\\s+')).toBeTruthy());
  });
});
