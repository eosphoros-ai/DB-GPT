import { ChatContext } from '@/app/chat-context';
import { ChartData } from '@/types/chat';
import { Chart } from '@berryv/g2-react';
import { useContext, useMemo } from 'react';

export default function PieChart({ chart }: { key: string; chart: ChartData }) {
  const { mode } = useContext(ChatContext);

  // Transform raw data into pie chart format
  const pieData = useMemo(() => {
    if (!chart.values || !Array.isArray(chart.values)) {
      return [];
    }

    return chart.values.map(item => ({
      name: item.name,
      value: Number(item.value) || 0,
    }));
  }, [chart.values]);

  if (!pieData.length) {
    return null;
  }

  // Calculate total for percentage
  const total = pieData.reduce((sum, item) => sum + item.value, 0);

  return (
    <div className='flex-1 min-w-[300px] p-4 bg-white dark:bg-theme-dark-container rounded'>
      <div className='h-full'>
        <div className='mb-2'>{chart.chart_name}</div>
        <div className='opacity-80 text-sm mb-2'>{chart.chart_desc}</div>
        <div className='h-[300px]'>
          <Chart
            style={{ height: '100%' }}
            options={{
              autoFit: true,
              data: pieData,
              theme: mode,
              animate: {
                enter: {
                  type: 'waveIn',
                  duration: 500,
                },
              },
              children: [
                {
                  type: 'interval',
                  encode: {
                    y: 'value',
                    color: 'name',
                  },
                  transform: [{ type: 'stackY' }],
                  coordinate: {
                    type: 'theta',
                    outerRadius: 0.8,
                  },
                  style: {
                    lineWidth: 1,
                    stroke: '#fff',
                  },
                  state: {
                    active: {
                      style: {
                        lineWidth: 2,
                        stroke: '#fff',
                        fillOpacity: 0.9,
                      },
                    },
                  },
                  interaction: {
                    elementHighlightByColor: true,
                  },
                },
              ],
              legend: {
                color: {
                  position: 'right',
                  title: false,
                  itemName: {
                    style: {
                      fill: mode === 'dark' ? '#fff' : '#333',
                    },
                  },
                  itemValue: {
                    formatter: (value: number) => {
                      const percentage = ((value / total) * 100).toFixed(1);
                      return `${percentage}%`;
                    },
                  },
                },
              },
              tooltip: {
                format: {
                  value: (v: number) => `${v}`,
                },
              },
            }}
          />
        </div>
      </div>
    </div>
  );
}
