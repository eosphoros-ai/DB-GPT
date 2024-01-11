import { ChatContext } from '@/app/chat-context';
import { ChartData } from '@/types/chat';
import { Chart } from '@berryv/g2-react';
import { useContext } from 'react';

export default function BarChart({ chart }: { key: string; chart: ChartData }) {
  const { mode } = useContext(ChatContext);

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
              type: 'interval',
              data: chart.values,
              encode: { x: 'name', y: 'value', color: 'type' },
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
