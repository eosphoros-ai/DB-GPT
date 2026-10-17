import type { DashboardFilter } from '@/types/dashboard';
import { fireEvent, render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('antd', () => {
  const Select = ({
    mode,
    onChange,
    'aria-label': ariaLabel,
  }: {
    mode?: string;
    onChange: (value: unknown) => void;
    'aria-label'?: string;
  }) => (
    <button
      type='button'
      aria-label={ariaLabel}
      onClick={() => onChange(mode === 'multiple' ? ['north', 'south'] : 'north')}
    >
      {mode === 'multiple' ? 'choose-many' : 'choose-one'}
    </button>
  );
  const RangePicker = ({
    onChange,
    'aria-label': ariaLabel,
  }: {
    onChange: (value: unknown) => void;
    'aria-label'?: string;
  }) => (
    <button
      type='button'
      aria-label={ariaLabel}
      onClick={() => onChange([{ format: () => '2024-01-01' }, { format: () => '2024-12-31' }])}
    >
      choose-dates
    </button>
  );
  const Input = ({
    onChange,
    placeholder,
    value,
    'aria-label': ariaLabel,
  }: {
    onChange: (event: { target: { value: string } }) => void;
    placeholder?: string;
    value?: string;
    'aria-label'?: string;
  }) => (
    <input aria-label={ariaLabel} value={value || ''} placeholder={placeholder} onChange={event => onChange(event)} />
  );
  const InputNumber = ({
    onChange,
    placeholder,
    value,
    'aria-label': ariaLabel,
  }: {
    onChange: (value: number | null) => void;
    placeholder?: string;
    value?: number | null;
    'aria-label'?: string;
  }) => (
    <input
      type='number'
      aria-label={ariaLabel}
      value={value ?? ''}
      placeholder={placeholder}
      onChange={event => onChange(event.target.value === '' ? null : Number(event.target.value))}
    />
  );
  return {
    Button: ({
      children,
      disabled,
      onClick,
      ...props
    }: {
      children: ReactNode;
      disabled?: boolean;
      onClick?: () => void;
      'aria-label'?: string;
    }) => (
      <button type='button' disabled={disabled} onClick={onClick} aria-label={props['aria-label']}>
        {children}
      </button>
    ),
    DatePicker: { RangePicker },
    Input,
    InputNumber,
    Select,
    Tooltip: ({ children }: { children: ReactNode }) => children,
    ConfigProvider: ({ children }: { children: ReactNode }) => children,
  };
});

vi.mock('@ant-design/icons', () => ({ UndoOutlined: () => null }));

import DashboardFilters from './DashboardFilters';

const filters: DashboardFilter[] = [
  {
    id: 'dates',
    type: 'date_range',
    label: 'Date range',
    field: 'sale_date',
    default: ['2023-01-01', '2023-12-31'],
    options: [],
  },
  {
    id: 'region',
    type: 'select',
    label: 'Region',
    field: 'region',
    default: null,
    options: [{ label: 'North', value: 'north' }],
  },
  {
    id: 'stores',
    type: 'multi_select',
    label: 'Stores',
    field: 'store',
    default: [],
    options: [],
  },
  {
    id: 'keyword',
    type: 'text',
    label: 'Keyword',
    field: 'product_name',
    default: '',
    options: [],
  },
  {
    id: 'amount',
    type: 'number_range',
    label: 'Amount range',
    field: 'sales_amount',
    default: [10, 20],
    options: [],
  },
];

describe('DashboardFilters', () => {
  it('maps all five filter controls into one immutable values object', () => {
    const onChange = vi.fn();
    render(<DashboardFilters filters={filters} values={{ untouched: 'keep-me' }} onChange={onChange} />);

    fireEvent.click(screen.getByRole('button', { name: 'Date range筛选' }));
    expect(onChange).toHaveBeenNthCalledWith(1, {
      untouched: 'keep-me',
      dates: ['2024-01-01', '2024-12-31'],
    });

    fireEvent.click(screen.getByRole('button', { name: 'Region筛选' }));
    expect(onChange).toHaveBeenNthCalledWith(2, {
      untouched: 'keep-me',
      region: 'north',
    });

    fireEvent.click(screen.getByRole('button', { name: 'Stores筛选' }));
    expect(onChange).toHaveBeenNthCalledWith(3, {
      untouched: 'keep-me',
      stores: ['north', 'south'],
    });

    fireEvent.change(screen.getByRole('textbox', { name: 'Keyword筛选' }), { target: { value: 'phone' } });
    expect(onChange).toHaveBeenNthCalledWith(4, {
      untouched: 'keep-me',
      keyword: 'phone',
    });

    fireEvent.change(screen.getByRole('spinbutton', { name: 'Amount range最小值' }), { target: { value: '15' } });
    expect(onChange).toHaveBeenNthCalledWith(5, {
      untouched: 'keep-me',
      amount: [15, 20],
    });
  });

  it('explains filter scope and restores every filter default in one action', () => {
    const onReset = vi.fn();
    render(
      <DashboardFilters
        filters={filters}
        values={{
          dates: ['2024-01-01', '2024-02-01'],
          region: 'north',
          stores: ['north'],
          keyword: 'phone',
          amount: [15, 30],
        }}
        scopeByFilter={{ dates: ['Revenue', 'Trend'], region: [], stores: ['Ranking'] }}
        onReset={onReset}
      />,
    );

    expect(screen.getByText('影响 2 个组件')).toBeTruthy();
    expect(screen.getByText('未绑定')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '恢复默认筛选并刷新' }));

    expect(onReset).toHaveBeenCalledWith({
      dates: ['2023-01-01', '2023-12-31'],
      region: null,
      stores: [],
      keyword: '',
      amount: [10, 20],
    });
  });
});
