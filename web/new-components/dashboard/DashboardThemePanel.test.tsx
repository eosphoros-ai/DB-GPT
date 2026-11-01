import { DashboardVisualTheme } from '@/types/dashboard';
import { fireEvent, render, screen } from '@testing-library/react';
import { ReactNode, useState } from 'react';
import { describe, expect, it, vi } from 'vitest';
import DashboardThemePanel from './DashboardThemePanel';

vi.mock('antd', () => ({
  Alert: ({ message }: { message: ReactNode }) => <div>{message}</div>,
  Button: ({ children, icon, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { icon?: ReactNode }) => (
    <button type='button' {...props}>
      {icon}
      {children}
    </button>
  ),
  InputNumber: ({
    onChange,
    addonAfter: _addonAfter,
    ...props
  }: {
    onChange?: (value: number) => void;
    value?: number;
    addonAfter?: ReactNode;
    'aria-label'?: string;
  }) => <input type='number' {...props} onChange={event => onChange?.(Number(event.target.value))} />,
  Segmented: ({ options, value, onChange, ...props }: any) => (
    <div {...props}>
      {options.map((option: { label: string; value: string }) => (
        <button
          key={option.value}
          type='button'
          aria-pressed={value === option.value}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  ),
  Select: ({ options, value, onChange, ...props }: any) => (
    <select {...props} value={value} onChange={event => onChange(event.target.value)}>
      {options.map((option: { label: string; value: string }) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  ),
}));

const ThemeHarness = ({ onChange }: { onChange: (theme: DashboardVisualTheme) => void }) => {
  const [theme, setTheme] = useState<DashboardVisualTheme>({ preset: 'clarity', mode: 'light', overrides: {} });
  return (
    <DashboardThemePanel
      theme={theme}
      onChange={next => {
        setTheme(next);
        onChange(next);
      }}
    />
  );
};

describe('DashboardThemePanel', () => {
  it('switches preset and mode through accessible controls', () => {
    const onChange = vi.fn();
    render(<ThemeHarness onChange={onChange} />);

    fireEvent.click(screen.getByRole('button', { name: '选择石墨主题' }));
    expect(onChange).toHaveBeenLastCalledWith({ preset: 'graphite', mode: 'light', overrides: {} });

    fireEvent.click(screen.getByText('深色'));
    expect(onChange).toHaveBeenLastCalledWith({ preset: 'graphite', mode: 'dark', overrides: {} });
  });

  it('stores only changed values and clears all overrides on reset', () => {
    const onChange = vi.fn();
    render(<ThemeHarness onChange={onChange} />);

    fireEvent.click(screen.getByRole('button', { name: '展开二次创作' }));
    fireEvent.change(screen.getByLabelText('主题主色'), { target: { value: '#7b4ba8' } });
    expect(onChange).toHaveBeenLastCalledWith({
      preset: 'clarity',
      mode: 'light',
      overrides: { primary_color: '#7B4BA8' },
    });

    fireEvent.click(screen.getByRole('button', { name: '恢复主题默认' }));
    expect(onChange).toHaveBeenLastCalledWith({ preset: 'clarity', mode: 'light', overrides: {} });
  });
});
