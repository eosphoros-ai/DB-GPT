import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
import QuestionDock, { QuestionRequest } from './QuestionDock';

const request = (questions: unknown[], request_id = 'A'): QuestionRequest => ({
  request_id,
  conv_id: 'conversation',
  questions,
});

const nextBtn = () => screen.getByRole('button', { name: /qdock_next|qdock_submit/ });
const advance = () => fireEvent.click(nextBtn());

describe('question slots and request identity', () => {
  it.each([['当前 Walmart_Sales 数据源没有顾客年龄字段，如何继续？'], [{ question: '请说明查询工具的参数结构。' }]])(
    'allows the original historical wire shape %j',
    questions => {
      const onReply = vi.fn();
      render(<QuestionDock request={request([questions])} onReply={onReply} onReject={vi.fn()} />);
      fireEvent.change(screen.getByRole('textbox'), { target: { value: '保留可计算指标' } });
      fireEvent.click(screen.getByRole('button', { name: /qdock_submit/ }));
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
    // Page 1 is a hole: invalid note, advanceable without input.
    expect(screen.getAllByRole('status')).toHaveLength(1);
    advance();
    fireEvent.change(screen.getByRole('textbox', { name: '销量口径？' }), { target: { value: '按订单量' } });
    advance();
    expect(screen.getAllByRole('status')).toHaveLength(1); // hole page 3
    advance();
    fireEvent.change(screen.getByRole('textbox', { name: '时间口径？' }), { target: { value: '按月份' } });
    advance(); // hole page 5
    advance(); // last page -> submit
    expect(onReply).toHaveBeenCalledWith('A', [[], ['按订单量'], [], ['按月份'], []]);
  });

  it('starts B empty and submits only B answers, not selections from A', () => {
    const onReply = vi.fn();
    const view = render(<QuestionDock request={request(['A question'])} onReply={onReply} onReject={vi.fn()} />);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'A answer' } });
    view.rerender(
      <QuestionDock request={request(['B first', 'B second'], 'B')} onReply={onReply} onReject={vi.fn()} />,
    );
    expect(screen.getAllByRole('textbox').map(input => (input as HTMLInputElement).value)).toEqual(['']);
    fireEvent.change(screen.getByRole('textbox', { name: 'B first' }), { target: { value: 'B1' } });
    fireEvent.click(screen.getByRole('button', { name: /qdock_next/ }));
    fireEvent.change(screen.getByRole('textbox', { name: 'B second' }), { target: { value: 'B2' } });
    fireEvent.click(screen.getByRole('button', { name: /qdock_submit/ }));
    expect(onReply).toHaveBeenCalledWith('B', [['B1'], ['B2']]);
  });

  it('selects numbered options and the recommend shortcut', () => {
    const onReply = vi.fn();
    render(
      <QuestionDock
        request={
          request([
            {
              question: '交付形态？',
              header: '交付物',
              options: [
                { label: 'HTML 报告', description: '单文件（推荐）' },
                { label: 'Word 报告', description: '归档用' },
              ],
            },
          ])
        }
        onReply={onReply}
        onReject={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'qdock_recommend', exact: true }));
    fireEvent.click(screen.getByRole('button', { name: /qdock_submit/ }));
    expect(onReply).toHaveBeenCalledWith('A', [['HTML 报告']]);
  });

  it('keeps failed submissions visible and retryable', async () => {
    const onReply = vi.fn().mockRejectedValueOnce(new Error('请重试')).mockResolvedValue(undefined);
    render(<QuestionDock request={request(['问题'])} onReply={onReply} onReject={vi.fn()} />);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: '答案' } });
    fireEvent.click(screen.getByRole('button', { name: /qdock_submit/ }));
    expect(await screen.findByRole('alert')).toHaveProperty('textContent', '请重试');
    await waitFor(() => expect((nextBtn() as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByRole('button', { name: /qdock_submit/ }));
    expect(onReply).toHaveBeenCalledTimes(2);
  });

  it('keeps an entirely malformed request cancellable and cannot submit an empty answer', () => {
    const onReply = vi.fn(),
      onReject = vi.fn();
    render(<QuestionDock request={request([null, {}])} onReply={onReply} onReject={onReject} />);
    advance(); // hole page 1 -> last (hole) page
    expect((screen.getByRole('button', { name: /qdock_submit/ }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'qdock_skip' }));
    expect(onReject).toHaveBeenCalledWith('A');
    expect(onReply).not.toHaveBeenCalled();
  });
});
