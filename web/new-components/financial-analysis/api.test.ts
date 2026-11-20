import { POST } from '@/client/api';
import i18next from 'i18next';
import { expect, it, vi } from 'vitest';
import { createExport } from './api';

vi.mock('@/client/api', () => ({ GET: vi.fn(), POST: vi.fn() }));

it('pins export requests to the revision and the currently selected UI language', async () => {
  const post = vi.mocked(POST);
  post.mockResolvedValue({ data: { success: true, data: { id: 'export' } } } as Awaited<ReturnType<typeof POST>>);
  await i18next.init({ lng: 'en-US' });
  await createExport('scope', 'run', 'saved-revision', 'html');
  expect(post).toHaveBeenLastCalledWith('/api/v1/financial-analysis/runs/run/exports', {
    session_id: 'scope',
    revision: 'saved-revision',
    format: 'html',
    language: 'en',
  });
  await i18next.changeLanguage('zh-CN');
  await createExport('scope', 'run', 'saved-revision', 'html');
  expect(post).toHaveBeenLastCalledWith('/api/v1/financial-analysis/runs/run/exports', {
    session_id: 'scope',
    revision: 'saved-revision',
    format: 'html',
    language: 'zh',
  });
});
