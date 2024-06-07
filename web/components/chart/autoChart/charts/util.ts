import { FieldInfo } from "@antv/ava";
import { hasSubset, intersects } from "../advisor/utils";

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
  return fields.find((field) => field.levelOfMeasurements && intersects(field.levelOfMeasurements,  ['Time', 'Ordinal']))
}

export function findNominalField(fields: FieldInfo[]) {
  return fields.find((field) => field.levelOfMeasurements && hasSubset(field.levelOfMeasurements, ['Nominal']))
}
