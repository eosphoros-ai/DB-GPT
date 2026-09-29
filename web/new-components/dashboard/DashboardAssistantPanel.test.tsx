import type { DashboardRecord, DashboardTargetResolution } from '@/types/dashboard';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { App } from 'antd';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { DashboardAnnotationDraft, makeDashboardAnnotationDraft } from './dashboard-assistant';

vi.mock('antd', async () => {
  const actual = await vi.importActual<typeof import('antd')>('antd');
  return {
    ...actual,
    Select: ({
      value,
      options = [],
      onChange,
      ...props
    }: {
      value?: string;
      options?: Array<{ value: string; label: string }>;
      onChange?: (value: string) => void;
    }) => (
      <select {...props} value={value} onChange={event => onChange?.(event.target.value)}>
        {options.map(option => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    ),
  };
});

import DashboardAssistantPanel from './DashboardAssistantPanel';

const record = {
  id: 'dashboard-1',
  conversation_id: 'conversation-1',
  schema: { dashboard: { title: '经营看板' } },
} as DashboardRecord;

function Harness({ resolution }: { resolution: DashboardTargetResolution }) {
  const [drafts, setDrafts] = useState<DashboardAnnotationDraft[]>([]);
  return (
    <App>
      <DashboardAssistantPanel
        record={record}
        drafts={drafts}
        available
        onDraftsChange={setDrafts}
        onResolveReference={vi.fn().mockResolvedValue(resolution)}
        onSubmit={vi.fn()}
      />
    </App>
  );
}

describe('DashboardAssistantPanel natural target resolution', () => {
  it('keeps the batch after failure and sends all annotations together without a type selector', async () => {
    const submit = vi.fn().mockRejectedValueOnce(new Error('请补充第二张图的要求')).mockResolvedValue(undefined);
    const target = { kind: 'widget' as const, widget_id: 'sales', label: '销售额', datum_key: {}, row_key: {} };
    const initial = [
      { ...makeDashboardAnnotationDraft(target), content: '改成柱状图' },
      { ...makeDashboardAnnotationDraft({ ...target, widget_id: 'margin', label: '利润率' }), content: '怎么算的？' },
    ];
    function Batch() {
      const [drafts, setDrafts] = useState(initial);
      return (
        <DashboardAssistantPanel
          record={record}
          drafts={drafts}
          onDraftsChange={setDrafts}
          available
          onSubmit={submit}
          onResolveReference={vi.fn()}
        />
      );
    }
    render(
      <App>
        <Batch />
      </App>,
    );
    expect(screen.queryAllByRole('combobox')).toHaveLength(0);
    fireEvent.click(screen.getByRole('button', { name: /发送给 AI/ }));
    expect(await screen.findByText('请补充第二张图的要求')).toBeTruthy();
    expect(screen.getAllByTestId('annotation-queue-item')).toHaveLength(2);
    expect(submit.mock.calls[0][0]).toEqual(initial);
    fireEvent.click(screen.getByRole('button', { name: /发送给 AI/ }));
    await waitFor(() => expect(screen.queryAllByTestId('annotation-queue-item')).toHaveLength(0));
    expect(submit).toHaveBeenCalledTimes(2);
  });
  it('adds a uniquely resolved natural reference to the proposal queue', async () => {
    render(
      <Harness
        resolution={{
          status: 'resolved',
          target: {
            kind: 'widget',
            widget_id: 'trend',
            label: '组件：收入趋势',
            datum_key: {},
            row_key: {},
          },
          candidates: [{ widget_id: 'trend', label: '收入趋势' }],
          matched_by: 'position_right',
        }}
      />,
    );

    fireEvent.click(screen.getByText('也可以用文字指定图表'));
    fireEvent.change(screen.getByPlaceholderText('例如：右边的收入趋势图改成柱状图'), {
      target: { value: '右边那个改成柱状图' },
    });
    fireEvent.click(screen.getByRole('button', { name: /加入待发送批注/ }));

    expect(await screen.findByText('组件：收入趋势')).toBeTruthy();
    expect(screen.getByText('右边那个改成柱状图')).toBeTruthy();
    expect(screen.getByText(/修改会先返回预览提案/)).toBeTruthy();
  });

  it('asks for clarification and creates no draft when the target is ambiguous', async () => {
    render(
      <Harness
        resolution={{
          status: 'needs_clarification',
          candidates: [
            { widget_id: 'revenue', label: '营业收入' },
            { widget_id: 'trend', label: '收入趋势' },
          ],
          question: '我还不能唯一确定目标。你指的是“营业收入”还是“收入趋势”？',
          matched_by: 'missing_selection',
        }}
      />,
    );

    fireEvent.click(screen.getByText('也可以用文字指定图表'));
    fireEvent.change(screen.getByPlaceholderText('例如：右边的收入趋势图改成柱状图'), {
      target: { value: '这个图改一下' },
    });
    fireEvent.click(screen.getByRole('button', { name: /加入待发送批注/ }));

    expect(await screen.findByText('我还不能唯一确定目标。你指的是“营业收入”还是“收入趋势”？')).toBeTruthy();
    await waitFor(() => expect(screen.queryByText('组件：营业收入')).toBeNull());
    expect(screen.getByRole('button', { name: /发送给 AI/ }).hasAttribute('disabled')).toBe(true);
  });
});
