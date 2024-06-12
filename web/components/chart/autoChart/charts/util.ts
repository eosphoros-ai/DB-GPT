import { Datum, FieldInfo } from '@antv/ava';
import { hasSubset, intersects } from '../advisor/utils';
import { uniq } from 'lodash';

type BasicDataPropertyForAdvice = any;

/**
 * Process date column to new Date().
 * @param field
 * @param dataProps
 * @returns
 */
export function processDateEncode(field: string, dataProps: BasicDataPropertyForAdvice[]) {
  const dp = dataProps.find((dataProp) => dataProp.name === field);

  if (dp?.recommendation === 'date') {
    return (d: any) => new Date(d[field]);
  }
  return field;
}

export function findOrdinalField(fields: FieldInfo[]) {
  return fields.find((field) => field.levelOfMeasurements && intersects(field.levelOfMeasurements, ['Time', 'Ordinal']));
}

export function findNominalField(fields: FieldInfo[]) {
  return fields.find((field) => field.levelOfMeasurements && hasSubset(field.levelOfMeasurements, ['Nominal']));
}

// 识别 x 轴是否只有一条数据（绘制的折线图是否只有一个点）
export const isUniqueXValue = ({ data, xField }: { xField: string; data: Datum[] }): boolean => {
  const uniqXValues = uniq(data.map((datum) => datum[xField]));
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
    const splitData = allData.filter((item) => field4Split.name && item[field4Split.name] === seriesValue);
    return isUniqueXValue({ data: splitData, xField: field4X.name }) ? 5 : undefined;
  }
  return field4X?.name && isUniqueXValue({ data: allData, xField: field4X.name }) ? 5 : undefined;
};
