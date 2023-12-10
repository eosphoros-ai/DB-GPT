import { Card, CardContent, Typography } from '@mui/joy';
import BarChart from './bar-chart';
import LineChart from './line-chart';
import TableChart from './table-chart';
import { ChartData } from '@/types/chat';
import { useMemo } from 'react';

type Props = {
  chartsData: Array<ChartData>;
};

function Chart({ chartsData }: Props) {
  const chartRows = useMemo(() => {
    if (chartsData) {
      let res = [];
      // 若是有类型为 IndicatorValue 的，提出去，独占一行
      const chartCalc = chartsData?.filter((item) => item.chart_type === 'IndicatorValue');
      if (chartCalc.length > 0) {
        res.push({
          charts: chartCalc,
          type: 'IndicatorValue',
        });
      }
      let otherCharts = chartsData?.filter((item) => item.chart_type !== 'IndicatorValue');
      let otherLength = otherCharts.length;
      let curIndex = 0;
      // charts 数量 3～8个，暂定每行排序
      let chartLengthMap = [[0], [1], [2], [1, 2], [1, 3], [2, 1, 2], [2, 1, 3], [3, 1, 3], [3, 2, 3]];
      chartLengthMap[otherLength].forEach((item) => {
        if (item > 0) {
          const rowsItem = otherCharts.slice(curIndex, curIndex + item);
          curIndex = curIndex + item;
          res.push({
            charts: rowsItem,
          });
        }
      });
      return res;
    }
    return undefined;
  }, [chartsData]);

  return (
    <div className="flex flex-col gap-3">
      {chartRows?.map((chartRow, index) => (
        <div key={`chart_row_${index}`} className={`${chartRow?.type !== 'IndicatorValue' ? 'flex gap-3' : ''}`}>
          {chartRow.charts.map((chart) => {
            if (chart.chart_type === 'IndicatorValue') {
              return (
                <div key={chart.chart_uid} className="flex flex-row gap-3">
                  {chart.values.map((item) => (
                    <div key={item.name} className="flex-1">
                      <Card sx={{ background: 'transparent' }}>
                        <CardContent className="justify-around">
                          <Typography gutterBottom component="div">
                            {item.name}
                          </Typography>
                          <Typography>{item.value}</Typography>
                        </CardContent>
                      </Card>
                    </div>
                  ))}
                </div>
              );
            } else if (chart.chart_type === 'LineChart') {
              return <LineChart key={chart.chart_uid} chart={chart} />;
            } else if (chart.chart_type === 'BarChart') {
              return <BarChart key={chart.chart_uid} chart={chart} />;
            } else if (chart.chart_type === 'Table') {
              return <TableChart key={chart.chart_uid} chart={chart} />;
            }
          })}
        </div>
      ))}
    </div>
  );
}

export * from './autoChart';
export default Chart;
