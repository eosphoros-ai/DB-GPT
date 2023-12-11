import { hasSubset, intersects } from '../advisor/utils';
import { processDateEncode } from './util';
import type { ChartKnowledge, CustomChart, GetChartConfigProps, Specification } from '../types';

const getChartSpec = (data: GetChartConfigProps['data'], dataProps: GetChartConfigProps['dataProps']) => {
  const field4X = dataProps.find((field) =>
    // @ts-ignore
    intersects(field.levelOfMeasurements, ['Time', 'Ordinal']),
  );
  // @ts-ignore
  const field4Y = dataProps.filter((field) => hasSubset(field.levelOfMeasurements, ['Interval']));
  const field4Nominal = dataProps.find((field) =>
    // @ts-ignore
    hasSubset(field.levelOfMeasurements, ['Nominal']),
  );
  if (!field4X || !field4Y) return null;

  const spec: Specification = {
    type: 'view',
    autoFit: true,
    data,
    children: [],
  };

  field4Y.forEach((field) => {
    const singleLine: Specification = {
      type: 'line',
      encode: {
        x: processDateEncode(field4X.name as string, dataProps),
        y: field.name,
      },
    };
    if (field4Nominal) {
      singleLine.encode.color = field4Nominal.name;
    }
    spec.children.push(singleLine);
  });
  return spec;
};

const ckb: ChartKnowledge = {
  id: 'multi_line_chart',
  name: 'multi_line_chart',
  alias: ['multi_line_chart'],
  family: ['LineCharts'],
  def: 'multi_line_chart uses lines with segments to show changes in data in a ordinal dimension',
  purpose: ['Comparison', 'Trend'],
  coord: ['Cartesian2D'],
  category: ['Statistic'],
  shape: ['Lines'],
  dataPres: [
    { minQty: 1, maxQty: 1, fieldConditions: ['Time', 'Ordinal'] },
    { minQty: 1, maxQty: '*', fieldConditions: ['Interval'] },
    { minQty: 0, maxQty: 1, fieldConditions: ['Nominal'] },
  ],
  channel: ['Color', 'Direction', 'Position'],
  recRate: 'Recommended',
  toSpec: getChartSpec,
};

/* 订制一个图表需要的所有参数 */
export const multi_line_chart: CustomChart = {
  /* 图表唯一 Id */
  chartType: 'multi_line_chart',
  /* 图表知识 */
  chartKnowledge: ckb as ChartKnowledge,
  /** 图表中文名 */
  chineseName: '折线图',
};

export default multi_line_chart;
