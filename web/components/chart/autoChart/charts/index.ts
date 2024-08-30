import type { CustomChart } from '../types';
import multi_line_chart from './multi-line-chart';
import multi_measure_column_chart from './multi-measure-column-chart';
import multi_measure_line_chart from './multi-measure-line-chart';

export const customCharts: CustomChart[] = [multi_line_chart, multi_measure_column_chart, multi_measure_line_chart];

export type CustomChartsType = 'multi_line_chart' | 'multi_measure_column_chart' | 'multi_measure_line_chart';
