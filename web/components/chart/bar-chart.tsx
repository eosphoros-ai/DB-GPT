import { ChartData } from '@/types/chat';
import { Chart } from '@berryv/g2-react';
import { Card, CardContent, Typography } from '@mui/joy';

export default function BarChart({ chart }: { key: string; chart: ChartData }) {
  return (
    <div className="flex-1 min-w-0">
      <Card className="h-full" sx={{ background: 'transparent' }}>
        <CardContent className="h-full">
          <Typography gutterBottom component="div">
            {chart.chart_name}
          </Typography>
          <Typography gutterBottom level="body3">
            {chart.chart_desc}
          </Typography>
          <div className="h-[300px]">
            <Chart
              style={{ height: '100%' }}
              options={{
                autoFit: true,
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
        </CardContent>
      </Card>
    </div>
  );
}
