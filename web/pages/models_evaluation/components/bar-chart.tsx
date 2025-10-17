import React from 'react';
import { Column } from '@ant-design/plots';

interface ChartData {
  name: string;
  label: string;
  value: number;
}

interface BarChartProps {
  data: ChartData[];
  height?: number;
}

export const BarChart: React.FC<BarChartProps> = ({ data, height = 400 }) => {
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
      }
    },
    interaction: {
      tooltip: {
        render: (e: any, {title, items}: { title: string, items: {name: string, value: number, color: string}[]}) => {
          return (
            <div key={title}>
              <h4>{title}</h4>
              {items.map((item) => {
                const { name, value, color } = item;
                return (
                  <div className="flex justify-between gap-4">
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
          )
        }
      }
    }
  };

  return <Column {...config} />;
};