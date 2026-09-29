import { describe, expect, it } from 'vitest';
import { describeDashboardError, groupMissingPublicationBindings } from './dashboard-errors';

const axiosError = (detail: unknown, message = 'Request failed') => ({
  isAxiosError: true,
  message,
  response: { data: { detail } },
});

const wrappedApiError = (errMsg: unknown, message = 'Request failed with status code 422') => ({
  isAxiosError: true,
  message,
  response: { data: { success: false, err_code: '422', err_msg: errMsg, data: null } },
});

describe('describeDashboardError', () => {
  it('turns backend validation issues into a readable message', () => {
    expect(
      describeDashboardError(
        axiosError({ issues: [{ message: 'SQL must be read-only' }, { message: 'Unknown field' }] }),
        'Validation failed',
      ),
    ).toBe('SQL must be read-only；Unknown field');
  });

  it('shows FastAPI validation messages instead of a generic 422', () => {
    expect(
      describeDashboardError(
        axiosError([{ loc: ['body', 'schema'], msg: 'heatmap visualization requires row, column and value' }]),
        'Validation failed',
      ),
    ).toBe('heatmap visualization requires row, column and value');
  });

  it('extracts actionable messages from DB-GPT wrapped Python-style validation payloads', () => {
    expect(
      describeDashboardError(
        wrappedApiError(
          "{'valid': False, 'issues': [{'path': 'widgets.w1.publication', 'message': '请配置分享页筛选数据绑定'}]}",
        ),
        '发布失败',
      ),
    ).toBe('请配置分享页筛选数据绑定');
  });

  it('keeps actionable local error details and otherwise uses a safe fallback', () => {
    expect(describeDashboardError(new Error('local failure'), 'Operation failed')).toBe('local failure');
    expect(describeDashboardError('unknown failure', 'Operation failed')).toBe('Operation failed');
  });
});

describe('groupMissingPublicationBindings', () => {
  it('merges repeated missing-binding errors while preserving component order and other issues', () => {
    const grouped = groupMissingPublicationBindings(
      [
        {
          path: 'widgets.sales.publication',
          code: 'publication_binding_required',
          message: 'missing',
          severity: 'error',
        },
        {
          path: 'widgets.profit.publication',
          code: 'publication_binding_required',
          message: 'missing',
          severity: 'error',
        },
        {
          path: 'widgets.sales.query',
          code: 'unbound_sql_parameter',
          message: 'parameter missing',
          severity: 'error',
        },
      ],
      [
        { id: 'profit', title: '利润' },
        { id: 'sales', title: '销售额' },
      ],
    );

    expect(grouped.missingWidgets).toEqual([
      { id: 'profit', title: '利润' },
      { id: 'sales', title: '销售额' },
    ]);
    expect(grouped.otherIssues).toHaveLength(1);
    expect(grouped.otherIssues[0].code).toBe('unbound_sql_parameter');
  });
});
