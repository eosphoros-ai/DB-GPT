import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ArtifactCards from './ArtifactCards';
import SuiteArtifactCard from './SuiteArtifactCard';

const { push } = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock('next/router', () => ({ useRouter: () => ({ push }) }));
vi.mock('react-i18next', () => ({
  useTranslation: () => ({ i18n: { language: 'zh' }, t: (key: string) => key }),
}));

const snapshot = {
  artifact_id: 'artifact-1',
  draft_id: 'draft-1',
  revision: 1,
  suite_name: 'office',
  display: '周报专家',
  description: '整理项目材料生成周报',
  version: '1.0.0',
  package_digest: 'digest-1',
  files: { 'README.md': '# 周报', '.qwenwork-plugin/plugin.json': '{}' },
  validation: { status: 'ready', errors: [], warnings: [], dependencies: [], pending_configuration: [] },
};

function mockApi(installed: any = null, validationErrors: string[] = []) {
  const fetcher = vi.fn(async (url: any, init: any) => {
    const path = String(url);
    let data: any = snapshot;
    if (path.endsWith('/installation')) data = installed;
    else if (path.endsWith('/install')) {
      installed = { name: 'office', status: 'enabled' };
      data = installed;
    } else if (path.endsWith('/suite-drafts')) data = { draft_id: 'copy', revision: 0 };
    else if (path.endsWith('/suite-drafts/copy')) data = { draft_id: 'copy', revision: 1 };
    else if (path.endsWith('/validate')) data = { errors: validationErrors };
    else if (path.endsWith('/build')) data = { ...snapshot, artifact_id: 'artifact-2' };
    else if (path.endsWith('/artifact-2')) data = { ...snapshot, artifact_id: 'artifact-2' };
    else if (path.endsWith('/suites/office')) data = { manifest_snapshot: { commands: [{ name: '/周报' }] } };
    return { ok: true, json: async () => ({ success: true, data }) };
  });
  vi.stubGlobal('fetch', fetcher);
  return fetcher;
}

beforeEach(() => vi.clearAllMocks());

describe('Expert suite artifacts', () => {
  it('renders a typed suite card, installs explicitly and opens a fresh business chat', async () => {
    const fetcher = mockApi();
    render(<ArtifactCards artifacts={[{ id: 'a', type: 'expert_suite', name: '周报专家', content: snapshot }]} />);
    await screen.findByText('校验通过 · 未安装');
    expect(fetcher.mock.calls.some(([url]) => String(url).endsWith('/install'))).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: '一键安装' }));
    await screen.findByRole('button', { name: '用于新对话' });
    const installCall = fetcher.mock.calls.find(([url]) => String(url).endsWith('/install'))!;
    expect(JSON.parse(installCall[1].body)).toEqual({ package_digest: 'digest-1' });
    fireEvent.click(screen.getByRole('button', { name: '用于新对话' }));
    await waitFor(() =>
      expect(push).toHaveBeenCalledWith({
        pathname: '/',
        query: { suite: 'office', suite_command: '/周报' },
      }),
    );
  });

  it('restores the real installation status and previews frozen files', async () => {
    mockApi({ name: 'office', status: 'enabled' });
    render(<SuiteArtifactCard content={snapshot} />);
    await screen.findByRole('button', { name: '用于新对话' });
    expect(screen.queryByRole('button', { name: '一键安装' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '预览与编辑' }));
    await screen.findByDisplayValue('# 周报');
    expect(screen.getByText('尚未真实试跑')).toBeTruthy();
  });

  it('validates edits and builds a separate artifact without changing the old package', async () => {
    const fetcher = mockApi();
    render(<SuiteArtifactCard content={snapshot} />);
    fireEvent.click(screen.getByRole('button', { name: '预览与编辑' }));
    await screen.findByDisplayValue('# 周报');
    fireEvent.change(screen.getByRole('textbox', { name: '文件正文' }), { target: { value: '# Updated' } });
    fireEvent.click(screen.getByRole('button', { name: '保存、校验并生成新产物' }));
    await waitFor(() => expect(fetcher.mock.calls.some(([url]) => String(url).endsWith('/build'))).toBe(true));
    const buildCall = fetcher.mock.calls.find(([url]) => String(url).endsWith('/build'))!;
    expect(JSON.parse(buildCall[1].body).source_artifact_id).toBe('artifact-1');
    const editCall = fetcher.mock.calls.find(
      ([url, init]) => String(url).endsWith('/copy') && init.method === 'PATCH',
    )!;
    expect(JSON.parse(editCall[1].body).files['README.md']).toBe('# Updated');
  });

  it('keeps invalid edits out of build and install', async () => {
    const fetcher = mockApi(null, ['skill body incomplete']);
    render(<SuiteArtifactCard content={snapshot} />);
    fireEvent.click(screen.getByRole('button', { name: '预览与编辑' }));
    await screen.findByDisplayValue('# 周报');
    fireEvent.change(screen.getByRole('textbox', { name: '文件正文' }), { target: { value: 'bad' } });
    fireEvent.click(screen.getByRole('button', { name: '保存、校验并生成新产物' }));
    await screen.findByText('skill body incomplete');
    expect(fetcher.mock.calls.some(([url]) => String(url).endsWith('/build'))).toBe(false);
    expect(fetcher.mock.calls.some(([url]) => String(url).endsWith('/install'))).toBe(false);
  });
});
