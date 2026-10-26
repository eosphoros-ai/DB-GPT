import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key: string) => key }) }));

import ApprovalModeBadge from './ApprovalModeBadge';

const mockFetch = (initial = 'default') => {
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  const fn = vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, init });
    if (init?.method === 'POST') {
      const mode = JSON.parse(String(init.body)).mode;
      return { ok: true, json: async () => ({ data: { mode } }) };
    }
    return { ok: true, json: async () => ({ data: { mode: initial } }) };
  });
  vi.stubGlobal('fetch', fn);
  return { fn, calls };
};

const postBody = (calls: Array<{ url: string; init?: RequestInit }>) => {
  const post = calls.find(c => c.init?.method === 'POST');
  expect(post).toBeTruthy();
  return JSON.parse(String(post!.init!.body));
};

describe('approval mode badge', () => {
  it('lists the three modes and posts the selection', async () => {
    const { calls } = mockFetch();
    render(<ApprovalModeBadge convId='c1' ensureConvId={() => 'c1'} />);
    await waitFor(() => expect(screen.getByTestId('approval-mode-badge')).toBeTruthy());
    fireEvent.click(screen.getByTestId('approval-mode-badge'));
    for (const m of ['default', 'strict', 'open']) {
      expect(screen.getByTestId(`approval-mode-${m}`)).toBeTruthy();
    }
    fireEvent.click(screen.getByTestId('approval-mode-open'));
    expect(postBody(calls)).toEqual({ con_uid: 'c1', mode: 'open' });
    await waitFor(() =>
      expect(screen.getByTestId('approval-mode-badge').textContent).toContain(
        'approval_mode_open',
      ),
    );
    vi.unstubAllGlobals();
  });

  it('rehydrates the stored mode for an existing conversation', async () => {
    mockFetch('strict');
    render(<ApprovalModeBadge convId='c9' ensureConvId={() => 'c9'} />);
    await waitFor(() =>
      expect(screen.getByTestId('approval-mode-badge').textContent).toContain(
        'approval_mode_strict',
      ),
    );
    vi.unstubAllGlobals();
  });

  it('creates a conversation id when selecting before the first send', () => {
    const { calls } = mockFetch();
    const ensure = vi.fn(() => 'fresh-conv');
    render(<ApprovalModeBadge convId={null} ensureConvId={ensure} />);
    fireEvent.click(screen.getByTestId('approval-mode-badge'));
    fireEvent.click(screen.getByTestId('approval-mode-strict'));
    expect(ensure).toHaveBeenCalled();
    expect(postBody(calls)).toEqual({ con_uid: 'fresh-conv', mode: 'strict' });
    vi.unstubAllGlobals();
  });
});
