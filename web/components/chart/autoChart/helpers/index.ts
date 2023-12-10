import { ChartId } from '@antv/ava';
import { CustomChartsType } from '../charts';

export type BackEndChartType =
  | 'response_line_chart'
  | 'response_bar_chart'
  | 'response_pie_chart'
  | 'response_scatter_chart'
  | 'response_area_chart'
  | 'response_heatmap_chart'
  | 'response_table';

type ChartType = ChartId | CustomChartsType;

export const getChartType = (backendChartType: BackEndChartType): ChartType[] => {
  if (backendChartType === 'response_line_chart') {
    return ['multi_line_chart', 'multi_measure_line_chart'];
  }
  if (backendChartType === 'response_bar_chart') {
    return ['multi_measure_column_chart'];
  }
  if (backendChartType === 'response_pie_chart') {
    return ['pie_chart'];
  }
  if (backendChartType === 'response_scatter_chart') {
    return ['scatter_plot'];
  }
  if (backendChartType === 'response_area_chart') {
    return ['area_chart'];
  }
  if (backendChartType === 'response_heatmap_chart') {
    return ['heatmap'];
  }
  return [];
};
