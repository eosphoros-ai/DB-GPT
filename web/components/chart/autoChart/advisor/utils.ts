import { isNull } from 'lodash';
import type { Advice } from '@antv/ava';

export function defaultAdvicesFilter(props: { advices: Advice[] }) {
  const { advices } = props;
  return advices;
}
export const compare = (f1: any, f2: any) => {
  if (isNull(f1.distinct) || isNull(f2.distinct)) {
    if (f1.distinct! < f2!.distinct!) {
      return 1;
    }
    if (f1.distinct! > f2.distinct!) {
      return -1;
    }
    return 0;
  }
  return 0;
};

export function hasSubset(array1: any[], array2: any[]): boolean {
  return array2.every((e) => array1.includes(e));
}

export function intersects(array1: any[], array2: any[]): boolean {
  return array2.some((e) => array1.includes(e));
}

export function LOM2EncodingType(lom: string) {
  switch (lom) {
    case 'Nominal':
      return 'nominal';
    case 'Ordinal':
      return 'ordinal';
    case 'Interval':
      return 'quantitative';
    case 'Time':
      return 'temporal';
    case 'Continuous':
      return 'quantitative';
    case 'Discrete':
      return 'nominal';
    default:
      return 'nominal';
  }
}
