import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const state = vi.hoisted(() => ({ chat: vi.fn(), push: vi.fn(), getDbList: vi.fn() }));
vi.mock('@/app/chat-context', async () => {
  const { createContext } = await import('react');
  return { ChatContext: createContext({ model: 'selected-model', modelList: ['selected-model'] }) };
});
vi.mock('@/client/api', () => ({ getDbList: state.getDbList }));
vi.mock('@/hooks/use-chat', () => ({ default: () => ({ chat: state.chat, pendingQuestion: null }) }));
vi.mock('@/utils', () => ({ getUserId: () => 'fixture-user' }));
vi.mock('next/router', () => ({ useRouter: () => ({ push: state.push }) }));
vi.mock('next/head', () => ({ default: ({ children }: { children: ReactNode }) => children }));
vi.mock('next/link', () => ({
  default: ({ children, href }: { children: ReactNode; href: string }) => <a href={href}>{children}</a>,
}));
// These tests exercise request and confirmation state. Ant Design's dropdown
// layout needs a browser CSS engine and is covered by production browser checks.
vi.mock('antd', async importOriginal => {
  const actual = await importOriginal<typeof import('antd')>();
  return {
    ...actual,
    Select: ({
      options,
      value,
      onChange,
      ...props
    }: {
      options: { value: string; label: string }[];
      value?: string;
      onChange: (value: string) => void;
      disabled?: boolean;
      'aria-label'?: string;
    }) => (
      <select {...props} value={value || ''} onChange={event => onChange(event.target.value)}>
        <option value=''>Select</option>
        {options.map(option => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    ),
  };
});

import DashboardCreatePage from '@/pages/dashboards/new';

async function chooseSource() {
  await screen.findByRole('option', { name: 'sales-db' });
  fireEvent.change(screen.getByRole('combobox', { name: '数据源' }), { target: { value: 'sales-db' } });
}

const plan = {
  type: 'dashboard.plan.awaiting_confirmation',
  dashboard_id: 'draft-1',
  title: 'Sales plan',
  confirmation_prompt: '[[confirm-dashboard:draft-1]]',
  revision_prompt: 'Please revise',
  plan: { business_theme: 'Sales', widgets: [{ id: 'total', type: 'kpi', title: 'Total' }] },
};

beforeEach(() => {
  vi.resetAllMocks();
  vi.unstubAllGlobals();
  state.getDbList.mockResolvedValue({
    data: { success: true, data: [{ id: 1, db_name: 'sales-db', type: 'sqlite', params: { name: 'sales-db' } }] },
  });
});

describe('scoped Dashboard creation entry', () => {
  it('plans before confirmation and reuses the conversation and selected source', async () => {
    state.chat.mockImplementationOnce(async request => request.onDashboardEvent(plan));
    state.chat.mockImplementationOnce(async request =>
      request.onDashboardEvent({ ...plan, type: 'dashboard.updated' }),
    );
    render(<DashboardCreatePage />);
    await chooseSource();
    fireEvent.change(screen.getByRole('textbox', { name: '分析需求' }), { target: { value: 'Show monthly sales' } });
    fireEvent.click(screen.getByRole('button', { name: '发送需求' }));
    const confirm = await screen.findByRole('button', { name: '确认并生成 SQL' });
    await waitFor(() => expect((confirm as HTMLButtonElement).disabled).toBe(false));
    expect(state.chat).toHaveBeenCalledTimes(1);
    const first = state.chat.mock.calls[0][0];
    expect(first.data.ext_info).toEqual({
      creation_mode: 'dashboard',
      database_name: 'sales-db',
      database_type: 'sqlite',
    });
    expect(first.data.model_name).toBe('selected-model');
    fireEvent.click(confirm);
    await waitFor(() => expect(state.chat).toHaveBeenCalledTimes(2));
    expect(state.chat.mock.calls[1][0].chatId).toBe(first.chatId);
    expect(state.chat.mock.calls[1][0].data.user_input).toBe(plan.confirmation_prompt);
    fireEvent.click(await screen.findByRole('button', { name: '查看看板' }));
    expect(state.push).toHaveBeenCalledWith('/dashboards/draft-1');
  });

  it('uploads a grouped dataset once and retains it for explicit confirmation', async () => {
    const upload = vi
      .fn()
      .mockResolvedValue({ ok: true, json: async () => ({ success: true, data: { dataset_id: 'dataset-1' } }) });
    vi.stubGlobal('fetch', upload);
    state.chat.mockImplementation(async request => request.onDashboardEvent(plan));
    render(<DashboardCreatePage />);
    fireEvent.change(screen.getByLabelText('上传数据文件'), {
      target: { files: [new File(['amount\n10'], 'sales.csv', { type: 'text/csv' })] },
    });
    fireEvent.change(screen.getByRole('textbox', { name: '分析需求' }), {
      target: { value: 'Analyze uploaded sales' },
    });
    fireEvent.click(screen.getByRole('button', { name: '发送需求' }));
    const confirm = await screen.findByRole('button', { name: '确认并生成 SQL' });
    await waitFor(() => expect((confirm as HTMLButtonElement).disabled).toBe(false));
    expect(state.chat.mock.calls[0][0].data.ext_info).toEqual({ creation_mode: 'dashboard', dataset_id: 'dataset-1' });
    const body = upload.mock.calls[0][1].body as FormData;
    expect(body.get('conv_uid')).toBe(state.chat.mock.calls[0][0].chatId);
    expect(body.getAll('files')).toHaveLength(1);
    fireEvent.click(confirm);
    await waitFor(() => expect(state.chat).toHaveBeenCalledTimes(2));
    expect(upload).toHaveBeenCalledTimes(1);
  });

  it('prevents duplicate starts and stops the active transport without losing the request', async () => {
    let complete!: () => void;
    state.chat.mockImplementation(
      () =>
        new Promise<void>(resolve => {
          complete = resolve;
        }),
    );
    render(<DashboardCreatePage />);
    await chooseSource();
    fireEvent.change(screen.getByRole('textbox', { name: '分析需求' }), { target: { value: 'Keep this request' } });
    const send = screen.getByRole('button', { name: '发送需求' });
    fireEvent.click(send);
    fireEvent.click(send);
    expect(state.chat).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole('button', { name: '停止生成' }));
    expect(state.chat.mock.calls[0][0].ctrl.signal.aborted).toBe(true);
    expect((screen.getByRole('textbox', { name: '分析需求' }) as HTMLTextAreaElement).value).toBe('Keep this request');
    await act(async () => complete());
    expect(screen.getByRole('alert').textContent).toContain('已停止生成');
  });

  it('releases a terminal failure without waiting for stream closure and preserves the next request', async () => {
    let resolveOld!: () => void;
    state.chat.mockImplementationOnce(
      () =>
        new Promise<void>(resolve => {
          resolveOld = resolve;
        }),
    );
    state.chat.mockImplementationOnce(() => new Promise<void>(() => {}));
    render(<DashboardCreatePage />);
    await chooseSource();
    fireEvent.change(screen.getByRole('textbox', { name: '分析需求' }), { target: { value: 'Retry this plan' } });
    const send = screen.getByRole('button', { name: '发送需求' }) as HTMLButtonElement;
    fireEvent.click(send);
    const first = state.chat.mock.calls[0][0];
    act(() => {
      first.onDashboardEvent({ ...plan, type: 'dashboard.generation.failed', summary: 'SQL validation failed' });
      first.onDone();
    });
    expect(first.ctrl.signal.aborted).toBe(true);
    expect(send.disabled).toBe(false);
    fireEvent.click(send);
    expect(state.chat).toHaveBeenCalledTimes(2);
    await act(async () => resolveOld());
    expect(send.disabled).toBe(true);
    expect(state.chat.mock.calls[1][0].ctrl.signal.aborted).toBe(false);
  });
});
