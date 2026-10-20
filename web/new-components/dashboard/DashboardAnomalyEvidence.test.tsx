import { DashboardAnomalyEvidence as DashboardAnomalyEvidenceType } from '@/types/dashboard';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import DashboardAnomalyEvidence from './DashboardAnomalyEvidence';

const evidence = (overrides: Partial<DashboardAnomalyEvidenceType> = {}): DashboardAnomalyEvidenceType => ({
  rule_id: 'revenue-change',
  rule_label: '收入环比异常',
  status: 'anomaly',
  baseline: 'previous_period',
  current_value: 125,
  baseline_value: 100,
  absolute_change: 25,
  change_ratio: 0.25,
  threshold: { mode: 'relative_change', value: 0.2 },
  comparison_time_range: {
    current_start: '2026-08',
    current_end: '2026-08',
    baseline_start: '2026-07',
    baseline_end: '2026-07',
  },
  sample_size: 12,
  matched_rule: 'abs(change_ratio) >= 0.2',
  ...overrides,
});

describe('DashboardAnomalyEvidence', () => {
  it('marks anomalies and exposes every required evidence field in expandable details', () => {
    render(<DashboardAnomalyEvidence evidence={[evidence()]} />);

    expect(screen.getByText('检测到 1 条异常')).toBeTruthy();
    fireEvent.click(screen.getByText('检测到 1 条异常'));
    expect(screen.getByText('收入环比异常')).toBeTruthy();
    expect(screen.getByText('125')).toBeTruthy();
    expect(screen.getByText('100')).toBeTruthy();
    expect(screen.getByText('25')).toBeTruthy();
    expect(screen.getByText('25%')).toBeTruthy();
    expect(screen.getByText('20%')).toBeTruthy();
    expect(screen.getByText('2026-08')).toBeTruthy();
    expect(screen.getByText('2026-07')).toBeTruthy();
    expect(screen.getByText('12')).toBeTruthy();
    expect(screen.getByText('abs(change_ratio) >= 0.2')).toBeTruthy();
  });

  it('renders insufficient and zero-denominator results as unable to determine', () => {
    render(
      <DashboardAnomalyEvidence
        evidence={[
          evidence({
            status: 'indeterminate',
            current_value: 10,
            baseline_value: 0,
            absolute_change: 10,
            change_ratio: null,
            reason_code: 'zero_denominator',
          }),
        ]}
      />,
    );

    expect(screen.getByText('1 条规则无法判断')).toBeTruthy();
    fireEvent.click(screen.getByText('1 条规则无法判断'));
    expect(screen.getByText('无法判断：基线为零，无法计算变化比例')).toBeTruthy();
  });
});
