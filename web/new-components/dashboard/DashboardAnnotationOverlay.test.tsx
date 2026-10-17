import type { DashboardAnnotationRecord } from '@/types/dashboard';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import DashboardAnnotationOverlay, { DashboardAnnotationSelection } from './DashboardAnnotationOverlay';

const selection: DashboardAnnotationSelection = {
  anchor: new DOMRect(100, 100, 240, 120),
  suggestedPrompt: '请为新热力图生成只读查询和字段映射。',
  target: {
    kind: 'widget',
    widget_id: 'heatmap-new',
    label: '组件：新热力图',
    datum_key: {},
    row_key: {},
  },
};

const dispatchPointerEvent = (
  element: Element,
  type: 'pointerdown' | 'pointermove' | 'pointerup',
  init: MouseEventInit & { pointerId: number },
) => {
  const event = new MouseEvent(type, { bubbles: true, cancelable: true, ...init });
  Object.defineProperty(event, 'pointerId', { configurable: true, value: init.pointerId });
  fireEvent(element, event);
};

describe('DashboardAnnotationOverlay', () => {
  it('opens the input immediately for a newly clicked chart', () => {
    render(
      <DashboardAnnotationOverlay
        selection={{ ...selection, suggestedPrompt: undefined }}
        annotations={[]}
        onTargetChange={vi.fn()}
        onCreate={vi.fn()}
        onApply={vi.fn()}
        onReject={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByRole('textbox', { name: '批注内容' })).toBeTruthy();
    expect(screen.getByRole('button', { name: '保存批注' }).hasAttribute('disabled')).toBe(true);
  });
  it('opens an agent-configuration request with an editable suggested prompt', async () => {
    const onCreate = vi.fn().mockResolvedValue(undefined);
    render(
      <DashboardAnnotationOverlay
        selection={selection}
        annotations={[]}
        onTargetChange={vi.fn()}
        onCreate={onCreate}
        onApply={vi.fn()}
        onReject={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    const prompt = screen.getByRole('textbox', { name: '批注内容' });
    expect((prompt as HTMLTextAreaElement).value).toBe(selection.suggestedPrompt);
    fireEvent.change(prompt, { target: { value: '请生成门店和月份销售热力图。' } });
    fireEvent.click(screen.getByRole('button', { name: '保存批注' }));

    await waitFor(() => expect(onCreate).toHaveBeenCalledWith('请生成门店和月份销售热力图。'));
    await waitFor(() => expect((prompt as HTMLTextAreaElement).value).toBe(''));
  });

  it('submits an AI configuration request for a selected global filter', async () => {
    const onCreate = vi.fn().mockResolvedValue(undefined);
    render(
      <DashboardAnnotationOverlay
        selection={{
          anchor: new DOMRect(80, 60, 220, 52),
          suggestedPrompt: '请把门店筛选改成多选并影响销售组件。',
          target: {
            kind: 'filter',
            filter_id: 'store-filter',
            label: '全局筛选器：门店',
            datum_key: {},
            row_key: {},
          },
        }}
        annotations={[]}
        onTargetChange={vi.fn()}
        onCreate={onCreate}
        onApply={vi.fn()}
        onReject={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText('全局筛选器：门店')).toBeTruthy();
    const prompt = screen.getByRole('textbox', { name: '批注内容' });
    fireEvent.click(screen.getByRole('button', { name: '保存批注' }));
    await waitFor(() => expect(onCreate).toHaveBeenCalledWith('请把门店筛选改成多选并影响销售组件。'));
    await waitFor(() => expect((prompt as HTMLTextAreaElement).value).toBe(''));
  });

  it('stops showing a failed proposal as an endless pending request', () => {
    const invalidated = {
      id: 'annotation-invalid',
      dashboard_id: 'dashboard-1',
      actor_id: 'alice',
      conversation_id: 'conversation-1',
      source_turn_id: null,
      base_revision: 2,
      target: selection.target,
      prompt: '请配置这个组件。',
      intent: 'modify',
      status: 'invalidated',
      proposal: null,
      created_at: '2026-08-29T00:00:00Z',
      updated_at: '2026-08-29T00:00:01Z',
      resolved_at: '2026-08-29T00:00:01Z',
    } satisfies DashboardAnnotationRecord;

    render(
      <DashboardAnnotationOverlay
        selection={{ ...selection, suggestedPrompt: undefined }}
        annotations={[invalidated]}
        onTargetChange={vi.fn()}
        onCreate={vi.fn()}
        onApply={vi.fn()}
        onReject={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText('数据助理未生成有效方案')).toBeTruthy();
    expect(screen.queryByText('等待 Agent 提案')).toBeNull();
    expect(screen.getByRole('button', { name: '再写一条批注' })).toBeTruthy();
  });

  it('gives proposal decisions stable accessible names', async () => {
    const onApply = vi.fn().mockResolvedValue(undefined);
    const proposed = {
      id: 'annotation-proposed',
      dashboard_id: 'dashboard-1',
      actor_id: 'alice',
      conversation_id: 'conversation-1',
      source_turn_id: null,
      base_revision: 3,
      target: { ...selection.target, filter_id: null, series: null, column: null },
      prompt: '只修改标题。',
      intent: 'modify',
      status: 'proposed',
      proposal: {
        summary: '修改标题',
        operations: [{ op: 'replace', path: '/widgets/0/title', value: '新标题' }],
        stable_operations: [{ op: 'replace', path: '/widgets/by-id/heatmap-new/title', value: '新标题' }],
        before: [],
        after: [],
        validation: { valid: true, issues: [], widget_status: {} },
        preview_schema: {},
      },
      created_at: '2026-08-31T00:00:00Z',
      updated_at: '2026-08-31T00:00:01Z',
      resolved_at: null,
    } as unknown as DashboardAnnotationRecord;

    render(
      <DashboardAnnotationOverlay
        selection={{ ...selection, suggestedPrompt: undefined }}
        annotations={[proposed]}
        onTargetChange={vi.fn()}
        onCreate={vi.fn()}
        onApply={onApply}
        onReject={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByRole('button', { name: '放弃提案' })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '应用到草稿' }));
    await waitFor(() => expect(onApply).toHaveBeenCalledWith(proposed));
  });

  it('can be moved by its title bar while keeping long content in an independent scroll area', async () => {
    const widthDescriptor = Object.getOwnPropertyDescriptor(window, 'innerWidth');
    const heightDescriptor = Object.getOwnPropertyDescriptor(window, 'innerHeight');
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1200 });
    Object.defineProperty(window, 'innerHeight', { configurable: true, value: 900 });

    render(
      <DashboardAnnotationOverlay
        selection={selection}
        annotations={[]}
        onTargetChange={vi.fn()}
        onCreate={vi.fn()}
        onApply={vi.fn()}
        onReject={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    const overlay = screen.getByTestId('dashboard-annotation-overlay');
    Object.defineProperty(overlay, 'getBoundingClientRect', {
      configurable: true,
      value: () =>
        new DOMRect(
          Number.parseFloat(overlay.style.left || '350'),
          Number.parseFloat(overlay.style.top || '100'),
          440,
          500,
        ),
    });
    const dragHandle = screen.getByRole('button', { name: '拖动批注窗口' });

    // Let the opening animation frame place the panel before simulating a user drag.
    // Otherwise that frame can run after the pointer events and overwrite the dragged
    // position, which cannot happen during a real interaction.
    await waitFor(() => {
      expect(overlay.style.left).toBe('350px');
      expect(overlay.style.top).toBe('100px');
    });

    dispatchPointerEvent(dragHandle, 'pointerdown', { button: 0, pointerId: 7, clientX: 370, clientY: 120 });
    dispatchPointerEvent(dragHandle, 'pointermove', { pointerId: 7, clientX: 500, clientY: 300 });
    dispatchPointerEvent(dragHandle, 'pointerup', { pointerId: 7, clientX: 500, clientY: 300 });

    await waitFor(() => {
      expect(overlay.style.left).toBe('480px');
      expect(overlay.style.top).toBe('280px');
    });
    expect(screen.getByTestId('dashboard-annotation-scroll-area').className).toContain('overflow-y-auto');

    fireEvent.keyDown(dragHandle, { key: 'ArrowLeft' });
    await waitFor(() => expect(overlay.style.left).toBe('472px'));

    if (widthDescriptor) Object.defineProperty(window, 'innerWidth', widthDescriptor);
    if (heightDescriptor) Object.defineProperty(window, 'innerHeight', heightDescriptor);
  });
});
