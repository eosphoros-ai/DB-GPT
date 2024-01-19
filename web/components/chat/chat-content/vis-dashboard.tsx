import { AutoChart, BackEndChartType, getChartType } from '@/components/chart';
import { Datum } from '@antv/ava';
import { useMemo } from 'react';

interface Props {
  data: {
    data: {
      data: Datum[];
      describe: string;
      title: string;
      type: BackEndChartType;
      sql: string;
    }[];
    title: string | null;
    display_strategy: string;
    chart_count: number;
  };
}

const chartLayout = [[2], [1, 2], [1, 3], [2, 1, 2], [2, 1, 3], [3, 1, 3], [3, 2, 3]];

function VisDashboard({ data }: Props) {
  const charts = useMemo(() => {
    if (data.chart_count > 1) {
      const layout = chartLayout[data.chart_count - 2];
      let prevIndex = 0;
      return layout.map((item) => {
        const items = data.data.slice(prevIndex, prevIndex + item);
        prevIndex = item;
        return items;
      });
    }
    return [data.data];
  }, [data.data, data.chart_count]);

  return (
    <div className="flex flex-col gap-3">
      {charts.map((row, index) => (
        <div key={`row-${index}`} className="flex gap-3">
          {row.map((chart, subIndex) => (
            <div
              key={`chart-${subIndex}`}
              className="flex flex-1 flex-col justify-between p-4 rounded border border-gray-200 dark:border-gray-500 whitespace-normal"
            >
              <div>
                {chart.title && <div className="mb-2 text-lg">{chart.title}</div>}
                {chart.describe && <div className="mb-4 text-sm text-gray-500">{chart.describe}</div>}
              </div>
              <AutoChart data={chart.data} chartType={getChartType(chart.type)} />
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

export default VisDashboard;
