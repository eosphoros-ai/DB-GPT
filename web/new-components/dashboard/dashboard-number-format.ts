import type { DashboardWidget, MetricContext } from '@/types/dashboard';

const fieldTail = (value?: string | null) => (value || '').split('.').at(-1)?.toLowerCase();

/** Semantic declarations take priority; numeric storage alone does not imply a measure. */
export function isDashboardMeasure(field: string, widget: DashboardWidget, values: unknown[], context?: MetricContext) {
  const key = field.toLowerCase();
  if (
    context?.dimensions?.some(item =>
      [item.id, item.name, fieldTail(item.field)].some(name => name?.toLowerCase() === key),
    )
  )
    return false;
  if (
    context?.metrics?.some(item =>
      [item.id, item.name, fieldTail(item.source_field)].some(name => name?.toLowerCase() === key),
    )
  )
    return true;
  if (widget.publication?.group_by.includes(field)) return false;
  if (widget.publication?.measures.some(item => item.output_field === field)) return true;
  const encoding = widget.encoding;
  if ([encoding.x, encoding.category, encoding.color, encoding.series, encoding.row, encoding.column].includes(field))
    return false;
  if ([encoding.y, encoding.y2, encoding.value, encoding.angle, encoding.target].includes(field)) return true;
  const normalized = field.replace(/([a-z])([A-Z])/g, '$1_$2');
  if (/(^|[_\s])(year|id|code|no|number)([_\s]|$)|年份|年度|编号|编码/i.test(normalized)) return false;
  const present = values.filter(value => value != null && value !== '');
  if (
    present.length &&
    present.every(value => Number.isInteger(Number(value)) && Number(value) >= 1900 && Number(value) <= 2100)
  )
    return false;
  const output = widget.query.output_fields.find(item => item.name === field);
  return output?.type === 'number' || output?.type === 'integer' || present.some(value => typeof value === 'number');
}

const scaleForUnit = (unit: string) => {
  const normalized = unit.trim().toLowerCase();
  if (/^(万|万元|万人|万件|万笔|万单)$/.test(normalized)) return 1e4;
  if (/^(亿|亿元|亿人|亿件|亿笔|亿单)$/.test(normalized)) return 1e8;
  if (/^(千|千元|k|thousand)$/.test(normalized)) return 1e3;
  if (/^(百万|百万元|百万美元|m|million|usd millions)$/.test(normalized)) return 1e6;
  if (/^(十亿|十亿元|b|billion)$/.test(normalized)) return 1e9;
  return 1;
};

export interface DashboardNumberFormat {
  unit: string;
  format: (value: unknown) => string;
}

/** A mixed-measure table's currency must not be inherited by declared count columns. */
export function dashboardTableFieldFormat(
  values: unknown[],
  widget: DashboardWidget,
  field: string,
  sourceUnit?: string | null,
): DashboardNumberFormat {
  const measures = widget.publication?.measures || [];
  const measure = measures.find(item => item.output_field === field);
  const isCount = (aggregation: string) => aggregation === 'count' || aggregation === 'count_distinct';
  const mixedCounts = measures.some(item => !isCount(item.aggregation));
  if (
    (widget.type === 'table' || widget.presentation?.visualization === 'table') &&
    !widget.publication?.row_mode &&
    mixedCounts &&
    measure &&
    isCount(measure.aggregation) &&
    (measure.scale ?? 1) === 1 &&
    !measure.denominator_field
  ) {
    return dashboardNumberFormat(
      values,
      {
        ...widget,
        style: { ...widget.style, prefix: '', suffix: '', precision: 0 },
        presentation: widget.presentation
          ? {
              ...widget.presentation,
              unit: sourceUnit || '',
              currency: '',
              precision: 0,
              percentage: false,
            }
          : undefined,
      },
      false,
      sourceUnit,
    );
  }
  return dashboardNumberFormat(values, widget, false, sourceUnit);
}

/** One scale for all measure values in a chart; exact tables use compact=false. */
export function dashboardNumberFormat(
  values: unknown[],
  widget: Pick<DashboardWidget, 'presentation' | 'style'>,
  compact = false,
  sourceUnit?: string | null,
): DashboardNumberFormat {
  const presentation = widget.presentation;
  const explicitUnit = presentation?.unit?.trim() || '';
  const legacySuffix = typeof widget.style.suffix === 'string' ? widget.style.suffix : '';
  const percentage = presentation?.percentage === true;
  const prefix = percentage
    ? ''
    : (presentation?.currency ?? (typeof widget.style.prefix === 'string' ? widget.style.prefix : ''));
  const precision = presentation?.precision ?? widget.style.precision;
  const fixed = typeof precision === 'number' && Number.isInteger(precision);
  const digits = fixed ? Math.min(20, Math.max(0, precision)) : 2;
  const numbers = values
    .filter(value => value != null && value !== '')
    .map(Number)
    .filter(Number.isFinite);
  const max = Math.max(0, ...numbers.map(Math.abs));
  // A percentage's scale is decided once for the entire result, never per row.
  let divisor = percentage && max <= 1 ? 0.01 : 1;
  let unit = percentage ? '%' : explicitUnit || legacySuffix || sourceUnit || '';
  let autoScaled = false;
  if (!percentage && explicitUnit) {
    divisor = scaleForUnit(explicitUnit) / scaleForUnit(sourceUnit || '');
  }
  // A semantic unit such as 美元 or 单 must not prevent compact chart labels.
  // Explicit scaled units and legacy literal suffixes retain their existing meaning.
  const displayedMax = max / divisor;
  if (!percentage && compact && !legacySuffix && scaleForUnit(unit) === 1 && displayedMax >= 1e5) {
    const scale = displayedMax >= 1e8 ? 1e8 : 1e4;
    divisor *= scale;
    unit = `${scale === 1e8 ? '亿' : '万'}${unit}`;
    autoScaled = true;
  }
  const formatter = new Intl.NumberFormat(
    'zh-CN',
    fixed && !autoScaled
      ? { minimumFractionDigits: digits, maximumFractionDigits: digits, useGrouping: true }
      : { maximumFractionDigits: autoScaled ? Math.max(2, digits) : digits, useGrouping: true },
  );
  return {
    unit: `${prefix}${unit}`,
    format: value => {
      if (value == null || value === '') return '—';
      const number = typeof value === 'number' || typeof value === 'string' ? Number(value) : NaN;
      if (!Number.isFinite(number)) return '—';
      return `${prefix}${formatter.format(number / divisor)}${unit ? (unit === '%' || legacySuffix === unit ? unit : ` ${unit}`) : ''}`;
    },
  };
}
