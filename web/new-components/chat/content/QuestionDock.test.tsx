import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import QuestionDock, { QuestionRequest } from './QuestionDock';

vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
const request = (questions: unknown[], request_id = 'A'): QuestionRequest => ({
  request_id,
  conv_id: 'conversation',
  questions,
});

describe('question slots and request identity', () => {
  it.each([['当前 Walmart_Sales 数据源没有顾客年龄字段，如何继续？'], [{ question: '请说明查询工具的参数结构。' }]])(
    'allows the original historical wire shape %j',
    questions => {
      const onReply = vi.fn();
      render(<QuestionDock request={request([questions])} onReply={onReply} onReject={vi.fn()} />);
      fireEvent.change(screen.getByRole('textbox'), { target: { value: '保留可计算指标' } });
      fireEvent.click(screen.getByRole('button', { name: 'confirm' }));
      expect(onReply).toHaveBeenCalledWith('A', [['保留可计算指标']]);
    },
  );

  it('submits holes, not shifted answers, after invalid entries cannot be rendered', () => {
    const onReply = vi.fn();
    render(
      <QuestionDock
        request={request([null, '销量口径？', {}, { question: '时间口径？' }, 9])}
        onReply={onReply}
        onReject={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByRole('textbox', { name: '销量口径？' }), { target: { value: '按订单量' } });
    fireEvent.change(screen.getByRole('textbox', { name: '时间口径？' }), { target: { value: '按月份' } });
    fireEvent.click(screen.getByRole('button', { name: 'confirm' }));
    expect(onReply).toHaveBeenCalledWith('A', [[], ['按订单量'], [], ['按月份'], []]);
    expect(screen.getAllByRole('status')).toHaveLength(3);
  });

  it('starts B empty and submits only B answers, not selections from A', () => {
    const onReply = vi.fn();
    const view = render(<QuestionDock request={request(['A question'])} onReply={onReply} onReject={vi.fn()} />);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'A answer' } });
    view.rerender(
      <QuestionDock request={request(['B first', 'B second'], 'B')} onReply={onReply} onReject={vi.fn()} />,
    );
    expect(screen.getAllByRole('textbox').map(input => (input as HTMLInputElement).value)).toEqual(['', '']);
    fireEvent.change(screen.getByRole('textbox', { name: 'B first' }), { target: { value: 'B1' } });
    fireEvent.change(screen.getByRole('textbox', { name: 'B second' }), { target: { value: 'B2' } });
    fireEvent.click(screen.getByRole('button', { name: 'confirm' }));
    expect(onReply).toHaveBeenCalledWith('B', [['B1'], ['B2']]);
  });

  it('keeps failed submissions visible and retryable', async () => {
    const onReply = vi.fn().mockRejectedValueOnce(new Error('请重试')).mockResolvedValue(undefined);
    render(<QuestionDock request={request(['问题'])} onReply={onReply} onReject={vi.fn()} />);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: '答案' } });
    fireEvent.click(screen.getByRole('button', { name: 'confirm' }));
    expect(await screen.findByRole('alert')).toHaveProperty('textContent', '请重试');
    await waitFor(() =>
      expect((screen.getByRole('button', { name: 'confirm' }) as HTMLButtonElement).disabled).toBe(false),
    );
    fireEvent.click(screen.getByRole('button', { name: 'confirm' }));
    expect(onReply).toHaveBeenCalledTimes(2);
  });

  it('keeps an entirely malformed request cancellable and cannot submit an empty answer', () => {
    const onReply = vi.fn(),
      onReject = vi.fn();
    render(<QuestionDock request={request([null, {}])} onReply={onReply} onReject={onReject} />);
    expect((screen.getByRole('button', { name: 'confirm' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'cancel' }));
    expect(onReject).toHaveBeenCalledWith('A');
    expect(onReply).not.toHaveBeenCalled();
  });
});
