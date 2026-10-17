import { DashboardAnomalyRule } from '@/types/dashboard';
import { fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { describe, expect, it } from 'vitest';
import DashboardAnomalyRuleEditor from './DashboardAnomalyRuleEditor';

const Harness = () => {
  const [rules, setRules] = useState<DashboardAnomalyRule[]>([]);
  return (
    <DashboardAnomalyRuleEditor
      rules={rules}
      fields={[
        { value: 'period', label: 'period' },
        { value: 'revenue', label: 'revenue' },
      ]}
      onChange={setRules}
    />
  );
};

describe('DashboardAnomalyRuleEditor', () => {
  it('requires an explicit threshold and lets the user configure it', () => {
    render(<Harness />);

    fireEvent.click(screen.getByRole('button', { name: /添加规则/ }));
    const threshold = screen.getByLabelText('异常规则 1阈值');
    expect((threshold as HTMLInputElement).value).toBe('');
    fireEvent.change(threshold, { target: { value: '15' } });
    expect((threshold as HTMLInputElement).value).toBe('15');
  });
});
