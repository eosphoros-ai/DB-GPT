import { ChartData } from '@/types/chat';
import { Card, CardContent, Typography } from '@mui/joy';
import { useMemo } from 'react';
import BarChart from './bar-chart';
import { groupChartsIntoRows } from './chart-rows';
import LineChart from './line-chart';
import PieChart from './pie-chart';
import TableChart from './table-chart';

type Props = {
  chartsData: Array<ChartData>;
};

function Chart({ chartsData }: Props) {
  const chartRows = useMemo(() => {
    if (chartsData) {
      const res = [];
      // 若是有类型为 IndicatorValue 的，提出去，独占一行
      const chartCalc = chartsData?.filter(item => item.chart_type === 'IndicatorValue');
      if (chartCalc.length > 0) {
        res.push({
          charts: chartCalc,
          type: 'IndicatorValue',
        });
      }
      const otherCharts = chartsData?.filter(item => item.chart_type !== 'IndicatorValue');
      for (const charts of groupChartsIntoRows(otherCharts)) {
        res.push({ charts });
      }
      return res;
    }
    return undefined;
  }, [chartsData]);

  return (
    <div className='flex flex-col gap-3'>
      {chartRows?.map((chartRow, index) => (
        <div key={`chart_row_${index}`} className={`${chartRow?.type !== 'IndicatorValue' ? 'flex gap-3' : ''}`}>
          {chartRow.charts.map(chart => {
            if (chart.chart_type === 'IndicatorValue' || chart.type === 'IndicatorValue') {
              return (
                <div key={chart.chart_uid} className='flex flex-row gap-3'>
                  {chart.values.map(item => (
                    <div key={item.name} className='flex-1'>
                      <Card sx={{ background: 'transparent' }}>
                        <CardContent className='justify-around'>
                          <Typography gutterBottom component='div'>
                            {item.name}
                          </Typography>
                          <Typography>{item.value}</Typography>
                        </CardContent>
                      </Card>
                    </div>
                  ))}
                </div>
              );
            } else if (chart.chart_type === 'LineChart' || chart.type === 'LineChart') {
              return <LineChart key={chart.chart_uid} chart={chart} />;
            } else if (chart.chart_type === 'BarChart' || chart.type === 'BarChart') {
              return <BarChart key={chart.chart_uid} chart={chart} />;
            } else if (chart.chart_type === 'Table' || chart.type === 'TableChartData') {
              return <TableChart key={chart.chart_uid} chart={chart} />;
            } else if (chart.chart_type === 'PieChart' || chart.type === 'PieChart') {
              return <PieChart key={chart.chart_uid} chart={chart} />;
            }
          })}
        </div>
      ))}
    </div>
  );
}

export * from './autoChart';
export default Chart;
