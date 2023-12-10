import { ChartData } from '@/types/chat';
import { Card, CardContent, Typography } from '@mui/joy';
import { Chart } from '@berryv/g2-react';

export default function LineChart({ chart }: { chart: ChartData }) {
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
        </CardContent>
      </Card>
    </div>
  );
}
