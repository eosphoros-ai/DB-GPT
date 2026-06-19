import { hasSubset } from '../advisor/utils';

import type { ChartKnowledge, CustomChart, GetChartConfigProps, Specification } from '../types';
import { findNominalField, findOrdinalField } from './util';

const getChartSpec = (data: GetChartConfigProps['data'], dataProps: GetChartConfigProps['dataProps']) => {
  try {
    const field4Y = dataProps?.filter(field => hasSubset(field.levelOfMeasurements, ['Interval']));
    const nominalField = findNominalField(dataProps);
    const ordinalField = findOrdinalField(dataProps);
    const field4X = nominalField ?? ordinalField;
    if (!field4X || !field4Y) return null;

    const spec: Specification = {
      type: 'view',
      data,
      children: [],
    };

    field4Y?.forEach(field => {
      const singleLine: Specification = {
        type: 'interval',
        encode: {
          x: field4X.name,
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

/* All parameters needed to define a custom chart */
export const multi_measure_column_chart: CustomChart = {
  /* Unique chart id */
  chartType: 'multi_measure_column_chart',
  /* Chart knowledge base entry */
  chartKnowledge: ckb as ChartKnowledge,
  /** Chart display name */
  chineseName: 'Line chart',
};

export default multi_measure_column_chart;
