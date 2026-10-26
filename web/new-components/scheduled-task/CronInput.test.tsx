import { fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';
import CronInput from './CronInput';
vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key: string) => key }) }));

describe('official frequency selector', () => {
  it.each(['* * * * *', '*/5 * * * *', '0 9 * 12 *', '0 9 * * mon-fri', '0 9 1,15 * *', '0 9 * * 1'])(
    'never rewrites an existing expression on opening: %s',
    expression => {
      const onChange = vi.fn();
      const { rerender } = render(<CronInput value={expression} onChange={onChange} />);
      expect(onChange).not.toHaveBeenCalled();
      rerender(<CronInput value='30 7 * * *' onChange={onChange} />);
      expect((screen.getByLabelText('执行时间') as HTMLInputElement).value).toBe('07:30');
      expect(onChange).not.toHaveBeenCalled();
    },
  );
  it('keeps custom minute schedules editable and generates unambiguous weekdays', () => {
    const onChange = vi.fn();
    function Controlled() {
      const [value, setValue] = useState('0 9 * * *');
      return (
        <CronInput
          value={value}
          onChange={v => {
            onChange(v);
            setValue(v);
          }}
        />
      );
    }
    render(<Controlled />);
    expect((screen.getByLabelText('执行时间') as HTMLInputElement).value).toBe('09:00');
    fireEvent.click(screen.getByText('scheduled.cron.weekly'));
    expect(onChange).toHaveBeenLastCalledWith('0 9 * * mon');
    fireEvent.click(screen.getByText('scheduled.cron.custom'));
    fireEvent.change(screen.getByLabelText('Cron 表达式'), { target: { value: '* * * * *' } });
    expect((screen.getByLabelText('Cron 表达式') as HTMLInputElement).value).toBe('* * * * *');
    expect(onChange).toHaveBeenLastCalledWith('* * * * *');
  });
});
