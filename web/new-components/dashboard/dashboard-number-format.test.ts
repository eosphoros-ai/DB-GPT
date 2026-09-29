import type { DashboardPresentation, MetricContext } from '@/types/dashboard';
import { describe, expect, it } from 'vitest';
import { makeUnconfiguredWidget } from './dashboard-editor-model';
import { dashboardNumberFormat, dashboardTableFieldFormat, isDashboardMeasure } from './dashboard-number-format';

const widget = makeUnconfiguredWidget('table', 'demo', 'numbers');
const presentation = (values: Partial<DashboardPresentation>) => ({
  ...widget,
  presentation: {
    stacked: false,
    smooth: false,
    colors: [],
    percentage: false,
    default_sort: { direction: 'default' as const },
    ...values,
  },
});

describe('measure formatting, not numeric dimension formatting', () => {
  const mixedTable = () => ({
    ...presentation({ unit: '元', currency: '¥', precision: 2 }),
    publication: {
      query: widget.query,
      filter_fields: {},
      group_by: ['category'],
      measures: [
        { source_field: 'value', output_field: 'records', aggregation: 'count' as const, scale: 1 },
        { source_field: 'value', output_field: 'amount', aggregation: 'sum' as const, scale: 1 },
      ],
      output_columns: ['category', 'records', 'amount'],
      row_mode: false,
      sort: [],
      max_output_rows: 500,
    },
  });

  it('keeps declared counts separate from the currency of a mixed-measure table', () => {
    const table = mixedTable();
    expect(dashboardTableFieldFormat([2, 1], table, 'records').format(2)).toBe('2');
    expect(dashboardTableFieldFormat([1400, 200], table, 'amount').format(1400)).toBe('¥1,400.00 元');
    expect(dashboardTableFieldFormat([2, 1], table, 'records', '条').format(2)).toBe('2 条');
  });

  it('does not strip a declared count unit from a KPI or a count-only table', () => {
    const table = mixedTable();
    table.presentation.unit = '条';
    table.presentation.currency = '';
    table.presentation.precision = 0;
    table.publication.measures = table.publication.measures.slice(0, 1);
    expect(dashboardTableFieldFormat([2], table, 'records').format(2)).toBe('2 条');
    expect(
      dashboardTableFieldFormat(
        [2],
        { ...table, type: 'kpi', presentation: { ...table.presentation, visualization: 'kpi' } },
        'records',
      ).format(2),
    ).toBe('2 条');
  });

  it('does not infer counts from a column name or reinterpret explicitly scaled measures', () => {
    const table = mixedTable();
    expect(dashboardTableFieldFormat([2], { ...table, publication: undefined }, 'records').format(2)).toBe('¥2.00 元');
    table.publication.measures[0].scale = 0.01;
    expect(dashboardTableFieldFormat([0.02], table, 'records').format(0.02)).toBe('¥0.02 元');
  });

  it.each([
    [0, '0'],
    [-352755, '-352,755'],
    [352755, '352,755'],
    [391035, '391,035'],
    [1e18, '1,000,000,000,000,000,000'],
    [null, '—'],
    [NaN, '—'],
    [Infinity, '—'],
  ])('formats %s without losing the zero/missing distinction', (value, expected) => {
    expect(dashboardNumberFormat([value], widget).format(value)).toBe(expected);
  });

  it('converts explicit 万元 and honors precision zero and two', () => {
    expect(dashboardNumberFormat([352755], presentation({ unit: '万元', precision: 2 })).format(352755)).toBe(
      '35.28 万元',
    );
    expect(dashboardNumberFormat([352755], presentation({ unit: '万元', precision: 0 })).format(352755)).toBe(
      '35 万元',
    );
  });

  it('does not double-convert a declared source unit', () => {
    expect(dashboardNumberFormat([352755], presentation({ unit: '万元' }), true, '万元').format(352755)).toBe(
      '352,755 万元',
    );
    expect(dashboardNumberFormat([352755], presentation({ unit: '亿元' }), true, '万元').format(352755)).toBe(
      '35.28 亿元',
    );
  });

  it('uses one auto unit for all measures, including small and negative values', () => {
    const format = dashboardNumberFormat([352755, 123, -80], widget, true);
    expect(format.unit).toBe('万');
    expect(format.format(352755)).toBe('35.28 万');
    expect(format.format(123)).toBe('0.01 万');
    expect(format.format(-80)).toBe('-0.01 万');
  });

  it('keeps explicit precision and a literal legacy suffix', () => {
    const format = dashboardNumberFormat([391035], { style: { prefix: '$', suffix: 'M', precision: 1 } }, true);
    expect(format.format(391035)).toBe('$391,035.0M');
  });

  it('compacts currency chart ticks without rounding distinct ticks to the same integer', () => {
    const currency = presentation({ unit: '美元', precision: 0 });
    const compact = dashboardNumberFormat([150000000, 375123456], currency, true);
    expect(compact.unit).toBe('亿美元');
    expect(compact.format(150000000)).toBe('1.5 亿美元');
    expect(compact.format(200000000)).toBe('2 亿美元');
    expect(compact.format(375123456)).toBe('3.75 亿美元');
    expect(dashboardNumberFormat([375123456], currency, false).format(375123456)).toBe('375,123,456 美元');
  });

  it('compacts declared raw source units while preserving explicit scaled units', () => {
    expect(dashboardNumberFormat([352755], widget, true, '单').format(352755)).toBe('35.28 万单');
    expect(dashboardNumberFormat([352755], presentation({ unit: '万元', precision: 0 }), true).format(352755)).toBe(
      '35 万元',
    );
    expect(dashboardNumberFormat([352755], presentation({ unit: '美元' }), true, '百万美元').format(352755)).toBe(
      '3,527.55 亿美元',
    );
  });

  it('uses one percentage interpretation throughout the result', () => {
    const fraction = dashboardNumberFormat([0.12, 0.7], presentation({ percentage: true, precision: 1 }));
    expect(fraction.format(0.12)).toBe('12.0%');
    const points = dashboardNumberFormat([0.12, 70], presentation({ percentage: true, precision: 1 }));
    expect(points.format(0.12)).toBe('0.1%');
    expect(points.format(70)).toBe('70.0%');
  });

  it.each(['fiscal_year', 'fiscalYear', 'customer_id', 'productCode', 'store_no'])('keeps %s as a dimension', field => {
    expect(isDashboardMeasure(field, widget, [2024, 2023])).toBe(false);
  });

  it('recognizes year-shaped values only after explicit Schema semantics', () => {
    const context: MetricContext = {
      grain: '',
      source_notes: [],
      metrics: [
        {
          id: 'revenue',
          name: 'Revenue',
          business_definition: '',
          aggregation: 'sum',
          source_field: 'orders.revenue',
          definition_source: 'user_confirmed',
        },
      ],
    };
    expect(isDashboardMeasure('revenue', widget, [2024], context)).toBe(true);
    expect(isDashboardMeasure('period', widget, [2024, 2023])).toBe(false);
    expect(isDashboardMeasure('revenue', widget, [391035])).toBe(true);
    expect(
      isDashboardMeasure('store', { ...widget, encoding: { x: 'store', y: 'revenue', columns: [] } }, [10000]),
    ).toBe(false);
  });
});
