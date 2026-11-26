import { ChatZh } from '@/locales/zh/chat';
import { userMessageCopyText, type UserMessageCopyContext } from '@/utils/user-message-copy';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ManusLeftPanel, { type ManusLeftPanelProps } from './ManusLeftPanel';

const clipboard = vi.hoisted(() => ({
  writeText: vi.fn(),
  fallback: vi.fn(),
  success: vi.fn(),
  error: vi.fn(),
}));

vi.mock('copy-to-clipboard', () => ({ default: clipboard.fallback }));
vi.mock('antd', () => ({
  Tooltip: ({ children }: { children: React.ReactNode }) => children,
  Button: 'button',
  message: { success: clipboard.success, error: clipboard.error },
}));
const translate = (key: string, values?: { name?: string }) =>
  ((ChatZh as Record<string, string>)[key] || key).replace('{{name}}', values?.name || '');
vi.mock('react-i18next', async importOriginal => ({
  ...(await importOriginal<typeof import('react-i18next')>()),
  useTranslation: () => ({ t: translate }),
}));
vi.mock('../../financial-analysis/i18n', () => ({
  useFinancialLocale: vi.fn(),
  financialText: (key: string) => key,
}));
vi.mock('./FlowRunView', () => ({ default: () => null }));
vi.mock('./FinancialProgressPanel', () => ({
  default: () => null,
  FinancialProgressUpdates: () => null,
  financialTasksForStep: () => [],
}));
vi.mock('./ObservationFormatter', () => ({ default: () => null }));
vi.mock('./SemanticProvenance', () => ({ default: () => null }));
vi.mock('./TaskPlanCard', () => ({ default: () => null }));
vi.mock('@/modules/session-files/AttachmentPreview', () => ({ FileKindIcon: () => null }));
vi.mock('@/modules/session-files', async () => ({
  AttachmentMessageCards: (await import('@/modules/session-files/AttachmentMessageCards')).default,
}));

const context: Pick<ManusLeftPanelProps, keyof UserMessageCopyContext> = {
  userQuery: '比较经营表现。\n保留换行。',
  attachedSuite: { name: 'financial', display: '财报分析', command: '/财报对比' },
  attachedKnowledge: { id: 1, name: '财务知识库', desc: '会计口径', vector_type: 'Chroma' },
  attachedSkill: { id: 'skill-1', name: 'compare-reports' },
  attachedDb: { db_name: '业务数据库', db_type: 'sqlite' },
  attachedConnectors: [{ id: 'connector-1', display_name: '报表服务', connector_type: 'mcp' }],
  attachedFiles: [
    {
      file_id: 'file-2',
      name: '第二份年报.pdf',
      ordinal: 2,
      size: 2048,
      media_type: 'application/pdf',
      kind: 'document',
      status: 'preview_failed',
    },
    {
      file_id: 'file-1',
      name: '2020-04-11__常柴股份有限公司__200570__苏常柴__2019年年度报告完整文件名.pdf',
      ordinal: 1,
      size: 1024,
      media_type: 'application/pdf',
      kind: 'document',
      status: 'ready',
    },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  clipboard.writeText.mockResolvedValue(undefined);
  clipboard.fallback.mockReturnValue(true);
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: clipboard.writeText } });
});
afterEach(cleanup);

