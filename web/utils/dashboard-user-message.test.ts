import { describe, expect, it } from 'vitest';
import { dashboardUserDisplayText } from './dashboard-user-message';

const labels = { confirm: '确认并生成看板', revise: '修改计划' };

describe('dashboard user messages', () => {
  it('hides the confirmation marker and generated English request', () => {
    expect(
      dashboardUserDisplayText(
        '[Database: Walmart_Sales] [[confirm-dashboard:plan-1]] I confirm this dashboard plan at expected revision 1. Generate and validate its SQL queries now.',
        labels,
      ),
    ).toBe(labels.confirm);
  });

  it('keeps the actual revision request', () => {
    expect(
      dashboardUserDisplayText(
        '[[revise-dashboard-plan:plan-1]] Revise this dashboard plan at expected revision 2 as follows: 只保留四个组件',
        labels,
      ),
    ).toBe('修改计划：只保留四个组件');
  });

  it('does not change ordinary queries or inline marker examples', () => {
    for (const text of ['构建销售大盘', '说明 [[confirm-dashboard:plan-1]] 的含义']) {
      expect(dashboardUserDisplayText(text, labels)).toBe(text);
    }
  });
});
