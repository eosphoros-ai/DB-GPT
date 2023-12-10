import { hasSubset } from '../advisor/utils';

import type { ChartKnowledge, CustomChart, GetChartConfigProps, Specification } from '../types';

const getChartSpec = (data: GetChartConfigProps['data'], dataProps: GetChartConfigProps['dataProps']) => {
  try {
    // @ts-ignore
    const field4Y = dataProps?.filter((field) => hasSubset(field.levelOfMeasurements, ['Interval']));
    const field4Nominal = dataProps?.find((field) =>
      // @ts-ignore
      hasSubset(field.levelOfMeasurements, ['Nominal']),
    );
    if (!field4Nominal || !field4Y) return null;

    const spec: Specification = {
      type: 'view',
      data,
      children: [],
    };

    field4Y?.forEach((field) => {
      const singleLine: Specification = {
        type: 'interval',
        encode: {
          x: field4Nominal.name,
          y: field.name,
          color: () => field.name,
          series: () => field.name,
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
  id: 'multi_measure_column_chart',
  name: 'multi_measure_column_chart',
  alias: ['multi_measure_column_chart'],
  family: ['ColumnCharts'],
  def: 'multi_measure_column_chart uses lines with segments to show changes in data in a ordinal dimension',
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
export const multi_measure_column_chart: CustomChart = {
  /* 图表唯一 Id */
  chartType: 'multi_measure_column_chart',
  /* 图表知识 */
  chartKnowledge: ckb as ChartKnowledge,
  /** 图表中文名 */
  chineseName: '折线图',
};

export default multi_measure_column_chart;