describe('user message copy', () => {
  it('preserves complete names, command, card order and newlines without mutating file snapshots', () => {
    const text = userMessageCopyText(context, translate);
    expect(text).toBe(
      '[专家套件] 财报分析 · /财报对比\n\n' +
        '[知识库] 财务知识库 · 会计口径\n\n' +
        '[技能] compare-reports\n\n' +
        '[数据库] 业务数据库 · sqlite\n\n' +
        '[连接器] 报表服务 · mcp\n\n' +
        `[文件] ${context.attachedFiles![1].name} · application/pdf · 1.00 KB\n\n` +
        '[文件] 第二份年报.pdf · application/pdf · 2.00 KB\n\n' +
        context.userQuery,
    );
    expect(context.attachedFiles?.[0].file_id).toBe('file-2');
  });

  it('copies a plain user message without adding headings', async () => {
    render(<ManusLeftPanel sections={[]} userQuery={'你好\nDB-GPT'} />);
    fireEvent.click(screen.getByRole('button', { name: '复制消息及引用' }));
    await waitFor(() => expect(clipboard.writeText).toHaveBeenCalledWith('你好\nDB-GPT'));
  });

  it('copies all references and offers an independent action for every card', async () => {
    render(<ManusLeftPanel sections={[]} {...context} />);
    fireEvent.click(screen.getByRole('button', { name: '复制消息及引用' }));
    await waitFor(() => expect(clipboard.writeText).toHaveBeenCalledWith(userMessageCopyText(context, translate)));
    const references = [
      ['财报分析', { attachedSuite: context.attachedSuite }],
      ['财务知识库', { attachedKnowledge: context.attachedKnowledge }],
      ['compare-reports', { attachedSkill: context.attachedSkill }],
      ['业务数据库', { attachedDb: context.attachedDb }],
      ['报表服务', { attachedConnectors: context.attachedConnectors }],
      ...context.attachedFiles!.map(file => [file.name, { attachedFiles: [file] }]),
    ] as [string, UserMessageCopyContext][];
    for (const [name, reference] of references) {
      fireEvent.click(screen.getByRole('button', { name: `复制${name}` }));
      await waitFor(() =>
        expect(clipboard.writeText).toHaveBeenLastCalledWith(userMessageCopyText(reference, translate)),
      );
    }
  });

  it('supports attachment-only messages and hides transport markers for dashboard controls', async () => {
    const { rerender } = render(<ManusLeftPanel sections={[]} attachedDb={context.attachedDb} />);
    fireEvent.click(screen.getByRole('button', { name: '复制消息及引用' }));
    await waitFor(() => expect(clipboard.writeText).toHaveBeenLastCalledWith('[数据库] 业务数据库 · sqlite'));
    rerender(<ManusLeftPanel sections={[]} userQuery='[[confirm-dashboard-plan:123]] internal control text' />);
    fireEvent.click(screen.getByRole('button', { name: '复制消息及引用' }));
    await waitFor(() => expect(clipboard.writeText).toHaveBeenLastCalledWith(ChatZh.dashboard_chat_confirm));
  });

  it('does not expand a collapsed turn when copying', async () => {
    const expand = vi.fn();
    render(<ManusLeftPanel sections={[]} {...context} isCollapsed onExpand={expand} />);
    fireEvent.click(screen.getByRole('button', { name: '复制消息及引用' }));
    await waitFor(() => expect(clipboard.writeText).toHaveBeenCalled());
    expect(expand).not.toHaveBeenCalled();
  });

  it('falls back when the clipboard API is unavailable', async () => {
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: undefined });
    render(<ManusLeftPanel sections={[]} userQuery='fallback' />);
    fireEvent.click(screen.getByRole('button', { name: '复制消息及引用' }));
    await waitFor(() => expect(clipboard.fallback).toHaveBeenCalledWith('fallback'));
    expect(clipboard.success).toHaveBeenCalled();
  });

  it('reports failure without showing success when both clipboard methods fail', async () => {
    clipboard.writeText.mockRejectedValue(new Error('Denied'));
    clipboard.fallback.mockReturnValue(false);
    render(<ManusLeftPanel sections={[]} userQuery='failed' />);
    fireEvent.click(screen.getByRole('button', { name: '复制消息及引用' }));
    await waitFor(() => expect(clipboard.error).toHaveBeenCalled());
    expect(clipboard.success).not.toHaveBeenCalled();
    expect(screen.queryByRole('img', { name: 'check' })).toBeNull();
  });
});
