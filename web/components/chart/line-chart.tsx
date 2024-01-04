import { ChartData } from '@/types/chat';
import { useColorScheme } from '@mui/joy';
import { Chart } from '@berryv/g2-react';

export default function LineChart({ chart }: { chart: ChartData }) {
  const { mode } = useColorScheme();

  return (
    <div className="flex-1 min-w-0 p-4 bg-white dark:bg-theme-dark-container rounded">
      <div className="h-full">
        <div className="mb-2">{chart.chart_name}</div>
        <div className="opacity-80 text-sm mb-2">{chart.chart_desc}</div>
        <div className="h-[300px]">
          <Chart
            style={{ height: '100%' }}
            options={{
              autoFit: true,
              theme: mode,
              type: 'view',
              data: chart.values,
              children: [
                {
                  type: 'line',
                  encode: {
                    x: 'name',
                    y: 'value',
                    color: 'type',
                    shape: 'smooth',
                  },
                },
                {
                  type: 'area',
                  encode: {
                    x: 'name',
                    y: 'value',
                    color: 'type',
                    shape: 'smooth',
                  },
                  legend: false,
                  style: {
                    fillOpacity: 0.15,
                  },
                },
              ],
              axis: {
                x: {
                  labelAutoRotate: false,
                },
              },
            }}
          />
        </div>
      </div>
    </div>
  );
}
