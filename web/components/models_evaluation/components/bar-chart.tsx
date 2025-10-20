import { Column } from '@ant-design/plots';
import React from 'react';

interface ChartData {
  name: string;
  label: string;
  value: number;
}

interface BarChartProps {
  data: ChartData[];
  height?: number;
}

interface InnerDataItem {
  name: string;
  color: string;
  value: number;
}

export const BarChart: React.FC<BarChartProps> = ({ data }) => {
  // 转换数据格式以适应Ant Design Charts
  const chartData = data.map(item => ({
    ...item,
    // value: item.value * 100 // 转换为百分比
  }));

  const config = {
    data: chartData,
    xField: 'label',
    yField: 'value',
    colorField: 'name',
    seriesField: 'name',
    axis: {
      y: {
        labelFormatter: '.00%',
      },
    },
    label: {
      text: (d: InnerDataItem) => (d.value * 100).toFixed(2) + '%',
      textBaseline: 'bottom',
    },
    interaction: {
      tooltip: {
        render: (_e: any, { title, items }: { title: string; items: InnerDataItem[] }) => {
          return (
            <div key={title}>
              <h4>{title}</h4>
              {items.map(item => {
                const { name, value, color } = item;
                return (
                  <div className='flex justify-between gap-4' key={item.name}>
                    <div>
                      <span
                        style={{
                          display: 'inline-block',
                          width: 6,
                          height: 6,
                          borderRadius: '50%',
                          backgroundColor: color,
                          marginRight: 6,
                        }}
                      ></span>
                      <span>{name}:</span>
                    </div>
                    <span>{(value * 100).toFixed(2)}%</span>
                  </div>
                );
              })}
            </div>
          );
        },
      },
    },
  };

  return <Column {...config} />;
};
