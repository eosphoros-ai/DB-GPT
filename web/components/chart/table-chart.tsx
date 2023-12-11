import { ChartData } from '@/types/chat';
import { Card, CardContent, Typography, Table } from '@mui/joy';
import { groupBy } from 'lodash';

export default function TableChart({ chart }: { key: string; chart: ChartData }) {
  const data = groupBy(chart.values, 'type');
  return (
    <div className="flex-1 min-w-0">
      <Card className="h-full overflow-auto" sx={{ background: 'transparent' }}>
        <CardContent className="h-full">
          <Typography gutterBottom component="div">
            {chart.chart_name}
          </Typography>
          <Typography gutterBottom level="body3">
            {chart.chart_desc}
          </Typography>
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
        </CardContent>
      </Card>
    </div>
  );
}
