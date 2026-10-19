import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import DashboardGenerationCard, { DashboardGenerationState } from './DashboardGenerationCard';

describe('DashboardGenerationCard', () => {
  it('lists completed trials separately from saves and offers only explicit recovery actions', () => {
    const onOpen = vi.fn(),
      onRevise = vi.fn();
    render(
      <DashboardGenerationCard
        state={{
          status: 'failed',
          title: '超时看板',
          generationId: 'run-1',
          errorMessage: '生成达到 180 秒时限',
          stageLabel: '公开分享数据绑定校验',
          totalWidgets: 2,
          validatedWidgets: 1,
          failedWidgets: 0,
          widgetStates: {},
          validatedWidgetIds: ['sales'],
          pendingWidgetIds: ['trend'],
          plan: {
            widgets: [
              { id: 'sales', title: '销售总额', type: 'kpi' },
              { id: 'trend', title: '月度趋势', type: 'line' },
            ],
          },
          editorPath: '/dashboards/plan',
          revisionPrompt: 'revise',
          retryHint: '减少组件后确认，不会自动重试。',
        }}
        onOpen={onOpen}
        onRevise={onRevise}
      />,
    );
    expect(screen.getByRole('alert').textContent).toContain('SQL 试运行通过（不等于已保存）：销售总额');
    expect(screen.getByRole('alert').textContent).toContain('尚未通过试运行：月度趋势');
    expect(screen.getByText('本轮未保存可用组件；候选 SQL 只在本轮内存中暂存。')).toBeTruthy();
    expect(document.querySelector('.anticon-loading')).toBeNull();
    expect(onOpen).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '查看保留的规划/草稿' }));
    fireEvent.click(screen.getByRole('button', { name: '修改计划后重试' }));
    expect(onOpen).toHaveBeenCalledOnce();
    expect(onRevise).toHaveBeenCalledOnce();
  });

  it('shows incomplete generation without a spinner, confirmation or success button', () => {
    render(
      <DashboardGenerationCard
        state={{
          status: 'failed',
          title: 'Unfinished plan',
          errorMessage: '本次看板生成未完成，规划仍保留。',
          totalWidgets: 3,
          validatedWidgets: 0,
          failedWidgets: 0,
          widgetStates: {},
        }}
        onOpen={vi.fn()}
      />,
    );
    expect(screen.getByText('本次看板生成未完成，规划仍保留。')).toBeTruthy();
    expect(screen.queryByRole('button', { name: '确认并生成 SQL' })).toBeNull();
    expect(screen.queryByRole('button', { name: '查看看板' })).toBeNull();
    expect(document.querySelector('.anticon-loading')).toBeNull();
  });

  it('opens the generated draft and exposes partial failure status', () => {
    const onOpen = vi.fn();
    const state: DashboardGenerationState = {
      status: 'created',
      title: 'Retail dashboard',
      totalWidgets: 3,
      validatedWidgets: 2,
      failedWidgets: 1,
      widgetStates: { a: 'validated', b: 'validated', c: 'failed' },
      dashboardId: 'dashboard-1',
      assetState: 'generated',
      editorPath: '/dashboards/dashboard-1',
    };
    render(<DashboardGenerationCard state={state} onOpen={onOpen} />);

    expect(screen.getByText('Retail dashboard')).toBeTruthy();
    expect(screen.getByText('1 个组件待修正')).toBeTruthy();
    expect(screen.getByText('可恢复的看板草稿已生成，保存后进入资产库')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '查看看板' }));
    expect(onOpen).toHaveBeenCalledTimes(1);
  });

  it('labels a saved task dashboard as a resumable asset', () => {
    const state: DashboardGenerationState = {
      status: 'created',
      title: 'Saved dashboard',
      totalWidgets: 1,
      validatedWidgets: 1,
      failedWidgets: 0,
      widgetStates: { a: 'validated' },
      dashboardId: 'dashboard-saved',
      assetState: 'saved',
      editorPath: '/dashboards/dashboard-saved',
    };

    render(<DashboardGenerationCard state={state} onOpen={vi.fn()} />);

    expect(screen.getByText('看板已保存，可在当前任务中继续编辑')).toBeTruthy();
    expect(screen.getByRole('button', { name: '继续编辑' })).toBeTruthy();
  });

  it('shows a SQL-free plan and requires an explicit confirmation action', () => {
    const onConfirm = vi.fn();
    const onRevise = vi.fn();
    const state: DashboardGenerationState = {
      status: 'awaiting_confirmation',
      title: 'Retail dashboard plan',
      totalWidgets: 2,
      validatedWidgets: 0,
      failedWidgets: 0,
      widgetStates: {},
      dashboardId: 'dashboard-plan-1',
      confirmationPrompt: '[[confirm-dashboard:dashboard-plan-1]] confirm',
      revisionPrompt: '[[revise-dashboard-plan:dashboard-plan-1]] revise: ',
      plan: {
        business_theme: 'Store performance',
        audience: 'Regional managers',
        decision_goal: 'Choose intervention priorities',
        analysis_logic: ['Check health', 'Locate drivers'],
        layout_rationale: 'Decision signals first',
        filter_strategy: 'Rolling dates',
        layout_template: 'trend-focus',
        metrics: ['sales'],
        dimensions: ['month'],
        widgets: [
          { id: 'trend', title: 'Sales trend', type: 'line', analysis_level: 3 },
          { id: 'sales', title: 'Total sales', type: 'kpi', analysis_level: 1 },
        ],
      },
    };
    render(<DashboardGenerationCard state={state} onOpen={vi.fn()} onConfirm={onConfirm} onRevise={onRevise} />);

    expect(screen.getByText('SQL 尚未生成，请先确认指标、维度、筛选器和图表计划')).toBeTruthy();
    expect(screen.getByText('受众：')).toBeTruthy();
    expect(screen.getByText('Choose intervention priorities')).toBeTruthy();
    expect(screen.getByText('L1 · Total sales（kpi）')).toBeTruthy();
    expect(screen.getByText('布局理由：Decision signals first')).toBeTruthy();
    expect(screen.queryByText(/布局模板：/)).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '确认并生成 SQL' }));
    fireEvent.click(screen.getByRole('button', { name: '修改计划' }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onRevise).toHaveBeenCalledTimes(1);
  });
});
