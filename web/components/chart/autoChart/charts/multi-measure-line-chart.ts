import { hasSubset } from '../advisor/utils';
import { findNominalField, findOrdinalField, getLineSize, processDateEncode, sortData } from './util';
import type { ChartKnowledge, CustomChart, GetChartConfigProps, Specification } from '../types';
import { Datum } from '@antv/ava';

const MULTI_MEASURE_LINE_CHART = 'multi_measure_line_chart'
const getChartSpec = (data: GetChartConfigProps['data'], dataProps: GetChartConfigProps['dataProps']) => {
  try {
    // @ts-ignore
    const field4Y = dataProps?.filter((field) => hasSubset(field.levelOfMeasurements, ['Interval']));
    const field4Nominal = findNominalField(dataProps) ?? findOrdinalField(dataProps);
    if (!field4Nominal || !field4Y) return null;

    const spec: Specification = {
      type: 'view',
      data: sortData({ data, chartType: MULTI_MEASURE_LINE_CHART, xField: field4Nominal }),
      children: [],
    };

    field4Y?.forEach((field) => {
      const singleLine: Specification = {
        type: 'line',
        encode: {
          x: processDateEncode(field4Nominal.name as string, dataProps),
          y: field.name,
          color: () => field.name,
          series: () => field.name,
          size: (datum: Datum) => getLineSize(datum, data, { field4X: field4Nominal }),
        },
        legend: {
          size: false,
        },
      };
      spec.children.push(singleLine);
    });
    return spec;
  } catch (err) {
    console.log(err);
    return null;
  }
};

const ckb: ChartKnowledge = {
  id: MULTI_MEASURE_LINE_CHART,
  name: 'multi_measure_line_chart',
  alias: ['multi_measure_line_chart'],
  family: ['LineCharts'],
  def: 'multi_measure_line_chart uses lines with segments to show changes in data in a ordinal dimension',
  purpose: ['Comparison', 'Distribution'],
  coord: ['Cartesian2D'],
  category: ['Statistic'],
  shape: ['Lines'],
  dataPres: [
    { minQty: 1, maxQty: '*', fieldConditions: ['Interval'] },
    { minQty: 1, maxQty: 1, fieldConditions: ['Nominal'] },
  ],
  channel: ['Color', 'Direction', 'Position'],
  recRate: 'Recommended',
  toSpec: getChartSpec,
};

/* 订制一个图表需要的所有参数 */
export const multi_measure_line_chart: CustomChart = {
  /* 图表唯一 Id */
  chartType: 'multi_measure_line_chart',
  /* 图表知识 */
  chartKnowledge: ckb as ChartKnowledge,
  /** 图表中文名 */
  chineseName: '折线图',
};

export default multi_measure_line_chart;
