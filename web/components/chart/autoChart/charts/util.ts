import type { Datum, FieldInfo } from '@antv/ava';
import { cloneDeep, uniq } from 'lodash';
import { hasSubset, intersects } from '../advisor/utils';

/**
 * Process date column to new Date().
 * @param field
 * @param dataProps
 * @returns
 */
export function processDateEncode(field: string, dataProps: FieldInfo[]) {
  const dp = dataProps.find(dataProp => dataProp.name === field);

  if (dp?.recommendation === 'date') {
    return (d: any) => new Date(d[field]);
  }
  return field;
}

export function findOrdinalField(fields: FieldInfo[]) {
  return fields.find(field => field.levelOfMeasurements && intersects(field.levelOfMeasurements, ['Time', 'Ordinal']));
}

export function findNominalField(fields: FieldInfo[]) {
  return fields.find(field => field.levelOfMeasurements && hasSubset(field.levelOfMeasurements, ['Nominal']));
}

// Detect whether the x-axis has only one data point (line chart with a single point)
export const isUniqueXValue = ({ data, xField }: { xField: string; data: Datum[] }): boolean => {
  const uniqXValues = uniq(data.map(datum => datum[xField]));
  return uniqXValues.length <= 1;
};

/** Line width when only one data point exists; otherwise the line may render as 1px and be invisible */
export const getLineSize = (
  datum: Datum,
  allData: Datum[],
  fields: {
    field4Split?: FieldInfo;
    field4X?: FieldInfo;
  },
) => {
  const { field4Split, field4X } = fields;
  if (field4Split?.name && field4X?.name) {
    const seriesValue = datum[field4Split.name];
    const splitData = allData.filter(item => field4Split.name && item[field4Split.name] === seriesValue);
    return isUniqueXValue({ data: splitData, xField: field4X.name }) ? 5 : undefined;
  }
  return field4X?.name && isUniqueXValue({ data: allData, xField: field4X.name }) ? 5 : undefined;
};

export const sortData = ({ data, chartType, xField }: { data: Datum[]; xField?: FieldInfo; chartType: string }) => {
  const sortedData = cloneDeep(data);
  try {
    // Line charts: sort points by date ascending before drawing
    if (chartType.includes('line') && xField?.name && xField.recommendation === 'date') {
      sortedData.sort(
        (datum1, datum2) =>
          new Date(datum1[xField.name as string]).getTime() - new Date(datum2[xField.name as string]).getTime(),
      );
      return sortedData;
    }
    // If the x-axis is numeric, sort by value ascending
    if (chartType.includes('line') && xField?.name && ['float', 'integer'].includes(xField.recommendation)) {
      sortedData.sort(
        (datum1, datum2) => (datum1[xField.name as string] as number) - (datum2[xField.name as string] as number),
      );
      return sortedData;
    }
  } catch (err) {
    console.error(err);
  }
  return sortedData;
};

/** Replace backend empty marker '-' with null for chart rendering */
export const processNilData = (data: Datum[], emptyValue = '-') =>
  data.map(datum => {
    const processedDatum: Record<string, string | number | null> = {};
    Object.keys(datum).forEach(key => {
      processedDatum[key] = datum[key] === emptyValue ? null : datum[key];
    });
    return processedDatum;
  });
