import { ChartData } from '@/types/chat';
import { Table } from '@mui/joy';
import { groupBy } from 'lodash';

export default function TableChart({ chart }: { key: string; chart: ChartData }) {
  const data = groupBy(chart.values, 'type');

  return (
    <div className="flex-1 min-w-0 p-4 bg-white dark:bg-theme-dark-container rounded">
      <div className="h-full">
        <div className="mb-2">{chart.chart_name}</div>
        <div className="opacity-80 text-sm mb-2">{chart.chart_desc}</div>
        <div className="flex-1">
          <Table aria-label="basic table" stripe="odd" hoverRow borderAxis="bothBetween">
            <thead>
              <tr>
                {Object.keys(data).map((key) => (
                  <th key={key}>{key}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Object.values(data)?.[0]?.map((value, i) => (
                <tr key={i}>
                  {Object.keys(data)?.map((k) => (
                    <td key={k}>{data?.[k]?.[i].value || ''}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </Table>
        </div>
      </div>
    </div>
  );
}
