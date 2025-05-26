import { ChartData } from '@/types/chat';
import { Table } from '@mui/joy';
import { useMemo } from 'react';

interface TableChartProps {
  chart: ChartData;
  columnNameMap?: Record<string, string>;
  renderCell?: (value: any, row: any, col: string) => React.ReactNode;
}

export default function TableChart({ chart, columnNameMap, renderCell }: TableChartProps) {
  // Process table data
  const { columns, dataSource } = useMemo(() => {
    if (!chart.values || chart.values.length === 0) {
      return { columns: [], dataSource: [] };
    }

    const firstRow = chart.values[0];

    // Handle type-value structure
    if ('type' in firstRow && 'value' in firstRow && 'name' in firstRow) {
      // Group by name and transform type-value pairs into columns
      const mergedData = new Map();

      chart.values.forEach(item => {
        if (!mergedData.has(item.name)) {
          mergedData.set(item.name, { name: item.name });
        }
        const row = mergedData.get(item.name);
        row[item.type] = item.value;
      });

      // Get all unique types as columns
      const types = [...new Set(chart.values.map(item => item.type))];

      return {
        columns: ['name', ...types],
        dataSource: Array.from(mergedData.values()),
      };
    }

    // Use data as is for other formats
    return {
      columns: Object.keys(chart.values[0]),
      dataSource: chart.values,
    };
  }, [chart]);

  // Smart column name formatting
  const formatCol = (col: string) =>
    columnNameMap?.[col] ||
    col
      .replace(/_/g, ' ')
      .replace(/([a-z])([A-Z])/g, '$1 $2')
      .replace(/\b\w/g, l => l.toUpperCase());

  // Cell value formatting
  const formatCellValue = (value: any) => {
    if (value === null || value === undefined) return '-';
    if (typeof value === 'number') {
      // Handle percentage and score values (0-100 range)
      if (value >= 0 && value <= 100) {
        return value.toFixed(2); // Keep two decimal places for scores/percentages
      }
      // For large numbers, use thousand separators
      if (value >= 1000) {
        return value.toLocaleString();
      }
      // For other numbers, limit to 2 decimal places if needed
      return Number.isInteger(value) ? value.toString() : value.toFixed(2);
    }
    return String(value);
  };

  return (
    <div className='flex-1 min-w-0 p-4 bg-white dark:bg-theme-dark-container rounded'>
      <div className='h-full'>
        <div className='mb-2'>{chart.chart_name}</div>
        <div className='opacity-80 text-sm mb-2'>{chart.chart_desc}</div>
        <div className='flex-1 overflow-auto'>
          <Table aria-label='dashboard table' stripe='odd' hoverRow borderAxis='bothBetween'>
            <thead>
              <tr>
                {columns.map(col => (
                  <th key={col}>{formatCol(col)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {dataSource.map((row, i) => (
                <tr key={i}>
                  {columns.map(col => (
                    <td key={col}>
                      {renderCell
                        ? renderCell(row[col as keyof typeof row], row, col)
                        : formatCellValue(row[col as keyof typeof row])}
                    </td>
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
