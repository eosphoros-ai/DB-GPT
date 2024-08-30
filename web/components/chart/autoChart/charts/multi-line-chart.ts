import type { Datum } from '@antv/ava';
import { hasSubset } from '../advisor/utils';
import type { ChartKnowledge, CustomChart, GetChartConfigProps, Specification } from '../types';
import { findNominalField, findOrdinalField, getLineSize, processDateEncode, sortData } from './util';

const MULTI_LINE_CHART = 'multi_line_chart';
const getChartSpec = (data: GetChartConfigProps['data'], dataProps: GetChartConfigProps['dataProps']) => {
  const ordinalField = findOrdinalField(dataProps);
  const nominalField = findNominalField(dataProps);
  // 放宽折线图的 x 轴条件，优先选择 time， ordinal, nominal 类型，没有的话使用第一个字段作兜底
  const field4X = ordinalField ?? nominalField ?? dataProps[0];
  const remainFields = dataProps.filter(field => field.name !== field4X?.name);

  const field4Y = remainFields.filter(
    field => field.levelOfMeasurements && hasSubset(field.levelOfMeasurements, ['Interval']),
  ) ?? [remainFields[0]];
  const field4Nominal = remainFields
    .filter(field => !field4Y.find(y => y.name === field.name))
    .find(field => field.levelOfMeasurements && hasSubset(field.levelOfMeasurements, ['Nominal']));
  if (!field4X || !field4Y) return null;

  const spec: Specification = {
    type: 'view',
    autoFit: true,
    data: sortData({ data, chartType: MULTI_LINE_CHART, xField: field4X }),
    children: [],
  };

  field4Y.forEach(field => {
    const singleLine: Specification = {
      type: 'line',
      encode: {
        x: processDateEncode(field4X.name as string, dataProps),
        y: field.name,
        size: (datum: Datum) => getLineSize(datum, data, { field4Split: field4Nominal, field4X }),
      },
      legend: {
        size: false,
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
  id: MULTI_LINE_CHART,
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
