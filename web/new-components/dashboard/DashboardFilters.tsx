import { DashboardFilter } from '@/types/dashboard';
import { EditOutlined, UndoOutlined } from '@ant-design/icons';
import { Button, DatePicker, Input, InputNumber, Select, Tooltip } from 'antd';
import dayjs from 'dayjs';
import styles from './DashboardWorkspace.module.css';

interface DashboardFiltersProps {
  filters: DashboardFilter[];
  values: Record<string, unknown>;
  disabled?: boolean;
  emptyOptionText?: string;
  scopeByFilter?: Record<string, string[]>;
  showReset?: boolean;
  variant?: 'bar' | 'card';
  className?: string;
  onEditFilter?: (filterId: string) => void;
  onChange?: (values: Record<string, unknown>) => void;
  onReset?: (values: Record<string, unknown>) => void;
}

export default function DashboardFilters({
  filters,
  values,
  disabled,
  emptyOptionText = '尚未配置可选值，请在编辑器右侧选择数据字段或手动输入选项',
  scopeByFilter = {},
  showReset = true,
  variant = 'card',
  className = '',
  onEditFilter,
  onChange,
  onReset,
}: DashboardFiltersProps) {
  if (!filters.length) return null;

  const update = (filterId: string, value: unknown) => onChange?.({ ...values, [filterId]: value });
  const resetValues = {
    ...values,
    ...Object.fromEntries(filters.map(filter => [filter.id, filter.default])),
  };
  const isAtDefaults = filters.every(
    filter => JSON.stringify(values[filter.id] ?? filter.default) === JSON.stringify(filter.default),
  );

  return (
    <div
      className={`${styles.filters} ${variant === 'card' ? styles.filtersCard : styles.filtersBar} ${className}`.trim()}
    >
      {filters.map(filter => {
        const value = values[filter.id] ?? filter.default;
        const scope = scopeByFilter[filter.id] || [];
        return (
          <div key={filter.id} className={styles.filterItem} data-filter-type={filter.type}>
            <span className={styles.filterItemHeader}>
              <Tooltip title={scope.length ? `${filter.label} · 影响：${scope.join('、')}` : filter.label}>
                <span className={styles.filterLabel}>{filter.label}</span>
              </Tooltip>
              <span className='flex min-w-0 items-center gap-1'>
                {variant !== 'bar' && Object.prototype.hasOwnProperty.call(scopeByFilter, filter.id) && (
                  <Tooltip title={scope.length ? `影响：${scope.join('、')}` : '尚未绑定任何组件'}>
                    <span className={`${styles.filterScope} ${scope.length ? '' : '!text-[var(--app-warning)]'}`}>
                      {scope.length ? `影响 ${scope.length} 个组件` : '未绑定'}
                    </span>
                  </Tooltip>
                )}
                {onEditFilter && (
                  <Button
                    type='link'
                    size='small'
                    aria-label={`编辑${filter.label}筛选器`}
                    title={`编辑${filter.label}筛选器`}
                    icon={variant === 'bar' ? <EditOutlined /> : undefined}
                    className={styles.editFilterButton}
                    onClick={event => {
                      event.preventDefault();
                      event.stopPropagation();
                      onEditFilter(filter.id);
                    }}
                  >
                    {variant === 'bar' ? null : '编辑'}
                  </Button>
                )}
              </span>
            </span>
            <div className={styles.filterControl}>
              {filter.type === 'date_range' ? (
                <DatePicker.RangePicker
                  size='small'
                  aria-label={`${filter.label}筛选`}
                  allowClear
                  disabled={disabled}
                  value={
                    Array.isArray(value) && value.length === 2
                      ? [dayjs(String(value[0])), dayjs(String(value[1]))]
                      : undefined
                  }
                  onChange={dates =>
                    update(filter.id, dates ? [dates[0]?.format('YYYY-MM-DD'), dates[1]?.format('YYYY-MM-DD')] : null)
                  }
                />
              ) : filter.type === 'text' ? (
                <Input
                  size='small'
                  aria-label={`${filter.label}筛选`}
                  allowClear
                  disabled={disabled}
                  value={typeof value === 'string' ? value : undefined}
                  placeholder='输入关键词；清空表示全部'
                  onChange={event => update(filter.id, event.target.value || null)}
                />
              ) : filter.type === 'number_range' ? (
                <div className='flex items-center gap-2'>
                  <InputNumber
                    size='small'
                    aria-label={`${filter.label}最小值`}
                    disabled={disabled}
                    value={Array.isArray(value) && typeof value[0] === 'number' ? value[0] : null}
                    placeholder='最小值'
                    onChange={next => update(filter.id, [next, Array.isArray(value) ? (value[1] ?? null) : null])}
                  />
                  <span>—</span>
                  <InputNumber
                    size='small'
                    aria-label={`${filter.label}最大值`}
                    disabled={disabled}
                    value={Array.isArray(value) && typeof value[1] === 'number' ? value[1] : null}
                    placeholder='最大值'
                    onChange={next => update(filter.id, [Array.isArray(value) ? (value[0] ?? null) : null, next])}
                  />
                </div>
              ) : (
                <Select
                  size='small'
                  aria-label={`${filter.label}筛选`}
                  allowClear
                  disabled={disabled}
                  showSearch
                  optionFilterProp='label'
                  maxTagCount='responsive'
                  mode={filter.type === 'multi_select' ? 'multiple' : undefined}
                  value={value as string | number | (string | number)[] | undefined}
                  placeholder={filter.type === 'multi_select' ? '可选择多个值；清空表示全部' : '请选择一个值'}
                  notFoundContent={<span className='text-xs text-[var(--app-muted)]'>{emptyOptionText}</span>}
                  options={filter.options.map(option => ({
                    label: option.label,
                    value: option.value as string | number,
                  }))}
                  onChange={next => update(filter.id, next)}
                />
              )}
            </div>
          </div>
        );
      })}
      {showReset && (
        <Button
          aria-label='恢复默认筛选并刷新'
          className={styles.filterReset}
          disabled={disabled || isAtDefaults}
          icon={<UndoOutlined />}
          onClick={() => (onReset || onChange)?.(resetValues)}
        >
          恢复默认
        </Button>
      )}
    </div>
  );
}
