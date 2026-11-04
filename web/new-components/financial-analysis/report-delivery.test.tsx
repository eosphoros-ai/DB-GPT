import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import FinancialProgressPanel from '../chat/content/FinancialProgressPanel';
import type { TaskItem } from '../chat/content/TaskPlanCard';
import type { FinancialReportReference } from './agent-artifact';
import {
  financialObservations,
  financialStepSubtitle,
  financialStepTitle,
  recentFinancialObservations,
} from './execution-display';
import { FinancialReportDelivery, financialArtifact, mergeArtifacts } from './report-delivery';

const reference: FinancialReportReference = {
  kind: 'financial-report',
  sessionId: 'session',
  runId: '12345678-1234-4234-8234-123456789012',
  revision: 'published-v1',
  title: '合成测试报告',
  published: true,
};

describe('report delivery before final answer', () => {
  it('makes a draft available without opening it, then opens the publication without a final event', () => {
    const delivery = new FinancialReportDelivery();
    const draft = delivery.receive({ ...reference, published: false, revision: 'draft' }, 'session', 'turn', true)!;
    expect(draft.open).toBe(false);
    expect(delivery.hasPublished('turn')).toBe(false);
    const published = delivery.receive(reference, 'session', 'turn', true)!;
    expect(published.open).toBe(true);
    expect(delivery.hasPublished('turn')).toBe(true);
    const artifacts = mergeArtifacts([draft.artifact, published.artifact]);
    expect(artifacts).toHaveLength(1);
    expect(artifacts[0].content.revision).toBe('published-v1');
  });

  it('never takes focus after user navigation or repeated publication events', () => {
    const delivery = new FinancialReportDelivery();
    expect(delivery.receive(reference, 'session', 'turn', false)?.open).toBe(false);
    expect(delivery.hasReport('turn')).toBe(true);
    expect(delivery.receive(reference, 'session', 'turn', true)?.open).toBe(false);
    expect(delivery.receive({ ...reference, revision: 'published-v2' }, 'session', 'turn', true)?.open).toBe(false);
    expect(delivery.receive(reference, 'session', 'another-turn', true)?.open).toBe(true);
  });

  it('does not treat unmarked legacy references as published or accept another session', () => {
    const delivery = new FinancialReportDelivery();
    expect(delivery.receive({ ...reference, published: undefined }, 'session', 'legacy', true)?.open).toBe(false);
    expect(delivery.receive(reference, 'other-session', 'turn', true)).toBeNull();
    expect(delivery.hasReport('turn')).toBe(false);
    expect(delivery.receive('<html>ordinary report</html>', 'session', 'turn', true)).toBeNull();
  });

  it('does not call a new revision published merely because the turn read an earlier publication', () => {
    const delivery = new FinancialReportDelivery();
    delivery.receive(reference, 'session', 'turn', true);
    delivery.receive({ ...reference, revision: 'revision-in-progress', published: false }, 'session', 'turn', true);
    expect(delivery.hasPublished('turn')).toBe(false);
    expect(delivery.hasReport('turn')).toBe(true);
  });

  it('merges renamed reports by identity while keeping equal titles from different runs and turns', () => {
    const first = financialArtifact(reference, 'turn');
    const renamed = financialArtifact({ ...reference, title: '修订标题', revision: 'v2' }, 'turn');
    const other = financialArtifact({ ...reference, runId: '22345678-1234-4234-8234-123456789012' }, 'turn');
    const history = financialArtifact(reference, 'older-turn');
    expect(mergeArtifacts([first, other, history, renamed])).toEqual([other, history, renamed]);
  });
});

describe('public financial execution progress', () => {
  const step = { id: 'prepare', title: 'prepare_financial_report', status: 'done' };
  const text = (content: string) => ({ output_type: 'text', content });

  it('gives old history without action metadata a business title and an honest fallback', () => {
    expect(financialStepTitle(step)).toBe('读取财报并分析财务数据');
    expect(financialStepSubtitle(step, [])).toBe('本次调用已结束，可展开查看结果。');
    expect(financialStepSubtitle({ ...step, status: 'failed' }, [])).toContain('未完成');
  });

  it('only promotes public observations, never reasoning, arguments or unresolved references', () => {
    expect(
      financialObservations([
        text('Thought: secret\nAction Input: {"private":true}\n{"model_context":{}}'),
        text('已校验的分析发现（待最终复核）：收入为 {{fact:unresolved}}。'),
        text('[00:10] 读取财报：已提取财务数据。\n已读取财务科目：营业收入、净利润。'),
        { output_type: 'html', content: reference },
      ]),
    ).toEqual(['读取财报：已提取财务数据。', '已读取财务科目：营业收入、净利润。']);
  });

  it('restores only three distinct recent observations from persisted outputs', () => {
    const outputs = [
      text('[00:01] 读取财报：已提取数据。'),
      text('[00:01] 读取财报：已提取数据。'),
      text('已读取财务科目：营业收入。'),
      text('[00:02] 分析财务数据：正在分析现金流。'),
      text('[00:03] 核对结论：正在核对引用。'),
    ];
    expect(recentFinancialObservations([step], { prepare: outputs })).toEqual([
      '已读取财务科目：营业收入。',
      '分析财务数据：正在分析现金流。',
      '核对结论：正在核对引用。',
    ]);
  });

  it('lets the user open a published report while the reply is still running', () => {
    const open = vi.fn();
    const tasks: TaskItem[] = ['读取财报', '分析财务数据', '核对结论', '生成报告'].map((content, index) => ({
      id: String(index),
      kind: 'financial-stage',
      content,
      status: 'completed',
      priority: 'high',
    }));
    render(
      <FinancialProgressPanel
        tasks={tasks}
        isRunning
        reportPublished
        onOpenReport={open}
        updates={['生成报告：报告已生成。', '已校验的分析发现（待最终复核）：早期发现。']}
      />,
    );
    expect(screen.getByRole('status').textContent).toContain('正在整理回复');
    fireEvent.click(screen.getByRole('button', { name: '查看报告与原文依据' }));
    expect(open).toHaveBeenCalledOnce();
    expect(screen.queryByText(/早期发现/)).toBeNull();
    expect(screen.getByRole('log').textContent).toContain('报告已生成');
  });

  it('keeps an interrupted draft available without claiming it is published', () => {
    const tasks: TaskItem[] = [
      { id: 'read', kind: 'financial-stage', content: '读取财报', status: 'completed', priority: 'high' },
      {
        id: 'analyze',
        kind: 'financial-stage',
        content: '分析财务数据',
        status: 'error',
        priority: 'high',
        detail: '已保存草稿。',
      },
    ];
    render(<FinancialProgressPanel tasks={tasks} isRunning={false} onOpenReport={vi.fn()} />);
    expect(screen.getByRole('button', { name: '查看已有分析内容' })).toBeTruthy();
    expect(screen.queryByText('报告已生成')).toBeNull();
    expect(screen.getByRole('status').textContent).toBe('已保存草稿。');
  });
});
