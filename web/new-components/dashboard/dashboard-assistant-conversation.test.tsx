import { act, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import { ReadableStream } from 'node:stream/web';
import { TextEncoder } from 'node:util';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import DashboardAssistantConversation from './DashboardAssistantConversation';
import { useDashboardAssistantSession, type SavedDashboardAnnotation } from './dashboard-assistant-session';
import { readDashboardAssistantStream } from './dashboard-assistant-stream';

vi.mock('@/client/api', () => ({ ensureDashboardAssistantTask: vi.fn(), getDbList: vi.fn() }));
vi.mock('@/utils', () => ({ getUserId: () => 'test-user' }));

function stream(text: string) {
  const bytes = new TextEncoder().encode(text);
  return new ReadableStream({
    start(controller) {
      for (let i = 0; i < bytes.length; i += 3) controller.enqueue(bytes.slice(i, i + 3));
      controller.close();
    },
  }) as unknown as globalThis.ReadableStream<Uint8Array>;
}

describe('dashboard conversation', () => {
  beforeEach(() => sessionStorage.clear());
  it('reads split UTF-8 frames and forwards interactive questions', async () => {
    const event = vi.fn();
    const response = await readDashboardAssistantStream(
      stream(
        'data: {"type":"question.asked","request_id":"q1"}\r\n\r\n' +
          'data: {"type":"final","content":"已生成修改方案。"}',
      ),
      vi.fn(),
      event,
    );
    expect(response).toBe('已生成修改方案。');
    expect(event).toHaveBeenCalledWith({ type: 'question.asked', request_id: 'q1' });
  });
  it('does not treat an interrupted stream as a completed answer', async () => {
    await expect(readDashboardAssistantStream(stream('data: [DONE]\n\n'), vi.fn())).rejects.toThrow('没有返回完整答复');
    await expect(
      readDashboardAssistantStream(stream('data: {"type":"error","message":"服务断开"}\n\n'), vi.fn()),
    ).rejects.toThrow('服务断开');
  });
  it('restores per-board messages without overwriting another board during navigation', async () => {
    const view = renderHook(({ id }) => useDashboardAssistantSession(id), { initialProps: { id: 'a' } });
    await waitFor(() => expect(view.result.current.loaded).toBe(true));
    act(() =>
      view.result.current.setSession(current => ({
        ...current,
        messages: [{ id: 'm1', role: 'user', content: '门店销售批注' }],
      })),
    );
    view.rerender({ id: 'b' });
    await waitFor(() => expect(view.result.current.loaded).toBe(true));
    expect(view.result.current.session.messages).toHaveLength(0);
    view.rerender({ id: 'a' });
    await waitFor(() => expect(view.result.current.loaded).toBe(true));
    expect(view.result.current.session.messages[0].content).toBe('门店销售批注');
  });
  it('accepts a follow-up and keeps proposals folded until requested', () => {
    const onSend = vi.fn();
    render(
      <DashboardAssistantConversation
        attachments={[]}
        onEditAttachment={vi.fn()}
        onRemoveAttachment={vi.fn()}
        onLocateAnnotation={vi.fn()}
        messages={[{ id: 'q', role: 'assistant', content: '请说明这两条批注分别想修改什么。' }]}
        running={false}
        status=''
        onSend={onSend}
        onStop={vi.fn()}
        onRetry={vi.fn()}
        onShowAnnotations={vi.fn()}
        savedCount={2}
        proposals={[]}
        applying={false}
        onApplyBatch={vi.fn()}
        onPreview={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByRole('textbox'), { target: { value: '第一张改标题，第二张改颜色' } });
    fireEvent.keyDown(screen.getByRole('textbox'), { key: 'Enter', shiftKey: true });
    expect(onSend).not.toHaveBeenCalled();
    fireEvent.keyDown(screen.getByRole('textbox'), { key: 'Enter' });
    expect(onSend).toHaveBeenCalledWith('第一张改标题，第二张改颜色');
    expect(screen.queryByText('批注尚未发送')).toBeNull();
  });
  it('keeps saved annotations attached after a conversation, supports editing and sends without extra text', () => {
    const onSend = vi.fn();
    const onEdit = vi.fn();
    const onRemove = vi.fn();
    const onLocate = vi.fn();
    const attachment: SavedDashboardAnnotation = {
      id: 'a1',
      content: '改成面积图',
      intent: 'modify',
      target: { kind: 'widget', widget_id: 'sales', label: '月度收入', datum_key: {}, row_key: {} },
      chartType: '折线图',
      dashboardTitle: '经营总览',
      savedAt: '2026-09-15',
      state: 'saved',
    };
    render(
      <DashboardAssistantConversation
        attachments={[attachment]}
        onEditAttachment={onEdit}
        onRemoveAttachment={onRemove}
        onLocateAnnotation={onLocate}
        messages={[
          { id: 'earlier', role: 'assistant', content: '可以继续添加批注。' },
          { id: 'sent', role: 'user', content: '之前的要求', annotations: [{ ...attachment, content: '之前的批注' }] },
        ]}
        running={false}
        status=''
        onSend={onSend}
        onStop={vi.fn()}
        onRetry={vi.fn()}
        onShowAnnotations={vi.fn()}
        savedCount={1}
        proposals={[]}
        applying={false}
        onApplyBatch={vi.fn()}
        onPreview={vi.fn()}
      />,
    );
    expect(screen.getByTestId('annotation-composer-attachments').textContent).toContain('改成面积图');
    fireEvent.click(screen.getByRole('button', { name: /编辑 月度收入 批注/ }));
    expect(onEdit).toHaveBeenCalledWith(attachment);
    fireEvent.click(screen.getByRole('button', { name: /移除 月度收入 批注/ }));
    expect(onRemove).toHaveBeenCalledWith('a1');
    fireEvent.click(screen.getByRole('button', { name: /1. 月度收入 折线图 改成面积图/ }));
    expect(onLocate).toHaveBeenCalledWith(attachment);
    fireEvent.click(screen.getByRole('button', { name: '发送消息' }));
    expect(onSend).toHaveBeenCalledWith('');
    const details = screen.getByText('1 条批注').closest('details');
    expect(details?.hasAttribute('open')).toBe(false);
    expect(details?.textContent).toContain('之前的批注');
  });
});
