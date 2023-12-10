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
