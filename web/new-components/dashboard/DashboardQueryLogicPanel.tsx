import { getDashboardQueryLogic } from '@/client/api/dashboard';
import { DashboardFilter, DashboardQueryLogic, DashboardWidget } from '@/types/dashboard';
import { CopyOutlined } from '@ant-design/icons';
import { App, Button, Spin } from 'antd';
import { useEffect, useMemo, useState } from 'react';
import { format } from 'sql-formatter';
import { dashboardSourceLabel } from './dashboard-source-label';

export const widgetQueryParameters = (
  widget: DashboardWidget,
  filters: DashboardFilter[],
  values: Record<string, unknown>,
) => {
  const parameters = { ...widget.query.default_parameters };
  for (const [id, binding] of Object.entries(widget.query.filter_parameters)) {
    const filter = filters.find(item => item.id === id);
    const supplied = !!filter && Object.prototype.hasOwnProperty.call(values, id);
    const hasValue = supplied || (filter?.default !== undefined && filter.default !== null);
    const value = supplied ? values[id] : filter?.default;
    const optional = filter?.type === 'multi_select' ? [] : null;
    const bind = (name: string | null | undefined, boundValue: unknown, emptyValue: unknown = optional) => {
      if (!name) return;
      if (hasValue) parameters[name] = boundValue;
      else if (!Object.prototype.hasOwnProperty.call(parameters, name)) parameters[name] = emptyValue;
    };
    if (typeof binding === 'string') bind(binding, value);
    else {
      bind(binding.parameter, value);
      bind(binding.start_parameter, Array.isArray(value) ? (value[0] ?? null) : null, null);
      bind(binding.end_parameter, Array.isArray(value) ? (value[1] ?? null) : null, null);
    }
  }
  return parameters;
};

export default function DashboardQueryLogicPanel({
  dashboardId,
  widget,
  filters,
  values,
}: {
  dashboardId: string;
  widget: DashboardWidget;
  filters: DashboardFilter[];
  values: Record<string, unknown>;
}) {
  const { message } = App.useApp();
  const sql = widget.query.sql || '';
  const source = widget.query.data_source_id;
  const key = JSON.stringify([dashboardId, source, sql]);
  const [result, setResult] = useState<{ key: string; logic?: DashboardQueryLogic; error?: string } | null>(null);
  const current = result?.key === key ? result : null;
  useEffect(() => {
    let active = true;
    if (!sql.trim()) return;
    const timer = setTimeout(async () => {
      try {
        const response = await getDashboardQueryLogic(dashboardId, sql, source);
        if (!response.data.success || !response.data.data) throw new Error('无法解析');
        if (active) setResult({ key, logic: response.data.data });
      } catch {
        if (active) setResult({ key, error: '暂时无法解析计算步骤，可直接查看下方原始 SQL。' });
      }
    }, 180);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [dashboardId, key, source, sql]);
  const formattedSql = useMemo(() => {
    try {
      return format(sql, { paramTypes: { named: [':'] } });
    } catch {
      return sql;
    }
  }, [sql]);
  const parameters = widgetQueryParameters(widget, filters, values);
  return (
    <div className='space-y-4 text-xs' data-testid='dashboard-query-logic'>
      <section className='space-y-3 rounded-lg border border-[var(--app-border)] p-3'>
        <h3 className='text-sm font-semibold'>计算口径</h3>
        <p>
          <span className='text-[var(--app-muted)]'>数据源：</span>
          {dashboardSourceLabel(source)}
        </p>
        {!sql.trim() ? (
          <p className='text-[var(--app-muted)]'>尚未配置 SQL，可在高级数据设置中添加。</p>
        ) : !current ? (
          <Spin size='small' />
        ) : current.error ? (
          <p role='status'>{current.error}</p>
        ) : (
          current.logic && (
            <>
              <p className='break-words'>
                <span className='text-[var(--app-muted)]'>数据表：</span>
                {current.logic.tables.join('、') || '查询常量或派生结果'}
              </p>
              {!!current.logic.set_operations.length && <p>合并方式：{current.logic.set_operations.join(' → ')}</p>}
              {current.logic.stages.map((stage, index) => (
                <details key={index} open={index === 0} className='space-y-2 border-t border-[var(--app-border)] pt-3'>
                  <summary className='cursor-pointer font-medium'>{stage.label}</summary>
                  <div>
                    <div className='mb-1 text-[var(--app-muted)]'>输出与计算表达式</div>
                    {stage.expressions.map((expression, i) => (
                      <code
                        key={i}
                        className='mb-1 block whitespace-pre-wrap break-words rounded bg-[var(--app-surface-muted)] p-2 leading-5'
                      >
                        {expression}
                      </code>
                    ))}
                  </div>
                  {!!stage.group_by.length && (
                    <p className='break-words'>
                      分组维度：<code>{stage.group_by.join('、')}</code>
                    </p>
                  )}
                  {stage.where && (
                    <p className='break-words'>
                      数据筛选：<code>{stage.where}</code>
                    </p>
                  )}
                  {stage.having && (
                    <p className='break-words'>
                      汇总后筛选：<code>{stage.having}</code>
                    </p>
                  )}
                  {!!stage.joins.length && (
                    <p className='break-words'>
                      关联条件：<code>{stage.joins.join('; ')}</code>
                    </p>
                  )}
                  {stage.order_by && (
                    <p className='break-words'>
                      排序：<code>{stage.order_by}</code>
                    </p>
                  )}
                  {stage.limit && (
                    <p>
                      查询条数：<code>{stage.limit}</code>
                    </p>
                  )}
                </details>
              ))}
              <p className='text-[var(--app-muted)]'>以上步骤来自当前 SQL；展开子查询可核对指标的完整计算过程。</p>
            </>
          )
        )}
      </section>
      <details className='rounded-lg border border-[var(--app-border)] p-3'>
        <summary className='cursor-pointer text-sm font-semibold'>实际 SQL</summary>
        <div className='mb-2 flex items-center justify-between gap-2'>
          <Button
            size='small'
            icon={<CopyOutlined />}
            disabled={!sql.trim()}
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(sql);
                message.success('SQL 已复制');
              } catch {
                message.error('复制失败，请选中 SQL 手动复制');
              }
            }}
          >
            复制 SQL
          </Button>
        </div>
        <pre
          tabIndex={0}
          aria-label='图表实际 SQL'
          className='max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-lg border border-[var(--app-border)] bg-[var(--app-surface-muted)] p-3 font-mono text-xs leading-5'
        >
          {formattedSql || '尚未配置 SQL'}
        </pre>
      </details>
      <details className='space-y-2 rounded-lg border border-[var(--app-border)] p-3'>
        <summary className='cursor-pointer text-sm font-semibold'>当前筛选参数</summary>
        {Object.keys(parameters).length ? (
          <dl className='space-y-1'>
            {Object.entries(parameters).map(([name, value]) => (
              <div
                key={name}
                className='flex flex-wrap justify-between gap-2 rounded bg-[var(--app-surface-muted)] px-3 py-2'
              >
                <dt className='break-all font-mono'>{name}</dt>
                <dd className='break-all'>
                  {value == null ? '未设置' : typeof value === 'string' ? value || '空字符串' : JSON.stringify(value)}
                </dd>
              </div>
            ))}
          </dl>
        ) : (
          <p className='text-[var(--app-muted)]'>这条查询没有绑定筛选参数。</p>
        )}
        <p className='text-[var(--app-muted)]'>当前查询最多返回 {widget.query.max_rows} 行。</p>
      </details>
    </div>
  );
}
