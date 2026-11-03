import { describe, expect, it } from 'vitest';
import { decodeHistoryAnswer } from '../../utils/react-agent-final';
import { recoverFinancialHistory } from './recover-history';
import type { ReportData } from './types';

const report = {
  revision: 'saved-revision',
  report: { companyName: '测试公司', run: { id: '7fe43ba4-a567-493a-b329-1b8691596252' } },
} as ReportData;

describe('financial conversation recovery', () => {
  it('restores the real report reference without inventing a user message or steps', () => {
    const message = recoverFinancialHistory(report, 'original-session');
    expect(message.role).toBe('view');
    const payload = JSON.parse(message.context);
    expect(payload.steps).toEqual([]);
    expect(payload.financial_report).toEqual({
      kind: 'financial-report',
      sessionId: 'original-session',
      runId: report.report.run.id,
      revision: report.revision,
      title: '测试公司财报分析',
    });
    expect(payload.final_content).not.toContain('已完成');
    expect(decodeHistoryAnswer(message.context).content).toBe(payload.final_content);
  });

  it('rejects an invalid saved reference', () => {
    expect(() => recoverFinancialHistory(report, '../other-session')).toThrow('保存的财报引用无效');
  });
});
