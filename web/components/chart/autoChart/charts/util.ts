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

// 识别 x 轴是否只有一条数据（绘制的折线图是否只有一个点）
export const isUniqueXValue = ({ data, xField }: { xField: string; data: Datum[] }): boolean => {
  const uniqXValues = uniq(data.map(datum => datum[xField]));
  return uniqXValues.length <= 1;
};

/** 获取线宽：当只有一条数据时，折线图需要特殊设置线宽，否则仅绘制 1px，看不见 */
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
    // 折线图绘制需要将数据点按照日期从小到大的顺序排序和连线
    if (chartType.includes('line') && xField?.name && xField.recommendation === 'date') {
      sortedData.sort(
        (datum1, datum2) =>
          new Date(datum1[xField.name as string]).getTime() - new Date(datum2[xField.name as string]).getTime(),
      );
      return sortedData;
    }
    // 如果折线图横轴是数值类型，则按照数值大小排序
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

/** 数据空值处理：后端返回的空数据为 '-', 在展示为图表时会有问题，修改为 null */
export const processNilData = (data: Datum[], emptyValue = '-') =>
  data.map(datum => {
    const processedDatum: Record<string, string | number | null> = {};
    Object.keys(datum).forEach(key => {
      processedDatum[key] = datum[key] === emptyValue ? null : datum[key];
    });
    return processedDatum;
  });
